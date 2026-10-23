-- Preserve administrator-issued credentials; hardware proof becomes opt-in.
-- No key material, usage or existing hardware binding is changed.
BEGIN;
CREATE TABLE IF NOT EXISTS codex_ops.device_access (
    device_id UUID PRIMARY KEY REFERENCES codex_ops.devices(device_id),
    auth_mode VARCHAR(16) NOT NULL DEFAULT 'api_key' CHECK (auth_mode IN ('api_key','hardware')),
    approved_at TIMESTAMPTZ,
    approved_by BIGINT REFERENCES iam.users(user_id),
    revision BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS codex_ops.device_access_audit (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES codex_ops.devices(device_id),
    action VARCHAR(32) NOT NULL,
    auth_mode VARCHAR(16) NOT NULL,
    actor BIGINT REFERENCES iam.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
WITH migrated AS (
    INSERT INTO codex_ops.device_access(device_id,approved_at)
    SELECT device_id,now() FROM codex_ops.devices ON CONFLICT DO NOTHING RETURNING device_id
)
INSERT INTO codex_ops.device_access_audit(device_id,action,auth_mode)
    SELECT device_id,'migrate_admin_issued_key','api_key' FROM migrated;
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='amazon_ads_admin') THEN
        GRANT SELECT,INSERT,UPDATE ON codex_ops.device_access,codex_ops.device_access_audit TO amazon_ads_admin;
        GRANT USAGE,SELECT ON SEQUENCE codex_ops.device_access_audit_id_seq TO amazon_ads_admin;
    END IF;
END $$;
COMMIT;
