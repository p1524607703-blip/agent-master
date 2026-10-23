from pathlib import Path

SQL=Path(__file__).resolve().parents[1]/"migrations"/"allocation"/"001_schema.sql"

def test_migration_is_isolated_and_explicit():
    text=SQL.read_text(encoding="utf-8")
    assert "CREATE SCHEMA IF NOT EXISTS allocation_finance" in text
    assert "BEGIN;" in text and "COMMIT;" in text
    assert "DROP TABLE" not in text and "TRUNCATE" not in text
    assert "UPDATE core." not in text and "DELETE FROM core." not in text
    for t in ("source_snapshots","rule_bundles","mapping_versions","runs",
              "campaign_balances","product_allocations","evidence_issues",
              "approval_events","publication_pointers","idempotency_commands"):
        assert "allocation_finance."+t in text
        assert "ALTER TABLE allocation_finance."+t+" ENABLE ROW LEVEL SECURITY" in text

def test_conservation_and_idempotency_contracts_present():
    text=SQL.read_text()
    for fragment in ("spend_minor = transfer_minor + creator_kept_minor",
                     "creator_kept_minor = direct_minor + halo_minor + protection_minor + remainder_minor",
                     "PRIMARY KEY (tenant_id,actor,command,idempotency_key)",
                     "final_minor=self_minor+halo_minor+protection_minor+remainder_minor"):
        assert fragment in text
