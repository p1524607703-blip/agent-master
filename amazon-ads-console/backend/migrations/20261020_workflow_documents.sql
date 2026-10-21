BEGIN;
CREATE TABLE IF NOT EXISTS app.cpo_workflow_documents (
    name text PRIMARY KEY CHECK (name IN ('allocation-console','mapping-proposals')),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision > 0),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
INSERT INTO app.cpo_workflow_documents(name,payload)
VALUES ('allocation-console','{"objects":{},"commands":{}}'),
       ('mapping-proposals','{"batches":{},"idempotency":{}}')
ON CONFLICT (name) DO NOTHING;
COMMIT;
