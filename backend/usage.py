"""Integer micro-USD reservations shared by models, voice and source clients."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal, ROUND_CEILING
import hashlib
import json

from .db import utcnow
from .domain import date, fail, require
from .access import principal

def micros(usd): return int((Decimal(str(usd))*1_000_000).to_integral_value(rounding=ROUND_CEILING))
def defaults():
    def limits(requests,tokens,voice,parallel,cost,leads):
        return {'requests':requests,'tokens':tokens,'voice_seconds':voice,'source_calls':1000,'concurrency':parallel,
                'max_task_cost_micros':cost,'max_leads':leads,'max_retries':3,'job_concurrency':parallel}
    return {'monthly_budget_micros':300_000_000,'warning_percent':80,'monthly_tokens':1_000_000,
            'monthly_voice_seconds':36000,'monthly_source_calls':10000,'concurrency':4,'paused':False,
            'model_enabled':False,'voice_enabled':False,'model':'gpt-4.1-mini','pricing_reviewed':False,
            'input_micros_per_million':0,'output_micros_per_million':0,'voice_micros_per_minute':0,
            'roles':{'employee':limits(20,20000,600,1,250000,0),'manager':limits(100,200000,1800,2,1_000_000,200),
                     'super_admin':limits(200,400000,3600,4,5_000_000,200),'service':limits(200,0,0,2,1_000_000,200)}}

def policy(db,lock=False):
    # Serializes first-time initialization too; a tenant never gets two policy rows.
    db.conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(db.tenant_id+':usage-policy',))
    rows=db.list('ai_policies')
    return db.get('ai_policies',rows[0]['id'],lock=lock) if rows else db.put('ai_policies',defaults())

def limits(db,who,p):
    role=principal(db,who['user_id'])['role']; out=deepcopy(p['roles'][role])
    for row in db.list('user_quotas',user_id=who['user_id']):
        for key in ['requests','tokens','voice_seconds','source_calls','concurrency','max_task_cost_micros','max_leads','job_concurrency']:
            if key in row: out[key]=min(out[key],row[key])
    if role=='employee': out['max_leads']=0
    return out

def totals(rows):
    fields=['cost_micros','input_tokens','output_tokens','voice_seconds','source_calls']
    out={k:sum(int(r.get(k,0)) for r in rows) for k in fields}
    out['requests']=len(rows); out['tokens']=out['input_tokens']+out['output_tokens']
    out['concurrency']=sum(r['state']=='reserved' and date(r['reserved_until'])>utcnow() for r in rows)
    return out

def snapshot(db,who=None):
    p=policy(db); now=utcnow(); month=now.replace(day=1,hour=0,minute=0,second=0,microsecond=0); day=now.replace(hour=0,minute=0,second=0,microsecond=0)
    rows=[r for r in db.list('usage_ledger') if date(r['created_at'])>=month]
    company=totals(rows); company['warning']=company['cost_micros']*100>=p['monthly_budget_micros']*p['warning_percent']
    company['blocked']=p['paused'] or company['cost_micros']>=p['monthly_budget_micros']
    if who:
        personal=[r for r in rows if r['user_id']==who['user_id'] and date(r['created_at'])>=day]
        return {'today':totals(personal),'limits':limits(db,who,p),'model_enabled':p['model_enabled'],
                'voice_enabled':p['voice_enabled'],'ai_paused':company['blocked']}
    return {'policy':p,'month':company,'users':{u['id']:totals([r for r in rows if r['user_id']==u['id']]) for u in db.list('users')},
            'pending_quota_requests':db.list('quota_requests',status='pending')}

def reserve(db,who,key,kind,*,cost_micros,input_tokens=0,output_tokens=0,voice_seconds=0,source_calls=0,task_id=None,request_hash=None):
    p=policy(db,lock=True); current=principal(db,who['user_id']); lim=limits(db,current,p)
    quantities={'cost_micros':cost_micros,'input_tokens':input_tokens,'output_tokens':output_tokens,'voice_seconds':voice_seconds,'source_calls':source_calls}
    if any(type(v)!=int or v<0 for v in quantities.values()): fail('Invalid server usage estimate',422)
    digest=request_hash or hashlib.sha256(json.dumps([who['user_id'],kind,task_id,quantities],sort_keys=True).encode()).hexdigest()
    old=db.list('usage_ledger',idempotency_key=key)
    if old:
        if old[0]['user_id']!=who['user_id'] or old[0].get('request_hash')!=digest: fail('Usage key conflict',409)
        return {**old[0],'replayed':True}
    now=utcnow(); day=now.replace(hour=0,minute=0,second=0,microsecond=0); month=day.replace(day=1)
    rows=db.list('usage_ledger'); monthly=totals([r for r in rows if date(r['created_at'])>=month])
    daily=totals([r for r in rows if r['user_id']==who['user_id'] and date(r['created_at'])>=day])
    active=totals(rows)['concurrency']; personal_active=totals([r for r in rows if r['user_id']==who['user_id']])['concurrency']
    if p['paused']: fail('Enterprise AI/API circuit breaker is open',429)
    if monthly['cost_micros']>=p['monthly_budget_micros'] or monthly['cost_micros']+cost_micros>p['monthly_budget_micros']: fail('Enterprise monthly budget exceeded',429)
    for field,maximum,added in [('tokens',p['monthly_tokens'],input_tokens+output_tokens),('voice_seconds',p['monthly_voice_seconds'],voice_seconds),('source_calls',p['monthly_source_calls'],source_calls)]:
        if monthly[field]+added>maximum: fail('Enterprise '+field+' quota exceeded',429)
    if daily['requests']>=lim['requests']: fail('Daily paid request quota exceeded',429)
    for field,added in [('tokens',input_tokens+output_tokens),('voice_seconds',voice_seconds),('source_calls',source_calls)]:
        if daily[field]+added>lim[field]: fail('User/role '+field+' quota exceeded',429)
    if active>=p['concurrency'] or personal_active>=lim['concurrency']: fail('Concurrent call quota exceeded',429)
    if cost_micros>lim['max_task_cost_micros']: fail('Single task cost exceeded',429)
    if task_id:
        task_cost=sum(r.get('cost_micros',0) for r in rows if r.get('task_id')==task_id)
        job=db.get('search_jobs',task_id)
        task_max=min(lim['max_task_cost_micros'],micros(job['cost_budget'])) if job else lim['max_task_cost_micros']
        if task_cost+cost_micros>task_max: fail('Accumulated task cost exceeded',429)
    row=db.put('usage_ledger',{'user_id':who['user_id'],'idempotency_key':key,'state':'reserved','reserved_until':now+timedelta(seconds=120),
                             **quantities,'kind':kind,'task_id':task_id,'request_hash':digest})
    db.audit('usage_reserved',row['id'],kind)
    if (monthly['cost_micros']+cost_micros)*100>=p['monthly_budget_micros']*p['warning_percent']:
        db.audit('budget_warning',p['id'],'Configured warning threshold reached')
    return row

def settle(db,identifier,actual=None,failed=False,result=None):
    p=policy(db,lock=True); row=require(db,'usage_ledger',identifier,lock=True)
    if row['state']!='reserved': return row
    # No reliable receipt: retain every reserved unit; never refund a failed paid request.
    quantities={k:int((actual or {}).get(k,row.get(k,0))) for k in ['cost_micros','input_tokens','output_tokens','voice_seconds','source_calls']}
    if any(v<0 for v in quantities.values()): fail('Invalid provider receipt',422)
    if any(quantities[k]>row.get(k,0) for k in quantities):
        db.put('ai_policies',{**p,'paused':True}); db.audit('cost_circuit_opened',identifier,'Provider usage exceeded its reservation')
    updated=db.put('usage_ledger',{**row,**quantities,'state':'failed' if failed else 'settled','result':result})
    db.audit('usage_settled',identifier,'failed_retained' if failed else 'provider_receipt')
    return updated

def model_estimate(p,input_tokens,output_tokens):
    if not p['model_enabled'] or not p['pricing_reviewed']: fail('Model/pricing not enabled and reviewed',503)
    return (input_tokens*p['input_micros_per_million']+output_tokens*p['output_micros_per_million']+999999)//1000000

def job_limits(db,who,value,existing_id=None):
    p=policy(db,lock=True); current=principal(db,who['user_id']); lim=limits(db,current,p)
    if 'research.start' not in current['permissions']: fail('Research permission denied',403)
    if value['max_results']>lim['max_leads'] or micros(value['cost_budget'])>lim['max_task_cost_micros']: fail('Research task exceeds role/user limits',429)
    jobs=[j for j in db.list('search_jobs') if j['status'] in ['queued','running'] and j['id']!=existing_id]
    if len(jobs)>=p['concurrency'] or sum(j.get('actor_id')==who['user_id'] for j in jobs)>=lim['job_concurrency']: fail('Concurrent research task limit exceeded',429)
    if value['mode']=='live' and snapshot(db)['month']['blocked']: fail('Enterprise AI/API budget suspended',429)
    return lim
