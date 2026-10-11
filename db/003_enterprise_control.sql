-- V3.3: identity, assignments and authoritative cost reservations.
ALTER TABLE users DROP CONSTRAINT users_role_check;
UPDATE users SET role=CASE role WHEN 'admin' THEN 'super_admin' WHEN 'sales' THEN 'employee'
 WHEN 'researcher' THEN 'manager' WHEN 'compliance' THEN 'manager' ELSE role END;
ALTER TABLE users ADD CONSTRAINT users_role_check CHECK(role IN ('super_admin','manager','employee','service'));
CREATE TABLE auth_sessions(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id), user_id text NOT NULL,
 token_hash text NOT NULL, expires_at timestamptz NOT NULL, revoked boolean NOT NULL DEFAULT false,
 data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,token_hash),
 FOREIGN KEY(tenant_id,user_id) REFERENCES users(tenant_id,id));
CREATE TABLE user_grants(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id), user_id text NOT NULL,
 permission text NOT NULL, data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,user_id,permission), FOREIGN KEY(tenant_id,user_id) REFERENCES users(tenant_id,id));
ALTER TABLE tasks ADD COLUMN owner_id text;
ALTER TABLE tasks ADD FOREIGN KEY(tenant_id,owner_id) REFERENCES users(tenant_id,id);
CREATE INDEX tasks_owner ON tasks(tenant_id,owner_id,status);
CREATE TABLE work_assignments(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id), account_id text NOT NULL,
 task_id text NOT NULL, user_id text NOT NULL, contact_id text, status text NOT NULL CHECK(status IN ('active','revoked')),
 data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,task_id),
 FOREIGN KEY(tenant_id,account_id) REFERENCES accounts(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY(tenant_id,user_id) REFERENCES users(tenant_id,id), FOREIGN KEY(tenant_id,contact_id) REFERENCES contacts(tenant_id,id) ON DELETE CASCADE);
CREATE INDEX assignment_user ON work_assignments(tenant_id,user_id,status);
CREATE TABLE work_notes(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id), task_id text NOT NULL, user_id text NOT NULL,
 data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES tasks(tenant_id,id) ON DELETE CASCADE, FOREIGN KEY(tenant_id,user_id) REFERENCES users(tenant_id,id));
CREATE TABLE ai_policies(id text PRIMARY KEY, tenant_id text NOT NULL UNIQUE REFERENCES tenants(id), data jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id));
CREATE TABLE user_quotas(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id), user_id text NOT NULL,
 data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,user_id),
 FOREIGN KEY(tenant_id,user_id) REFERENCES users(tenant_id,id));
CREATE TABLE usage_ledger(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id), user_id text NOT NULL,
 idempotency_key text NOT NULL, state text NOT NULL CHECK(state IN ('reserved','settled','failed')), reserved_until timestamptz NOT NULL,
 data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), UNIQUE(tenant_id,idempotency_key),
 FOREIGN KEY(tenant_id,user_id) REFERENCES users(tenant_id,id));
CREATE INDEX ledger_time ON usage_ledger(tenant_id,created_at,user_id);
CREATE TABLE quota_requests(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id), user_id text NOT NULL,
 status text NOT NULL CHECK(status IN ('pending','approved','rejected')), data jsonb NOT NULL DEFAULT '{}',
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(tenant_id,id), FOREIGN KEY(tenant_id,user_id) REFERENCES users(tenant_id,id));
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['auth_sessions','user_grants','work_assignments','work_notes','ai_policies','user_quotas','usage_ledger','quota_requests'] LOOP
  EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY',t);
  EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY',t);
  EXECUTE format('CREATE POLICY tenant_scope ON %I USING (tenant_id = nullif(current_setting(''app.tenant_id'',true),'''')) WITH CHECK (tenant_id = nullif(current_setting(''app.tenant_id'',true),''''))',t);
 END LOOP;
END $$;
INSERT INTO schema_migrations(version) VALUES(3);
