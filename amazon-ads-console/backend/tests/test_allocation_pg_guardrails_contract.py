
from pathlib import Path

SQL2 = Path(__file__).resolve().parents[1] / "migrations" / "allocation" / "002_guardrails.sql"

def test_financial_guardrails_are_transactional_and_conservative():
    s=SQL2.read_text(encoding="utf8")
    assert s.startswith("-- Review-only")
    assert "BEGIN;" in s and "COMMIT;" in s
    for name in ("guard_snapshot_mutation","guard_frozen_rules","guard_frozen_mappings",
                 "guard_financial_run","guard_ledger_mutation","guard_audit_event","publish_locked_run"):
        assert name in s
    for prohibition in ("LOCKED_RUN_IMMUTABLE","SOURCE_SNAPSHOT_IMMUTABLE",
                        "APPROVED_RULES_IMMUTABLE","APPROVED_MAPPING_IMMUTABLE",
                        "READY_LEDGER_IMMUTABLE","AUDIT_EVENT_APPEND_ONLY","PUBLICATION_CAS_CONFLICT"):
        assert prohibition in s
    assert "SECURITY INVOKER" in s and "FROM PUBLIC" in s
    assert "DROP TABLE" not in s
    assert "DELETE FROM core." not in s
