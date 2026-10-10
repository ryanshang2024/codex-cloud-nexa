"""Read-only acceptance evidence snapshot. Never infer grades from DEMO tests."""
from datetime import datetime, timezone
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import httpx

ROOT=Path(__file__).resolve().parents[1]


def main():
    tokens=json.loads((ROOT/'.local/tokens.json').read_text())
    with httpx.Client(base_url='http://127.0.0.1:8000',
            headers={'Authorization':'Bearer '+tokens['nexa-workspace']['admin']},timeout=20) as client:
        response=client.get('/api/dashboard');response.raise_for_status();data=response.json()
        health=client.get('/health');health.raise_for_status()
    suites=ET.parse(ROOT/'.local/pytest-results.xml').getroot()
    checks=[{k:s.attrib[k] for k in ['tests','failures','errors','skipped','timestamp']} for s in suites]
    browser=json.loads((ROOT/'.local/browser-results.json').read_text())['stats']
    real_accounts=[a for a in data['accounts'] if not a['is_demo']]
    categories=[('ICP 客户画像精准度',25),('多渠道获客及数据质量',20),('AI 研究与商机评分',15),
                ('触达与回复工作流',15),('工程质量与系统稳定性',15),('安全与合规',10)]
    report={'generated_at':datetime.now(timezone.utc).isoformat(),
        'score_status':'user_reported_baseline_unchanged_pending_independent_acceptance',
        'categories':[{'name':name,'maximum':maximum,'user_reported_score':0,'regraded_score':None} for name,maximum in categories],
        'user_reported_total':0,'regraded_total':None,
        'real_accounts':len(real_accounts),'independent_labelled_sample_count':None,
        'icp_precision':None,'data_accuracy':None,'ai_grounded_research_accuracy':None,
        'unmeasured_reason':'No independently reviewed real QC/ON acceptance dataset has been provided; DEMO and test fixtures cannot establish business accuracy.',
        'source_policies':[{'provider':p['provider'],'enabled':p['enabled'],
            'calls_reserved':p.get('requests_used',0)} for p in data['source_policies']],
        'development_checks':{'backend':checks,'browser':browser,'health':health.json()},
        'production_acceptance':'unrun'}
    target=ROOT/'docs/acceptance-evidence.json'
    target.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'report':str(target),'real_accounts':len(real_accounts),
        'regraded_total':None,'auto_send':health.json()['auto_send']},ensure_ascii=False))


if __name__=='__main__':
    main()
