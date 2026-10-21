-- Review-only hardening migration; never execute against production without approval.
-- Immutable input snapshots and locked ledger rows, fail-closed publishing.
BEGIN;
CREATE OR REPLACE FUNCTION allocation_finance.guard_snapshot_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'SOURCE_SNAPSHOT_IMMUTABLE'; END IF;
  IF ROW(NEW.tenant_id, NEW.snapshot_id, NEW.report_period, NEW.report_timezone,
         NEW.currency, NEW.scope_sha256, NEW.content_sha256, NEW.frozen_payload,
         NEW.manifest, NEW.created_by, NEW.created_at)
     IS DISTINCT FROM
     ROW(OLD.tenant_id, OLD.snapshot_id, OLD.report_period, OLD.report_timezone,
         OLD.currency, OLD.scope_sha256, OLD.content_sha256, OLD.frozen_payload,
         OLD.manifest, OLD.created_by, OLD.created_at)
  THEN RAISE EXCEPTION 'SOURCE_SNAPSHOT_IMMUTABLE'; END IF;
  IF OLD.evidence_status <> 'PENDING_REVIEW'
     AND NEW.evidence_status IS DISTINCT FROM OLD.evidence_status
  THEN RAISE EXCEPTION 'SOURCE_REVIEW_FINAL'; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS allocation_snapshot_guard ON allocation_finance.source_snapshots;
CREATE TRIGGER allocation_snapshot_guard BEFORE UPDATE OR DELETE
ON allocation_finance.source_snapshots FOR EACH ROW EXECUTE FUNCTION allocation_finance.guard_snapshot_mutation();

CREATE OR REPLACE FUNCTION allocation_finance.guard_frozen_rules() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'RULE_BUNDLE_IMMUTABLE'; END IF;
  IF ROW(NEW.tenant_id,NEW.bundle_id,NEW.policy_version,NEW.content_sha256,NEW.frozen_rules)
     IS DISTINCT FROM ROW(OLD.tenant_id,OLD.bundle_id,OLD.policy_version,OLD.content_sha256,OLD.frozen_rules)
  THEN RAISE EXCEPTION 'RULE_BUNDLE_IMMUTABLE'; END IF;
  IF OLD.approval_state = 'APPROVED' AND NEW IS DISTINCT FROM OLD
  THEN RAISE EXCEPTION 'APPROVED_RULES_IMMUTABLE'; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS allocation_rule_guard ON allocation_finance.rule_bundles;
CREATE TRIGGER allocation_rule_guard BEFORE UPDATE OR DELETE
ON allocation_finance.rule_bundles FOR EACH ROW EXECUTE FUNCTION allocation_finance.guard_frozen_rules();

CREATE OR REPLACE FUNCTION allocation_finance.guard_frozen_mappings() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'MAPPING_VERSION_IMMUTABLE'; END IF;
  IF ROW(NEW.tenant_id,NEW.mapping_version_id,NEW.content_sha256,
         NEW.effective_from,NEW.effective_to,NEW.frozen_mapping)
     IS DISTINCT FROM ROW(OLD.tenant_id,OLD.mapping_version_id,OLD.content_sha256,
                          OLD.effective_from,OLD.effective_to,OLD.frozen_mapping)
  THEN RAISE EXCEPTION 'MAPPING_VERSION_IMMUTABLE'; END IF;
  IF OLD.approval_state = 'APPROVED' AND NEW IS DISTINCT FROM OLD
  THEN RAISE EXCEPTION 'APPROVED_MAPPING_IMMUTABLE'; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS allocation_mapping_guard ON allocation_finance.mapping_versions;
CREATE TRIGGER allocation_mapping_guard BEFORE UPDATE OR DELETE
ON allocation_finance.mapping_versions FOR EACH ROW EXECUTE FUNCTION allocation_finance.guard_frozen_mappings();

CREATE OR REPLACE FUNCTION allocation_finance.guard_financial_run() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE approvals_ok boolean;
BEGIN
  IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'RUN_APPEND_ONLY'; END IF;
  IF OLD.review_status = 'LOCKED' THEN RAISE EXCEPTION 'LOCKED_RUN_IMMUTABLE'; END IF;
  IF ROW(NEW.tenant_id,NEW.run_id,NEW.report_period,NEW.scope_sha256,
         NEW.source_snapshot_id,NEW.rule_bundle_id,NEW.mapping_version_id,
         NEW.engine_version,NEW.calculation_mode,NEW.base_run_id,NEW.input_sha256,NEW.created_by)
     IS DISTINCT FROM
     ROW(OLD.tenant_id,OLD.run_id,OLD.report_period,OLD.scope_sha256,
         OLD.source_snapshot_id,OLD.rule_bundle_id,OLD.mapping_version_id,
         OLD.engine_version,OLD.calculation_mode,OLD.base_run_id,OLD.input_sha256,OLD.created_by)
  THEN RAISE EXCEPTION 'RUN_INPUTS_IMMUTABLE'; END IF;
  IF OLD.output_sha256 IS NOT NULL AND NEW.output_sha256 IS DISTINCT FROM OLD.output_sha256
  THEN RAISE EXCEPTION 'RUN_OUTPUT_IMMUTABLE'; END IF;
  IF NEW.review_status = 'LOCKED' AND OLD.review_status <> 'LOCKED' THEN
    IF OLD.review_status <> 'READY' OR NEW.calculation_status <> 'SUCCEEDED'
       OR NEW.output_sha256 IS NULL OR NEW.has_unresolved_evidence
    THEN RAISE EXCEPTION 'LOCK_PREREQUISITES_NOT_MET'; END IF;
    SELECT (s.evidence_status = 'VERIFIED' AND b.approval_state = 'APPROVED'
            AND m.approval_state = 'APPROVED')
      INTO approvals_ok
      FROM allocation_finance.source_snapshots s
      JOIN allocation_finance.rule_bundles b ON b.tenant_id=NEW.tenant_id AND b.bundle_id=NEW.rule_bundle_id
      JOIN allocation_finance.mapping_versions m ON m.tenant_id=NEW.tenant_id AND m.mapping_version_id=NEW.mapping_version_id
      WHERE s.tenant_id=NEW.tenant_id AND s.snapshot_id=NEW.source_snapshot_id;
    IF NOT COALESCE(approvals_ok,false)
    THEN RAISE EXCEPTION 'LOCK_SOURCE_RULE_MAPPING_UNAPPROVED'; END IF;
  END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS allocation_run_guard ON allocation_finance.runs;
CREATE TRIGGER allocation_run_guard BEFORE UPDATE OR DELETE
ON allocation_finance.runs FOR EACH ROW EXECUTE FUNCTION allocation_finance.guard_financial_run();

CREATE OR REPLACE FUNCTION allocation_finance.guard_ledger_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE current_status text;
DECLARE target_run uuid;
DECLARE target_tenant text;
BEGIN
  IF TG_OP = 'DELETE' THEN
    target_run=OLD.run_id; target_tenant=OLD.tenant_id;
  ELSE
    target_run=COALESCE(OLD.run_id,NEW.run_id);
    target_tenant=COALESCE(OLD.tenant_id,NEW.tenant_id);
    IF TG_OP='UPDATE' AND ROW(OLD.tenant_id,OLD.run_id) IS DISTINCT FROM ROW(NEW.tenant_id,NEW.run_id)
    THEN RAISE EXCEPTION 'LEDGER_IDENTITY_IMMUTABLE'; END IF;
  END IF;
  SELECT review_status INTO current_status FROM allocation_finance.runs
  WHERE tenant_id=target_tenant AND run_id=target_run;
  IF current_status IN ('READY','LOCKED') OR current_status IS NULL
  THEN RAISE EXCEPTION 'READY_LEDGER_IMMUTABLE'; END IF;
  IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
  RETURN NEW;
END $$;
DROP TRIGGER IF EXISTS allocation_campaign_guard ON allocation_finance.campaign_balances;
CREATE TRIGGER allocation_campaign_guard BEFORE UPDATE OR DELETE
ON allocation_finance.campaign_balances FOR EACH ROW EXECUTE FUNCTION allocation_finance.guard_ledger_mutation();
DROP TRIGGER IF EXISTS allocation_product_guard ON allocation_finance.product_allocations;
CREATE TRIGGER allocation_product_guard BEFORE UPDATE OR DELETE
ON allocation_finance.product_allocations FOR EACH ROW EXECUTE FUNCTION allocation_finance.guard_ledger_mutation();

CREATE OR REPLACE FUNCTION allocation_finance.guard_audit_event() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'AUDIT_EVENT_APPEND_ONLY';
END $$;
DROP TRIGGER IF EXISTS allocation_approval_append_only ON allocation_finance.approval_events;
CREATE TRIGGER allocation_approval_append_only BEFORE UPDATE OR DELETE
ON allocation_finance.approval_events FOR EACH ROW EXECUTE FUNCTION allocation_finance.guard_audit_event();

CREATE OR REPLACE FUNCTION allocation_finance.publish_locked_run(
  p_tenant text, p_run uuid, p_expected_revision integer, p_actor text
) RETURNS integer
LANGUAGE plpgsql SECURITY INVOKER AS $$
DECLARE found_run allocation_finance.runs%ROWTYPE;
DECLARE new_revision integer;
BEGIN
  IF p_tenant IS NULL OR p_actor IS NULL OR p_actor=''
     OR p_expected_revision IS NULL OR p_expected_revision < 0
  THEN RAISE EXCEPTION 'PUBLISH_ARGUMENTS_INVALID'; END IF;
  SELECT * INTO found_run
    FROM allocation_finance.runs
    WHERE tenant_id=p_tenant AND run_id=p_run AND review_status='LOCKED'
      AND calculation_status='SUCCEEDED' AND NOT has_unresolved_evidence
      AND output_sha256 IS NOT NULL;
  IF NOT FOUND THEN RAISE EXCEPTION 'PUBLISH_REQUIRES_LOCKED_VERIFIED_RUN'; END IF;
  INSERT INTO allocation_finance.publication_pointers
      (tenant_id,report_period,scope_sha256,published_run_id,revision,published_by)
  VALUES (p_tenant,found_run.report_period,found_run.scope_sha256,
          p_run,1,p_actor)
  ON CONFLICT (tenant_id,report_period,scope_sha256)
  DO UPDATE SET published_run_id=EXCLUDED.published_run_id,
                revision=allocation_finance.publication_pointers.revision+1,
                published_by=EXCLUDED.published_by, published_at=now()
  WHERE allocation_finance.publication_pointers.revision = p_expected_revision
  RETURNING revision INTO new_revision;
  IF new_revision IS NULL OR (p_expected_revision=0 AND new_revision<>1)
  THEN RAISE EXCEPTION 'PUBLICATION_CAS_CONFLICT'; END IF;
  RETURN new_revision;
END $$;
-- The routine is SECURITY INVOKER; no production execution privilege granted here.
REVOKE ALL ON FUNCTION allocation_finance.publish_locked_run(text,uuid,integer,text) FROM PUBLIC;
COMMIT;
