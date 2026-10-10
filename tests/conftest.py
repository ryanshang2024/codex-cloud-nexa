import hashlib
import uuid

import psycopg
import pytest
from fastapi.testclient import TestClient

import backend.app as api_module
from backend.db import config, transaction
from backend.domain import SETTINGS
from backend.jobs import store_demo
from backend.providers import demo_candidate


@pytest.fixture
def env(monkeypatch):
    cfg=config()
    tenant='test-'+str(uuid.uuid4())
    other='test-'+str(uuid.uuid4())
    with psycopg.connect(cfg['admin_database_url']) as c:
        for t in [tenant,other]:
            c.execute('INSERT INTO tenants(id,name,is_demo) VALUES(%s,%s,true)',(t,'isolated automated test'))
    bindings=[]
    headers={}
    for role in ['admin','manager','researcher','sales','compliance']:
        token='TEST_ONLY_'+uuid.uuid4().hex
        headers[role]={'Authorization':'Bearer '+token}
        bindings.append({'token_hash':hashlib.sha256(token.encode()).hexdigest(),'tenant_id':tenant,
                         'role':role,'user_id':tenant+':'+role})
    token='TEST_ONLY_'+uuid.uuid4().hex
    headers['other']={'Authorization':'Bearer '+token}
    bindings.append({'token_hash':hashlib.sha256(token.encode()).hexdigest(),'tenant_id':other,'role':'admin','user_id':other+':admin'})
    monkeypatch.setattr(api_module,'config',lambda:{**cfg,'auth_bindings':bindings})
    for t in [tenant,other]:
        with transaction(t,'test') as db:
            for code,value in SETTINGS['profiles'].items():
                db.put('icp_profiles',{'code':code,**value})
            for provider in SETTINGS['sources']:
                db.put('source_policies',{'provider':provider,'enabled':False})
    with TestClient(api_module.app) as client:
        yield {'client':client,'headers':headers,'tenant':tenant,'other':other,'cfg':cfg}


@pytest.fixture
def seed(env):
    def make(province='QC',profile='H01',index=0):
        with transaction(env['tenant'],'test') as db:
            identifier=store_demo(db,demo_candidate(province,profile,index))
        response=env['client'].get('/api/accounts/'+identifier,headers=env['headers']['admin'])
        assert response.status_code==200
        return response.json()
    return make
