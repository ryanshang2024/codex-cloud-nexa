-- Keep minimal one-way business identity hashes after personal/research deletion.
CREATE TABLE suppression_keys(id text PRIMARY KEY, tenant_id text NOT NULL REFERENCES tenants(id),
 kind text NOT NULL CHECK(kind IN ('domain','registry','external')), digest text NOT NULL CHECK(length(digest)=64),
 data jsonb NOT NULL DEFAULT '{}', created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,kind,digest));
ALTER TABLE suppression_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE suppression_keys FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_scope ON suppression_keys USING(tenant_id = nullif(current_setting('app.tenant_id',true),''))
 WITH CHECK(tenant_id = nullif(current_setting('app.tenant_id',true),''));
INSERT INTO schema_migrations(version) VALUES(2);
