from unittest.mock import Mock, patch

from app.services import report_data
from app.services.build_cache import RedisBuildCache


def test_catalog_keeps_exact_fact_counts_without_unused_spend_aggregation():
    rows = [{"account_id": "account", "account_name": "store", "min_date": "2026-09-01",
             "max_date": "2026-10-19", "rows": 7, "lineage_rows": 7}]
    with patch.object(report_data, "query_rows", return_value=rows) as query:
        result = report_data._reports_uncached()
    assert len(result) == 6
    assert all(row["rows"] == 7 and row["status"] == "READY" for row in result)
    assert all(row["lineage"] == "完整（source_file_name 已回填）" for row in result)
    assert all("sum(spend)" not in call.args[0] for call in query.call_args_list)
    assert all("count(source_file_name)" in call.args[0] for call in query.call_args_list)


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
