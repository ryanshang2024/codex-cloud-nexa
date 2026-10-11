from datetime import timedelta

import httpx
import pytest
from fastapi import HTTPException

from backend.db import transaction,utcnow
from backend.jobs import create_job,process_one
from backend.providers import Providers,public_target
from tests.test_workflow import enable,post,approve_basis


def test_provider_api_contracts_and_no_maps_content_cache(monkeypatch):
    monkeypatch.setenv('GOOGLE_PLACES_API_KEY','TEST_ONLY_NOT_A_CREDENTIAL')
    seen=[]
    def handler(req):
        seen.append(req)
        assert req.url.host=='places.googleapis.com'
        assert req.headers['X-Goog-FieldMask']=='places.id'
        return httpx.Response(200,json={'places':[{'id':'test-place','displayName':{'text':'Must not persist'},'rating':4.9}]})
    p={'enabled':True,'reviewed_by':'test','terms_url':'https://terms.example','provenance_license':'TEST',
       'purposes':['discovery'],'expires_at':(utcnow()+timedelta(days=1)).isoformat(),'request_limit':2,'requests_per_minute':1}
    providers=Providers(httpx.Client(transport=httpx.MockTransport(handler)))
    result=providers.call('google_places_api',p,{'query':'HVAC QC','language':'fr'})
    assert result=={'discovery_place_ids':['test-place'],'requires_independent_research':True}
    providers.close()


def test_private_business_dataset_and_missing_credentials(monkeypatch):
    monkeypatch.setenv('APIFY_API_TOKEN','TEST_ONLY_NOT_A_CREDENTIAL')
    p={'enabled':True,'reviewed_by':'test','terms_url':'https://terms.example','provenance_license':'TEST',
       'purposes':['discovery'],'expires_at':(utcnow()+timedelta(days=1)).isoformat(),'request_limit':2,'requests_per_minute':1,
       'allowed_dataset_ids':['dataset1'],'business_content_only':True}
    providers=Providers(httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,json=[{'is_business':False}]))))
    with pytest.raises(HTTPException):providers.call('authorized_social_api',p,{'dataset_id':'dataset1'})
    with pytest.raises(HTTPException):providers.call('authorized_social_api',p,{'dataset_id':'unreviewed'})
    monkeypatch.delenv('APIFY_API_TOKEN')
    with pytest.raises(HTTPException):providers.call('authorized_social_api',p,{'dataset_id':'dataset1'})
    providers.close()


@pytest.mark.parametrize('url',['https://127.0.0.1','https://localhost','http://public.example','https://169.254.169.254/latest/meta-data/','https://user:password@public.org'])
def test_ssrf_private_targets(url):
    with pytest.raises(HTTPException):public_target(url,[url])


def test_source_retries_rate_limit_and_quota(env):
    with transaction(env['tenant']) as db:
        policy=enable(db,'inbound_forms')
        job=create_job(db,{'province':'QC','profile':'H09','mode':'live','idempotency_key':'three-attempts',
            'items':[{'authorized_records':[{}]}],'max_results':200,'call_budget':10,'cost_budget':5}, who={'tenant_id':env['tenant'],'user_id':env['tenant']+':admin'})
    class Failure:
        def __init__(self):self.calls=0
        def call(self,*a):self.calls+=1;raise httpx.HTTPStatusError('limited',request=httpx.Request('POST','https://api.example'),response=httpx.Response(429))
    f=Failure()
    for i in range(3):
        process_one(env['tenant'],job['id'],f)
        with transaction(env['tenant']) as db:
            j=db.get('search_jobs',job['id']);db.put('search_jobs',{**j,'next_attempt_at':None})
            p=db.get('source_policies',policy['id']);db.put('source_policies',{**p,'next_call_at':None})
    assert f.calls==3
    with transaction(env['tenant']) as db:
        assert db.get('search_jobs',job['id'])['status']=='failed'
        assert db.list('job_items',job_id=job['id'])[0]['tries']==3
        assert db.get('search_jobs',job['id'])['calls_used']==3


def test_import_only_pending_business_records_result_cap(env):
    with transaction(env['tenant']) as db:
        enable(db,'inbound_forms')
        job=create_job(db,{'province':'QC','profile':'H09','mode':'live','idempotency_key':'canonical-import',
            'items':[{'authorized_records':[{}]}],'max_results':1,'call_budget':2,'cost_budget':1}, who={'tenant_id':env['tenant'],'user_id':env['tenant']+':admin'})
    class Import:
        def call(self,*a):return {'business_records':[
            {'account':{'name':'TEST RECORD not a real lead','province':'QC','profile':'H09','website':'https://test-company-1.public-domain.org'},
             'source_url':'https://test-source.public-domain.org','raw_excerpt':'TEST imported claim only.',
             'facts':[{'fact_type':'real_business','value':True}]},
            {'account':{'name':'Second record exceeds cap','province':'QC','profile':'H09'},
             'source_url':'https://test-source.public-domain.org','raw_excerpt':'TEST only.'}]}
    assert process_one(env['tenant'],job['id'],Import())['status']=='completed'
    with transaction(env['tenant']) as db:
        assert len(db.list('accounts'))==1
        assert db.list('accounts')[0]['state']=='review'
        assert db.list('evidence')[0]['verification']=='unverified'
        assert db.get('search_jobs',job['id'])['results_count']==1
    assert env['client'].get('/api/export',headers=env['headers']['admin']).json()['records']==[]


def test_evidence_change_revokes_draft_approval(env,seed):
    d=seed();a=d['account'];approve_basis(env,d)
    draft=post(env,'accounts/'+a['id']+'/drafts',{'contact_id':d['contacts'][0]['id']}).json()
    assert post(env,'drafts/'+draft['id']+'/approve',{'approved':True,'revision':1,'reason':'Manually reviewed DEMO draft.'}).status_code==200
    e=d['evidence'][0]
    assert post(env,'evidence/'+e['id']+'/review',{'approved':False,'reason':'Evidence rejected after manual review.'}).status_code==200
    detail=env['client'].get('/api/accounts/'+a['id'],headers=env['headers']['admin']).json()
    assert detail['outreach_drafts'][0]['status']=='draft' and detail['outreach_drafts'][0]['approved_by'] is None


def test_human_override_persists_and_blocks_contact(env,seed):
    d=seed();a=d['account'];approve_basis(env,d)
    points={k:0 for k in ['product_fit','purchasing_authority']}
    ids=[d['assessment']['breakdown'][k]['evidence_id'] for k in points]
    r=post(env,'accounts/'+a['id']+'/score/override',{'points':points,'evidence_ids':ids,'reason':'Human evidence reassessment lowers this DEMO fit.'},'manager')
    assert r.status_code==200
    detail=env['client'].get('/api/accounts/'+a['id'],headers=env['headers']['admin']).json()
    assert detail['assessment']['fit']==55 and detail['assessment']['state']=='review'
    assert post(env,'accounts/'+a['id']+'/drafts',{'contact_id':d['contacts'][0]['id']}).status_code==409


def test_two_reviewed_contacts_do_not_conflict_and_unknown_agent_fields(env,seed):
    d=seed();a=d['account']
    first=next(e for e in d['evidence'] if e['fact_type']=='contact')
    with transaction(env['tenant']) as db:
        e=db.put('evidence',{**first,'id':None,'value':'second@demo-qc-h01-0.example'})
        c=db.put('contacts',{'account_id':a['id'],'email':e['value'],'evidence_id':e['id'],'name':None})
    detail=env['client'].get('/api/accounts/'+a['id'],headers=env['headers']['admin']).json()
    assert len(detail['contacts'])==2 and detail['assessment']['state']=='qualified'
    result=env['client'].get('/api/accounts/'+a['id']+'/agent-result',headers=env['headers']['admin']).json()
    assert result['structured_results']['facts']['capacity']['value'] is None
    assert result['structured_results']['facts']['real_business']['source_url'].startswith('https://')


def test_real_evidence_without_policy_or_separate_contact_basis_is_blocked(env):
    from backend.domain import assess
    a=post(env,'accounts',{'name':'TEST unverified intake','province':'QC','profile':'H01'}).json()
    e=post(env,'accounts/'+a['id']+'/evidence',{'source_url':'https://test-source.public-domain.org',
        'observed_at':utcnow().isoformat(),'expires_at':(utcnow()+timedelta(days=30)).isoformat(),
        'confidence':.95,'fact_type':'real_business','value':True,'raw_excerpt':'TEST claim, not a real prospect.',
        'provenance_license':'TEST_SOURCE','permitted_purposes':['score','outreach','export'],
        'source_provider':'government_registry','independent':True}).json()
    assert post(env,'evidence/'+e['id']+'/review',{'approved':True,'reason':'TEST manual review cannot replace source authorization.'}).status_code==200
    with transaction(env['tenant']) as db:
        assert 'unknown:real_business' in assess(db,a)['manual_review']
        ce=db.put('evidence',{**db.get('evidence',e['id']),'id':None,'fact_type':'contact','value':'test@public-domain.org'})
        contact=db.put('contacts',{'account_id':a['id'],'email':ce['value'],'evidence_id':ce['id'],'name':None})
    assert post(env,'accounts/'+a['id']+'/consents',{'contact_id':contact['id'],'basis':'express_consent',
        'evidence_id':ce['id'],'business_relevance':'TEST public email is not an opt-in record.',
        'expires_at':(utcnow()+timedelta(days=30)).isoformat()}).status_code==404
    assert env['client'].get('/api/export',headers=env['headers']['admin']).json()['records']==[]


def test_ai_quota_commits_before_failure_and_is_bounded(env,monkeypatch):
    from backend.ai import reserve
    monkeypatch.setenv('NEXA_OPENAI_API_KEY','TEST_ONLY_NOT_A_CREDENTIAL')
    monkeypatch.setenv('NEXA_AI_ENABLED','true')
    with transaction(env['tenant']) as db:
        db.put('source_policies',{'provider':'openai','enabled':True,'reviewed_by':'test-reviewer',
            'terms_url':'https://terms.example','provenance_license':'TEST_ONLY','purposes':['draft'],
            'expires_at':(utcnow()+timedelta(days=1)).isoformat(),'request_limit':1,'requests_per_minute':1})
    with transaction(env['tenant']) as db:
        reserve(db)
    # Simulate an uncertain external response; the committed reservation remains consumed.
    with transaction(env['tenant']) as db:
        assert db.list('source_policies',provider='openai')[0]['requests_used']==1
        with pytest.raises(HTTPException) as e:reserve(db)
        assert e.value.status_code==429
