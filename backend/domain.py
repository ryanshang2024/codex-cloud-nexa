from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from fastapi import HTTPException

from .db import ROOT, utcnow

SETTINGS = json.load(open(ROOT + '/config/hvac-qc-on.json'))
FACTS = {'real_business', 'province', 'product_match', 'business_role', 'autonomy', 'contact',
         'product_fit', 'purchasing_authority', 'market_coverage', 'intent', 'business_verification',
         'partner_feasibility', 'credentials', 'service_area', 'business_autonomy',
         'installation_fit', 'capacity', 'public_project', 'recent_service', 'partner_application', 'expansion',
         'credential', 'company_inactive', 'employee_only', 'out_of_scope', 'reply', 'first_cooperation', 'contact_basis',
         'service_capabilities', 'market_segments', 'business_models'}
SIGNALS = {'public_project': 30, 'recent_service': 20, 'partner_application': 30, 'expansion': 20}
CAPABILITY_VALUES = {
    'service_capabilities': {'heat_pump_installation','heating','cooling','commercial_hvac','hvac_repair',
                             'hvac_replacement','mini_split_installation','subcontract_installation',
                             'automotive_air_conditioning','appliance_repair'},
    'market_segments': {'residential','commercial','industrial'},
    'business_models': {'company','multi_brand_dealer','independent_operator','installation_team','employee_only'},
}


def fail(message, code=409):
    raise HTTPException(code, message)


def require(db, table, identifier, lock=False):
    item = db.get(table, identifier, lock)
    if item is None:
        fail('Record not found', 404)
    return item


def date(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    return parsed.astimezone(timezone.utc) if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def usable(e, purpose='score', is_demo=False):
    return (e['verification'] == 'verified' and bool(e.get('reviewer_id'))
            and e['is_demo'] == is_demo and float(e['confidence']) >= .7
            and bool(e.get('provenance_license')) and str(e.get('provenance_license')).casefold() not in ['unknown','pending','unverified'] and purpose in e.get('permitted_purposes', [])
            and date(e['observed_at']) <= utcnow() and date(e['expires_at']) > utcnow()
            and bool(e.get('independent')))


def allowed_evidence(db,e,account,purpose):
    if not usable(e,purpose,account['is_demo']):
        return False
    if account['is_demo']:
        return True
    ps=db.list('source_policies',provider=e.get('source_provider',''))
    p=ps[0] if ps else None
    return bool(p and p['enabled'] and p.get('reviewed_by') and p.get('terms_url')
        and purpose in p.get('purposes',[]) and p.get('expires_at') and date(p['expires_at'])>utcnow()
        and p.get('provenance_license')==e.get('provenance_license'))


def evidence_map(db, account, purpose='score'):
    # Latest reviewed assertion wins; contradictory current evidence forces review.
    result, conflicts = {}, []
    for e in db.list('evidence', account_id=account['id']):
        if not allowed_evidence(db,e,account,purpose):
            continue
        key = e['fact_type']
        if key not in ['contact','reply','first_cooperation'] and key in result and result[key].get('value') != e.get('value'):
            conflicts.append(key)
        result[key] = e
    return result, sorted(set(conflicts))


def credential_supports(db, evidence, credential, account):
    if not (evidence and evidence['account_id']==account['id'] and evidence['fact_type']=='credential'
            and allowed_evidence(db,evidence,account,'score')):
        return False
    claim=evidence.get('value')
    if account['is_demo'] and claim is True:
        return True
    if not isinstance(claim,dict):
        return False
    required=['status','province','work_class']
    if credential['status']=='verified':
        required.append('authority')
    return all(credential.get(k) is not None and claim.get(k)==credential[k] for k in required)


def assess(db, account):
    ev, conflicts = evidence_map(db, account)
    get = lambda k: ev.get(k, {}).get('value')
    excluded, review = [], [f'conflicting_evidence:{x}' for x in conflicts]
    if account['profile'] == 'H10':
        excluded.append('employee_or_apprentice_profile')
    for k in ['company_inactive', 'employee_only', 'out_of_scope']:
        if get(k) is True:
            excluded.append(k)
    if db.list('suppressions', account_id=account['id']):
        excluded.append('do_not_contact')
    profile_checks={}
    for fact,required in SETTINGS['profile_qualification'][account['profile']].items():
        e=ev.get(fact)
        observed=e.get('value') if e else None
        valid=isinstance(observed,list) and all(isinstance(x,str) and x in CAPABILITY_VALUES[fact] for x in observed)
        matched=set(required)<=set(observed) if valid else None
        profile_checks[fact]={'required':required,'observed':observed,'matched':matched,
                              'evidence_id':e['id'] if e else None}
        if matched is None:
            review.append('unknown:'+fact)
        elif not matched:
            excluded.append('profile_mismatch:'+fact)
    for k in ['real_business', 'product_match', 'business_role']:
        if get(k) is False:
            excluded.append(k)
        elif get(k) is not True:
            review.append('unknown:' + k)
    if get('province') not in ['QC', 'ON']:
        review.append('unknown:province')
    elif get('province') != account['province']:
        excluded.append('province_mismatch')
    kind = SETTINGS['profiles'][account['profile']]['entity_type']
    if kind == 'business':
        authority=get('purchasing_authority')
        if not isinstance(authority,(int,float)) or not 0<float(authority)<=1:
            review.append('unknown:purchasing_authority')
    if kind in ['owner_operator', 'partner']:
        if get('autonomy') is False:
            excluded.append('not_independent')
        elif get('autonomy') is not True:
            review.append('unknown:autonomy')
    creds = db.list('credential_verifications', account_id=account['id'])
    credential = creds[-1] if creds else None
    if credential is None or credential['status'] == 'unknown':
        review.append('unknown:credential')
    elif credential['province'] != account['province']:
        excluded.append('credential_province_mismatch')
    elif credential['status'] == 'invalid':
        excluded.append('invalid_credential')
    else:
        credential_evidence=[db.get('evidence',x) for x in credential.get('evidence_ids',[])]
        if not credential.get('work_class') or not credential_evidence or not all(
            credential_supports(db,e,credential,account)
            for e in credential_evidence):
            review.append('unverified_credential_scope')
    weights = SETTINGS['scoring']['owner_operator' if kind in ['owner_operator', 'partner'] else 'business']
    breakdown = {}
    for k, w in weights.items():
        e = ev.get(k)
        v = e.get('value') if e else None
        factor = float(v) if isinstance(v, (int, float)) and 0 <= float(v) <= 1 else 0
        breakdown[k] = {'weight': w, 'points': round(w * factor), 'value': v, 'evidence_id': e['id'] if e else None}
    fit = sum(x['points'] for x in breakdown.values())
    signals = []
    for k, w in SIGNALS.items():
        e = ev.get(k)
        if e and e.get('value') is True and e.get('event_date'):
            event = date(e['event_date'])
            if utcnow() - timedelta(days=90) <= event <= utcnow():
                signals.append({'type': k, 'points': w, 'evidence_id': e['id'], 'event_date': e['event_date']})
    state = 'excluded' if excluded else 'review' if review or fit < 70 else 'qualified'
    output = {'fit': fit, 'intent': sum(x['points'] for x in signals), 'state': state,
            'tier': 'A' if fit >= 80 else 'B' if fit >= 70 else 'deferred',
            'breakdown': breakdown, 'signals': signals, 'exclusion_reasons': excluded,
            'manual_review': review, 'evidence_ids': [e['id'] for e in ev.values()],
            'profile_checks': profile_checks,
            'is_demo': account['is_demo'], 'model': kind, 'assessed_at': utcnow().isoformat()}
    old=db.list('leads',account_id=account['id'])
    ev_hash=hashlib.sha256(json.dumps(sorted((e['id'],e.get('value')) for e in ev.values()),default=str,sort_keys=True).encode()).hexdigest()
    output['evidence_hash']=ev_hash
    if old and old[0].get('override') and old[0].get('evidence_hash')==ev_hash and not excluded and not review:
        override=old[0]['override']
        for k,v in override['points'].items():
            output['breakdown'][k]['points']=v
        output['fit']=sum(x['points'] for x in output['breakdown'].values())
        output['state']='qualified' if output['fit']>=70 else 'review'
        output['tier']='A' if output['fit']>=80 else 'B' if output['fit']>=70 else 'deferred'
        output['override']=override
    return output


def score(db, account_id):
    account = require(db, 'accounts', account_id, lock=True)
    result = assess(db, account)
    existing = db.list('leads', account_id=account_id)
    lead = db.put('leads', {**result, 'id': existing[0]['id'] if existing else None, 'account_id': account_id})
    db.put('accounts', {**account, 'state': result['state']})
    db.audit('score', account_id)
    return lead


def entity_keys(value):
    keys = []
    if value.get('website'):
        url = urlsplit(value['website'])
        if url.scheme != 'https' or not url.hostname or url.username or url.password:
            fail('Website must be a public HTTPS URL', 422)
        host = url.hostname.lower().removeprefix('www.')
        keys.append(('domain', host))
    if value.get('registration_id'):
        keys.append(('registry', value['province'] + ':' + str(value['registration_id']).strip().upper()))
    if value.get('external_id') and value.get('external_id_storage_allowed') is True:
        keys.append(('external', value.get('source_provider', '') + ':' + value['external_id']))
    return keys


def ingest_account(db, value):
    keys = entity_keys(value)
    host=urlsplit(value.get('website') or '').hostname or ''
    reserved=host.endswith(('.example','.invalid','.test')) or host in ['example.com','example.org','example.net']
    if not value.get('is_demo') and reserved:
        fail('Reserved demo domains cannot be used as real accounts',422)
    if value.get('is_demo') and (not value['name'].startswith('DEMO') or (host and not reserved)):
        fail('DEMO accounts require a DEMO name and reserved domain',422)
    for kind, key in sorted(keys):
        db.conn.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (db.tenant_id + ':' + kind + ':' + key,))
    matches = {x['account_id'] for kind, key in keys for x in db.list('account_keys', kind=kind, value=key)}
    if len(matches) > 1:
        fail('Conflicting identities require manual entity resolution')
    if matches:
        account = require(db, 'accounts', next(iter(matches)), lock=True)
        if account['is_demo'] != value.get('is_demo', False) or account['province'] != value['province']:
            fail('Conflicting province or DEMO identity')
    else:
        account = db.put('accounts', {**value, 'state': 'review'})
        db.audit('account_discovered', account['id'])
    for kind, key in keys:
        if not db.list('account_keys', kind=kind, value=key):
            db.put('account_keys', {'account_id': account['id'], 'kind': kind, 'value': key})
        digest=hashlib.sha256((kind+':'+key).encode()).hexdigest()
        if db.list('suppression_keys',kind=kind,digest=digest):
            suppress(db,account['id'],'previous_business_identity_opt_out')
    return require(db,'accounts',account['id'])


def suppress(db, account_id, reason):
    require(db, 'accounts', account_id, lock=True)
    if not db.list('suppressions', account_id=account_id):
        db.put('suppressions', {'account_id': account_id, 'reason': reason, 'at': utcnow().isoformat()})
    for key in db.list('account_keys',account_id=account_id):
        digest=hashlib.sha256((key['kind']+':'+key['value']).encode()).hexdigest()
        if not db.list('suppression_keys',kind=key['kind'],digest=digest):
            db.put('suppression_keys',{'kind':key['kind'],'digest':digest,'purpose':'enforce_business_opt_out'})
    for draft in db.list('outreach_drafts', account_id=account_id):
        db.put('outreach_drafts', {**draft, 'status': 'blocked', 'approved_by': None})
    for consent in db.list('consent_records', account_id=account_id):
        db.put('consent_records', {**consent, 'status': 'revoked'})
    score(db, account_id)
    db.audit('do_not_contact', account_id, reason)


def invalidate_drafts(db, account_id):
    for d in db.list('outreach_drafts',account_id=account_id):
        if d['status'] not in ['blocked','rejected']:
            db.put('outreach_drafts',{**d,'status':'draft','approved_by':None,'approved_revision':None,
                'context_hash':None,'blocking_reasons':['research_context_changed']})


def contact_gate(db, account, contact, real=False):
    reasons = []
    if real and account['is_demo']:
        reasons.append('demo_never_contactable')
    result = assess(db, account)
    if result['state'] != 'qualified':
        reasons += result['exclusion_reasons'] + result['manual_review'] + ['account_not_qualified']
    if contact.get('account_id') != account['id']:
        reasons.append('contact_account_mismatch')
    ev = db.get('evidence', contact.get('evidence_id', ''))
    if not ev or ev['account_id'] != account['id'] or ev.get('fact_type') != 'contact' or ev.get('value') != contact.get('email') or not usable(ev, 'outreach', account['is_demo']):
        reasons.append('unverified_business_contact')
    if ev and not allowed_evidence(db,ev,account,'outreach'):
        reasons.append('contact_source_policy_not_valid')
    records = db.list('consent_records', account_id=account['id'], contact_id=contact['id'])
    approved = [r for r in records if r['status'] == 'approved' and r.get('reviewer_id')
                and r.get('basis') in ['express_consent', 'existing_relationship', 'conspicuous_business_publication']
                and r.get('business_relevance') and r.get('evidence_id') == contact.get('evidence_id')
                and r.get('expires_at') and date(r['expires_at']) > utcnow()]
    if not account['is_demo']:
        valid=[]
        for r in approved:
            basis=db.get('evidence',r.get('basis_evidence_id',''))
            if basis and basis['account_id']==account['id'] and basis['fact_type']=='contact_basis' and allowed_evidence(db,basis,account,'outreach'):
                valid.append(r)
        approved=valid
    if not approved:
        reasons.append('contact_basis_not_reviewed')
    if db.list('suppressions', account_id=account['id']):
        reasons.append('do_not_contact')
    stored = db.list('leads', account_id=account['id'])
    if stored and stored[0].get('override') and stored[0]['fit'] < 70:
        reasons.append('human_override_below_threshold')
    return sorted(set(reasons))


def fingerprint(db, account, contact):
    payload = {'account': account, 'contact': contact,
               'evidence': db.list('evidence', account_id=account['id']),
               'credentials': db.list('credential_verifications', account_id=account['id']),
               'consent': db.list('consent_records', account_id=account['id']),
               'suppression': db.list('suppressions', account_id=account['id'])}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def render_draft(account, language, facts):
    fact = facts.get('product_match')
    if not fact or fact.get('value') is not True:
        fail('No verified HVAC service evidence')
    prefix = '[DEMO — FICTIONAL / NON ENVOYABLE]\n' if account['is_demo'] else ''
    if language == 'fr':
        subject = 'Échange au sujet de votre activité CVAC'
        body = f'Bonjour,\nNous avons consulté votre information publique sur les services CVAC en {account["province"]}. Seriez-vous disponible pour discuter de vos critères de partenariat?\nMerci.\n[Identité de l’expéditeur et coordonnées à compléter]\nPour ne plus être contacté, veuillez nous le signaler.'
    else:
        subject = 'A conversation about your HVAC services'
        body = f'Hello,\nWe reviewed your public information about HVAC services in {account["province"]}. Would you be open to discussing your partnership criteria?\nThank you.\n[Sender identity and business address to be completed]\nPlease let us know if you do not want further contact.'
    return {'subject': subject, 'body': prefix + body, 'evidence_ids': [fact['id']],
            'sender_identity_complete': False, 'product_claims': None, 'purchase_signals': None,
            'contact_name': None, 'template_id': 'partnership_intro'}


def classify_reply(text):
    text = text.casefold()
    rules = [
        ('UNSUBSCRIBE', r'unsubscribe|remove me|do not contact|stop contacting|^\s*stop[.!]?\s*$|désabonn|désinscri|ne me contactez|retirez.moi|arrêtez|退订|拒绝联系'),
        ('PRICE_REQUEST', r'price|pricing|quote|prix|tarif|devis|报价|价格'),
        ('INSTALLER_APPLICATION', r'join|installer application|become.*partner|partenaire|inscription|入驻'),
        ('PROJECT_AVAILABLE', r'project|installation project|projet|chantier|项目'),
        ('TECHNICAL_QUESTION', r'specification|technical|warranty|capacity|technique|garantie|参数|技术'),
        ('NOT_NOW', r'not now|later|pas maintenant|plus tard|暂不|以后'),
    ]
    return next((c for c, pattern in rules if re.search(pattern, text)), 'OTHER')


def ingest_reply(db, account_id, external_id, text, evidence_id):
    account = require(db, 'accounts', account_id, lock=True)
    prior = db.list('interactions', external_id=external_id)
    if prior:
        if prior[0]['account_id'] != account_id:
            fail('External reply identity conflict')
        return prior[0]
    ev = require(db, 'evidence', evidence_id)
    if ev['account_id'] != account_id or ev.get('value') != text or not usable(ev, 'reply', account['is_demo']):
        fail('Reply requires reviewed inbound evidence')
    category = classify_reply(text)
    interaction = db.put('interactions', {'account_id': account_id, 'external_id': external_id,
                                         'category': category, 'text': text, 'evidence_id': evidence_id,
                                         'classification': 'rules_v1', 'requires_human': True})
    if category == 'UNSUBSCRIBE':
        suppress(db, account_id, 'inbound_unsubscribe')
    else:
        db.put('tasks', {'account_id': account_id, 'status': 'open', 'kind': category,
                        'owner': None, 'requires_human': True, 'interaction_id': interaction['id'],
                        'instructions': 'Human review required; no price, technical, warranty or contract commitments.'})
        if category in ['PRICE_REQUEST', 'PROJECT_AVAILABLE', 'INSTALLER_APPLICATION']:
            stage = {'PRICE_REQUEST': 'rfq', 'PROJECT_AVAILABLE': 'new', 'INSTALLER_APPLICATION': 'partner_review'}[category]
            db.put('opportunities', {'account_id': account_id, 'stage': stage, 'owner': None, 'interaction_id': interaction['id']})
        if category == 'PROJECT_AVAILABLE':
            db.put('projects', {'account_id': account_id, 'state': 'unverified', 'interaction_id': interaction['id']})
        if category == 'INSTALLER_APPLICATION' and not db.list('partners', account_id=account_id):
            db.put('partners', {'account_id': account_id, 'state': 'application', 'interaction_id': interaction['id']})
    db.audit('reply_classified:' + category, account_id)
    return interaction
