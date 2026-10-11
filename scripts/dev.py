"""Reviewed local setup. Secrets generated locally, never logged or committed."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.db import transaction
from backend.domain import SETTINGS
from backend.access import normalize_role, password_hash

IMAGE='postgres@sha256:b0f9560a2de083e2cc7382e75f808c7381a32852a7ec49117deedb300e552b24'
LOCAL=ROOT/'.local'


def run(args,**kw):
    return subprocess.run(args,check=True,**kw)


def secure_json(path,value):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(value,f,indent=2)


def owned_process(pid,name):
    try:
        cmd=Path(f'/proc/{pid}/cmdline').read_bytes()
        fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
        started=int(fields[19])/os.sysconf('SC_CLK_TCK')
        boot=time.time()-float(Path('/proc/uptime').read_text().split()[0])
        # PID reuse cannot pass the timestamp written immediately after our Popen.
        recorded=(LOCAL/(name+'.pid')).stat().st_mtime
        expected={'api':b'backend.app:app','worker':b'backend.jobs','frontend':b'npm run start'}[name]
        return expected in cmd and os.getpgid(pid)==pid and abs(recorded-boot-started)<5
    except (OSError,ValueError):
        return False


def setup():
    LOCAL.mkdir(mode=0o700,exist_ok=True)
    cfg_path=LOCAL/'runtime.json'
    if not cfg_path.exists():
        admin_pw=secrets.token_urlsafe(32)
        app_pw=secrets.token_urlsafe(32)
        tenant_ids=['nexa-demo','nexa-demo-other','nexa-workspace']
        bindings,tokens=[],{}
        for tenant in tenant_ids:
            tokens[tenant]={}
            for role in ['admin','manager','researcher','sales','compliance']:
                token=secrets.token_urlsafe(40)
                tokens[tenant][role]=token
                bindings.append({'token_hash':hashlib.sha256(token.encode()).hexdigest(),
                    'tenant_id':tenant,'role':role,'user_id':tenant+':'+role})
        secure_json(LOCAL/'tokens.json',tokens)
        secure_json(cfg_path,{'database_url':f'postgresql://nexa_app:{app_pw}@127.0.0.1:54329/nexa',
            'admin_database_url':f'postgresql://postgres:{admin_pw}@127.0.0.1:54329/nexa',
            'app_password':app_pw,'auth_bindings':bindings,'tenant_ids':tenant_ids,
            'webhook_secret':secrets.token_urlsafe(40),'postgres_image':IMAGE})
        fd=os.open(LOCAL/'postgres.env',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            f.write('POSTGRES_PASSWORD='+admin_pw+'\nPOSTGRES_DB=nexa\n')
    cfg=json.loads(cfg_path.read_text())
    # Each automation identity has its own server-side token and HMAC secret.
    cfg.setdefault('webhook_secrets',{})
    service_path=LOCAL/'service-identities.json'
    services=json.loads(service_path.read_text()) if service_path.exists() else {}
    for tenant in cfg['tenant_ids']:
        actor=tenant+':automation'
        if actor not in services:
            token=secrets.token_urlsafe(40)
            cfg['auth_bindings']=[b for b in cfg['auth_bindings'] if b['user_id']!=actor]
            cfg['auth_bindings'].append({'token_hash':hashlib.sha256(token.encode()).hexdigest(),
                'tenant_id':tenant,'user_id':actor,'role':'service'})
            services[actor]={'tenant_id':tenant,'user_id':actor,'token':token}
        cfg['webhook_secrets'].setdefault(actor,secrets.token_urlsafe(40))
        services[actor]['signing_secret']=cfg['webhook_secrets'][actor]
    service_path.write_text(json.dumps(services,indent=2));service_path.chmod(0o600)
    cfg_path.write_text(json.dumps(cfg,indent=2));cfg_path.chmod(0o600)
    inspected=subprocess.run(['docker','inspect','nexa-postgres'],capture_output=True,text=True)
    if inspected.returncode:
        run(['docker','run','-d','--name','nexa-postgres','--label','nexa.project=hvac-mvp',
             '--env-file',str(LOCAL/'postgres.env'),'-p','127.0.0.1:54329:5432',
             '-v',str(LOCAL/'pgdata')+':/var/lib/postgresql/data',cfg['postgres_image']],capture_output=True)
    else:
        obj=json.loads(inspected.stdout)[0]
        if obj['Config'].get('Labels',{}).get('nexa.project')!='hvac-mvp':
            raise RuntimeError('Existing container name is not owned by this project')
        if not obj['State']['Running']:
            run(['docker','start','nexa-postgres'],capture_output=True)
    for _ in range(40):
        try:
            with psycopg.connect(cfg['admin_database_url'],connect_timeout=2) as conn:
                conn.execute('SELECT 1')
            break
        except psycopg.OperationalError:
            time.sleep(.5)
    else:
        raise RuntimeError('PostgreSQL did not become ready; inspect local container logs')
    with psycopg.connect(cfg['admin_database_url'],autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname='nexa_app'").fetchone():
            conn.execute(sql.SQL('CREATE ROLE nexa_app LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS').format(sql.Literal(cfg['app_password'])))
        with conn.transaction():
            if not conn.execute("SELECT to_regclass('public.schema_migrations')").fetchone()[0]:
                conn.execute((ROOT/'db/001_initial.sql').read_text())
            for path in sorted((ROOT/'db').glob('[0-9]*_*.sql')):
                version=int(path.name.split('_',1)[0])
                if not conn.execute('SELECT 1 FROM schema_migrations WHERE version=%s',(version,)).fetchone():
                    conn.execute(path.read_text())
            conn.execute('GRANT USAGE ON SCHEMA public TO nexa_app')
            conn.execute('GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO nexa_app')
            conn.execute('REVOKE UPDATE,DELETE ON audit_events FROM nexa_app')
            for tenant in cfg['tenant_ids']:
                conn.execute('INSERT INTO tenants(id,name,is_demo) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
                             (tenant,tenant,tenant.startswith('nexa-demo')))
    for tenant in cfg['tenant_ids']:
        with transaction(tenant,'setup') as db:
            if not db.list('industry_templates'):
                db.put('industry_templates',{'industry':'HVAC','version':'3.3','market':['QC','ON']})
            for code,value in SETTINGS['profiles'].items():
                if not db.list('icp_profiles',code=code):
                    db.put('icp_profiles',{'code':code,**value})
            for provider in SETTINGS['sources']+['openai']:
                if not db.list('source_policies',provider=provider):
                    db.put('source_policies',{'provider':provider,'enabled':False,'purposes':[],
                        'provenance_license':None,'terms_url':None,'reviewed_by':None,'expires_at':None,
                        'request_limit':0,'requests_per_minute':0,'cost_per_call':None})
    login_path=LOCAL/'demo-logins.json'
    logins=json.loads(login_path.read_text()) if login_path.exists() else {}
    for b in cfg['auth_bindings']:
        with transaction(b['tenant_id'],'setup') as db:
            existing=db.get('users',b['user_id'])
            role=normalize_role(existing['role'] if existing else b['role'])
            if not existing or (role!='service' and not existing.get('password_hash')):
                password=secrets.token_urlsafe(24)
                db.put('users',{**(existing or {}),'id':b['user_id'],'role':role,'active':existing.get('active',True) if existing else True,'display_name':existing.get('display_name',b['user_id'].split(':')[-1]) if existing else b['user_id'].split(':')[-1],
                    'password_hash':password_hash(password) if role!='service' else None})
                if role!='service': logins[b['user_id']]={'tenant_id':b['tenant_id'],'user_id':b['user_id'],'password':password}
    login_path.write_text(json.dumps(logins,indent=2));login_path.chmod(0o600)
    envfile=ROOT/'frontend/.env.local'
    if envfile.parent.exists() and not envfile.exists():
        fd=os.open(envfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:
            f.write('NEXA_API_URL=http://127.0.0.1:8000\n')
    print('PostgreSQL ready; migrations, app role and three isolated tenants verified.')


def up():
    setup()
    commands={'api':[str(ROOT/'.venv/bin/python'),'-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','8000'],
              'worker':[str(ROOT/'.venv/bin/python'),'-m','backend.jobs'],
              'frontend':['npm','run','start','--','--hostname','127.0.0.1','--port','3000']}
    for name,args in commands.items():
        pidfile=LOCAL/(name+'.pid')
        if pidfile.exists():
            if owned_process(int(pidfile.read_text()),name):
                continue
        log=open(LOCAL/(name+'.log'),'ab')
        process_env=os.environ.copy()
        if name=='frontend':
            # This launcher always binds loopback; public releases use private_demo.
            process_env.setdefault('NEXA_WORKSPACE_MODE','local')
        proc=subprocess.Popen(args,cwd=ROOT/'frontend' if name=='frontend' else ROOT,
            env=process_env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        pidfile.write_text(str(proc.pid))
    import httpx
    for port,path in [(8000,'/health'),(3000,'/')]:
        for _ in range(60):
            try:
                response=httpx.get(f'http://127.0.0.1:{port}'+path,timeout=2)
                if response.status_code==200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.5)
        else:
            raise RuntimeError(f'Service on port {port} not ready; see .local logs')
    print('API, durable worker and Next.js are running. Marketing delivery remains disabled.')


def down():
    for name in ['api','worker','frontend']:
        p=LOCAL/(name+'.pid')
        if p.exists():
            pid=int(p.read_text())
            if owned_process(pid,name):
                os.killpg(pid,signal.SIGTERM)
            p.unlink()
    print('Only project-owned API/worker/frontend processes stopped; database data retained.')


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['init','up','down'])
    args=parser.parse_args()
    {'init':setup,'up':up,'down':down}[args.action]()
