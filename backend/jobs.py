from __future__ import annotations

import hashlib
import json
import time
from datetime import timedelta

from fastapi import HTTPException

from .db import record, transaction, utcnow
from .domain import date, fail, ingest_account, require, score
from .providers import Providers, demo_candidate, policy_ready, route


def create_job(db, value):
    # Pydantic defaults may retain integer 1 while an explicit budget is float 1.0.
    # Normalize the typed request so equivalent retry bodies share a fingerprint.
    value={**value,'cost_budget':float(value['cost_budget'])}
    db.conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (db.tenant_id + ':job:' + value['idempotency_key'],))
    old = db.list('search_jobs', idempotency_key=value['idempotency_key'])
    request_hash=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    if old:
        existing=old[0]
        previous_hash=existing.get('request_hash')
        if previous_hash is None:
            # Compatibility with jobs created before request hashes were recorded.
            previous={k:existing.get(k) for k in value if k!='items'}
            previous['items']=[] if existing['mode']=='demo' else [i['payload'] for i in
                sorted(db.list('job_items',job_id=existing['id']),key=lambda i:i['ordinal'])]
            previous['cost_budget']=float(previous['cost_budget'])
            previous_hash=hashlib.sha256(json.dumps(previous,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        if previous_hash!=request_hash:
            fail('Idempotency key already belongs to a different search request')
        return old[0]
    items = value.get('items', [])
    if value['mode'] == 'demo':
        tenant = db.conn.execute('SELECT is_demo FROM tenants WHERE id=%s', (db.tenant_id,)).fetchone()
        if not tenant or not tenant['is_demo']:
            fail('DEMO jobs require a DEMO tenant')
        items = [{'candidate': demo_candidate(value['province'], value['profile'], i)} for i in range(3)]
    if not items or len(items) > min(200, value['max_results']):
        fail('Job requires 1–200 items within max_results', 422)
    data = {**value, 'request_hash':request_hash, 'items': None, 'status': 'queued', 'cursor': 0, 'calls_used': 0,
            'lease_until': None, 'next_attempt_at': None, 'results_count': 0}
    job = db.put('search_jobs', data)
    for i, item in enumerate(items):
        db.put('job_items', {'job_id': job['id'], 'ordinal': i, 'status': 'pending', 'payload': item, 'tries': 0})
    db.audit('job_created', job['id'])
    return job


def store_demo(db, candidate):
    account = ingest_account(db, {k: v for k, v in candidate.items() if k not in ['facts', 'email', 'fixture_index']})
    evidence = {}
    for k, v in candidate['facts'].items():
        e = db.put('evidence', {'account_id': account['id'], 'source_url': candidate['website'] + '/demo/' + k,
            'observed_at': utcnow(), 'confidence': .95, 'verification': 'verified', 'is_demo': True,
            'fact_type': k, 'value': v, 'expires_at': (utcnow() + timedelta(days=30)).isoformat(),
            'raw_excerpt': 'DEMO fixture assertion; not a real company or licence.', 'provenance_license': 'DEMO_ONLY',
            'permitted_purposes': ['score', 'outreach', 'export'], 'source_provider': 'demo',
            'independent': True, 'reviewer_id': 'DEMO_FIXTURE_REVIEWER', 'signal_type': None, 'event_date': None})
        evidence[k] = e['id']
    ce = db.put('evidence', {'account_id': account['id'], 'source_url': candidate['website'] + '/demo/contact',
        'observed_at': utcnow(), 'confidence': .95, 'verification': 'verified', 'is_demo': True,
        'fact_type': 'contact', 'value': candidate['email'], 'expires_at': (utcnow() + timedelta(days=30)).isoformat(),
        'raw_excerpt': 'DEMO business email; cannot receive real messages.', 'provenance_license': 'DEMO_ONLY',
        'permitted_purposes': ['score', 'outreach', 'export'], 'source_provider': 'demo',
        'independent': True, 'reviewer_id': 'DEMO_FIXTURE_REVIEWER', 'signal_type': None, 'event_date': None})
    contacts = db.list('contacts', account_id=account['id'])
    if not contacts:
        db.put('contacts', {'account_id': account['id'], 'email': candidate['email'], 'name': None,
                            'evidence_id': ce['id'], 'is_business': True, 'is_demo': True})
    if not db.list('credential_verifications', account_id=account['id']):
        db.put('credential_verifications', {'account_id': account['id'], 'province': account['province'],
            'status': 'verified' if 'credential' in evidence else 'unknown', 'work_class': 'DEMO_HVAC',
            'authority': 'DEMO_AUTHORITY', 'evidence_ids': [evidence['credential']] if 'credential' in evidence else [],
            'reviewer_id': 'DEMO_FIXTURE_REVIEWER', 'is_demo': True})
    score(db, account['id'])
    return account['id']


def process_one(tenant_id, job_id=None, providers=None):
    # Lock only long enough to claim work. Provider calls run outside database locks.
    with transaction(tenant_id, 'worker') as db:
        query = '''SELECT * FROM search_jobs WHERE tenant_id=%s
            AND status IN ('queued','running') AND (lease_until IS NULL OR lease_until<now())
            AND (next_attempt_at IS NULL OR next_attempt_at<=now())'''
        args = [tenant_id]
        if job_id:
            query += ' AND id=%s'; args.append(job_id)
        row = db.conn.execute(query + ' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1', args).fetchone()
        if not row:
            return None
        job = record(row)
        items = sorted([i for i in db.list('job_items', job_id=job['id']) if i['status'] == 'pending'], key=lambda x: x['ordinal'])
        if not items:
            db.put('search_jobs', {**job, 'status': 'completed', 'lease_until': None})
            return {'status': 'completed', 'id': job['id']}
        item = items[0]
        lease = utcnow() + timedelta(seconds=120)
        job = db.put('search_jobs', {**job, 'status': 'running', 'lease_until': lease})
    result, attempts, error = None, [], None
    payload = item['payload']
    used = 0
    if job['mode'] == 'demo':
        result = {'demo': payload['candidate']}
    else:
        available = route_for_job(tenant_id, job, payload)
        own = providers is None
        client = providers or Providers()
        try:
            for p in available:
                # Persist budget before side effect; lost response still consumes a call.
                with transaction(tenant_id, 'worker') as db:
                    current = require(db, 'search_jobs', job['id'], lock=True)
                    policy = require(db, 'source_policies', p['id'], lock=True)
                    if current['status'] == 'paused':
                        return {'id': job['id'], 'status': 'paused'}
                    if not policy_ready(policy,payload.get('purpose','discovery')):
                        attempts.append((p['provider'],'policy_revoked','policy_no_longer_authorized',0))
                        error='no_authorized_source'; continue
                    cost=policy.get('cost_per_call',0)
                    if current['calls_used'] >= current['call_budget'] or current.get('cost_used', 0) + cost > current['cost_budget']:
                        error = 'budget_exhausted'; break
                    if policy.get('requests_used', 0) >= policy['request_limit']:
                        attempts.append((p['provider'], 'quota_exhausted', 'policy_request_limit', 0)); continue
                    if policy.get('next_call_at') and date(policy['next_call_at']) > utcnow():
                        error = 'rate_limited'; continue
                    db.put('search_jobs', {**current, 'calls_used': current['calls_used'] + 1,
                        'cost_used': current.get('cost_used', 0) + cost})
                    db.put('source_policies', {**policy, 'requests_used': policy.get('requests_used', 0) + 1,
                        'next_call_at': (utcnow() + timedelta(seconds=60/policy['requests_per_minute'])).isoformat()})
                used += 1
                try:
                    result = client.call(p['provider'], policy, payload)
                    attempts.append((p['provider'], 'success', None, cost))
                    break
                except Exception as exc:
                    code = exc.status_code if isinstance(exc, HTTPException) else None
                    if hasattr(exc, 'response') and exc.response is not None:
                        code = exc.response.status_code
                    attempts.append((p['provider'], 'failed', f'provider_error:{code or type(exc).__name__}', cost))
                    error = 'provider_failed'
        finally:
            if own:
                client.close()
        if not available:
            error = 'no_authorized_source'
    with transaction(tenant_id, 'worker') as db:
        current = require(db, 'search_jobs', job['id'], lock=True)
        # A recovered worker owns a different lease: stale responses cannot overwrite it.
        if current['lease_until'] != lease:
            return {'id': job['id'], 'status': current['status'], 'stale_lease': True}
        for provider, status, reason, cost in attempts:
            db.put('source_attempts', {'job_id': job['id'], 'provider': provider, 'status': status, 'error': reason, 'cost': cost})
        tries = item.get('tries', 0) + (0 if error == 'rate_limited' else 1)
        if result is not None:
            if 'demo' in result:
                account_id = store_demo(db, result['demo'])
                result = {'account_id': account_id, 'is_demo': True}
            # Live provider outputs remain unverified; do not manufacture accounts or facts.
            if job['mode']=='live' and result.get('business_records'):
                result=import_records(db,{**job,'remaining_results':job['max_results']-current.get('results_count',0)},result,attempts[-1][0],payload)
            elif job['mode']=='live' and result.get('raw_excerpt') and payload.get('account_id'):
                account=require(db,'accounts',payload['account_id'])
                policy=db.list('source_policies',provider=attempts[-1][0])[0]
                evidence=db.put('evidence',{'account_id':account['id'],'source_url':result['source_url'],
                    'observed_at':utcnow(),'confidence':0,'verification':'unverified','is_demo':False,
                    'fact_type':'product_match','value':None,'expires_at':(utcnow()+timedelta(days=30)).isoformat(),
                    'raw_excerpt':result['raw_excerpt'],'provenance_license':policy['provenance_license'],
                    'permitted_purposes':[x for x in policy['purposes'] if x in ['score','outreach','export']],
                    'source_provider':policy['provider'],'independent':True,'reviewer_id':None,'event_date':None,'signal_type':None})
                result={'evidence_id':evidence['id'],'verification':'unverified','requires_manual_review':True}
            db.put('job_items', {**item, 'status': 'done', 'tries': tries, 'result': result})
            count=1 if job['mode']=='demo' else len(result.get('account_ids',result.get('discovery_place_ids',[])))
            current.update(cursor=item['ordinal'] + 1, results_count=min(job['max_results'],current.get('results_count', 0) + count),
                           next_attempt_at=None, lease_until=None)
        else:
            final = tries >= 3 or error in ['no_authorized_source', 'budget_exhausted']
            db.put('job_items', {**item, 'status': 'failed' if final else 'pending', 'tries': tries, 'error': error})
            current.update(lease_until=None, next_attempt_at=None if final else utcnow() + timedelta(seconds=60 if error=='rate_limited' else min(60, 2 ** tries)))
            if error == 'budget_exhausted':
                current['status'] = 'budget_exhausted'
        pending = [i for i in db.list('job_items', job_id=job['id']) if i['status'] == 'pending']
        if not pending and current['status'] != 'paused':
            failures = [i for i in db.list('job_items', job_id=job['id']) if i['status'] == 'failed']
            current['status'] = 'failed' if failures else 'completed'
        db.put('search_jobs', current)
        db.audit('job_checkpoint', job['id'], error)
        return {'id': job['id'], 'status': current['status'], 'cursor': current['cursor']}


def route_for_job(tenant, job, payload):
    with transaction(tenant) as db:
        routes = route(db, job['province'], job['profile'], payload.get('purpose', 'discovery'))['routes']
        ps = {p['provider']: p for p in db.list('source_policies')}
        return [ps[r['provider']] for r in routes if r['available']]


def import_records(db,job,result,provider,payload):
    """Provider records become pending research, never trusted customer facts."""
    from .schemas import AccountInput
    from .domain import FACTS
    policy=db.list('source_policies',provider=provider)[0]
    ids=[]
    rejected=[]
    for row in result['business_records'][:job.get('remaining_results',job['max_results'])]:
        try:
            # A provider must use this canonical contract; arbitrary Actor fields are not CRM data.
            value=AccountInput.model_validate(row['account']).model_dump()
            if value['is_demo'] or value['province']!=job['province'] or value['profile']!=job['profile']:
                raise ValueError('market/profile/demo mismatch')
            source=row['source_url']
            if not source.startswith('https://') or not row.get('raw_excerpt'):
                raise ValueError('missing provenance')
            facts=row.get('facts',[])
            if any(not isinstance(f,dict) or f.get('fact_type') not in FACTS for f in facts):
                raise ValueError('unsupported fact')
            a=ingest_account(db,value)
            ids.append(a['id'])
            for fact in facts:
                db.put('evidence',{'account_id':a['id'],'source_url':source,'observed_at':utcnow(),
                    'confidence':0,'verification':'unverified','is_demo':False,'fact_type':fact['fact_type'],
                    'value':fact.get('value'),'expires_at':(utcnow()+timedelta(days=30)).isoformat(),
                    'raw_excerpt':row['raw_excerpt'][:20000],'provenance_license':policy['provenance_license'],
                    'permitted_purposes':[x for x in policy['purposes'] if x in ['score','outreach','export']],
                    'source_provider':provider,'independent':True,'reviewer_id':None,
                    'signal_type':fact.get('signal_type'),'event_date':fact.get('event_date')})
            score(db,a['id'])
        except (KeyError,ValueError,HTTPException) as exc:
            rejected.append({'reason':type(exc).__name__,'requires_manual_review':True})
    return {'account_ids':ids,'verification':'unverified','requires_manual_review':True,'rejected_records':rejected}


def worker_loop():
    from .db import config
    while True:
        worked = False
        for tenant in config()['tenant_ids']:
            worked |= process_one(tenant) is not None
        if not worked:
            time.sleep(1)


if __name__ == '__main__':
    worker_loop()
