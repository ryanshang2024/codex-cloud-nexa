import hashlib
import hmac
import json
import time
from datetime import timedelta

import psycopg
import pytest
from pydantic import ValidationError

from backend.ai import validate_suggestion
from backend.db import transaction, utcnow
from backend.domain import assess, classify_reply, score
from backend.jobs import process_one


def post(env,path,body,role='admin'):
    return env['client'].post('/api/'+path,headers=env['headers'][role],json=body)


def approve_basis(env,detail):
    a=detail['account'];c=detail['contacts'][0]
    r=post(env,'accounts/'+a['id']+'/consents',{'contact_id':c['id'],'basis':'express_consent',
        'evidence_id':c['evidence_id'],'business_relevance':'DEMO voluntary HVAC partnership request.',
        'expires_at':(utcnow()+timedelta(days=30)).isoformat()})
    assert r.status_code==200,r.text
    r=post(env,'consents/'+r.json()['id']+'/review',{'approved':True,'reason':'DEMO consent manually reviewed by compliance.'},'compliance')
    assert r.status_code==200,r.text


@pytest.mark.parametrize('province',['QC','ON'])
@pytest.mark.parametrize('profile',[f'H{i:02}' for i in range(1,11)])
def test_profiles_scoring_and_h10(env,seed,province,profile):
    d=seed(province,profile)
    result=d['assessment']
    assert result['fit']==100
    assert result['intent']==0
    assert result['state']==('excluded' if profile=='H10' else 'qualified')
    assert sum(v['weight'] for v in result['breakdown'].values())==100
    r=env['client'].get('/api/router',params={'province':province,'profile':profile},headers=env['headers']['admin'])
    assert r.status_code==200
    if profile=='H10':assert r.json()['routes']==[]
    else:assert all(not x['available'] for x in r.json()['routes'])


def test_unknown_credential_and_excluded_employee(seed):
    assert seed(index=1)['assessment']['state']=='review'
    assert 'unknown:credential' in seed(index=1)['assessment']['manual_review']
    assert seed(index=2)['assessment']['state']=='excluded'


def test_unverified_expired_conflicting_wrong_province(env,seed):
    d=seed();a=d['account']
    with transaction(env['tenant']) as db:
        e=next(x for x in db.list('evidence',account_id=a['id']) if x['fact_type']=='real_business')
        db.put('evidence',{**e,'verification':'unverified'})
        assert assess(db,a)['state']=='review'
        db.put('evidence',{**e,'expires_at':(utcnow()-timedelta(days=1)).isoformat()})
        assert assess(db,a)['state']=='review'
        db.put('evidence',e)
        p=next(x for x in db.list('evidence',account_id=a['id']) if x['fact_type']=='province')
        db.put('evidence',{**p,'value':'ON'})
        assert 'province_mismatch' in assess(db,a)['exclusion_reasons']
        db.put('evidence',p)
        db.put('evidence',{**e,'id':None,'value':False})
        assert 'conflicting_evidence:real_business' in assess(db,a)['manual_review']


def test_auth_rbac_and_tenant_hiding(env,seed):
    c=env['client'];a=seed()['account']
    assert c.get('/api/dashboard').status_code==401
    assert c.get('/api/dashboard',headers={'Authorization':'Bearer invalid'}).status_code==401
    assert c.get('/api/accounts/'+a['id'],headers=env['headers']['other']).status_code==404
    assert post(env,'jobs',{'province':'QC','profile':'H01','idempotency_key':'sales-disallowed'},'sales').status_code==403
    assert post(env,'accounts/'+a['id']+'/score/override',{'points':{},'evidence_ids':[],'reason':'Attempts cannot bypass hard conditions.'},'researcher').status_code==403


def test_database_rls_and_composite_foreign_keys(env,seed):
    a=seed()['account']
    with psycopg.connect(env['cfg']['database_url']) as c:
        assert c.execute('SELECT count(*) FROM accounts').fetchone()[0]==0
        c.execute("SELECT set_config('app.tenant_id',%s,true)",(env['other'],))
        assert c.execute('SELECT count(*) FROM accounts WHERE id=%s',(a['id'],)).fetchone()[0]==0
    with transaction(env['other']) as db:
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            db.put('contacts',{'account_id':a['id'],'email':'test@example.invalid'})


def test_audit_cannot_be_mutated(env,seed):
    seed()
    with transaction(env['tenant']) as db:
        e=db.list('audit_events')[0]
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            db.conn.execute('UPDATE audit_events SET data=%s WHERE id=%s',('{}',e['id']))


@pytest.mark.parametrize('province,language',[('QC','fr'),('ON','en')])
def test_bilingual_approval_contact_basis_send_lock_revision(env,seed,province,language):
    d=seed(province);a=d['account'];c=d['contacts'][0]
    draft=post(env,'accounts/'+a['id']+'/drafts',{'contact_id':c['id']}).json()
    assert draft['language']==language and 'DEMO' in draft['body']
    assert draft['contact_name'] is None and draft['purchase_signals'] is None
    review={'approved':True,'revision':1,'reason':'Human checked exact draft revision.'}
    assert post(env,'drafts/'+draft['id']+'/approve',review).status_code==409
    approve_basis(env,d)
    assert post(env,'drafts/'+draft['id']+'/approve',review,'sales').status_code==403
    assert post(env,'drafts/'+draft['id']+'/approve',review,'manager').status_code==200
    assert post(env,'drafts/'+draft['id']+'/send',{}).status_code==423
    assert env['client'].patch('/api/drafts/'+draft['id'],headers=env['headers']['sales'],json={'revision':1,'language':'en' if language=='fr' else 'fr'}).status_code==403
    edit=env['client'].patch('/api/drafts/'+draft['id'],headers=env['headers']['manager'],json={'revision':1,'language':'en' if language=='fr' else 'fr'})
    assert edit.status_code==200 and edit.json()['status']=='draft' and edit.json()['approved_by'] is None
    assert edit.json()['approved_revision'] is None
    assert post(env,'drafts/'+draft['id']+'/approve',review).status_code==409


@pytest.mark.parametrize('text,category',[
 ('Please send your price list.','PRICE_REQUEST'),('Projet disponible à Montréal','PROJECT_AVAILABLE'),
 ('I want to become a partner','INSTALLER_APPLICATION'),('Technical warranty question','TECHNICAL_QUESTION'),
 ('Pas maintenant, plus tard','NOT_NOW'),('Unsubscribe and send a quote','UNSUBSCRIBE'),
 ('Ne me contactez plus','UNSUBSCRIBE'),('Bonjour, merci','OTHER')])
def test_reply_categories(text,category):
    assert classify_reply(text)==category


def test_unambiguous_stop_is_suppression():
    assert classify_reply('STOP')=='UNSUBSCRIBE'


def reply(env,d,text,external='test-reply'):
    a=d['account']
    ev=post(env,'accounts/'+a['id']+'/evidence',{'source_url':a['website']+'/reply','observed_at':utcnow().isoformat(),
        'expires_at':(utcnow()+timedelta(days=30)).isoformat(),'confidence':1,'fact_type':'reply','value':text,
        'raw_excerpt':'DEMO simulated inbound reply.','provenance_license':'DEMO_ONLY','permitted_purposes':['reply'],
        'source_provider':'demo','independent':True})
    assert ev.status_code==200,ev.text
    eid=ev.json()['id']
    assert post(env,'evidence/'+eid+'/review',{'approved':True,'reason':'Manually reviewed DEMO inbound reply.'}).status_code==200
    return post(env,'accounts/'+a['id']+'/replies',{'external_id':external,'text':text,'evidence_id':eid})


def test_reply_crm_idempotency_and_unsubscribe(env,seed):
    d=seed();a=d['account'];approve_basis(env,d)
    draft=post(env,'accounts/'+a['id']+'/drafts',{'contact_id':d['contacts'][0]['id']}).json()
    assert reply(env,d,'We have an installation project.').json()['category']=='PROJECT_AVAILABLE'
    assert reply(env,d,'We have an installation project.').status_code==200
    detail=env['client'].get('/api/accounts/'+a['id'],headers=env['headers']['admin']).json()
    assert len(detail['projects'])==1 and len(detail['opportunities'])==1 and len(detail['tasks'])==1
    assert reply(env,d,'Please unsubscribe and do not contact us.','unsub').json()['category']=='UNSUBSCRIBE'
    detail=env['client'].get('/api/accounts/'+a['id'],headers=env['headers']['admin']).json()
    assert detail['outreach_drafts'][0]['status']=='blocked'
    assert detail['consent_records'][0]['status']=='revoked'
    assert detail['assessment']['state']=='excluded'
    assert post(env,'drafts/'+draft['id']+'/approve',{'approved':True,'revision':1,'reason':'Cannot override a do-not-contact flag.'}).status_code==409


def test_dedupe_preserves_separate_contacts(env,seed):
    d=seed();a=d['account']
    r=post(env,'accounts',{'name':a['name'],'province':'QC','profile':'H01','website':a['website'],'is_demo':True})
    assert r.json()['id']==a['id']
    with transaction(env['tenant']) as db:
        assert len(db.list('accounts'))==1
        assert len(db.list('contacts',account_id=a['id']))==1
        assert len(db.list('evidence',account_id=a['id']))>5
    r=post(env,'accounts',{'name':'DEMO Conflicting ON account','province':'ON','profile':'H01','website':a['website'],'is_demo':True})
    assert r.status_code==409


def test_resume_pause_checkpoint_idempotency_crash(env):
    body={'province':'ON','profile':'H06','mode':'demo','idempotency_key':'resume-test'}
    j=post(env,'jobs',body).json()
    assert post(env,'jobs',body).json()['id']==j['id']
    assert post(env,'jobs/'+j['id']+'/pause',{}).status_code==200
    assert process_one(env['tenant'],j['id']) is None
    assert post(env,'jobs/'+j['id']+'/resume',{}).status_code==200
    assert process_one(env['tenant'],j['id'])['cursor']==1
    with transaction(env['tenant']) as db:
        job=db.get('search_jobs',j['id'])
        db.put('search_jobs',{**job,'lease_until':utcnow()+timedelta(seconds=60)})
    assert process_one(env['tenant'],j['id']) is None
    with transaction(env['tenant']) as db:
        job=db.get('search_jobs',j['id']);db.put('search_jobs',{**job,'lease_until':utcnow()-timedelta(seconds=1)})
    assert process_one(env['tenant'],j['id'])['cursor']==2
    assert process_one(env['tenant'],j['id'])['status']=='completed'
    detail=env['client'].get('/api/jobs/'+j['id'],headers=env['headers']['admin']).json()
    assert detail['job']['cursor']==3 and len(detail['items'])==3
    assert all(x['status']=='done' for x in detail['items'])


def test_repeated_research_keeps_existing_valid_credentials_and_contacts(env,seed):
    first=seed();second=seed()
    assert first['account']['id']==second['account']['id']
    assert second['assessment']['state']=='qualified'
    approve_basis(env,second)
    draft=post(env,'accounts/'+second['account']['id']+'/drafts',{'contact_id':second['contacts'][0]['id']}).json()
    assert post(env,'drafts/'+draft['id']+'/approve',{'approved':True,'revision':1,'reason':'Repeated research keeps reviewed evidence usable.'}).status_code==200


def enable(db,provider):
    old=db.list('source_policies',provider=provider)[0]
    return db.put('source_policies',{**old,'enabled':True,'terms_url':'https://policy.example/terms','reviewed_by':'test-reviewer',
        'provenance_license':'TEST_ONLY','purposes':['discovery'],'expires_at':(utcnow()+timedelta(days=1)).isoformat(),
        'request_limit':5,'requests_per_minute':120,'cost_per_call':.1})


def test_live_source_fallback_budget_and_disabled(env):
    from backend.jobs import create_job
    class Fake:
        def __init__(self):self.calls=[]
        def call(self,provider,policy,payload):
            self.calls.append(provider)
            if provider=='inbound_forms':raise ValueError('source unavailable')
            return {'business_records':[],'verification':'unverified'}
    fake=Fake()
    with transaction(env['tenant']) as db:
        enable(db,'inbound_forms');enable(db,'government_registry')
        job=create_job(db,{'province':'QC','profile':'H09','mode':'live','idempotency_key':'fallback',
            'items':[{'authorized_records':[{'name':'TEST_ONLY'}]}],'max_results':200,'call_budget':2,'cost_budget':1}, who={'tenant_id':env['tenant'],'user_id':env['tenant']+':admin'})
    assert process_one(env['tenant'],job['id'],fake)['status']=='completed'
    assert fake.calls==['inbound_forms','government_registry']
    with transaction(env['tenant']) as db:
        assert db.get('search_jobs',job['id'])['calls_used']==2
        assert len(db.list('accounts'))==0  # provider output not falsely promoted to verified CRM
        job=create_job(db,{'province':'QC','profile':'H09','mode':'live','idempotency_key':'budget',
            'items':[{'authorized_records':[{'name':'TEST_ONLY'}]}],'max_results':200,'call_budget':0,'cost_budget':0}, who={'tenant_id':env['tenant'],'user_id':env['tenant']+':admin'})
    result=process_one(env['tenant'],job['id'],fake)
    assert result['status'] in ['budget_exhausted','failed']
    assert len(fake.calls)==2


def test_no_unauthorized_source_is_called(env):
    j=post(env,'jobs',{'province':'QC','profile':'H01','mode':'live','idempotency_key':'disabled','items':[{'query':'test'}]}).json()
    class Never:
        def call(self,*args):raise AssertionError('Unauthorized provider was called')
    assert process_one(env['tenant'],j['id'],Never())['status']=='failed'


def test_model_cannot_invent_evidence_or_free_text():
    assert validate_suggestion({'template_id':'partnership_intro','evidence_ids':['known']},['known'])['template_id']=='partnership_intro'
    with pytest.raises(Exception):validate_suggestion({'template_id':'partnership_intro','evidence_ids':['fabricated']},['known'])
    with pytest.raises(ValidationError):validate_suggestion({'template_id':'partnership_intro','evidence_ids':['known'],'company':'invented'},['known'])


def test_export_formula_unknown_and_delete(env,seed):
    d=seed();a=d['account']
    with transaction(env['tenant']) as db:
        db.put('accounts',{**db.get('accounts',a['id']),'name':'=HYPERLINK("malicious")'})
    r=env['client'].get('/api/export?format=csv',headers=env['headers']['researcher'])
    assert r.status_code==200 and "'=HYPERLINK" in r.text
    assert 'DEMO_ONLY' in r.text and 'verified' in r.text
    post(env,'accounts',{'name':'Unverified candidate','province':'QC','profile':'H01'})
    export=env['client'].get('/api/export',headers=env['headers']['researcher']).json()['records']
    assert len(export)==1
    assert env['client'].delete('/api/accounts/'+a['id'],headers=env['headers']['compliance']).status_code==200
    with transaction(env['tenant']) as db:
        assert not db.list('evidence',account_id=a['id']) and not db.list('contacts',account_id=a['id'])
        assert any(e['action']=='account_deleted' for e in db.list('audit_events'))


def test_signed_webhook_expiry_replay(env):
    raw=json.dumps({'event_id':'event-1','job':{'province':'QC','profile':'H01','mode':'demo','idempotency_key':'webhook'}}).encode()
    stamp=str(int(time.time()))
    sig=hmac.new(env['cfg']['webhook_secret'].encode(),stamp.encode()+b'.'+raw,hashlib.sha256).hexdigest()
    headers={**env['headers']['service'],'X-Nexa-Timestamp':stamp,'X-Nexa-Signature':sig,'Content-Type':'application/json'}
    c=env['client']
    assert c.post('/api/webhooks/n8n',headers={**headers,'X-Nexa-Signature':'wrong'},content=raw).status_code==401
    assert c.post('/api/webhooks/n8n',headers=headers,content=raw).status_code==200
    assert c.post('/api/webhooks/n8n',headers=headers,content=raw).status_code==409
    assert c.post('/api/webhooks/n8n',headers={**headers,'X-Nexa-Timestamp':'0'},content=raw).status_code==401


def test_delete_and_rediscover_cannot_erase_business_opt_out(env,seed):
    d=seed();a=d['account']
    assert post(env,'accounts/'+a['id']+'/suppress',{'approved':True,'reason':'DEMO business explicitly declined further contact.'}).status_code==200
    assert env['client'].delete('/api/accounts/'+a['id'],headers=env['headers']['compliance']).status_code==200
    rediscovered=post(env,'accounts',{'name':a['name'],'province':a['province'],'profile':a['profile'],
        'website':a['website'],'is_demo':True})
    assert rediscovered.status_code==200 and rediscovered.json()['state']=='excluded'
    with transaction(env['tenant']) as db:
        assert len(db.list('suppression_keys'))==1
        key=db.list('suppression_keys')[0]
        assert len(key['digest'])==64 and 'value' not in key
