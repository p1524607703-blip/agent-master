import copy
from datetime import date,timedelta
import pytest
from app.services.allocation_binding_audit import audit_business_bindings,BindingAuditBlocked


def scope():
    return {"period":"2026-09","report_timezone":"America/Los_Angeles",
            "currency":"USD","ad_account_ids":["ad-1"]}


def binding(**override):
    out={"ad_account_id":"ad-1","business_account_id":"biz-1","marketplace":"US",
         "financial_product_id":"W81-WOMEN","operator_group":"XH1","style":"W81女",
         "child_asins":["B0ABC12345"],"approved":True,"binding_version":"v1",
         "unit":"双","unit_evidence_id":"unit-evidence",
         "evidence_id":"binding-approval","effective_from":"2026-09-01",
         "effective_to":"2026-09-30"}
    out.update(override)
    return out


def facts():
    result=[]
    for d in range(1,31):
        result.append({"business_account_id":"biz-1","marketplace":"US",
                       "stat_date":f"2026-09-{d:02d}","child_asin":"B0ABC12345",
                       "ordered_product_units":1,"source_file_hash":"source",
                       "fact_version":"v1"})
    return result


def test_complete_observed_facts_still_not_approved_denominator():
    a=audit_business_bindings(scope(),[binding()],facts())
    assert a["products"][0]["observed_units"]==30
    assert a["products"][0]["denominator"] is None
    assert a["cost_accounting_unchanged"] and not a["may_compute_business_cpo"]


def test_missing_child_day_not_zero_eligibility():
    a=audit_business_bindings(scope(),[binding()],facts()[:-1])
    assert any(i["code"]=="MISSING_BUSINESS_CHILD_DAY_NOT_ZERO_PROOF" for i in a["issues"])
    assert not a["business_denominator_approved"]


def test_duplicate_source_child_daily_row_detected():
    f=facts();f.append(dict(f[0]))
    a=audit_business_bindings(scope(),[binding()],f)
    assert any(i["code"]=="BUSINESS_FACT_DUPLICATE" for i in a["issues"])


def test_two_products_reusing_one_child_detected():
    a=audit_business_bindings(scope(),[binding(),binding(financial_product_id="W81-MEN",style="W81男")],facts())
    assert any(i["code"]=="BUSINESS_DENOMINATOR_REUSED" for i in a["issues"])


def test_unknown_account_does_not_move_cost():
    a=audit_business_bindings(scope(),[binding(ad_account_id="unknown")],facts())
    assert any(i["code"]=="AD_ACCOUNT_MAPPING_UNAPPROVED_OR_OUT_OF_SCOPE" for i in a["issues"])
    assert a["cost_accounting_unchanged"]


def test_unapproved_child_binding_is_flagged():
    a=audit_business_bindings(scope(),[binding(approved=False)],facts())
    assert any(i["code"]=="ACCOUNT_BINDING_NOT_APPROVED" for i in a["issues"])


def test_unit_evidence_must_be_explicit():
    a=audit_business_bindings(scope(),[binding(unit_evidence_id=None)],facts())
    assert any(i["code"]=="UNIT_AND_EVIDENCE_NOT_CONFIRMED" for i in a["issues"])


def test_effective_date_not_entire_month_flags():
    a=audit_business_bindings(scope(),[binding(effective_from="2026-09-15")],facts())
    assert any(i["code"]=="BINDING_NOT_EFFECTIVE_ALL_MONTH" for i in a["issues"])


def test_missing_version_in_business_facts_flags():
    f=facts();f[0]["fact_version"]=""
    a=audit_business_bindings(scope(),[binding()],f)
    assert any(i["code"]=="BUSINESS_FACT_LINEAGE_INCOMPLETE" for i in a["issues"])


def test_duplicate_account_scope_rejected():
    s=scope();s["ad_account_ids"]=["ad-1","ad-1"]
    with pytest.raises(BindingAuditBlocked,match="SCOPE"):
        audit_business_bindings(s,[binding()],facts())
