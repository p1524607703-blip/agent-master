-- Explicit migration. Existing keys must enroll before their next model call.
BEGIN;
CREATE TABLE IF NOT EXISTS codex_ops.device_bindings (
    device_id UUID PRIMARY KEY REFERENCES codex_ops.devices(device_id),
    public_key TEXT UNIQUE,
    fingerprint CHAR(64),
    provider VARCHAR(40),
    generation INTEGER NOT NULL DEFAULT 1,
    approved_at TIMESTAMPTZ,
    approved_by BIGINT REFERENCES iam.users(user_id)
);
INSERT INTO codex_ops.device_bindings(device_id)
    SELECT device_id FROM codex_ops.devices ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS codex_ops.device_binding_claims (
    claim_id UUID PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES codex_ops.devices(device_id),
    public_key TEXT NOT NULL,
    fingerprint CHAR(64) NOT NULL,
    provider VARCHAR(40) NOT NULL,
    generation INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(device_id, generation, fingerprint)
);
CREATE TABLE IF NOT EXISTS codex_ops.device_proof_nonces (
    device_id UUID NOT NULL REFERENCES codex_ops.devices(device_id),
    nonce VARCHAR(64) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(device_id, nonce)
);
CREATE TABLE IF NOT EXISTS codex_ops.device_binding_audit (
    id BIGSERIAL PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES codex_ops.devices(device_id),
    action VARCHAR(24) NOT NULL,
    fingerprint CHAR(64),
    actor BIGINT REFERENCES iam.users(user_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS device_proof_expiry ON codex_ops.device_proof_nonces(expires_at);
DO $$ BEGIN
    IF EXISTS(SELECT 1 FROM pg_roles WHERE rolname='amazon_ads_admin') THEN
        GRANT SELECT,INSERT,UPDATE,DELETE ON codex_ops.device_bindings,codex_ops.device_binding_claims,
            codex_ops.device_proof_nonces,codex_ops.device_binding_audit TO amazon_ads_admin;
        GRANT USAGE,SELECT ON SEQUENCE codex_ops.device_binding_audit_id_seq TO amazon_ads_admin;
    END IF;
END $$;
COMMIT;
