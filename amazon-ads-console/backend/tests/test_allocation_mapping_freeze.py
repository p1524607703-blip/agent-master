import copy
import pytest
from app.services.allocation_mapping_freeze import (
    freeze_review_request,verify_review_request,accept_mapping_approval,MappingFreezeError)

REG={"川鹏":"a1","WHITIN":"a1"}
def row(acct, asin="B0ABC12345", group="ZJ1", product="W81"):
    return {"account_scope":acct,"child_asin":asin,"parent_asin":"B012345678",
            "operator_group":group,"product_code":product,
            "mapping_status":"confirmed","effective_date":"2026-09-01"}
def data():
    return ({"child":[row("川鹏")],"parent":[dict(row("川鹏"),child_asin="")]},
            {"child":[row("WHITIN")],"parent":[dict(row("WHITIN"),child_asin="")]})
def freeze(a,b):
    return freeze_review_request(a,b,REG,{"confirmed"},"2026-09-30",["a1"],"finance-review")

def test_technical_match_is_never_auto_financial_approval():
    a,b=data()
    p=freeze(a,b)
    assert p["candidate_products"] and p["technical_issues"]==[]
    assert not p["financial_approved"] and not p["apply_allowed"]
    assert p["authority_selected"] is None
    assert p["pending"]


def test_review_request_hash_stable():
    a,b=data()
    assert freeze(a,b)["request_hash"]==freeze(copy.deepcopy(a),copy.deepcopy(b))["request_hash"]


def test_tampering_audit_request_detected():
    a,b=data();p=freeze(a,b)
    p["candidate_products"][0]["financial_product"][1]="W81女"
    with pytest.raises(MappingFreezeError,match="TAMPERED"):
        verify_review_request(p)


def test_drifted_warehouse_snapshot_detected():
    a,b=data();p=freeze(a,b);b["child"][0]["product_code"]="W81女"
    with pytest.raises(MappingFreezeError,match="WAREHOUSE_MAPPING_DRIFTED"):
        verify_review_request(p,warehouse=b)


def test_alias_without_resolved_canonical_account_rejected():
    a,b=data()
    with pytest.raises(MappingFreezeError,match="SCOPE_NOT_IN_REGISTRY"):
        freeze_review_request(a,b,REG,{"confirmed"},"2026-09-30",["different"],"finance")


def test_different_financial_product_retains_technical_issue():
    a,b=data();b["child"][0]["product_code"]="W81女"
    p=freeze(a,b)
    assert any(x["code"]=="FINANCIAL_MAPPING_CONFLICT" for x in p["technical_issues"])
    assert p["apply_allowed"] is False


def test_unknown_account_alias_does_not_silently_match():
    a,b=data();b["child"][0]["account_scope"]="Unregistered"
    p=freeze(a,b)
    assert any(x["code"]=="ACCOUNT_SCOPE_UNRESOLVED" for x in p["technical_issues"])


def test_missing_two_source_collection_rejected():
    a,b=data()
    b.pop("child")
    with pytest.raises(MappingFreezeError,match="COLLECTION_MISSING"):
        freeze(a,b)


def test_untrusted_approval_receipt_never_bypasses_iam():
    a,b=data();p=freeze(a,b)
    with pytest.raises(MappingFreezeError,match="VERIFIER_UNAVAILABLE"):
        accept_mapping_approval(p,{"approved":True,"actor":"user"})


def test_duplicate_account_scope_rejected():
    a,b=data()
    with pytest.raises(MappingFreezeError,match="DUPLICATE_ACCOUNT"):
        freeze_review_request(a,b,REG,{"confirmed"},"2026-09-30",["a1","a1"],"finance")
