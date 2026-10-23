-- Explicit application migration; never run by application startup or release.py.
-- personnel_roster is an existing view; iam and advertising tables are untouched.
BEGIN;
CREATE SCHEMA IF NOT EXISTS codex_ops;
CREATE TABLE IF NOT EXISTS codex_ops.devices (
    device_id UUID PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES iam.users(user_id),
    device_name VARCHAR(80) NOT NULL,
    platform VARCHAR(16) NOT NULL CHECK (platform IN ('windows','macos','linux')),
    key_hash CHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at TIMESTAMPTZ,
    last_heartbeat_at TIMESTAMPTZ,
    codex_running BOOLEAN NOT NULL DEFAULT false,
    client_version VARCHAR(64)
);
CREATE TABLE IF NOT EXISTS codex_ops.model_requests (
    request_id UUID PRIMARY KEY,
    device_id UUID NOT NULL REFERENCES codex_ops.devices(device_id),
    response_id VARCHAR(256) UNIQUE,
    finished_at TIMESTAMPTZ NOT NULL,
    http_status INTEGER NOT NULL,
    completed BOOLEAN NOT NULL,
    input_tokens BIGINT,
    output_tokens BIGINT,
    total_tokens BIGINT,
    cached_tokens BIGINT,
    reasoning_tokens BIGINT,
    CHECK ((input_tokens IS NULL AND output_tokens IS NULL AND total_tokens IS NULL)
        OR (input_tokens >= 0 AND output_tokens >= 0
            AND total_tokens = input_tokens + output_tokens)),
    CHECK (cached_tokens IS NULL OR cached_tokens BETWEEN 0 AND input_tokens),
    CHECK (reasoning_tokens IS NULL OR reasoning_tokens BETWEEN 0 AND output_tokens)
);
CREATE INDEX IF NOT EXISTS codex_requests_device_time
    ON codex_ops.model_requests(device_id,finished_at);
COMMIT;
