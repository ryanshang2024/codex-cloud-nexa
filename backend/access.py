"""One policy owner for human API, worker and Agent tool authorization."""
import base64
import hashlib
import hmac
import secrets
from contextlib import contextmanager
from datetime import timedelta

from fastapi import Header, HTTPException
from .db import config, transaction, utcnow
from .domain import date, fail, require

WORK={'work.read','work.update','work.notes','ai.task.query','ai.work.summary','ai.voice.record'}
EMPLOYEE_CEILING=WORK|{'work.draft','work.reply','ai.followup.draft'}
MANAGER=WORK|{'work.draft','work.reply','ai.followup.draft','leads.read','leads.review','leads.assign','drafts.create','drafts.approve','crm.manage','audit.read'}
DELEGATABLE={'icp.configure','research.start','research.analyze','leads.export','analytics.company','leads.override'}
ADMIN=MANAGER|DELEGATABLE|{'sources.configure','users.manage','ai.policy.manage','ai.budget.approve','leads.override','ai.followup.draft'}
SERVICE_CEILING={'n8n.webhook','research.start'}
ROLE_MAP={'admin':'super_admin','sales':'employee','researcher':'manager','compliance':'manager'}

def normalize_role(role): return ROLE_MAP.get(role,role)

def principal(db,user_id):
    u=db.get('users',user_id)
    if not u or not u.get('active',True): fail('Identity disabled or missing',401)
    role=u['role']; grants=db.list('user_grants',user_id=user_id)
    granted={g['permission'] for g in grants if g.get('enabled',True)}
    denied={g['permission'] for g in grants if not g.get('enabled',True)}
    permissions=ADMIN if role=='super_admin' else MANAGER|(granted&DELEGATABLE) if role=='manager' else WORK|(granted&EMPLOYEE_CEILING) if role=='employee' else granted&SERVICE_CEILING if role=='service' else set()
    if role not in ['super_admin','service']: permissions=permissions-denied
    return {'tenant_id':db.tenant_id,'user_id':user_id,'role':role,'permissions':sorted(permissions),
            'display_name':u.get('display_name',user_id),'grants':{g['permission']:g.get('provinces',[]) for g in grants if g.get('enabled',True)}}

def identity(authorization:str|None=Header(default=None)):
    if not authorization or not authorization.startswith('Bearer '): fail('Authentication required',401)
    token=authorization[7:]; digest=hashlib.sha256(token.encode()).hexdigest()
    if token.startswith('sess.'):
        try:
            _,encoded,_=token.split('.'); tenant=base64.urlsafe_b64decode(encoded+'='*(-len(encoded)%4)).decode()
        except (ValueError,UnicodeError): fail('Invalid session',401)
        with transaction(tenant) as db:
            sessions=db.list('auth_sessions',token_hash=digest)
            if not sessions or sessions[0]['revoked'] or date(sessions[0]['expires_at'])<=utcnow(): fail('Session expired or revoked',401)
            return {**principal(db,sessions[0]['user_id']),'session_id':sessions[0]['id']}
    for b in config()['auth_bindings']:
        if hmac.compare_digest(b['token_hash'],digest):
            with transaction(b['tenant_id']) as db: return principal(db,b['user_id'])
    fail('Invalid credential',401)

def authorize(who,permission):
    # Re-read the authoritative user on each boundary: queued jobs and stale model outputs cannot retain old grants.
    with transaction(who['tenant_id'],who['user_id']) as db:
        current=principal(db,who['user_id']); allowed=permission in current['permissions']
        if not allowed: db.audit('access_denied',permission,'Role policy denied this action')
    if not allowed: fail('Permission denied: '+permission,403)
    return current

@contextmanager
def scope(who,permission=None):
    if permission: who=authorize(who,permission)
    try:
        with transaction(who['tenant_id'],who['user_id']) as db: yield db
    except HTTPException as exc:
        if exc.status_code in [403,404,429]:
            # Persist the refusal after the request transaction rolls back.
            with transaction(who['tenant_id'],who['user_id']) as db:
                db.audit('record_access_denied' if exc.status_code in [403,404] else 'quota_denied',permission or 'authenticated_action',str(exc.status_code))
        raise

def password_hash(password,salt=None):
    salt=salt or secrets.token_hex(16)
    value=hashlib.scrypt(password.encode(),salt=bytes.fromhex(salt),n=16384,r=8,p=1).hex()
    return 'scrypt$'+salt+'$'+value

def verify_password(password,hashed):
    try: _,salt,_=hashed.split('$'); return hmac.compare_digest(password_hash(password,salt),hashed)
    except (ValueError,TypeError): return False

def login(tenant,user_id,password):
    error=None; result=None
    with transaction(tenant,user_id) as db:
        u=db.get('users',user_id,lock=True); now=utcnow()
        attempts=u.get('login_failures',0) if u and u.get('login_window') and date(u['login_window'])>now-timedelta(minutes=1) else 0
        if attempts>=5: error=('Sign-in attempts temporarily limited',429)
        elif not u or u['role']=='service' or not u.get('active',True) or not verify_password(password,u.get('password_hash')):
            if u:
                db.put('users',{**u,'login_failures':attempts+1,'login_window':u.get('login_window') if attempts else now.isoformat()})
                db.audit('sign_in_denied',user_id,'Invalid or disabled credential')
            error=('Invalid sign-in credentials',401)
        else:
            db.put('users',{**u,'login_failures':0,'login_window':None})
            token='sess.'+base64.urlsafe_b64encode(tenant.encode()).decode().rstrip('=')+'.'+secrets.token_urlsafe(40)
            expiry=now+timedelta(hours=8)
            db.put('auth_sessions',{'user_id':user_id,'token_hash':hashlib.sha256(token.encode()).hexdigest(),'expires_at':expiry,'revoked':False})
            db.audit('session_created',user_id)
            result={'access_token':token,'expires_at':expiry.isoformat(),'identity':principal(db,user_id)}
    if error: fail(*error)
    return result

def assignment(db,who,task_id,lock=False):
    task=require(db,'tasks',task_id,lock=lock)
    rows=db.list('work_assignments',task_id=task_id,user_id=who['user_id'],status='active')
    if not rows or task.get('owner_id')!=who['user_id']: fail('Assigned task not found',404)
    a=rows[0]
    if a['account_id']!=task['account_id']: fail('Assigned task not found',404)
    return task,a

def work_projection(db,who,task_id):
    from .domain import allowed_evidence, assess
    task,a=assignment(db,who,task_id)
    account=require(db,'accounts',a['account_id'])
    needs_review=assess(db,account)['state']!='qualified'
    allowed=set(a.get('allowed_fields',[]))
    customer={k:account[k] for k in ['name','province','website'] if k in allowed and k in account}
    if not needs_review and 'email' in allowed and a.get('contact_id'):
        c=require(db,'contacts',a['contact_id']); e=db.get('evidence',c.get('evidence_id',''))
        if c['account_id']==account['id'] and e and allowed_evidence(db,e,account,'outreach'):
            customer['email']=c['email']
    db.audit('assigned_record_read',task_id,'Minimum field projection')
    return {'id':task['id'],'kind':task.get('kind','follow_up'),'status':task['status'],'due_at':task.get('due_at'),
            'instructions':a.get('instructions',''),'customer':customer,'is_demo':account['is_demo'],'needs_review':needs_review,
            'notes':[{'id':n['id'],'text':n['text'],'created_at':n['created_at']} for n in db.list('work_notes',task_id=task_id,user_id=who['user_id'])]}
