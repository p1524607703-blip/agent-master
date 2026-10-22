from unittest.mock import Mock, patch

from app.services import report_data
from app.services.build_cache import RedisBuildCache


def test_catalog_keeps_exact_fact_counts_without_unused_spend_aggregation():
    rows = [{"account_id": "account", "account_name": "store", "min_date": "2026-09-01",
             "max_date": "2026-10-19", "rows": 7, "lineage_rows": 7}]
    constraints = [{"table_name": table.split('.',1)[1], "source_name_not_null": True}
                   for _,table,_ in report_data.REPORT_SPECS]
    with patch.object(report_data, "query_rows", side_effect=lambda sql: constraints if 'pg_catalog.pg_attribute' in sql else rows) as query:
        result = report_data._reports_uncached()
    assert len(result) == 6
    assert all(row["rows"] == 7 and row["status"] == "READY" for row in result)
    assert all(row["lineage"] == "完整（source_file_name 已回填）" for row in result)
    assert all("sum(spend)" not in call.args[0] for call in query.call_args_list)
    scans = [call.args[0] for call in query.call_args_list if 'WITH coverage' in call.args[0]]
    assert len(scans) == 6
    assert all('count(source_file_name)' not in sql for sql in scans)
    assert all('LEFT JOIN LATERAL' in sql and 'ORDER BY stat_date DESC LIMIT 1' in sql for sql in scans)


def test_nullable_source_names_retain_exact_lineage_count():
    row = {"account_id":"a","account_name":"store","min_date":"2026-09-01",
           "max_date":"2026-10-19","rows":7,"lineage_rows":6}
    with patch.object(report_data, 'query_rows', side_effect=lambda sql: [] if 'pg_catalog.pg_attribute' in sql else [row]) as query:
        result = report_data._reports_uncached()
    assert all(item['lineage'] == '缺失' and item['rows'] == 7 for item in result)
    scans = [call.args[0] for call in query.call_args_list if 'WITH coverage' in call.args[0]]
    assert all('count(source_file_name)' in sql for sql in scans)


def test_batch_revision_only_invalidates_and_never_replaces_fact_counts():
    shared = RedisBuildCache(enabled=True)
    shared._get_client = Mock(return_value=None)
    load = Mock(return_value=[{"rows": 7}])
    with patch.object(report_data, "build_cache", shared), \
         patch.object(report_data, "query_one", side_effect=[{"revision": 1}, {"revision": 1}, {"revision": 2}]), \
         patch.object(report_data, "_reports_uncached", load):
        assert report_data.reports() == [{"rows": 7}]
        assert report_data.reports() == [{"rows": 7}]
        assert report_data.reports() == [{"rows": 7}]
    assert load.call_count == 2
