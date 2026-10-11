"""Server-owner provisioning; never run from Employee App or hand humans this credential."""
import argparse
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.db import config, transaction

def provision(tenant,enable):
    cfg=config(); actor=tenant+':automation'
    if tenant not in cfg['tenant_ids'] or not any(b['user_id']==actor and b.get('role')=='service' for b in cfg['auth_bindings']):
        raise RuntimeError('Unknown provisioned tenant service identity')
    with transaction(tenant,'server-owner') as db:
        user=db.get('users',actor)
        if not user or user['role']!='service': raise RuntimeError('Service identity missing; run reviewed setup first')
        for permission in ['n8n.webhook','research.start']:
            old=db.list('user_grants',user_id=actor,permission=permission)
            db.put('user_grants',{'id':old[0]['id'] if old else None,'user_id':actor,'permission':permission,'enabled':enable})
        db.audit('service_identity_configured',actor,'enabled' if enable else 'disabled')
    print('Independent service permissions updated; no credentials displayed.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('tenant');p.add_argument('state',choices=['enable','disable']);args=p.parse_args()
    provision(args.tenant,args.state=='enable')
