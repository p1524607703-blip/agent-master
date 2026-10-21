-- CPO allocation accounting schema: REVIEW ONLY, do NOT run on production.
-- PostgreSQL 14+. Independent from core.*, app.*, ops_products.*.
BEGIN;
CREATE SCHEMA IF NOT EXISTS allocation_finance;

CREATE TABLE IF NOT EXISTS allocation_finance.source_snapshots (
    tenant_id text NOT NULL,
    snapshot_id uuid NOT NULL,
    report_period char(7) NOT NULL CHECK (report_period ~ '^[0-9]{4}-[0-9]{2}$'),
    report_timezone text NOT NULL,
    currency char(3) NOT NULL CHECK (currency = 'USD'),
    scope_sha256 char(64) NOT NULL,
    content_sha256 char(64) NOT NULL,
    frozen_payload jsonb NOT NULL,
    manifest jsonb NOT NULL,
    evidence_status text NOT NULL DEFAULT 'PENDING_REVIEW'
      CHECK (evidence_status IN ('PENDING_REVIEW','VERIFIED','REJECTED')),
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,snapshot_id),
    UNIQUE (tenant_id,content_sha256)
);

CREATE TABLE IF NOT EXISTS allocation_finance.rule_bundles (
    tenant_id text NOT NULL,
    bundle_id uuid NOT NULL,
    policy_version text NOT NULL,
    content_sha256 char(64) NOT NULL,
    frozen_rules jsonb NOT NULL,
    approval_state text NOT NULL DEFAULT 'DRAFT'
      CHECK (approval_state IN ('DRAFT','REVIEWED','APPROVED','REJECTED')),
    approved_by text,
    approved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,bundle_id),
    UNIQUE (tenant_id,content_sha256),
    CHECK ((approval_state = 'APPROVED' AND approved_by IS NOT NULL AND approved_at IS NOT NULL)
        OR approval_state <> 'APPROVED')
);

CREATE TABLE IF NOT EXISTS allocation_finance.mapping_versions (
    tenant_id text NOT NULL,
    mapping_version_id uuid NOT NULL,
    content_sha256 char(64) NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    frozen_mapping jsonb NOT NULL,
    approval_state text NOT NULL DEFAULT 'DRAFT'
      CHECK (approval_state IN ('DRAFT','APPROVED','REJECTED')),
    approved_by text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,mapping_version_id),
    UNIQUE (tenant_id,content_sha256),
    CHECK (effective_to IS NULL OR effective_to >= effective_from),
    CHECK (approval_state <> 'APPROVED' OR approved_by IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS allocation_finance.runs (
    tenant_id text NOT NULL,
    run_id uuid NOT NULL,
    report_period char(7) NOT NULL,
    scope_sha256 char(64) NOT NULL,
    source_snapshot_id uuid NOT NULL,
    rule_bundle_id uuid NOT NULL,
    mapping_version_id uuid NOT NULL,
    engine_version text NOT NULL,
    calculation_mode text NOT NULL CHECK (calculation_mode IN ('FULL','RULE_REVISION','REMAINDER_ONLY')),
    base_run_id uuid,
    input_sha256 char(64) NOT NULL,
    output_sha256 char(64),
    calculation_status text NOT NULL DEFAULT 'QUEUED'
      CHECK (calculation_status IN ('QUEUED','RUNNING','SUCCEEDED','PARTIAL','FAILED','CANCELLED')),
    review_status text NOT NULL DEFAULT 'DRAFT'
      CHECK (review_status IN ('DRAFT','IN_REVIEW','READY','LOCKED','REJECTED')),
    lock_revision integer NOT NULL DEFAULT 1 CHECK (lock_revision > 0),
    has_unresolved_evidence boolean NOT NULL DEFAULT true,
    created_by text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz,
    locked_at timestamptz,
    PRIMARY KEY (tenant_id,run_id),
    UNIQUE (tenant_id,report_period,scope_sha256,input_sha256),
    FOREIGN KEY (tenant_id,source_snapshot_id)
      REFERENCES allocation_finance.source_snapshots(tenant_id,snapshot_id),
    FOREIGN KEY (tenant_id,rule_bundle_id)
      REFERENCES allocation_finance.rule_bundles(tenant_id,bundle_id),
    FOREIGN KEY (tenant_id,mapping_version_id)
      REFERENCES allocation_finance.mapping_versions(tenant_id,mapping_version_id),
    FOREIGN KEY (tenant_id,base_run_id)
      REFERENCES allocation_finance.runs(tenant_id,run_id),
    CHECK (review_status NOT IN ('READY','LOCKED')
           OR (calculation_status='SUCCEEDED' AND has_unresolved_evidence=false
               AND output_sha256 IS NOT NULL)),
    CHECK (review_status <> 'LOCKED' OR locked_at IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS allocation_finance.campaign_balances (
    tenant_id text NOT NULL,
    run_id uuid NOT NULL,
    campaign_financial_key text NOT NULL,
    spend_minor bigint,
    transfer_minor bigint,
    creator_kept_minor bigint,
    direct_minor bigint,
    halo_minor bigint,
    protection_minor bigint,
    remainder_minor bigint,
    unallocated_minor bigint,
    is_complete boolean NOT NULL DEFAULT false,
    source_evidence jsonb NOT NULL DEFAULT '[]'::jsonb,
    PRIMARY KEY (tenant_id,run_id,campaign_financial_key),
    FOREIGN KEY (tenant_id,run_id) REFERENCES allocation_finance.runs(tenant_id,run_id),
    CHECK (NOT is_complete OR (
       spend_minor IS NOT NULL AND transfer_minor IS NOT NULL AND creator_kept_minor IS NOT NULL
       AND direct_minor IS NOT NULL AND halo_minor IS NOT NULL AND protection_minor IS NOT NULL
       AND remainder_minor IS NOT NULL AND unallocated_minor = 0
       AND spend_minor = transfer_minor + creator_kept_minor
       AND creator_kept_minor = direct_minor + halo_minor + protection_minor + remainder_minor)),
    CHECK (spend_minor IS NULL OR spend_minor >= 0),
    CHECK (transfer_minor IS NULL OR transfer_minor >= 0)
);

CREATE TABLE IF NOT EXISTS allocation_finance.product_allocations (
    tenant_id text NOT NULL,
    run_id uuid NOT NULL,
    financial_product_key text NOT NULL,
    operator_group text NOT NULL,
    self_minor bigint,
    halo_minor bigint,
    protection_minor bigint,
    remainder_minor bigint,
    final_minor bigint,
    evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (tenant_id,run_id,financial_product_key),
    FOREIGN KEY (tenant_id,run_id) REFERENCES allocation_finance.runs(tenant_id,run_id),
    CHECK (final_minor IS NULL OR
           (self_minor IS NOT NULL AND halo_minor IS NOT NULL
            AND protection_minor IS NOT NULL AND remainder_minor IS NOT NULL
            AND final_minor=self_minor+halo_minor+protection_minor+remainder_minor))
);

CREATE TABLE IF NOT EXISTS allocation_finance.evidence_issues (
    tenant_id text NOT NULL,
    issue_id uuid NOT NULL,
    run_id uuid NOT NULL,
    code text NOT NULL,
    affected_key text NOT NULL,
    status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RESOLVED','WAIVED')),
    evidence_uri text,
    evidence_sha256 char(64),
    reviewer text,
    reviewed_at timestamptz,
    PRIMARY KEY (tenant_id,issue_id),
    FOREIGN KEY (tenant_id,run_id) REFERENCES allocation_finance.runs(tenant_id,run_id),
    CHECK (status='OPEN' OR reviewer IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS allocation_finance.approval_events (
    tenant_id text NOT NULL,
    event_id uuid NOT NULL,
    run_id uuid NOT NULL,
    actor text NOT NULL,
    decision text NOT NULL CHECK (decision IN ('SUBMIT','APPROVE','REJECT','LOCK','ROLLBACK')),
    input_revision integer NOT NULL CHECK (input_revision > 0),
    evidence_sha256 char(64),
    event_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,event_id),
    FOREIGN KEY (tenant_id,run_id) REFERENCES allocation_finance.runs(tenant_id,run_id)
);

CREATE TABLE IF NOT EXISTS allocation_finance.publication_pointers (
    tenant_id text NOT NULL,
    report_period char(7) NOT NULL,
    scope_sha256 char(64) NOT NULL,
    published_run_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    published_by text NOT NULL,
    published_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,report_period,scope_sha256),
    FOREIGN KEY (tenant_id,published_run_id) REFERENCES allocation_finance.runs(tenant_id,run_id)
);

CREATE TABLE IF NOT EXISTS allocation_finance.idempotency_commands (
    tenant_id text NOT NULL,
    actor text NOT NULL,
    command text NOT NULL,
    idempotency_key text NOT NULL,
    request_sha256 char(64) NOT NULL,
    response_ref text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (tenant_id,actor,command,idempotency_key)
);

-- Explicit RLS fail-closed: no permissive policy is installed by this migration.
-- Role-specific policies and app.tenant_id handling require separate security review.
ALTER TABLE allocation_finance.source_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.rule_bundles ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.mapping_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.campaign_balances ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.product_allocations ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.evidence_issues ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.approval_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.publication_pointers ENABLE ROW LEVEL SECURITY;
ALTER TABLE allocation_finance.idempotency_commands ENABLE ROW LEVEL SECURITY;
COMMIT;
