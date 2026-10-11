import hashlib
import json
import re
from fastapi import APIRouter, Depends, Request
from .access import identity, scope, authorize, principal, assignment, work_projection, password_hash, DELEGATABLE, EMPLOYEE_CEILING
from .db import transaction, utcnow
from .domain import fail, require, assess, evidence_map, render_draft, fingerprint, contact_gate, allowed_evidence
from . import enterprise_schemas as s, schemas as base, usage
from .jobs import create_job

router=APIRouter()

@router.post('/api/auth/login')
def sign_in(value:s.Login):
    from .access import login
    return login(value.tenant_id,value.user_id,value.password)

@router.post('/api/auth/logout')
def sign_out(who=Depends(identity)):
    with scope(who) as db:
        if who.get('session_id'):
            session=require(db,'auth_sessions',who['session_id']); db.put('auth_sessions',{**session,'revoked':True})
        db.audit('session_revoked',who['user_id'])
    return {'signed_out':True}

def public_user(u): return {k:u.get(k) for k in ['id','role','display_name','active']}

@router.get('/api/admin/users')
def users(who=Depends(identity)):
    with scope(who,'leads.assign') as db:
        db.audit('user_directory_read',db.tenant_id)
        return [{'id':u['id'],'display_name':u.get('display_name'),'role':u['role'],'active':u.get('active',True),
                 'grants':[{k:g[k] for k in ['permission','provinces','enabled'] if k in g} for g in db.list('user_grants',user_id=u['id'])]} for u in db.list('users') if u['role']!='service']

@router.post('/api/admin/users')
def create_user(value:s.UserInput,who=Depends(identity)):
    with scope(who,'users.manage') as db:
        if db.get('users',value.user_id): fail('User already exists',409)
        u=db.put('users',{'id':value.user_id,'role':value.role,'display_name':value.display_name,'active':True,'password_hash':password_hash(value.password)})
        if u is None: fail('Database constraint or identity conflict',409)
        db.audit('user_created',u['id']); return public_user(u)

@router.patch('/api/admin/users/{user_id}')
def update_user(user_id:str,value:s.UserState,who=Depends(identity)):
    with scope(who,'users.manage') as db:
        db.conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(db.tenant_id+':user-administration',))
        u=require(db,'users',user_id,lock=True)
        if u['role']=='service': fail('Service identities are provisioned on the server',403)
        if u['role']=='super_admin' and (not value.active or value.role!='super_admin') and sum(x['role']=='super_admin' and x.get('active',True) for x in db.list('users'))<=1:
            fail('Keep at least one active super administrator',409)
        updated=db.put('users',{**u,'role':value.role,'active':value.active}); db.audit('user_identity_changed',user_id,value.reason)
        return public_user(updated)

@router.put('/api/admin/users/{user_id}/grants')
def grant(user_id:str,value:s.Grant,who=Depends(identity)):
    with scope(who,'users.manage') as db:
        u=require(db,'users',user_id)
        choices=DELEGATABLE|EMPLOYEE_CEILING if u['role']=='manager' else EMPLOYEE_CEILING if u['role']=='employee' else set()
        if value.permission not in choices: fail('Permission is outside the role ceiling',422)
        if value.enabled and value.permission=='analytics.company' and not value.provinces: fail('Company analysis requires a province scope',422)
        old=db.list('user_grants',user_id=user_id,permission=value.permission)
        db.put('user_grants',{'id':old[0]['id'] if old else None,'user_id':user_id,'permission':value.permission,'enabled':value.enabled,'provinces':value.provinces})
        db.audit('user_grant_changed',user_id,value.reason); return {'permissions':principal(db,user_id)['permissions']}

@router.post('/api/admin/assignments')
def assign(value:s.Assignment,who=Depends(identity)):
    with scope(who,'leads.assign') as db:
        account=require(db,'accounts',value.account_id,lock=True); u=require(db,'users',value.user_id)
        if assess(db,account)['state']!='qualified': fail('Only reviewed qualified customers may be assigned',409)
        if not u.get('active',True) or u['role']=='service': fail('Invalid work assignee',422)
        if 'email' in value.allowed_fields and not value.contact_id: fail('Select the authorized contact',422)
        if value.contact_id:
            c=require(db,'contacts',value.contact_id); e=db.get('evidence',c.get('evidence_id',''))
            if c['account_id']!=account['id'] or not e or not allowed_evidence(db,e,account,'outreach'): fail('Contact is not verified for this account',409)
        task=require(db,'tasks',value.task_id,lock=True) if value.task_id else db.put('tasks',{'account_id':account['id'],'status':'open','kind':'follow_up','owner_id':u['id'],'owner':u['id'],'requires_human':True})
        if task['account_id']!=account['id']: fail('Task/account mismatch',409)
        task=db.put('tasks',{**task,'owner_id':u['id'],'owner':u['id']})
        old=db.list('work_assignments',task_id=task['id'])
        row=db.put('work_assignments',{**value.model_dump(),'id':old[0]['id'] if old else None,'task_id':task['id'],'status':'active','assigned_by':who['user_id']})
        db.audit('work_assigned',row['id'],'Explicit fields: '+','.join(value.allowed_fields)); return row

@router.post('/api/admin/assignments/{identifier}/revoke')
def revoke(identifier:str,who=Depends(identity)):
    with scope(who,'leads.assign') as db:
        a=require(db,'work_assignments',identifier,lock=True)
        row=db.put('work_assignments',{**a,'status':'revoked'}); db.audit('assignment_revoked',identifier); return row

@router.get('/api/work/dashboard')
def employee_dashboard(who=Depends(identity)):
    with scope(who,'work.read') as db:
        rows=[work_projection(db,who,a['task_id']) for a in db.list('work_assignments',user_id=who['user_id'],status='active')]
        return {'identity':{k:who[k] for k in ['user_id','role','display_name','permissions']},'tasks':rows,
                'report':{'assigned':len(rows),'open':sum(r['status']=='open' for r in rows),'done':sum(r['status']=='done' for r in rows)},'usage':usage.snapshot(db,who),'auto_send':False}

@router.get('/api/work/tasks/{task_id}')
def work_detail(task_id:str,who=Depends(identity)):
    with scope(who,'work.read') as db: return work_projection(db,who,task_id)

@router.patch('/api/work/tasks/{task_id}')
def work_update(task_id:str,value:s.WorkUpdate,who=Depends(identity)):
    with scope(who,'work.update') as db:
        task,_=assignment(db,who,task_id,lock=True)
        db.put('tasks',{**task,'status':value.status}); db.audit('work_status_updated',task_id,value.reason)
        return work_projection(db,who,task_id)

@router.post('/api/work/tasks/{task_id}/notes')
def note(task_id:str,value:s.Note,who=Depends(identity)):
    with scope(who,'work.notes') as db:
        assignment(db,who,task_id,lock=True)
        row=db.put('work_notes',{'task_id':task_id,'user_id':who['user_id'],'text':value.text,'kind':'work_record'})
        db.audit('work_note_created',row['id']); return {'id':row['id'],'text':row['text']}

@router.post('/api/work/tasks/{task_id}/replies')
def reply_report(task_id:str,value:s.Note,who=Depends(identity)):
    with scope(who,'work.reply') as db:
        task,_=assignment(db,who,task_id,lock=True)
        row=db.put('work_notes',{'task_id':task_id,'user_id':who['user_id'],'text':value.text,'kind':'reply_report','requires_review':True})
        db.put('tasks',{'account_id':task['account_id'],'status':'open','kind':'reply_report_review','work_note_id':row['id'],'requires_human':True})
        db.audit('reply_report_submitted',row['id']); return {'recorded':True,'requires_review':True}

def assigned_draft_context(db,who,task_id):
    authorize(who,'work.draft')
    task,a=assignment(db,who,task_id)
    if not {'name','province','email'}<=set(a.get('allowed_fields',[])) or not a.get('contact_id'): fail('Follow-up requires explicitly authorized contact fields',403)
    account=require(db,'accounts',a['account_id'],lock=True)
    task,a=assignment(db,who,task_id,lock=True)  # same account → task order as management assignment
    c=require(db,'contacts',a['contact_id'])
    if c['account_id']!=account['id'] or assess(db,account)['state']!='qualified': fail('Qualified assigned customer required',409)
    if contact_gate(db,account,c): fail('Contact basis or suppression blocks this task',409)
    return account,c

def work_draft(db,who,task_id):
    account,c=assigned_draft_context(db,who,task_id)
    facts,_=evidence_map(db,account,'outreach'); language='fr' if account['province']=='QC' else 'en'
    d=db.put('outreach_drafts',{**render_draft(account,language,facts),'account_id':account['id'],'contact_id':c['id'],
        'status':'draft','revision':1,'language':language,'is_demo':account['is_demo'],'context_hash':fingerprint(db,account,c),
        'work_task_id':task_id,'created_by':who['user_id'],'approved_by':None,'blocking_reasons':[]})
    db.audit('assigned_draft_created',d['id']); return {k:d[k] for k in ['id','subject','body','status','language','revision']}

@router.post('/api/work/tasks/{task_id}/drafts')
def employee_draft(task_id:str,who=Depends(identity)):
    with scope(who,'work.draft') as db: return work_draft(db,who,task_id)

@router.get('/api/admin/ai-policy')
def ai_policy(who=Depends(identity)):
    with scope(who,'ai.policy.manage') as db:
        db.audit('ai_policy_read',db.tenant_id); return usage.policy(db)

@router.put('/api/admin/ai-policy')
def policy_update(value:s.AIPolicy,who=Depends(identity)):
    with scope(who,'ai.policy.manage') as db:
        old=usage.policy(db,lock=True); row=db.put('ai_policies',{**old,**value.model_dump()})
        db.audit('ai_policy_updated',row['id'],'Enterprise budget, model and role limits reviewed'); return row

@router.get('/api/admin/usage')
def company_usage(who=Depends(identity)):
    with scope(who,'ai.policy.manage') as db:
        db.audit('company_usage_read',db.tenant_id); return usage.snapshot(db)

@router.get('/api/work/usage')
def own_usage(who=Depends(identity)):
    with scope(who,'work.read') as db: return usage.snapshot(db,who)

@router.post('/api/work/quota-requests')
def quota_request(value:s.Quota,who=Depends(identity)):
    with scope(who,'work.read') as db:
        row=db.put('quota_requests',{'user_id':who['user_id'],'status':'pending',**value.model_dump()})
        db.audit('quota_increase_requested',row['id']); return row

@router.post('/api/admin/quota-requests/{identifier}/review')
def quota_review(identifier:str,value:base.Review,who=Depends(identity)):
    with scope(who,'ai.budget.approve') as db:
        row=require(db,'quota_requests',identifier,lock=True)
        if row['status']!='pending': fail('Quota request already reviewed',409)
        if value.approved:
            role=require(db,'users',row['user_id'])['role']; lim=usage.policy(db,lock=True)['roles'][role]
            if any(row[k]>lim[k] for k in ['requests','tokens','voice_seconds','concurrency']): fail('Requested quota exceeds the role limit; review role policy first',409)
            old=db.list('user_quotas',user_id=row['user_id'])
            db.put('user_quotas',{'id':old[0]['id'] if old else None,'user_id':row['user_id'],**{k:row[k] for k in ['requests','tokens','voice_seconds','concurrency']}})
        db.audit('quota_request_reviewed',identifier,value.reason)
        return db.put('quota_requests',{**row,'status':'approved' if value.approved else 'rejected','reviewer_id':who['user_id']})

ACTION_PERMISSION={'task_query':'ai.task.query','work_summary':'ai.work.summary','followup_draft':'ai.followup.draft',
                   'voice_record':'ai.voice.record','lead_research':'research.start','company_analysis':'analytics.company','export':'leads.export'}

@router.post('/api/assistant/actions')
def assistant(value:s.Assistant,who=Depends(identity)):
    action=value.action
    # This early business-intent refusal improves UX; authorization of tools below is the security boundary.
    if re.search(r'(找|搜索|发现|研究).*(\d[\d,，]*\s*家|几家|多家|一批).*(公司|企业|HVAC)|批量.*(获客|研究|线索|客户)|(find|search|research).*\d.*(companies|businesses|HVAC)|ignore.*permission|绕过.*权限',value.prompt,re.I):
        authorize(who,'research.start')
    authorize(who,ACTION_PERMISSION[action])
    if action=='voice_record': fail('Voice provider is not connected; no external voice call was made',503)
    if action in ['lead_research','company_analysis','export']: fail('Use the authorized Admin Console action with validated parameters',409)
    if not value.task_id: fail('Select an assigned task',422)
    with scope(who,ACTION_PERMISSION[action]) as db:
        context=work_projection(db,who,value.task_id)
    if value.use_ai:
        from .ai import reserve as reserve_source, work_plan
        # Never send fictional customer records to an external provider.
        if context['is_demo']: fail('External AI is disabled for fictional records',409)
        receipt={}
        with scope(who,ACTION_PERMISSION[action]) as db:
            context=work_projection(db,who,value.task_id)
            context_hash=hashlib.sha256(json.dumps(context,sort_keys=True,default=str).encode()).hexdigest()
            p=usage.policy(db,lock=True); input_bound=len(json.dumps(context,ensure_ascii=False).encode())+len(value.prompt.encode())+1024
            cost=usage.model_estimate(p,input_bound,300)
            reservation=usage.reserve(db,who,'assistant:'+value.idempotency_key,'openai',cost_micros=cost,input_tokens=input_bound,output_tokens=300,task_id=value.task_id,
                request_hash=hashlib.sha256(value.model_dump_json().encode()).hexdigest())
            if reservation.get('replayed'):
                if reservation.get('result') is not None:
                    cached=reservation['result']
                    authorize(who,ACTION_PERMISSION[cached['action']])
                    if reservation.get('context_hash')!=context_hash: fail('Task authorization or context changed; cached result withheld',409)
                    if cached['action']=='followup_draft':
                        account,contact=assigned_draft_context(db,who,value.task_id)
                        facts,_=evidence_map(db,account,'outreach')
                        fresh=render_draft(account,cached['payload']['draft']['language'],facts)
                        if fresh['body']!=cached['payload']['draft']['body']: fail('Draft context changed; cached result withheld',409)
                    return cached['payload']
                fail('This request was already reserved; it cannot invoke the provider again',409)
            reservation=db.put('usage_ledger',{**reservation,'context_hash':context_hash})
            reserve_source(db)
        try:
            plan=work_plan(context,action,value.prompt,p['model'],receipt)
            if plan['task_id']!=value.task_id: fail('Model attempted to access a different task',403)
            authorize(who,ACTION_PERMISSION[plan['action']]); action=plan['action']
        except Exception:
            with transaction(who['tenant_id'],who['user_id']) as db: usage.settle(db,reservation['id'],failed=True)
            raise
    try:
        with scope(who,ACTION_PERMISSION[action]) as db:
            context=work_projection(db,who,value.task_id)
            if action=='followup_draft': result={'mode':'evidence_template','draft':work_draft(db,who,value.task_id)}
            elif action in ['task_query','work_summary']: result={'mode':'verified_task_projection','task':context,
                'summary':f"任务：{context['kind']}；状态：{context['status']}；已记录 {len(context['notes'])} 条工作信息。"}
            else: fail('Model requested a management tool; no tool was executed',403)
    except Exception:
        if value.use_ai:
            with transaction(who['tenant_id'],who['user_id']) as db: usage.settle(db,reservation['id'],failed=True)
        raise
    if value.use_ai:
        actual={'input_tokens':receipt['input_tokens'],'output_tokens':receipt['output_tokens'],
                'cost_micros':(receipt['input_tokens']*p['input_micros_per_million']+receipt['output_tokens']*p['output_micros_per_million']+999999)//1000000}
        with transaction(who['tenant_id'],who['user_id']) as db:
            row=db.get('usage_ledger',reservation['id'])
            db.put('usage_ledger',{**row,'context_hash':hashlib.sha256(json.dumps(context,sort_keys=True,default=str).encode()).hexdigest()})
            usage.settle(db,reservation['id'],actual=actual,result={'action':action,'payload':result})
    return result

@router.post('/api/assistant/tools/{tool}')
def tool(tool:str,payload:dict,who=Depends(identity)):
    if tool=='research':
        authorize(who,'research.start')
        from pydantic import ValidationError
        try: value=base.JobInput.model_validate(payload)
        except ValidationError: fail('Invalid research tool parameters',422)
        with scope(who,'research.start') as db: return create_job(db,value.model_dump(),who=who)
    if tool=='export':
        authorize(who,'leads.export')
        if payload: fail('Unexpected export parameters',422)
        from .app import export
        return export(who=who)
    if tool=='assigned_task':
        authorize(who,'work.read')
        if set(payload)!={'task_id'} or not isinstance(payload['task_id'],str): fail('Invalid task parameters',422)
        with scope(who,'work.read') as db: return work_projection(db,who,payload['task_id'])
    fail('Unknown Agent tool',403)
