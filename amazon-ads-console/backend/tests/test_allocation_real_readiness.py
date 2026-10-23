import json
import pytest
from app.services.allocation_real_readiness import audit_import_inventory,AllocationReadinessError,sept2026_scope
from app.services.allocation_sources import TABLES,capture,validate_scope
from app.services.allocation_store import digest

S={"period":"2026-09","report_timezone":"America/Los_Angeles","currency":"USD",
   "account_ids":["acct1"],"ad_products":["SP"]}

def sample():
    row={"account_id":"acct1","ad_product":"Sponsored Products","stat_date":"2026-09-15",
         "campaign_id":"CAMPAIGN1","budget_currency":"USD","row_hash":"h1",
         "batch_id":12,"source_file_hash":"file12","manifest_file_hash":"file12",
         "purchases":2,"units":3,"spend":"11.00"}
    p={"database":"amazon_ads_v2","role":"ads_readonly","default_read_only":"on",
       "scope":validate_scope(S),"facts":{t:[dict(row,row_hash=t)] for t in TABLES},
       "mappings":{"child":[],"parent":[]}}
    return capture(S,lambda _:json.dumps(p))

def plan():
    return [{"source_table":t,"account_id":"acct1","ad_product":"SP",
             "report_start":"2026-09-01","report_end":"2026-09-30",
             "source_file_hash":"file12","request_id":"request-"+str(i)}
            for i,t in enumerate(TABLES)]


def test_all_three_reports_observed_remain_pending_finance():
    r=audit_import_inventory(sample(),plan())
    assert len(r["matrix"])==3
    assert all(x["observed_rows"]==1 for x in r["requests"])
    assert not r["real_data_verified"] and not r["publication_allowed"]


def test_no_expected_request_is_explicit_gap():
    r=audit_import_inventory(sample(),[])
    assert sum(i["code"]=="NO_EXPECTED_REPORT_REQUEST_DEFINED" for i in r["issues"])==3


def test_missing_report_does_not_claim_negative_eligibility():
    p=plan();p[0]["source_file_hash"]="not-there"
    r=audit_import_inventory(sample(),p)
    assert any(i["code"]=="REPORT_REQUEST_NOT_OBSERVED" for i in r["issues"])
    assert not r["negative_eligibility_proven"]
    assert r["requests"][0]["coverage_approved"] is False


def test_duplicate_request_id_blocks():
    p=plan();p.append(dict(p[0]))
    with pytest.raises(AllocationReadinessError,match="DUPLICATE_REPORT_REQUEST"):
        audit_import_inventory(sample(),p)


def test_tampered_capture_blocks():
    c=sample();c["facts"][TABLES[0]][0]["spend"]="900.00"
    with pytest.raises(AllocationReadinessError,match="CAPTURE_HASH_MISMATCH"):
        audit_import_inventory(c,plan())


def test_out_of_month_request_blocks():
    p=plan();p[0]["report_start"]="2026-08-31"
    with pytest.raises(AllocationReadinessError,match="REPORT_RANGE_OUTSIDE_MONTH"):
        audit_import_inventory(sample(),p)


def test_account_scope_expansion_blocks():
    p=plan();p[0]["account_id"]="other"
    with pytest.raises(AllocationReadinessError,match="OUTSIDE_SCOPE"):
        audit_import_inventory(sample(),p)


def test_known_september_candidates_are_not_approved():
    s=sept2026_scope()
    assert s["candidate_only"] and not s["account_registry_approved"]
    assert s["period"]=="2026-09" and len(s["account_ids"])==2


def test_row_quality_blocks_even_when_signed_hash_updated():
    c=sample();c["facts"][TABLES[0]].append(dict(c["facts"][TABLES[0]][0]))
    c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
    with pytest.raises(AllocationReadinessError,match="SOURCE_QUALITY"):
        audit_import_inventory(c,plan())
