"""Business-boundary regressions; all accounts/events are isolated TEST/DEMO fixtures."""
from datetime import timedelta

import pytest

from backend.db import transaction, utcnow
from backend.domain import classify_reply
from backend.jobs import process_one
from tests.test_workflow import approve_basis, enable, post, reply


@pytest.mark.parametrize('text',[
    'Please stop emailing me about pricing.',
    "Don't email me again.",
    'Do not send any more emails.',
    'Stop sending us messages.',
    "Ne m'écrivez plus, même pour un devis.",
    'Ne m’envoyez plus de courriels.',
    'Veuillez cesser de nous contacter.',
    'Arrêtez de nous envoyer des messages.',
])
def test_common_english_and_french_opt_outs_take_priority(text):
    assert classify_reply(text)=='UNSUBSCRIBE'


@pytest.mark.parametrize('text,category',[
    ('Can you stop by to provide a quote?','PRICE_REQUEST'),
    ('Please email me the technical specification.','TECHNICAL_QUESTION'),
    ('Arrêtez la machine avant installation.','OTHER'),
    ('Bonjour, merci pour votre message.','OTHER'),
])
def test_normal_business_messages_are_not_opt_outs(text,category):
    assert classify_reply(text)==category


@pytest.mark.parametrize('text',[
    'Please stop emailing me about pricing.',
    "Ne m'écrivez plus, même pour un devis.",
])
def test_opt_out_revokes_basis_and_cannot_create_sales_opportunity(env,seed,text):
    detail=seed(); account=detail['account']; approve_basis(env,detail)
    draft=post(env,'accounts/'+account['id']+'/drafts',{'contact_id':detail['contacts'][0]['id']}).json()
    response=reply(env,detail,text)
    assert response.status_code==200
    assert response.json()['category']=='UNSUBSCRIBE'
    with transaction(env['tenant']) as db:
        assert db.list('suppressions',account_id=account['id'])
        assert db.list('consent_records',account_id=account['id'])[0]['status']=='revoked'
        assert db.get('outreach_drafts',draft['id'])['status']=='blocked'
        assert db.list('opportunities',account_id=account['id'])==[]


def test_conflicting_reply_payload_is_not_a_successful_retry(env,seed):
    detail=seed()
    original=reply(env,detail,'Please send your price list.','stable-event-id')
    assert original.status_code==200
    retry=reply(env,detail,'Please send your price list.','stable-event-id')
    assert retry.json()['id']==original.json()['id']
    conflict=reply(env,detail,'STOP','stable-event-id')
    assert conflict.status_code==409
    with transaction(env['tenant']) as db:
        assert len(db.list('interactions',account_id=detail['account']['id']))==1


def inbound_evidence(env,seed,*,live=False,fact_type='reply'):
    account=seed()['account']; text='Please send your price list.'
    with transaction(env['tenant']) as db:
        if live:
            account=db.put('accounts',{**account,'is_demo':False,'name':'TEST RECORD: inbound authorization fixture'})
        sample=db.list('evidence',account_id=account['id'])[0]
        evidence=db.put('evidence',{**sample,'id':None,'fact_type':fact_type,'value':text,
            'is_demo':not live,'permitted_purposes':['reply'],'source_provider':'inbound_forms' if live else 'demo',
            'provenance_license':'TEST_ONLY' if live else 'DEMO_ONLY'})
        if live:
            policy=enable(db,'inbound_forms')
            db.put('source_policies',{**policy,'purposes':['reply']})
    return account,evidence,text


@pytest.mark.parametrize('invalid',['disabled','expired','wrong_purpose','wrong_license'])
def test_real_inbound_requires_current_matching_source_authorization(env,seed,invalid):
    account,evidence,text=inbound_evidence(env,seed,live=True)
    with transaction(env['tenant']) as db:
        policy=db.list('source_policies',provider='inbound_forms')[0]
        change={'disabled':{'enabled':False},'expired':{'expires_at':(utcnow()-timedelta(seconds=1)).isoformat()},
            'wrong_purpose':{'purposes':['score']},'wrong_license':{'provenance_license':'OTHER_TEST_LICENSE'}}[invalid]
        db.put('source_policies',{**policy,**change})
    response=post(env,'accounts/'+account['id']+'/replies',{
        'external_id':'unauthorized-event','text':text,'evidence_id':evidence['id']})
    assert response.status_code==409
    with transaction(env['tenant']) as db:
        assert db.list('interactions',account_id=account['id'])==[]
        assert db.list('opportunities',account_id=account['id'])==[]


def test_reviewed_non_reply_fact_cannot_be_an_inbound_message(env,seed):
    account,evidence,text=inbound_evidence(env,seed,fact_type='product_match')
    assert post(env,'accounts/'+account['id']+'/replies',{
        'external_id':'unrelated-proof','text':text,'evidence_id':evidence['id']}).status_code==409


def test_real_inbound_policy_can_be_reviewed_and_used(env,seed):
    account,evidence,text=inbound_evidence(env,seed,live=True)
    response=env['client'].put('/api/policies/inbound_forms',headers=env['headers']['compliance'],json={
        'enabled':True,'terms_url':'https://policy.example/test-only','provenance_license':'TEST_ONLY',
        'purposes':['reply'],'expires_at':(utcnow()+timedelta(days=1)).isoformat(),
        'request_limit':5,'requests_per_minute':60,'cost_per_call':0,'reviewed_terms':True,
        'reason':'TEST ONLY: explicitly reviewed inbound reply processing.'})
    assert response.status_code==200,response.text
    assert post(env,'accounts/'+account['id']+'/replies',{
        'external_id':'authorized-event','text':text,'evidence_id':evidence['id']}).json()['category']=='PRICE_REQUEST'


@pytest.mark.parametrize('invalid',['unrelated_fact','negative_action','undated_action','future_action'])
def test_partner_activation_requires_a_completed_cooperation_action(env,seed,invalid):
    account=seed()['account']
    with transaction(env['tenant']) as db:
        partner=db.put('partners',{'account_id':account['id'],'state':'approved'})
        sample=db.list('evidence',account_id=account['id'])[0]
        evidence=db.put('evidence',{**sample,'id':None,'fact_type':'first_cooperation','value':True,
            'event_date':(utcnow()-timedelta(days=1)).isoformat()})
        change={'unrelated_fact':{'fact_type':'product_match'},'negative_action':{'value':False},
            'undated_action':{'event_date':None},'future_action':{'event_date':(utcnow()+timedelta(days=1)).isoformat()}}[invalid]
        evidence=db.put('evidence',{**evidence,**change})
    response=env['client'].patch('/api/partners/'+partner['id'],headers=env['headers']['manager'],json={
        'state':'activated','reason':'TEST ONLY: first cooperation evidence must be substantive.',
        'evidence_ids':[evidence['id']],'first_action_evidence_id':evidence['id']})
    assert response.status_code==409
    with transaction(env['tenant']) as db:
        assert db.get('partners',partner['id'])['state']=='approved'


def test_reviewed_completed_cooperation_can_activate_a_partner(env,seed):
    account=seed()['account']
    with transaction(env['tenant']) as db:
        partner=db.put('partners',{'account_id':account['id'],'state':'approved'})
        sample=db.list('evidence',account_id=account['id'])[0]
        evidence=db.put('evidence',{**sample,'id':None,'fact_type':'first_cooperation','value':True,
            'event_date':(utcnow()-timedelta(days=1)).isoformat()})
    response=env['client'].patch('/api/partners/'+partner['id'],headers=env['headers']['manager'],json={
        'state':'activated','reason':'TEST ONLY: documented completed first cooperation reviewed.',
        'evidence_ids':[evidence['id']],'first_action_evidence_id':evidence['id']})
    assert response.status_code==200
    assert response.json()['state']=='activated'


@pytest.mark.parametrize('invalid',['expired','rejected','outreach_permission_removed'])
def test_qualified_account_cannot_approve_a_draft_with_invalid_citations(env,seed,invalid):
    detail=seed(); account=detail['account']; approve_basis(env,detail)
    draft=post(env,'accounts/'+account['id']+'/drafts',{'contact_id':detail['contacts'][0]['id']}).json()
    with transaction(env['tenant']) as db:
        original=db.get('evidence',draft['evidence_ids'][0])
        db.put('evidence',{**original,'id':None,'permitted_purposes':['score']})
        change={'expired':{'expires_at':(utcnow()-timedelta(seconds=1)).isoformat()},
            'rejected':{'verification':'rejected'},'outreach_permission_removed':{'permitted_purposes':['score']}}[invalid]
        db.put('evidence',{**original,**change})
    response=post(env,'drafts/'+draft['id']+'/approve',{
        'approved':True,'revision':1,'reason':'Qualification must not replace the exact outgoing citation check.'})
    assert response.status_code==409
    # A newly reviewed outreach fact must be cited in a new revision before approval.
    with transaction(env['tenant']) as db:
        replacement=db.put('evidence',{**original,'id':None})
    edited=env['client'].patch('/api/drafts/'+draft['id'],headers=env['headers']['sales'],json={
        'revision':1,'language':draft['language']})
    assert edited.status_code==200
    assert edited.json()['evidence_ids']==[replacement['id']]
    assert post(env,'drafts/'+draft['id']+'/approve',{
        'approved':True,'revision':2,'reason':'Human checked the regenerated revision and its current citation.'}).status_code==200


@pytest.mark.parametrize('change',[{'province':'ON'},{'profile':'H06'},{'call_budget':1}])
def test_job_idempotency_key_cannot_silently_change_search_scope(env,change):
    body={'province':'QC','profile':'H01','mode':'demo','idempotency_key':'same-search'}
    original=post(env,'jobs',body)
    assert original.status_code==200
    assert post(env,'jobs',body).json()['id']==original.json()['id']
    assert post(env,'jobs',{**body,**change}).status_code==409


@pytest.mark.parametrize('change',[
    {'enabled':False},
    {'purposes':['score']},
    {'cost_per_call':2},
])
def test_current_source_authorization_and_price_are_checked_before_call(env,monkeypatch,change):
    import backend.jobs as jobs
    with transaction(env['tenant']) as db:
        enable(db,'inbound_forms')
    job=post(env,'jobs',{'province':'QC','profile':'H09','mode':'live','idempotency_key':'revoked-after-route',
        'items':[{'authorized_records':[{'name':'TEST ONLY'}]}]}).json()
    original=jobs.route_for_job
    def revoked_route(*args):
        routes=original(*args)
        assert len(routes)==1
        with transaction(env['tenant']) as db:
            policy=db.list('source_policies',provider='inbound_forms')[0]
            db.put('source_policies',{**policy,**change})
        return routes
    monkeypatch.setattr(jobs,'route_for_job',revoked_route)
    class Fake:
        def __init__(self):self.calls=[]
        def call(self,provider,policy,payload):
            self.calls.append(provider)
            return {'business_records':[]}
    fake=Fake()
    process_one(env['tenant'],job['id'],fake)
    assert fake.calls==[]
    with transaction(env['tenant']) as db:
        assert db.get('search_jobs',job['id'])['calls_used']==0
        assert db.list('source_policies',provider='inbound_forms')[0].get('requests_used',0)==0


@pytest.mark.parametrize('mode',['demo','live'])
def test_existing_jobs_without_hashes_keep_exact_retry_compatibility(env,mode):
    body={'province':'QC','profile':'H01','mode':mode,'idempotency_key':'legacy-exact-retry'}
    if mode=='live':body['items']=[{'query':'TEST ONLY: unchanged search request'}]
    job=post(env,'jobs',body).json()
    with transaction(env['tenant']) as db:
        existing=db.get('search_jobs',job['id'])
        existing.pop('request_hash')
        db.put('search_jobs',existing)
    assert post(env,'jobs',body).json()['id']==job['id']
    assert post(env,'jobs',{**body,'province':'ON'}).status_code==409


def test_live_job_retry_compares_the_items_as_well_as_market(env):
    body={'province':'QC','profile':'H01','mode':'live','idempotency_key':'exact-import',
        'items':[{'authorized_records':[{'name':'TEST ONLY: first import'}]}]}
    original=post(env,'jobs',body).json()
    assert post(env,'jobs',body).json()['id']==original['id']
    changed={**body,'items':[{'authorized_records':[{'name':'TEST ONLY: different import'}]}]}
    assert post(env,'jobs',changed).status_code==409


def test_omitted_and_explicit_default_budget_are_the_same_job_request(env):
    body={'province':'QC','profile':'H01','mode':'demo','idempotency_key':'equivalent-defaults'}
    original=post(env,'jobs',body).json()
    retry=post(env,'jobs',{**body,'cost_budget':1.0,'call_budget':10,'max_results':200,'items':[]})
    assert retry.status_code==200
    assert retry.json()['id']==original['id']
