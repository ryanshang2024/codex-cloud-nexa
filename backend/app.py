from __future__ import annotations

import csv
import hashlib
import hmac
import io
import json
import time
from contextlib import contextmanager
from datetime import timedelta
from urllib.parse import urlsplit

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from psycopg import sql

from . import schemas as s
from .access import identity, scope, authorize
from . import usage
from .ai import reserve as reserve_ai, suggest, validate_suggestion
from .db import config, transaction, utcnow
from .domain import (FACTS, SETTINGS, allowed_evidence, assess, contact_gate, credential_supports, date, evidence_map, fail, fingerprint,
                     ingest_account, ingest_reply, invalidate_drafts, render_draft, require, score, suppress, usable)
from .jobs import create_job, process_one
from .providers import ENV, route

app = FastAPI(title='NEXA Enterprise AI Platform', version='3.3.0')


@app.exception_handler(psycopg.IntegrityError)
@app.exception_handler(psycopg.errors.InsufficientPrivilege)
async def integrity_error(request, exc):
    # Never return database SQL or personal values to clients.
    return Response(json.dumps({'detail':'Database constraint or identity conflict'}), status_code=409, media_type='application/json')


@app.get('/health')
def health():
    with transaction(config()['tenant_ids'][0]) as db:
        db.conn.execute('SELECT 1')
    return {'status':'ok','database':'postgresql','auto_send':False,'version':'3.3.0'}


@app.get('/api/identity')
def me(who=Depends(identity)):
    return {k:who[k] for k in ['tenant_id','user_id','role','display_name','permissions']}


@app.get('/api/dashboard')
def dashboard(who=Depends(identity)):
    with scope(who,'leads.read') as db:
        db.audit('lead_pool_read',db.tenant_id,'Management dashboard')
        tables = ['accounts','leads','icp_profiles','source_policies','search_jobs','outreach_drafts',
                  'opportunities','tasks','partners','projects','interactions','work_assignments','work_notes']
        output = {t: db.list(t) for t in tables}
        persisted={lead['account_id']:lead for lead in output['leads']}
        current={a['id']:assess(db,a) for a in output['accounts']}
        output['accounts']=[{**a,'state':current[a['id']]['state']} for a in output['accounts']]
        output['leads']=[{**persisted.get(a['id'],{}),**current[a['id']],'account_id':a['id']} for a in output['accounts']]
        output['icp_profiles']=[{**p,'qualification':SETTINGS['profile_qualification'][p['code']]} for p in output['icp_profiles']]
        output['auto_send'] = False
        output['analytics'] = analytics(db,None if who['role']=='super_admin' else who['grants'].get('analytics.company',[])) if 'analytics.company' in who['permissions'] else {}
        output['analytics_scope'] = ['QC','ON'] if who['role']=='super_admin' else who['grants'].get('analytics.company',[])
        output['identity'] = {k:who[k] for k in ['tenant_id','user_id','role']}
        return output


def analytics(db,provinces=None):
    groups = {}
    for demo in [True,False]:
        accounts = [a for a in db.list('accounts') if a['is_demo'] == demo and (provinces is None or a['province'] in provinces)]
        ids = {a['id'] for a in accounts}
        groups['demo' if demo else 'real'] = {
            'discovered':len(accounts),
            'verified':sum(evidence_map(db,a)[0].get('real_business',{}).get('value') is True for a in accounts),
            'qualified':sum(assess(db,a)['state']=='qualified' for a in accounts),
            'contactable':sum(any(not contact_gate(db,a,c,real=True) for c in db.list('contacts',account_id=a['id'])) for a in accounts),
            'replied':len({x['account_id'] for x in db.list('interactions') if x['account_id'] in ids}),
            'meeting':sum(x['stage']=='meeting' and x['account_id'] in ids for x in db.list('opportunities')),
            'activated':sum(x['state']=='activated' and x['account_id'] in ids for x in db.list('partners')),
            'delivered':None, 'positive_reply_rate':None,
        }
    return groups


@app.get('/api/router')
def router(province:s.Province, profile:s.Profile, who=Depends(identity)):
    with scope(who,'icp.configure') as db:
        return route(db,province,profile)


@app.patch('/api/profiles/{code}')
def profile_update(code:s.Profile, value:s.ProfileInput, who=Depends(identity)):
    with scope(who,'icp.configure') as db:
        old = db.list('icp_profiles',code=code)[0]
        row = db.put('icp_profiles',{**old,**value.model_dump()})
        db.audit('profile_updated',row['id'])
        return row


@app.put('/api/policies/{provider}')
def policy_update(provider:str,value:s.PolicyInput,who=Depends(identity)):
    with scope(who,'sources.configure') as db:
        if provider not in SETTINGS['sources']+['openai']:
            fail('Unsupported provider',422)
        if value.enabled and not value.reviewed_terms:
            fail('Source terms require explicit review')
        if value.expires_at <= utcnow():
            fail('Policy must have a future expiry')
        if any(not x.isalnum() for x in value.allowed_dataset_ids):
            fail('Invalid dataset ID',422)
        old=db.list('source_policies',provider=provider)
        row=db.put('source_policies',{**value.model_dump(mode='json'),'provider':provider,
            'id':old[0]['id'] if old else None,'reviewed_by':who['user_id']})
        for a in db.list('accounts'):
            if not a['is_demo']:
                invalidate_drafts(db,a['id'])
        db.audit('source_policy_reviewed',row['id'],value.reason)
        return row


@app.post('/api/accounts')
def account_create(value:s.AccountInput,who=Depends(identity)):
    with scope(who,'research.start') as db:
        tenant=db.conn.execute('SELECT is_demo FROM tenants WHERE id=%s',(db.tenant_id,)).fetchone()
        if value.is_demo and not tenant['is_demo']:
            fail('DEMO account requires DEMO tenant')
        return ingest_account(db,value.model_dump())


@app.get('/api/accounts/{account_id}')
def detail(account_id:str,who=Depends(identity)):
    with scope(who,'leads.read') as db:
        account=require(db,'accounts',account_id)
        db.audit('sensitive_account_read',account_id)
        result={'account':account,'assessment':assess(db,account)}
        for table in ['evidence','contacts','credential_verifications','consent_records','outreach_drafts','interactions','tasks','opportunities','partners','projects']:
            result[table]=db.list(table,account_id=account_id)
        return result


@app.post('/api/accounts/{account_id}/evidence')
def evidence_create(account_id:str,value:s.EvidenceInput,who=Depends(identity)):
    with scope(who,'leads.review') as db:
        a=require(db,'accounts',account_id,lock=True)
        if value.fact_type not in FACTS:
            fail('Unsupported fact type',422)
        if value.observed_at > utcnow() or value.expires_at <= value.observed_at:
            fail('Invalid evidence dates',422)
        if value.event_date and value.event_date>utcnow():
            fail('Future event is not a purchase signal',422)
        if value.source_provider=='google_places_api' and value.independent:
            fail('Maps evidence is not independently verified')
        row=db.put('evidence',{**value.model_dump(mode='json'),'account_id':account_id,
            'verification':'unverified','reviewer_id':None,'is_demo':a['is_demo']})
        invalidate_drafts(db,account_id)
        db.audit('evidence_added',row['id'])
        return row


@app.post('/api/evidence/{identifier}/review')
def evidence_review(identifier:str,value:s.EvidenceReview,who=Depends(identity)):
    with scope(who,'leads.review') as db:
        e=require(db,'evidence',identifier,lock=True)
        row=db.put('evidence',{**e,'verification':'verified' if value.approved else 'rejected','reviewer_id':who['user_id'],
            'confidence':value.confidence if value.confidence is not None else e['confidence']})
        invalidate_drafts(db,e['account_id'])
        db.audit('evidence_reviewed',identifier,value.reason)
        score(db,e['account_id'])
        return row


@app.post('/api/accounts/{account_id}/credentials')
def credentials(account_id:str,value:s.CredentialInput,who=Depends(identity)):
    with scope(who,'leads.review') as db:
        a=require(db,'accounts',account_id,lock=True)
        if value.province!=a['province']:
            fail('Credential province mismatch')
        if value.status!='unknown':
            if not value.work_class or not value.evidence_ids:
                fail('Credential scope and reviewed evidence required')
            for identifier in value.evidence_ids:
                e=require(db,'evidence',identifier)
                if e['account_id']!=account_id or e.get('fact_type')!='credential' or not usable(e,'score',a['is_demo']):
                    fail('Credential evidence is not verified')
                if value.status in ['verified','not_required'] and not credential_supports(db,e,value.model_dump(),a):
                    fail('Credential evidence does not prove the reviewed status and work scope')
                if not a['is_demo']:
                    domains={'RBQ':'rbq.gouv.qc.ca','STO':'skilledtradesontario.ca','TSSA':'tssa.org'}
                    authority=domains.get(value.authority)
                    host=urlsplit(e['source_url']).hostname or ''
                    if not authority or not (host==authority or host.endswith('.'+authority)):
                        fail('Credential needs the appropriate official registry source')
                    if (a['province']=='QC') != (value.authority=='RBQ'):
                        fail('Credential authority does not match province')
        row=db.put('credential_verifications',{**value.model_dump(),'account_id':account_id,'reviewer_id':who['user_id'],'is_demo':a['is_demo']})
        invalidate_drafts(db,account_id)
        db.audit('credential_reviewed',row['id'],value.reason)
        score(db,account_id)
        return row


@app.post('/api/accounts/{account_id}/score')
def scoring(account_id:str,who=Depends(identity)):
    with scope(who,'research.analyze') as db:
        return score(db,account_id)


@app.post('/api/accounts/{account_id}/score/override')
def override(account_id:str,value:s.Override,who=Depends(identity)):
    with scope(who,'leads.override') as db:
        a=require(db,'accounts',account_id,lock=True)
        current=assess(db,a)
        if current['exclusion_reasons'] or current['manual_review']:
            fail('Hard exclusions or Unknown cannot be overridden')
        allowed={e['id'] for e in evidence_map(db,a)[0].values()}
        if not value.evidence_ids or not set(value.evidence_ids)<=allowed:
            fail('Override needs reviewed evidence')
        for key,points in value.points.items():
            if key not in current['breakdown'] or not 0<=points<=current['breakdown'][key]['weight']:
                fail('Override points outside feature bounds')
            if current['breakdown'][key]['evidence_id'] not in value.evidence_ids:
                fail('Override must cite the feature evidence')
            current['breakdown'][key]['points']=points
        current['fit']=sum(x['points'] for x in current['breakdown'].values())
        current['state']='qualified' if current['fit']>=70 else 'review'
        current['override']={'reviewer_id':who['user_id'],'reason':value.reason,'evidence_ids':value.evidence_ids,'points':value.points}
        old=db.list('leads',account_id=account_id)
        row=db.put('leads',{**current,'account_id':account_id,'id':old[0]['id'] if old else None})
        db.audit('score_override',account_id,value.reason)
        return row


@app.post('/api/accounts/{account_id}/contacts')
def contact_create(account_id:str,value:s.ContactInput,who=Depends(identity)):
    with scope(who,'leads.review') as db:
        a=require(db,'accounts',account_id,lock=True)
        e=require(db,'evidence',value.evidence_id)
        if e['account_id']!=account_id or e.get('fact_type')!='contact' or e.get('value')!=value.email:
            fail('Contact must exactly match business contact evidence')
        if value.name is not None:
            fail('Contact names need a separately implemented identity review; leave null')
        row=db.put('contacts',{**value.model_dump(),'account_id':account_id,'is_business':True,'is_demo':a['is_demo']})
        invalidate_drafts(db,account_id)
        db.audit('business_contact_added',row['id'])
        return row


@app.post('/api/accounts/{account_id}/consents')
def consent_create(account_id:str,value:s.ConsentInput,who=Depends(identity)):
    with scope(who,'leads.review') as db:
        a=require(db,'accounts',account_id,lock=True)
        c=require(db,'contacts',value.contact_id)
        if c['account_id']!=account_id or c.get('evidence_id')!=value.evidence_id:
            fail('Consent/contact evidence mismatch')
        if value.expires_at<=utcnow():
            fail('Expired contact basis')
        if not a['is_demo']:
            e=require(db,'evidence',value.basis_evidence_id or '')
            if e['account_id']!=account_id or e['fact_type']!='contact_basis' or not allowed_evidence(db,e,a,'outreach'):
                fail('Real contact basis requires separately reviewed consent/legal evidence')
        row=db.put('consent_records',{**value.model_dump(mode='json'),'account_id':account_id,'status':'pending','reviewer_id':None})
        invalidate_drafts(db,account_id)
        db.audit('contact_basis_submitted',row['id'])
        return row


@app.post('/api/consents/{identifier}/review')
def consent_review(identifier:str,value:s.Review,who=Depends(identity)):
    with scope(who,'leads.review') as db:
        c=require(db,'consent_records',identifier,lock=True)
        a=require(db,'accounts',c['account_id'],lock=True)
        e=require(db,'evidence',c['evidence_id'])
        if value.approved and (not usable(e,'outreach',a['is_demo']) or db.list('suppressions',account_id=a['id'])):
            fail('Contact evidence or suppression blocks approval')
        if value.approved and not a['is_demo']:
            basis=require(db,'evidence',c.get('basis_evidence_id') or '')
            if not allowed_evidence(db,basis,a,'outreach'):
                fail('Contact basis evidence is no longer valid')
        row=db.put('consent_records',{**c,'status':'approved' if value.approved else 'rejected','reviewer_id':who['user_id']})
        invalidate_drafts(db,a['id'])
        db.audit('contact_basis_reviewed',identifier,value.reason)
        return row


@app.post('/api/accounts/{account_id}/drafts')
def draft_create(account_id:str,value:s.DraftInput,who=Depends(identity)):
    ai_result,context=None,None
    if value.use_ai:
        if not value.idempotency_key: fail('AI calls require an idempotency key',422)
        with scope(who,'drafts.create') as db:
            a=require(db,'accounts',account_id)
            c=require(db,'contacts',value.contact_id)
            if a['is_demo']:
                fail('No external model calls for fictional DEMO data')
            if c['account_id']!=account_id or assess(db,a)['state']!='qualified':
                fail('AI requires a qualified account and verified context')
            facts,_=evidence_map(db,a,'outreach')
            context=fingerprint(db,a,c)
        # Commit quota before the paid API call; a lost/failed response still consumes budget.
        with scope(who,'drafts.create') as db:
            p=usage.policy(db,lock=True)
            input_bound=len(str([{'id':e['id'],'fact_type':e['fact_type']} for e in facts.values()]).encode())+1024
            reservation=usage.reserve(db,who,'draft:'+value.idempotency_key,'openai',cost_micros=usage.model_estimate(p,input_bound,300),
                input_tokens=input_bound,output_tokens=300,task_id=account_id)
            if reservation.get('replayed'): fail('AI request already reserved; no repeated provider call',409)
            reserve_ai(db)
        receipt={}
        try:
            ai_result=suggest(a,list(facts.values()),model=p['model'],receipt=receipt)
        except Exception:
            with transaction(who['tenant_id'],who['user_id']) as db: usage.settle(db,reservation['id'],failed=True)
            raise
        actual={**receipt,'cost_micros':(receipt['input_tokens']*p['input_micros_per_million']+receipt['output_tokens']*p['output_micros_per_million']+999999)//1000000}
        with transaction(who['tenant_id'],who['user_id']) as db: usage.settle(db,reservation['id'],actual=actual)
    with scope(who,'drafts.create') as db:
        a=require(db,'accounts',account_id,lock=True)
        c=require(db,'contacts',value.contact_id)
        if c['account_id']!=account_id:
            fail('Contact account mismatch')
        if assess(db,a)['state']!='qualified' or db.list('suppressions',account_id=account_id):
            fail('Account is not qualified or suppressed')
        facts,_=evidence_map(db,a,'outreach')
        language=value.language or ('fr' if a['province']=='QC' else 'en')
        body=render_draft(a,language,facts)
        if ai_result is not None:
            if context!=fingerprint(db,a,c):
                fail('Research context changed during model call; manual retry required')
            validate_suggestion(ai_result,[e['id'] for e in facts.values()])
        row=db.put('outreach_drafts',{**body,'account_id':account_id,'contact_id':c['id'],'status':'draft',
            'revision':1,'language':language,'is_demo':a['is_demo'],'approved_by':None,'ai_suggestion':ai_result,
            'context_hash':fingerprint(db,a,c),'blocking_reasons':contact_gate(db,a,c)})
        db.audit('draft_created',row['id'])
        return row


@app.patch('/api/drafts/{identifier}')
def draft_edit(identifier:str,value:s.DraftEdit,who=Depends(identity)):
    with scope(who,'drafts.create') as db:
        d=require(db,'outreach_drafts',identifier,lock=True)
        if d['revision']!=value.revision:
            fail('Stale draft revision')
        a=require(db,'accounts',d['account_id'],lock=True)
        if db.list('suppressions',account_id=a['id']):
            fail('Do not contact')
        facts,_=evidence_map(db,a,'outreach')
        row=db.put('outreach_drafts',{**d,**render_draft(a,value.language,facts),'language':value.language,
            'revision':d['revision']+1,'status':'draft','approved_by':None,'approved_revision':None,
            'ai_suggestion':None,'context_hash':fingerprint(db,a,require(db,'contacts',d['contact_id']))})
        db.audit('draft_revision_changed',identifier)
        return row


@app.post('/api/drafts/{identifier}/approve')
def draft_approve(identifier:str,value:s.DraftApprove,who=Depends(identity)):
    with scope(who,'drafts.approve') as db:
        d=require(db,'outreach_drafts',identifier,lock=True)
        a=require(db,'accounts',d['account_id'],lock=True)
        c=require(db,'contacts',d['contact_id'])
        if d['revision']!=value.revision:
            fail('Stale draft revision')
        reasons=contact_gate(db,a,c)
        # Qualification may use different evidence. Review the exact citations in this revision.
        citations=[db.get('evidence',identifier2) for identifier2 in d.get('evidence_ids',[])]
        if (d.get('template_id')!='partnership_intro' or not citations
                or any(not e or e['account_id']!=a['id'] or e['fact_type']!='product_match'
                       or e.get('value') is not True or not allowed_evidence(db,e,a,'outreach') for e in citations)):
            reasons.append('draft_citations_invalid')
        _,conflicts=evidence_map(db,a,'outreach')
        if 'product_match' in conflicts:
            reasons.append('draft_citations_conflicting')
        if value.approved and reasons:
            fail({'blocked_by':reasons})
        # Refresh context only after all gates were re-evaluated by the human reviewer.
        row=db.put('outreach_drafts',{**d,'status':'approved' if value.approved else 'rejected',
            'context_hash':fingerprint(db,a,c),'approved_by':who['user_id'],'approved_revision':d['revision'],
            'approval_scope':'draft_review_only','blocking_reasons':[],'review_reason':value.reason})
        db.audit('draft_reviewed',identifier,value.reason)
        return row


@app.post('/api/drafts/{identifier}/send')
def no_send(identifier:str,who=Depends(identity)):
    with scope(who,'drafts.create') as db:
        require(db,'outreach_drafts',identifier)
    fail('Phase one: marketing delivery is permanently disabled',423)


@app.post('/api/accounts/{account_id}/replies')
def replies(account_id:str,value:s.ReplyInput,who=Depends(identity)):
    with scope(who,'crm.manage') as db:
        return ingest_reply(db,account_id,**value.model_dump())


@app.post('/api/accounts/{account_id}/suppress')
def dnc(account_id:str,value:s.Review,who=Depends(identity)):
    with scope(who,'crm.manage') as db:
        suppress(db,account_id,value.reason)
        return {'do_not_contact':True}


@app.post('/api/jobs')
def jobs(value:s.JobInput,who=Depends(identity)):
    with scope(who,'research.start') as db:
        return create_job(db,value.model_dump(),who=who)


@app.post('/api/jobs/{identifier}/{action}')
def job_action(identifier:str,action:str,who=Depends(identity)):
    if action not in ['pause','resume','step']:
        fail('Unsupported action',422)
    with scope(who,'research.start') as db:
        job=require(db,'search_jobs',identifier,lock=True)
        if action!='step':
            if job['status'] in ['completed','failed']:
                fail('Finished jobs cannot resume')
            if action=='resume': usage.job_limits(db,{'tenant_id':db.tenant_id,'user_id':job.get('actor_id','')},job,existing_id=job['id'])
            row=db.put('search_jobs',{**job,'status':'paused' if action=='pause' else 'queued',
                'lease_until':job['lease_until'],'next_attempt_at':None})
            db.audit('job_'+action,identifier)
            return row
    return process_one(who['tenant_id'],identifier) or {'status':'waiting_or_paused'}


@app.get('/api/jobs/{identifier}')
def job_detail(identifier:str,who=Depends(identity)):
    with scope(who,'leads.read') as db:
        db.audit('research_job_read',identifier)
        return {'job':require(db,'search_jobs',identifier),'items':db.list('job_items',job_id=identifier),
                'attempts':db.list('source_attempts',job_id=identifier)}


@app.patch('/api/opportunities/{identifier}')
def opportunity_stage(identifier:str,value:s.StageInput,who=Depends(identity)):
    transitions={'new':['meeting','rfq','partner_review','lost'],'meeting':['rfq','partner_review','lost'],
        'rfq':['meeting','won','lost'],'partner_review':['meeting','won','lost'],'won':[],'lost':[]}
    with scope(who,'crm.manage') as db:
        old=require(db,'opportunities',identifier,lock=True)
        if value.stage!=old['stage'] and value.stage not in transitions[old['stage']]:
            fail('Invalid opportunity stage transition')
        row=db.put('opportunities',{**old,**value.model_dump()})
        db.audit('opportunity_stage_changed',identifier,value.reason)
        return row


@app.patch('/api/tasks/{identifier}')
def task_assign(identifier:str,value:s.TaskInput,who=Depends(identity)):
    with scope(who,'leads.assign') as db:
        old=require(db,'tasks',identifier,lock=True)
        row=db.put('tasks',{**old,**value.model_dump()})
        db.audit('task_assigned',identifier,value.reason)
        return row


@app.patch('/api/partners/{identifier}')
def partner_change(identifier:str,value:s.PartnerInput,who=Depends(identity)):
    transitions={'application':['review','rejected'],'review':['approved','rejected'],
                 'approved':['activated','rejected'],'activated':[],'rejected':[]}
    with scope(who,'leads.review') as db:
        p=require(db,'partners',identifier,lock=True)
        a=require(db,'accounts',p['account_id'])
        if value.state!=p['state'] and value.state not in transitions[p['state']]:
            fail('Invalid partner transition')
        if value.state in ['approved','activated']:
            if assess(db,a)['state']!='qualified' or not value.evidence_ids:
                fail('Partner requires qualification and human-reviewed documents')
            for identifier2 in value.evidence_ids:
                e=require(db,'evidence',identifier2)
                if e['account_id']!=a['id'] or not allowed_evidence(db,e,a,'score'):
                    fail('Partner evidence is not reviewed')
            if value.state=='activated':
                if value.first_action_evidence_id not in value.evidence_ids:
                    fail('Activation requires evidence of the first real cooperation action')
                action=require(db,'evidence',value.first_action_evidence_id)
                if (action['fact_type']!='first_cooperation' or action.get('value') is not True
                        or not action.get('event_date') or date(action['event_date'])>utcnow()
                        or date(action['event_date'])>date(action['observed_at'])):
                    fail('Activation requires a reviewed, dated and completed first cooperation action')
        row=db.put('partners',{**p,**value.model_dump(),'reviewer_id':who['user_id']})
        db.audit('partner_state_changed',p['id'],value.reason)
        return row


@app.get('/api/export')
def export(format:str='json',who=Depends(identity)):
    with scope(who,'leads.export') as db:
        rows=[]
        for a in db.list('accounts'):
            evidence=[e for e in db.list('evidence',account_id=a['id']) if allowed_evidence(db,e,a,'export')]
            export_facts,_=evidence_map(db,a,'export')
            if not evidence or export_facts.get('real_business',{}).get('value') is not True or export_facts.get('province',{}).get('value')!=a['province']:
                continue
            assessment=assess(db,a)
            rows.append({'id':a['id'],'name':a['name'],'province':a['province'],'profile':a['profile'],
                'is_demo':a['is_demo'],'fit':assessment['fit'],'intent':assessment['intent'],'state':assessment['state'],
                'sources':[{'url':e['source_url'],'observed_at':date(e['observed_at']).isoformat(),
                    'license':e['provenance_license'],'verification':e['verification'],'is_demo':e['is_demo']} for e in evidence]})
        db.audit('export',format)
    if format=='json':
        return {'records':rows,'auto_send':False}
    if format!='csv':
        fail('Unsupported export format',422)
    output=io.StringIO()
    writer=csv.DictWriter(output,fieldnames=['id','name','province','profile','is_demo','fit','intent','state','sources'])
    writer.writeheader()
    for row in rows:
        safe={k:json.dumps(v,ensure_ascii=False) if isinstance(v,list) else v for k,v in row.items()}
        for k,v in safe.items():
            if isinstance(v,str) and v.lstrip().startswith(('=','+','-','@','\t','\r','\n')):
                safe[k]="'"+v
        writer.writerow(safe)
    return Response('\ufeff'+output.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename=nexa-evidence.csv'})


@app.delete('/api/accounts/{account_id}')
def delete_account(account_id:str,who=Depends(identity)):
    with scope(who,'leads.review') as db:
        require(db,'accounts',account_id,lock=True)
        task_ids={t['id'] for t in db.list('tasks',account_id=account_id)}
        for row in db.list('usage_ledger'):
            if row.get('task_id')==account_id or row.get('task_id') in task_ids:
                # Keep billable totals/idempotency while removing cached personal content.
                db.put('usage_ledger',{**row,'result':None,'context_hash':None})
        db.conn.execute('DELETE FROM accounts WHERE tenant_id=%s AND id=%s',(db.tenant_id,account_id))
        db.audit('account_deleted',account_id,'Personal and research records removed; audit retains ID only')
        return {'deleted':True}


@app.get('/api/audit')
def audit(who=Depends(identity)):
    with scope(who,'audit.read') as db:
        return db.list('audit_events')


@app.get('/api/accounts/{account_id}/agent-result')
def agent_result(account_id:str,who=Depends(identity)):
    with scope(who,'research.analyze') as db:
        db.audit('agent_account_read',account_id)
        a=require(db,'accounts',account_id)
        result=assess(db,a)
        facts,_=evidence_map(db,a)
        fields=['real_business','province','product_match','business_role','autonomy','purchasing_authority','capacity',
                'service_capabilities','market_segments','business_models']
        return {'schema_version':'3.2','region':a['province'],'profile':a['profile'],
            'reasoning_summary':{'fit':result['fit'],'intent':result['intent'],'state':result['state'],
                'profile_checks':result['profile_checks'],
                'policy':'Evidence reviewed before qualification; no automatic delivery.'},
            'structured_results':{'account_id':a['id'],'is_demo':a['is_demo'],
                'facts':{k:{'value':facts[k].get('value'),'source_url':facts[k]['source_url'],
                    'observed_at':date(facts[k]['observed_at']).isoformat(),'confidence':float(facts[k]['confidence'])}
                    if k in facts else {'value':None,'source_url':None,'observed_at':None,'confidence':None} for k in fields}},
            'excluded_leads':[{'account_id':a['id'],'reasons':result['exclusion_reasons']}] if result['exclusion_reasons'] else [],
            'uncertain_facts':result['manual_review'],
            'next_actions':['manual_evidence_review'] if result['state']=='review' else ['excluded_no_outreach']
                if result['state']=='excluded' else ['contact_basis_review','outreach_draft','human_approval'],
            'auto_send':False}


@app.post('/api/webhooks/n8n')
async def webhook(request:Request, x_nexa_timestamp:str=Header(default=''),
                  x_nexa_signature:str=Header(default=''),who=Depends(identity)):
    authorize(who,'n8n.webhook')
    if who['role']!='service': fail('Dedicated service identity required',403)
    authorize(who,'research.start')
    raw=await request.body()
    if len(raw)>100000:
        fail('Webhook too large',413)
    try:
        stamp=int(x_nexa_timestamp)
    except ValueError:
        fail('Invalid webhook timestamp',401)
    if abs(time.time()-stamp)>300:
        fail('Expired webhook',401)
    secret=config().get('webhook_secrets',{}).get(who['user_id'])
    if not secret: fail('Service webhook signature key is not configured',503)
    expected=hmac.new(secret.encode(),x_nexa_timestamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,x_nexa_signature):
        fail('Invalid webhook signature',401)
    try:
        payload=json.loads(raw)
        external_id=payload['event_id']
        if not isinstance(external_id,str) or not 1<=len(external_id)<=200:
            raise ValueError()
        job=s.JobInput.model_validate(payload['job'])
    except (ValueError,KeyError,TypeError):
        fail('Invalid webhook schema',422)
    with scope(who,'n8n.webhook') as db:
        db.conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))',(db.tenant_id+':webhook:'+external_id,))
        if db.list('webhook_events',external_id=external_id):
            fail('Webhook replay rejected')
        row=create_job(db,job.model_dump(),who=who)
        db.put('webhook_events',{'external_id':external_id,'job_id':row['id']})
        db.audit('n8n_webhook',row['id'])
        return row


from .enterprise_api import router as enterprise_router
app.include_router(enterprise_router)
