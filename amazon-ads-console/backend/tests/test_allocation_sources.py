import copy
import json
from decimal import Decimal

import pytest

from app.services.allocation_sources import TABLES, capture, save_capture, snapshot_query


SCOPE = {"period": "2026-09", "report_timezone": "America/Los_Angeles", "currency": "USD", "account_ids": ["0001"], "ad_products": ["SP"]}


def raw():
    row = {"account_id": "0001", "ad_product": "Sponsored Products", "stat_date": "2026-09-30", "budget_currency": "USD",
           "row_hash": "hash1", "source_file_hash": "hash2", "batch_id": 1, "units": 12, "purchases": 10, "spend": "12.3400"}
    return {"database": "amazon_ads_v2", "role": "ads_readonly", "default_read_only": "on", "scope": SCOPE,
            "facts": {t: [dict(row)] for t in TABLES}, "mappings": {"child": [], "parent": []}}


def test_exact_frozen_rows_and_pending_coverage(tmp_path):
    result = capture(SCOPE, lambda sql: json.dumps(raw()))
    assert result["manifest"][0]["spend_sum"] == "12.3400"
    assert result["manifest"][0]["purchases_sum"] == "10"
    assert all(m["coverage_status"] == "PENDING_VERIFICATION" for m in result["manifest"])
    assert result["capabilities"]["formal_publication"] is False
    first = save_capture(result, tmp_path)
    assert first == save_capture(result, tmp_path)
    result["facts"][TABLES[0]][0]["units"] = 999
    with pytest.raises(ValueError, match="HASH_MISMATCH"):
        save_capture(result, tmp_path)


def test_query_reuses_formal_filters_and_never_uses_name_for_ad_type():
    sql = snapshot_query(SCOPE)
    assert "excluded_from_cpo" in sql and "quarantined" in sql and "import_status = 'success'" in sql
    assert "Sponsored Products" in sql and "r.account_id IN ('0001')" in sql
    assert "INTERVAL '1 month'" in sql and "pg_current_snapshot()" in sql
    assert "INSERT" not in sql and "UPDATE" not in sql


@pytest.mark.parametrize("field,value,code", [("role", "amazon_ads_admin", "READONLY"), ("default_read_only", "off", "READONLY")])
def test_readonly_role_and_session_must_be_verified(field, value, code):
    data = raw()
    data[field] = value
    with pytest.raises(ValueError, match=code):
        capture(SCOPE, lambda _: json.dumps(data))


@pytest.mark.parametrize("field,value", [("account_id", "other"), ("stat_date", "2026-10-01"), ("budget_currency", "EUR"), ("row_hash", None)])
def test_source_scope_currency_and_lineage_are_required(field, value):
    data = raw()
    data["facts"][TABLES[0]][0][field] = value
    with pytest.raises(ValueError):
        capture(SCOPE, lambda _: json.dumps(data))


def test_source_decimal_is_not_binary_float():
    text = json.dumps(raw()).replace('"12.3400"', '12.340000000000000001')
    result = capture(SCOPE, lambda _: text)
    assert result["manifest"][0]["spend_sum"] == "12.340000000000000001"


def test_unknown_or_implicit_scope_is_rejected():
    with pytest.raises(ValueError):
        snapshot_query({})
    with pytest.raises(ValueError):
        snapshot_query(dict(SCOPE, ad_products=["DSP"]))
    with pytest.raises(ValueError):
        snapshot_query(dict(SCOPE, account_ids=[]))

def test_quality_finds_duplicate_campaign_grain_and_row_hash():
    from app.services.allocation_sources import audit_snapshot_quality
    data=raw()
    data["facts"][TABLES[0]][0]["campaign_id"]="campaign-1"
    data["facts"][TABLES[0]].append(dict(data["facts"][TABLES[0]][0]))
    audit=audit_snapshot_quality(data)
    codes={i["code"] for i in audit["issues"]}
    assert "DUPLICATE_CAMPAIGN_DAY" in codes and "DUPLICATE_SOURCE_ROW" in codes
    assert audit["financial_approved"] is False

def test_quality_separates_missing_purchases_from_zero():
    from app.services.allocation_sources import audit_snapshot_quality
    data=raw()
    data["facts"][TABLES[0]][0]["purchases"]=None
    assert "MISSING_PURCHASES" in {x["code"] for x in audit_snapshot_quality(data)["issues"]}
    data["facts"][TABLES[0]][0]["purchases"]=0
    assert "MISSING_PURCHASES" not in {x["code"] for x in audit_snapshot_quality(data)["issues"]}

def test_quality_detects_batch_target_and_original_file_mismatch():
    from app.services.allocation_sources import audit_snapshot_quality
    data=raw()
    row=data["facts"][TABLES[0]][0]
    row["manifest_target_table"]="core.report_purchased_product_daily"
    row["manifest_file_hash"]="different"
    codes={x["code"] for x in audit_snapshot_quality(data)["issues"]}
    assert "BATCH_TARGET_TABLE_MISMATCH" in codes
    assert "BATCH_FILE_HASH_MISMATCH" in codes

def test_quality_rejects_nan_negative_or_float_cost():
    from app.services.allocation_sources import audit_snapshot_quality
    for value in ("NaN","-1",1.2):
        data=raw()
        data["facts"][TABLES[0]][0]["spend"]=value
        assert "SPEND_NOT_EXACT" in {x["code"] for x in audit_snapshot_quality(data)["issues"]}

def test_capture_flags_unverified_financial_readiness_without_guessing():
    result=capture(SCOPE,lambda _:json.dumps(raw()))
    assert result["quality_audit"]["financial_approved"] is False
    assert result["capabilities"]["formal_publication"] is False

def test_sql_freezes_batch_target_table():
    assert "manifest_target_table" in snapshot_query(SCOPE)
