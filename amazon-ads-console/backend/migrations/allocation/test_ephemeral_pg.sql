-- This file is ONLY executed by the local ephemeral PostgreSQL acceptance script.
\set ON_ERROR_STOP on
INSERT INTO allocation_finance.source_snapshots
(tenant_id,snapshot_id,report_period,report_timezone,currency,scope_sha256,content_sha256,
 frozen_payload,manifest,created_by) VALUES
('tenant-test','00000000-0000-0000-0000-000000000001','2026-09','America/Los_Angeles',
 'USD',repeat('a',64),repeat('b',64),'{}'::jsonb,'[]'::jsonb,'tester');
INSERT INTO allocation_finance.rule_bundles
(tenant_id,bundle_id,policy_version,content_sha256,frozen_rules)
VALUES ('tenant-test','00000000-0000-0000-0000-000000000002','sop-v2.3.1',repeat('c',64),'{}'::jsonb);
INSERT INTO allocation_finance.mapping_versions
(tenant_id,mapping_version_id,content_sha256,effective_from,frozen_mapping)
VALUES ('tenant-test','00000000-0000-0000-0000-000000000003',repeat('d',64),'2026-09-01','{}'::jsonb);
INSERT INTO allocation_finance.runs
(tenant_id,run_id,report_period,scope_sha256,source_snapshot_id,rule_bundle_id,
 mapping_version_id,engine_version,calculation_mode,input_sha256,output_sha256,
 calculation_status,review_status,has_unresolved_evidence,created_by)
VALUES ('tenant-test','00000000-0000-0000-0000-000000000004','2026-09',repeat('a',64),
 '00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-000000000002',
 '00000000-0000-0000-0000-000000000003','allocation-0.1.0','FULL',repeat('e',64),
 repeat('f',64),'SUCCEEDED','READY',false,'tester');
DO $$
DECLARE was_blocked boolean := false;
BEGIN
  BEGIN
    UPDATE allocation_finance.source_snapshots SET frozen_payload='{"changed":true}'::jsonb
    WHERE tenant_id='tenant-test';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE '%SOURCE_SNAPSHOT_IMMUTABLE%' THEN was_blocked := true; ELSE RAISE; END IF;
  END;
  IF NOT was_blocked THEN RAISE EXCEPTION 'snapshot immutability broken'; END IF;
  was_blocked := false;
  BEGIN
    UPDATE allocation_finance.runs SET review_status='LOCKED',locked_at=now()
      WHERE tenant_id='tenant-test';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE '%LOCK_SOURCE_RULE_MAPPING_UNAPPROVED%' THEN was_blocked := true; ELSE RAISE; END IF;
  END;
  IF NOT was_blocked THEN RAISE EXCEPTION 'unapproved lock was permitted'; END IF;
END $$;

UPDATE allocation_finance.source_snapshots SET evidence_status='VERIFIED' WHERE tenant_id='tenant-test';
UPDATE allocation_finance.rule_bundles SET approval_state='APPROVED',
  approved_by='auditor',approved_at=now() WHERE tenant_id='tenant-test';
UPDATE allocation_finance.mapping_versions SET approval_state='APPROVED',
  approved_by='auditor' WHERE tenant_id='tenant-test';
UPDATE allocation_finance.runs SET review_status='LOCKED',locked_at=now()
  WHERE tenant_id='tenant-test';
DO $$
DECLARE was_blocked boolean := false;
BEGIN
  BEGIN
    UPDATE allocation_finance.runs SET output_sha256=repeat('0',64) WHERE tenant_id='tenant-test';
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE '%LOCKED_RUN_IMMUTABLE%' THEN was_blocked := true; ELSE RAISE; END IF;
  END;
  IF NOT was_blocked THEN RAISE EXCEPTION 'locked run immutability broken'; END IF;
END $$;
SELECT allocation_finance.publish_locked_run('tenant-test','00000000-0000-0000-0000-000000000004',0,'auditor') AS revision_one;
DO $$
DECLARE was_blocked boolean := false;
BEGIN
  BEGIN
    PERFORM allocation_finance.publish_locked_run('tenant-test','00000000-0000-0000-0000-000000000004',0,'auditor');
  EXCEPTION WHEN OTHERS THEN
    IF SQLERRM LIKE '%PUBLICATION_CAS_CONFLICT%' THEN was_blocked := true; ELSE RAISE; END IF;
  END;
  IF NOT was_blocked THEN RAISE EXCEPTION 'CAS replay unexpectedly accepted'; END IF;
END $$;
SELECT allocation_finance.publish_locked_run('tenant-test','00000000-0000-0000-0000-000000000004',1,'auditor') AS revision_two;
-- Prove that a non-owner cannot read rows through fail-closed RLS.
CREATE ROLE allocation_operator;
GRANT USAGE ON SCHEMA allocation_finance TO allocation_operator;
GRANT SELECT ON allocation_finance.runs TO allocation_operator;
SET ROLE allocation_operator;
DO $$
DECLARE rows_seen bigint;
BEGIN
  SELECT count(*) INTO rows_seen FROM allocation_finance.runs;
  IF rows_seen <> 0 THEN RAISE EXCEPTION 'RLS LEAK: % runs visible', rows_seen; END IF;
END $$;
RESET ROLE;
