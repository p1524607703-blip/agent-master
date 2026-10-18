-- Application DB only (amazon_ads). Does not change CPO roles or advertising facts.
BEGIN;
CREATE TABLE IF NOT EXISTS codex_ops.devices (
    device_id uuid PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES codex_ops.personnel_memberships(user_id),
    device_name text NOT NULL CHECK (length(device_name) BETWEEN 1 AND 128),
    platform text NOT NULL DEFAULT '' CHECK (length(platform) <= 64),
    heartbeat_key_hash text NOT NULL UNIQUE,
    created_at timestamptz NOT NULL DEFAULT now(),
    revoked_at timestamptz,
    last_heartbeat_at timestamptz,
    agent_version text CHECK (length(agent_version) <= 64)
);
CREATE TABLE IF NOT EXISTS codex_ops.usage_events (
    device_id uuid NOT NULL REFERENCES codex_ops.devices(device_id),
    response_id text NOT NULL CHECK (length(response_id) BETWEEN 1 AND 256),
    model text NOT NULL CHECK (length(model) BETWEEN 1 AND 128),
    outcome text NOT NULL CHECK (outcome IN ('completed', 'failed', 'interrupted')),
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    input_tokens bigint CHECK (input_tokens >= 0),
    cached_input_tokens bigint CHECK (cached_input_tokens >= 0),
    output_tokens bigint CHECK (output_tokens >= 0),
    reasoning_tokens bigint CHECK (reasoning_tokens >= 0),
    PRIMARY KEY (device_id, response_id),
    CHECK ((input_tokens IS NULL) = (output_tokens IS NULL)),
    CHECK (cached_input_tokens IS NULL OR input_tokens IS NOT NULL AND cached_input_tokens <= input_tokens),
    CHECK (reasoning_tokens IS NULL OR output_tokens IS NOT NULL AND reasoning_tokens <= output_tokens)
);
CREATE INDEX IF NOT EXISTS codex_usage_occurred_idx ON codex_ops.usage_events(occurred_at);
COMMIT;
