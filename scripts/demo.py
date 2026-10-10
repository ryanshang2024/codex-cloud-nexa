"""Repeatable internal HTTP demo; no provider calls, no marketing sends."""
import json
from pathlib import Path
import time
from datetime import datetime,timedelta,timezone

import httpx

ROOT=Path(__file__).resolve().parents[1]
tokens=json.loads((ROOT/'.local/tokens.json').read_text())
client=httpx.Client(base_url='http://127.0.0.1:8000',headers={'Authorization':'Bearer '+tokens['nexa-demo']['admin']},timeout=20)


def request(method,path,value=None):
    r=client.request(method,'/api/'+path,json=value)
    r.raise_for_status()
    return r.json()


def demo():
    report={'mode':'DEMO','real_provider_calls':0,'messages_sent':0,'steps':[]}
    for province,profile in [('QC','H01'),('ON','H06')]:
        job=request('POST','jobs',{'province':province,'profile':profile,'mode':'demo','idempotency_key':'documented-demo-'+province+'-'+profile})
        for _ in range(30):
            info=request('GET','jobs/'+job['id'])
            if info['job']['status']=='completed':break
            if info['job']['status']=='failed':raise RuntimeError('DEMO job failed')
            time.sleep(.2)
        else:raise RuntimeError('DEMO worker did not finish')
        snapshot=request('GET','dashboard')
        account=next(a for a in snapshot['accounts'] if a['province']==province and a['profile']==profile and a['name'].endswith('1 (FICTIONAL)'))
        d=request('GET','accounts/'+account['id'])
        if d['assessment']['state']!='qualified':raise RuntimeError('DEMO account has been suppressed or changed; use another DEMO tenant')
        c=d['contacts'][0]
        if not any(x['status']=='approved' for x in d['consent_records']):
            consent=request('POST','accounts/'+account['id']+'/consents',{'contact_id':c['id'],'basis':'express_consent',
                'evidence_id':c['evidence_id'],'business_relevance':'DEMO ONLY voluntary HVAC partnership enquiry, not real consent.',
                'expires_at':(datetime.now(timezone.utc)+timedelta(days=30)).isoformat()})
            request('POST','consents/'+consent['id']+'/review',{'approved':True,'reason':'Documented DEMO simulation of a human compliance review.'})
        drafts=[x for x in d['outreach_drafts'] if x['language']==('fr' if province=='QC' else 'en')]
        draft=drafts[-1] if drafts else request('POST','accounts/'+account['id']+'/drafts',{'contact_id':c['id']})
        request('POST','drafts/'+draft['id']+'/approve',{'approved':True,'revision':draft['revision'],
            'reason':'Documented DEMO simulation of human review, approval scope is draft only.'})
        r=client.post('/api/drafts/'+draft['id']+'/send')
        assert r.status_code==423
        external='documented-demo-reply-'+province
        if not any(x['external_id']==external for x in d['interactions']):
            now=datetime.now(timezone.utc)
            text='Pourriez-vous envoyer vos prix?' if province=='QC' else 'We have an installation project.'
            e=request('POST','accounts/'+account['id']+'/evidence',{'source_url':account['website']+'/demo/reply',
                'observed_at':now.isoformat(),'expires_at':(now+timedelta(days=30)).isoformat(),'confidence':1,
                'fact_type':'reply','value':text,'raw_excerpt':'DEMO fictional inbound response.',
                'provenance_license':'DEMO_ONLY','permitted_purposes':['reply'],'source_provider':'demo','independent':True})
            request('POST','evidence/'+e['id']+'/review',{'approved':True,'reason':'DEMO simulated inbound reply checked by demo operator.'})
            reply=request('POST','accounts/'+account['id']+'/replies',{'external_id':external,'text':text,'evidence_id':e['id']})
        else:reply=next(x for x in d['interactions'] if x['external_id']==external)
        final=request('GET','accounts/'+account['id'])
        report['steps'].append({'province':province,'profile':profile,'fit':final['assessment']['fit'],
            'language':draft['language'],'reply_category':reply['category'],'tasks':len(final['tasks']),
            'opportunities':len(final['opportunities']),'send_status':423,'evidence_count':len(final['evidence'])})
    exported=request('GET','export')
    assert all(x['is_demo'] for x in exported['records'])
    report['exported_demo_accounts']=len(exported['records'])
    (ROOT/'.local/demo-results.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    try:demo()
    finally:client.close()
