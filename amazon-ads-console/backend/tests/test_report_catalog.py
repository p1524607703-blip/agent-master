import re
from unittest.mock import patch

import pytest

from app.services import report_coverage, report_data
from app.services.report_coverage_sql import TABLES, exact_coverage_sql, maintenance_sql


def snapshot(**changes):
    result = {"table_name": TABLES[0], "snapshot_version": 1,
              "source_revision_at_refresh": 7,"source_revision":7,
              "payload":[{"account_id":"a","account_name":"test-store","min_date":"2026-09-01",
                          "max_date":"2026-10-19","rows":3,"lineage_rows":3}],
              "snapshot_at":"2026-10-22T12:00:00Z","refresh_state":"READY",
              "refresh_started_at":"2026-10-22T11:59:00Z","refresh_finished_at":"2026-10-22T12:00:00Z"}
    return {**result, **changes}


def catalog(*rows):
    with patch.object(report_coverage, "query_one", return_value={"relation": "core.report_coverage_snapshots"}), \
         patch.object(report_coverage, "query_rows", return_value=list(rows)):
        return report_data.reports()


def test_http_only_reads_persisted_catalog_and_import_ledger():
    with patch.object(report_coverage, "query_one", return_value={"relation":"core.report_coverage_snapshots"}) as one, \
         patch.object(report_coverage, "query_rows", return_value=[snapshot()]) as many:
        result = report_data.reports()
    assert result[0]["rows"] == 3 and result[0]["status"] == "READY"
    sql = " ".join(call.args[0] for call in [*one.call_args_list,*many.call_args_list])
    assert not any(re.search(r"\b(?:FROM|JOIN)\s+"+re.escape(table)+r"\b",sql,re.I) for table in TABLES)
    assert "valid_row_count" not in sql
    assert len(many.call_args_list) == 1


def test_missing_migration_or_snapshot_is_unknown_never_fake_zero():
    with patch.object(report_coverage,"query_one",return_value={"relation":None}), \
         patch.object(report_coverage,"query_rows") as query:
        result = report_data.reports()
    query.assert_not_called()
    assert len(result) == 6
    assert all(row["rows"] is None and row["status"] == "PENDING" for row in result)
    assert all(row["rows"] is None for row in catalog())


@pytest.mark.parametrize("changes",[
    {"source_revision":8}, {"refresh_state":"REFRESHING"},
    {"refresh_state":"FAILED","error_code":"QUERY_TIMEOUT"},
    {"refresh_state":"REFRESHING","interrupted":True},
])
def test_changed_refreshing_failed_or_interrupted_snapshots_keep_old_counts_but_are_stale(changes):
    row = catalog(snapshot(**changes))[0]
    assert row["rows"] == 3 and row["status"] == "STALE"
    assert row["snapshot_at"] == "2026-10-22T12:00:00Z"
    if changes.get("interrupted"):
        assert row["refresh_state"] == "FAILED" and row["error_code"] == "REFRESH_INTERRUPTED"


def test_first_refresh_failure_and_unsupported_snapshot_version_are_not_ready():
    row=catalog(snapshot(payload=None,snapshot_at=None,refresh_state="FAILED"))[0]
    assert row["rows"] is None and row["status"] == "FAILED"
    row=catalog(snapshot(snapshot_version=999))[0]
    assert row["rows"] is None and row["status"] == "PENDING"


def test_proven_empty_snapshot_and_nullable_lineage_are_distinct_from_missing():
    row=catalog(snapshot(payload=[]))[0]
    assert row["rows"] == 0 and row["status"] == "READY"
    data=snapshot();data["payload"][0]["lineage_rows"]=2
    assert catalog(data)[0]["lineage"] == "缺失"


def test_database_failure_propagates_instead_of_successful_empty_catalog():
    with patch.object(report_coverage,"query_one",side_effect=RuntimeError("unavailable")):
        with pytest.raises(RuntimeError): report_data.reports()


def test_exact_maintenance_uses_fact_counts_with_verified_not_null_fast_path():
    sql=exact_coverage_sql(TABLES[0],True)
    assert "count(*)::bigint AS rows,count(*)::bigint AS lineage_rows" in sql
    assert "count(source_file_name)" not in sql and "sum(spend)" not in sql
    assert "count(source_file_name)" in exact_coverage_sql(TABLES[0],False)
    with pytest.raises(ValueError): exact_coverage_sql("core.unapproved",True)
    sql=maintenance_sql()
    assert "pg_try_advisory_lock" in sql and "REPEATABLE READ" in sql
    assert "max_parallel_workers_per_gather=0" in sql and "interval '900 seconds'" in sql
    assert "valid_row_count" not in sql
