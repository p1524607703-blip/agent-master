import json
import copy
import pytest

from app.services.allocation_input_adapter import (prepare_source_handoff,
                                                   require_financial_ready,
                                                   AllocationHandoffBlocked)
from app.services.allocation_sources import capture, TABLES, validate_scope
from app.services.allocation_store import digest

SCOPE={"period":"2026-09","report_timezone":"America/Los_Angeles","currency":"USD",
       "account_ids":["account-1"],"ad_products":["SP"]}


def payload():
    row={"account_id":"account-1","ad_product":"Sponsored Products",
         "campaign_id":"001","campaign_name":"ZJ1-W81","stat_date":"2026-09-01",
         "budget_currency":"USD","row_hash":"h1","source_file_hash":"f1",
         "batch_id":1,"purchases":2,"units":3,"spend":"10.00"}
    source={"database":"amazon_ads_v2","role":"ads_readonly","default_read_only":"on",
            "scope": validate_scope(SCOPE),
            "facts": {t:[dict(row, row_hash=("h1" if t==TABLES[0] else "h-"+t))] for t in TABLES},
            "mappings":{"child":[],"parent":[]}}
    return capture(SCOPE,lambda _:json.dumps(source))


def test_campaign_is_only_spend_pool_no_product_cost_double_count():
    c=payload()
    c["facts"][TABLES[1]][0]["spend"]="2999.00"
    c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
    result=prepare_source_handoff(c)
    assert result["campaigns"][0]["campaign_spend"]=="10.00"
    assert result["spend_source"]=="core.report_campaign_daily"
    assert result["campaigns"][0]["creator_group"] is None
    assert not result["financial_ready"] and not result["may_run_engine"]


def test_month_sums_exact_values_without_float():
    c=payload()
    r=dict(c["facts"][TABLES[0]][0],row_hash="h2",stat_date="2026-09-02",spend="10.10")
    c["facts"][TABLES[0]].append(r)
    c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
    r=prepare_source_handoff(c)
    assert r["campaigns"][0]["campaign_spend"]=="20.10"
    assert r["campaigns"][0]["observed_days"]==["2026-09-01","2026-09-02"]


def test_tampering_capture_rejected():
    c=payload();c["facts"][TABLES[0]][0]["spend"]="11.00"
    with pytest.raises(AllocationHandoffBlocked,match="HASH_MISMATCH"):
        prepare_source_handoff(c)


def test_duplicate_campaign_day_rejected():
    c=payload();c["facts"][TABLES[0]].append(dict(c["facts"][TABLES[0]][0],row_hash="other"))
    c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
    with pytest.raises(AllocationHandoffBlocked,match="QUALITY_BLOCKED"):
        prepare_source_handoff(c)


@pytest.mark.parametrize("bad", ["NaN","-0.01","1.002"])
def test_invalid_spend_blocks(bad):
    c=payload();c["facts"][TABLES[0]][0]["spend"]=bad
    c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
    with pytest.raises((AllocationHandoffBlocked, ValueError)):
        prepare_source_handoff(c)


def test_unknown_scope_account_rejected():
    c=payload();c["facts"][TABLES[0]][0]["account_id"]="other"
    c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
    with pytest.raises(AllocationHandoffBlocked,match="ACCOUNT_OUTSIDE_SCOPE"):
        prepare_source_handoff(c)


def test_missing_campaign_records_never_claim_no_ads():
    c=payload();c["facts"][TABLES[0]]=[]
    c["content_hash"]=digest({k:v for k,v in c.items() if k!="content_hash"})
    r=prepare_source_handoff(c)
    assert "CAMPAIGN_SOURCE_EMPTY_NOT_ZERO_SPEND_PROOF" in r["pending"]
    assert r["may_run_engine"] is False


def test_engine_must_stay_blocked_without_authoritative_approvals():
    r=prepare_source_handoff(payload())
    with pytest.raises(AllocationHandoffBlocked,match="NOT_APPROVED"):
        require_financial_ready(r)
    r["may_run_engine"]=True
    with pytest.raises(AllocationHandoffBlocked,match="NOT_INTACT"):
        require_financial_ready(r)


def test_unverified_negative_eligibility_not_promoted():
    from app.services.allocation_coverage import build_coverage_manifest
    c=payload();coverage=build_coverage_manifest(SCOPE,c)
    coverage["cells"][0]["negative_eligibility_proven"]=True
    coverage["manifest_hash"]=digest({k:v for k,v in coverage.items() if k!="manifest_hash"})
    with pytest.raises(AllocationHandoffBlocked,match="UNTRUSTED_NEGATIVE"):
        prepare_source_handoff(c,coverage_manifest=coverage)
