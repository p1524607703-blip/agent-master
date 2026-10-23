import copy
import pytest
from app.services.allocation_mapping_audit import reconcile

REGISTRY = {"川鹏美站": "account-001", "WHITIN": "account-001"}
DAY = "2026-09-30"

def item(account, child=None, parent="B012345678", product="W81", group="ZJ1", status="approved", dt="2026-09-01"):
    row = {"account_scope": account, "parent_asin": parent,
           "product_code": product, "operator_group": group,
           "mapping_status": status, "effective_date": dt}
    if child is not None:
        row["child_asin"] = child
    return row

def snapshots():
    return ({"child": [item("川鹏美站", child="B0ABC12345")],
             "parent": [item("川鹏美站")]},
            {"child": [item("WHITIN", child="B0ABC12345")],
             "parent": [item("WHITIN")]})

def audit(app,wh,registry=REGISTRY,approved={"approved"}):
    return reconcile(app, wh, registry, approved, DAY)

def test_matching_does_not_claim_authority_or_approval():
    a,b=snapshots()
    r=audit(a,b)
    assert r["matched_count"]==2 and not r["issues"]
    assert not r["ready_for_financial_use"] and not r["authority_selected"] and not r["applied"]
    assert r["matching"][0]["financial_product"]==["ZJ1","W81"]

def test_male_female_financial_style_differences_not_collapsed():
    a,b=snapshots()
    b["child"][0]["product_code"]="W81女"
    r=audit(a,b)
    assert any(x["code"]=="FINANCIAL_MAPPING_CONFLICT" for x in r["issues"])

def test_unknown_account_alias_blocks_not_guess():
    a,b=snapshots()
    assert any(x["code"]=="ACCOUNT_SCOPE_UNRESOLVED"
               for x in audit(a,b,{"川鹏美站":"account-001"})["issues"])

def test_missing_row_is_not_silent_zero():
    a,b=snapshots()
    b["child"]=[]
    assert any(x["code"]=="ONLY_ONE_SOURCE" for x in audit(a,b)["issues"])

def test_duplicate_financial_assignment_blocks():
    a,b=snapshots()
    a["child"].append(item("川鹏美站",child="B0ABC12345",product="W81女"))
    assert any(x["code"]=="DUPLICATE_MAPPING_KEY" for x in audit(a,b)["issues"])

@pytest.mark.parametrize("bad", ["blocked_conflict","draft",""])
def test_unapproved_mapping_never_enters_finance(bad):
    a,b=snapshots()
    a["child"][0]["mapping_status"]=bad
    assert any(x["code"]=="STATUS_NOT_APPROVED" for x in audit(a,b)["issues"])

def test_future_dated_mapping_flags():
    a,b=snapshots()
    a["child"][0]["effective_date"]="2026-10-01"
    assert any(x["code"]=="EFFECTIVE_DATE_NOT_CONFIRMED" for x in audit(a,b)["issues"])

def test_parent_mismatch_independently_reported():
    a,b=snapshots()
    b["child"][0]["parent_asin"]="B000000000"
    assert any(x["code"]=="FINANCIAL_MAPPING_CONFLICT" for x in audit(a,b)["issues"])

def test_explicit_registry_mandatory():
    a,b=snapshots()
    with pytest.raises(ValueError,match="REGISTRY"):
        audit(a,b,{})

def test_reproducible_fingerprint_despite_row_order():
    a,b=snapshots()
    a["child"].append(item("川鹏美站", child="B0ABC33333"))
    b["child"].append(item("WHITIN", child="B0ABC33333"))
    first=audit(a,b)["reconciliation_hash"]
    a["child"].reverse()
    assert first==audit(a,b)["reconciliation_hash"]
