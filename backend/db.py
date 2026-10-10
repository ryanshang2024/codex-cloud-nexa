from __future__ import annotations

import os
import json
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = os.path.dirname(os.path.dirname(__file__))
COLUMNS = {
    'users': ['role'], 'industry_templates': [], 'icp_profiles': ['code'],
    'source_policies': ['provider', 'enabled'],
    'accounts': ['name', 'province', 'profile', 'is_demo', 'state'],
    'account_keys': ['account_id', 'kind', 'value'], 'contacts': ['account_id'],
    'partners': ['account_id', 'state'], 'projects': ['account_id', 'state'],
    'project_participants': ['project_id', 'account_id'],
    'leads': ['account_id', 'fit', 'intent', 'state'],
    'evidence': ['account_id', 'source_url', 'observed_at', 'confidence', 'verification', 'is_demo'],
    'credential_verifications': ['account_id', 'province', 'status'],
    'search_jobs': ['status', 'idempotency_key', 'cursor', 'calls_used', 'lease_until', 'next_attempt_at'],
    'job_items': ['job_id', 'ordinal', 'status'], 'source_attempts': ['job_id', 'provider', 'status'],
    'consent_records': ['account_id', 'contact_id', 'status'],
    'outreach_drafts': ['account_id', 'contact_id', 'status', 'revision', 'language'],
    'interactions': ['account_id', 'external_id', 'category'],
    'opportunities': ['account_id', 'stage'], 'tasks': ['account_id', 'status'],
    'suppressions': ['account_id'], 'audit_events': [], 'webhook_events': ['external_id'],
    'suppression_keys': ['kind','digest'],
}


def utcnow():
    return datetime.now(timezone.utc)


def uid():
    return str(uuid4())


def config():
    import json
    path = os.environ.get('NEXA_RUNTIME_FILE', ROOT + '/.local/runtime.json')
    return json.loads(open(path).read())


def record(row):
    if row is None:
        return None
    return {**row.get('data', {}), **{k: v for k, v in row.items() if k != 'data'}}


class Store:
    def __init__(self, conn, tenant_id, actor='system'):
        self.conn, self.tenant_id, self.actor = conn, tenant_id, actor

    def get(self, table, identifier, lock=False):
        self._table(table)
        q = sql.SQL('SELECT * FROM {} WHERE tenant_id=%s AND id=%s' + (' FOR UPDATE' if lock else ''))
        return record(self.conn.execute(q.format(sql.Identifier(table)), (self.tenant_id, identifier)).fetchone())

    def list(self, table, **filters):
        self._table(table)
        clauses = [sql.SQL('tenant_id=%s')]
        params = [self.tenant_id]
        for k, v in filters.items():
            if k not in COLUMNS[table] + ['id']:
                raise ValueError('Unsupported filter')
            clauses.append(sql.SQL('{}=%s').format(sql.Identifier(k)))
            params.append(v)
        q = sql.SQL('SELECT * FROM {} WHERE {} ORDER BY created_at,id').format(sql.Identifier(table), sql.SQL(' AND ').join(clauses))
        return [record(x) for x in self.conn.execute(q, params).fetchall()]

    def put(self, table, value):
        self._table(table)
        value = dict(value)
        identifier = value.get('id') or uid()
        columns = [c for c in COLUMNS[table] if c in value]
        body = {k: v for k, v in value.items() if k not in COLUMNS[table] + ['id', 'tenant_id', 'created_at']}
        names = ['id', 'tenant_id'] + columns + ['data']
        params = [identifier, self.tenant_id] + [value[c] for c in columns] + [Jsonb(body, dumps=lambda x: json.dumps(x, default=str))]
        updates = sql.SQL(',').join(sql.SQL('{}=excluded.{}').format(sql.Identifier(c), sql.Identifier(c)) for c in columns + ['data'])
        if table == 'audit_events':
            q = sql.SQL('INSERT INTO {} ({}) VALUES ({}) RETURNING *').format(
                sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, names)),
                sql.SQL(',').join(sql.Placeholder() for _ in names))
            return record(self.conn.execute(q, params).fetchone())
        q = sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT(id) DO UPDATE SET {} WHERE {}.tenant_id=excluded.tenant_id RETURNING *').format(
            sql.Identifier(table), sql.SQL(',').join(map(sql.Identifier, names)),
            sql.SQL(',').join(sql.Placeholder() for _ in names), updates, sql.Identifier(table))
        return record(self.conn.execute(q, params).fetchone())

    def audit(self, action, target, reason=None):
        return self.put('audit_events', {'actor': self.actor, 'action': action, 'target': target, 'reason': reason})

    @staticmethod
    def _table(table):
        if table not in COLUMNS:
            raise ValueError('Unsupported table')


@contextmanager
def transaction(tenant_id, actor='system', url=None):
    with psycopg.connect(url or os.environ.get('DATABASE_URL') or config()['database_url'], row_factory=dict_row) as conn:
        conn.execute("SELECT set_config('app.tenant_id',%s,true)", (tenant_id,))
        yield Store(conn, tenant_id, actor)
