import copy
import json
import pytest

from app.services.allocation_sources import capture, TABLES, validate_scope
from app.services.allocation_coverage import build_coverage_manifest, check_review_receipt

SCOPE={"period":"2026-09","report_timezone":"America/Los_Angeles","currency":"USD","account_ids":["account-1","account-2"],"ad_products":["SP","SB"]}

def fake_capture():
    row={"account_id":"account-1","ad_product":"Sponsored Products","stat_date":"2026-09-01",
         "budget_currency":"USD","source_file_hash":"x","row_hash":"r1","batch_id":1,
         "purchases":2,"units":2,"spend":"1.20","manifest_file_hash":"x",
         "manifest_start_date":"2026-09-01","manifest_end_date":"2026-09-30"}
    payload={"database":"amazon_ads_v2","role":"ads_readonly","default_read_only":"on",
             "scope": validate_scope(SCOPE), "facts":{t:[dict(row)] for t in TABLES},
             "mappings":{"child":[],"parent":[]}}
    return capture(SCOPE,lambda _:json.dumps(payload))

def test_matrix_requires_all_explicit_account_type_table_cells():
    capture_data=fake_capture()
    manifest=build_coverage_manifest(SCOPE,capture_data)
    assert len(manifest["cells"])==len(TABLES)*2*2
    assert all(c["coverage_status"]=="PENDING_REVIEW" for c in manifest["cells"])
    assert all(c["negative_eligibility_proven"] is False for c in manifest["cells"])
    assert manifest["policy"]=="OBSERVATION_ONLY_NOT_A_SOURCE_COVERAGE_APPROVAL"
    assert sum(c["observed_rows"] for c in manifest["cells"])==len(TABLES)

def test_zero_rows_do_not_prove_no_advertising():
    manifest=build_coverage_manifest(SCOPE,fake_capture())
    assert any(i["code"]=="NO_ROWS_OBSERVED_NOT_NEGATIVE_PROOF" for i in manifest["issues"])

def test_capture_must_be_intact():
    data=fake_capture()
    data["facts"][TABLES[0]][0]["units"]=987
    with pytest.raises(ValueError,match="FINGERPRINT"):
        build_coverage_manifest(SCOPE,data)

def test_scope_cannot_be_silently_expanded():
    data=fake_capture()
    scope=dict(SCOPE,account_ids=["account-1"])
    with pytest.raises(ValueError,match="SCOPE"):
        build_coverage_manifest(scope,data)

def test_missing_import_manifest_fields_flagged():
    data=fake_capture()
    row=data["facts"][TABLES[1]][0]
    row.pop("manifest_file_hash")
    from app.services.allocation_store import digest
    data["content_hash"]=digest({k:v for k,v in data.items() if k!="content_hash"})
    manifest=build_coverage_manifest(SCOPE,data)
    assert any(i["code"]=="MISSING_BATCH_MANIFEST_FIELDS" for i in manifest["issues"])

def test_unsigned_coverage_receipt_is_never_accepted():
    with pytest.raises(ValueError,match="NOT_CONFIGURED"):
        check_review_receipt({},{"status":"APPROVED"})
