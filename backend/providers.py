"""Reviewed API boundaries; no scraper/actor install or marketing sender."""
from __future__ import annotations

import ipaddress
import os
import socket
from datetime import timedelta
from urllib.parse import urlsplit

import httpx

from .db import utcnow
from .domain import SETTINGS, fail

ORDERS = {
    'H01': ['licensed_business_directory', 'google_places_api', 'business_website', 'authorized_social_api'],
    'H02': ['licensed_business_directory', 'google_places_api', 'business_website', 'authorized_social_api'],
    'H03': ['licensed_business_directory', 'business_website', 'authorized_social_api'],
    'H04': ['government_registry', 'business_website', 'authorized_social_api'],
    'H05': ['google_places_api', 'business_website', 'authorized_social_api'],
    'H06': ['government_registry', 'google_places_api', 'authorized_social_api'],
    'H07': ['google_places_api', 'business_website', 'authorized_social_api'],
    'H08': ['government_registry', 'google_places_api', 'authorized_social_api'],
    'H09': ['inbound_forms', 'business_website', 'government_registry'], 'H10': [],
}
ENV = {'google_places_api': 'GOOGLE_PLACES_API_KEY', 'business_website': 'FIRECRAWL_API_KEY',
       'authorized_social_api': 'APIFY_API_TOKEN'}


def policy_ready(p, purpose):
    return bool(p and p['enabled'] and p.get('reviewed_by') and p.get('terms_url')
                and p.get('provenance_license') and purpose in p.get('purposes', [])
                and p.get('expires_at') and utcnow() < __import__('backend.domain', fromlist=['date']).date(p['expires_at'])
                and p.get('request_limit', 0) > 0 and p.get('requests_per_minute', 0) > 0)


def route(db, province, profile, purpose='discovery'):
    if province not in ['QC', 'ON'] or profile not in ORDERS:
        fail('Unsupported market/profile', 422)
    profiles = db.list('icp_profiles', code=profile)
    keywords = (profiles[0] if profiles else SETTINGS['profiles'][profile]).get('keywords', {})
    result = []
    for provider in ORDERS[profile]:
        policies = db.list('source_policies', provider=provider)
        p = policies[0] if policies else None
        ready = policy_ready(p, purpose)
        if provider in ENV and not os.environ.get(ENV[provider]):
            ready = False
        result.append({'provider': provider, 'available': ready, 'reason': None if ready else 'policy_or_credentials_missing',
                       'province': province, 'profile': profile, 'keywords': keywords.get(province, []),
                       'language': 'fr' if province == 'QC' else 'en', 'purpose': purpose})
    return {'routes': result, 'excluded_reason': 'H10 employees/apprentices excluded' if profile == 'H10' else None}


def public_target(url, allowed_urls):
    parsed = urlsplit(url)
    if (url not in allowed_urls or parsed.scheme != 'https' or not parsed.hostname
            or parsed.username or parsed.password or parsed.port not in [None, 443]):
        fail('Target URL is not explicitly authorized', 403)
    host = parsed.hostname
    if host == 'localhost' or host.endswith(('.local', '.internal', '.example')):
        fail('Private/reserved host blocked', 403)
    try:
        ips = [r[4][0] for r in socket.getaddrinfo(host, 443)]
        if not ips or any(not ipaddress.ip_address(ip).is_global for ip in ips):
            fail('Non-public target blocked', 403)
    except socket.gaierror:
        fail('Target DNS could not be verified', 403)
    return url


class Providers:
    def __init__(self, client=None):
        self.client = client or httpx.Client(timeout=httpx.Timeout(20, connect=5), follow_redirects=False)

    def close(self):
        self.client.close()

    def call(self, provider, p, item):
        if not policy_ready(p, item.get('purpose', 'discovery')):
            fail('Provider policy is not reviewed/enabled', 403)
        if provider in ENV and not os.environ.get(ENV[provider]):
            fail('Provider credential is missing', 403)
        if provider == 'google_places_api':
            r = self.client.post('https://places.googleapis.com/v1/places:searchText',
                headers={'X-Goog-Api-Key': os.environ[ENV[provider]], 'X-Goog-FieldMask': 'places.id'},
                json={'textQuery': item['query'], 'languageCode': item['language'], 'pageSize': 20})
            r.raise_for_status()
            # Never persist restricted Maps names/ratings/contact data to CRM.
            return {'discovery_place_ids': [x['id'] for x in r.json().get('places', [])], 'requires_independent_research': True}
        if provider == 'business_website':
            target = public_target(item['url'], p.get('allowed_urls', []))
            r = self.client.post('https://api.firecrawl.dev/v2/scrape',
                headers={'Authorization': 'Bearer ' + os.environ[ENV[provider]]},
                json={'url': target, 'formats': ['markdown'], 'onlyMainContent': True})
            r.raise_for_status()
            body = r.json()
            if body.get('success') is not True:
                raise ValueError('Firecrawl response was not successful')
            metadata = body.get('data', {}).get('metadata', {})
            final = metadata.get('sourceURL') or target
            public_target(final, p.get('allowed_urls', []))
            return {'source_url': final, 'raw_excerpt': body.get('data', {}).get('markdown', '')[:20000], 'verification': 'unverified'}
        if provider == 'authorized_social_api':
            dataset = item['dataset_id']
            if dataset not in p.get('allowed_dataset_ids', []) or not p.get('business_content_only'):
                fail('Dataset/Actor use has not been reviewed', 403)
            r = self.client.get(f'https://api.apify.com/v2/datasets/{dataset}/items',
                headers={'Authorization': 'Bearer ' + os.environ[ENV[provider]]}, params={'limit': 200, 'clean': 'true'})
            r.raise_for_status()
            rows = r.json()
            if not isinstance(rows, list) or any(x.get('is_business') is not True for x in rows):
                fail('Private or unclassified social records rejected', 403)
            return {'business_records': rows, 'verification': 'unverified'}
        if provider in ['licensed_business_directory', 'government_registry', 'inbound_forms']:
            if not item.get('authorized_records'):
                raise ValueError('Reviewed import required; no invented registry endpoint')
            return {'business_records': item['authorized_records'], 'verification': 'unverified'}
        raise ValueError('Unsupported provider')


def demo_candidate(province, profile, index=0):
    """Fictional fixtures only, reserved addresses and explicit DEMO provenance."""
    from .domain import SETTINGS
    kind = SETTINGS['profiles'][profile]['entity_type']
    weights = SETTINGS['scoring']['owner_operator' if kind in ['owner_operator', 'partner'] else 'business']
    facts = {'real_business': True, 'province': province, 'product_match': True, 'business_role': True,
             'autonomy': True, 'credential': True, **{k: 1 for k in weights}}
    facts.update(SETTINGS['profile_qualification'][profile])
    if index == 1:
        facts.pop('credential')
    if index == 2:
        facts['employee_only'] = True
    domain = f'demo-{province.lower()}-{profile.lower()}-{index}.example'
    return {'name': f'DEMO {province} {profile} HVAC {index + 1} (FICTIONAL)', 'province': province,
            'profile': profile, 'is_demo': True, 'website': 'https://' + domain, 'roles': ['Installer'],
            'facts': facts, 'email': 'business@' + domain, 'fixture_index': index}
