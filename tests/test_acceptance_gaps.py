"""Regression cases discovered while reviewing the user's six acceptance categories."""
from datetime import timedelta

import pytest

from backend.db import transaction, utcnow
from backend.domain import assess
from tests.test_workflow import post


@pytest.mark.parametrize('profile',[f'H{i:02}' for i in range(1,10)])
def test_generic_hvac_facts_cannot_prove_a_specific_profile(env,seed,profile):
    detail=seed('QC',profile)
    account=detail['account']
    with transaction(env['tenant']) as db:
        for e in db.list('evidence',account_id=account['id']):
            if e['fact_type'] in ['service_capabilities','market_segments','business_models']:
                db.put('evidence',{**e,'verification':'unverified'})
        assessment=assess(db,account)
        assert assessment['state']=='review'
        assert 'unknown:service_capabilities' in assessment['manual_review']


def test_commercial_only_business_cannot_qualify_as_residential_h01(env,seed):
    account=seed()['account']
    with transaction(env['tenant']) as db:
        rows=db.list('evidence',account_id=account['id'])
        market=next((e for e in rows if e['fact_type']=='market_segments'),None)
        if market:
            db.put('evidence',{**market,'value':['commercial']})
        else:
            db.put('evidence',{**rows[0],'id':None,'fact_type':'market_segments','value':['commercial']})
        assessment=assess(db,account)
        assert assessment['state']=='excluded'
        assert 'profile_mismatch:market_segments' in assessment['exclusion_reasons']


@pytest.mark.parametrize('profile,fact,value',[
    ('H02','service_capabilities',['heating']),
    ('H03','business_models',['company']),
    ('H05','service_capabilities',['hvac_repair']),
    ('H06','business_models',['employee_only']),
    ('H09','business_models',['independent_operator']),
])
def test_profile_specific_mismatches_are_excluded(env,seed,profile,fact,value):
    account=seed('ON',profile)['account']
    with transaction(env['tenant']) as db:
        proof=next(e for e in db.list('evidence',account_id=account['id']) if e['fact_type']==fact)
        db.put('evidence',{**proof,'value':value})
        assessment=assess(db,account)
        assert assessment['state']=='excluded'
        assert 'profile_mismatch:'+fact in assessment['exclusion_reasons']
        assert assessment['profile_checks'][fact]['matched'] is False


@pytest.mark.parametrize('value',[None,0,False])
def test_high_fit_does_not_replace_unknown_purchasing_authority(env,seed,value):
    account=seed()['account']
    with transaction(env['tenant']) as db:
        proof=next(e for e in db.list('evidence',account_id=account['id']) if e['fact_type']=='purchasing_authority')
        db.put('evidence',{**proof,'value':value})
        assessment=assess(db,account)
        assert assessment['fit']==80
        assert assessment['state']=='review'
        assert 'unknown:purchasing_authority' in assessment['manual_review']


def test_negative_credential_proof_cannot_be_marked_verified(env,seed):
    detail=seed();account=detail['account']
    with transaction(env['tenant']) as db:
        proof=next(e for e in db.list('evidence',account_id=account['id']) if e['fact_type']=='credential')
        db.put('evidence',{**proof,'value':False})
    response=post(env,'accounts/'+account['id']+'/credentials',{
        'province':'QC','status':'verified','work_class':'DEMO_HVAC','authority':'DEMO_AUTHORITY',
        'evidence_ids':[proof['id']],'reason':'Negative proof must never support a valid credential.'})
    assert response.status_code==409
    with transaction(env['tenant']) as db:
        assert assess(db,account)['state']=='review'


def test_credential_claim_must_prove_the_same_work_class(env,seed):
    account=seed()['account']
    with transaction(env['tenant']) as db:
        proof=next(e for e in db.list('evidence',account_id=account['id']) if e['fact_type']=='credential')
        db.put('evidence',{**proof,'value':{'status':'verified','province':'QC',
            'work_class':'DEMO_DIFFERENT_WORK','authority':'DEMO_AUTHORITY'}})
    response=post(env,'accounts/'+account['id']+'/credentials',{
        'province':'QC','status':'verified','work_class':'DEMO_HVAC','authority':'DEMO_AUTHORITY',
        'evidence_ids':[proof['id']],'reason':'A different work category does not verify this scope.'})
    assert response.status_code==409


@pytest.mark.parametrize('value',[True,'heat_pump_installation',['invented_service'],[{'name':'heating'}]])
def test_profile_evidence_rejects_malformed_capability_tags(env,seed,value):
    account=seed()['account']
    response=post(env,'accounts/'+account['id']+'/evidence',{
        'source_url':account['website']+'/demo/capabilities','observed_at':utcnow().isoformat(),
        'expires_at':(utcnow()+timedelta(days=1)).isoformat(),'confidence':1,
        'fact_type':'service_capabilities','value':value,'raw_excerpt':'DEMO malformed payload test only.',
        'provenance_license':'DEMO_ONLY','permitted_purposes':['score'],'source_provider':'demo','independent':True})
    assert response.status_code==422


def test_dashboard_does_not_display_expired_qualification(env,seed):
    account=seed()['account']
    with transaction(env['tenant']) as db:
        proof=next(e for e in db.list('evidence',account_id=account['id']) if e['fact_type']=='real_business')
        db.put('evidence',{**proof,'expires_at':(utcnow()-timedelta(seconds=1)).isoformat()})
    response=env['client'].get('/api/dashboard',headers=env['headers']['admin'])
    assert response.status_code==200
    payload=response.json()
    assert next(a for a in payload['accounts'] if a['id']==account['id'])['state']=='review'
    assert next(a for a in payload['leads'] if a['account_id']==account['id'])['state']=='review'
    assert payload['analytics']['demo']['qualified']==0
