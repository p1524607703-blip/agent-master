"""Read-only business Child-ASIN binding audit for allocation denominators.

Ad spend never changes ownership through this module. Missing business units
produce a NULL denominator candidate, never a zero-cost campaign.
"""
from collections import defaultdict
from datetime import date,timedelta
from .allocation_store import digest


class BindingAuditBlocked(ValueError):
    pass


def _date(value):
    if not isinstance(value,str):
        raise BindingAuditBlocked("DATE_REQUIRED")
    try:
        d=date.fromisoformat(value)
    except ValueError as ex:
        raise BindingAuditBlocked("DATE_INVALID") from ex
    if d.isoformat()!=value:
        raise BindingAuditBlocked("DATE_NONCANONICAL")
    return d


def _days(period):
    y,m=map(int,period.split("-"))
    start=date(y,m,1)
    end=date(y+int(m==12),m%12+1,1)
    days=[]
    while start<end:
        days.append(start.isoformat());start+=timedelta(days=1)
    return days


def audit_business_bindings(scope, bindings, business_facts):
    """Construct a conservative per-financial-product *observed* sales audit."""
    if not isinstance(scope,dict) or set(scope)!={"period","report_timezone","ad_account_ids","currency"}:
        raise BindingAuditBlocked("EXPLICIT_BUSINESS_SCOPE_REQUIRED")
    period=scope["period"]
    if not isinstance(period,str) or len(period)!=7 or period[4]!="-":
        raise BindingAuditBlocked("PERIOD_INVALID")
    days=_days(period)
    if scope["currency"]!="USD" or not scope.get("report_timezone"):
        raise BindingAuditBlocked("BUSINESS_SCOPE_INVALID")
    accounts=scope.get("ad_account_ids")
    if not isinstance(accounts,list) or not accounts or len(set(accounts))!=len(accounts):
        raise BindingAuditBlocked("AD_ACCOUNT_SCOPE_INVALID")
    if not isinstance(bindings,list) or not isinstance(business_facts,list):
        raise BindingAuditBlocked("BINDINGS_AND_FACTS_REQUIRED")
    fact_index={}
    issues=[]
    for i,fact in enumerate(business_facts):
        if not isinstance(fact,dict):
            raise BindingAuditBlocked("BUSINESS_FACT_INVALID")
        key=tuple(fact.get(k) for k in ("business_account_id","marketplace","stat_date","child_asin"))
        if any(not isinstance(v,str) or not v for v in key):
            raise BindingAuditBlocked("BUSINESS_FACT_KEY_INCOMPLETE")
        if key[2] not in days:
            issues.append({"code":"FACT_DATE_OUTSIDE_SCOPE","key":list(key)})
            continue
        if key in fact_index:
            issues.append({"code":"BUSINESS_FACT_DUPLICATE","key":list(key)})
        if type(fact.get("ordered_product_units")) is not int or fact["ordered_product_units"]<0:
            issues.append({"code":"BUSINESS_UNITS_UNTRUSTED","key":list(key)})
        if not fact.get("source_file_hash") or not fact.get("fact_version"):
            issues.append({"code":"BUSINESS_FACT_LINEAGE_INCOMPLETE","key":list(key)})
        fact_index[key]=fact
    used=set()
    output=[]
    for index,b in enumerate(bindings):
        if not isinstance(b,dict):
            raise BindingAuditBlocked("BINDING_INVALID")
        ad=b.get("ad_account_id")
        business=b.get("business_account_id")
        market=b.get("marketplace")
        product=b.get("financial_product_id")
        children=b.get("child_asins")
        if ad not in accounts:
            issues.append({"code":"AD_ACCOUNT_MAPPING_UNAPPROVED_OR_OUT_OF_SCOPE","binding_index":index})
        if not all(isinstance(v,str) and v for v in (business,market,product,b.get("operator_group"),b.get("style"))):
            issues.append({"code":"FINANCIAL_PRODUCT_OR_BUSINESS_IDENTITY_INCOMPLETE","binding_index":index})
        if not isinstance(children,list) or not children or len(set(children))!=len(children):
            issues.append({"code":"CHILD_SET_EMPTY_OR_DUPLICATE","binding_index":index})
            children=[]
        if not b.get("binding_version") or not b.get("evidence_id") or b.get("approved") is not True:
            issues.append({"code":"ACCOUNT_BINDING_NOT_APPROVED","binding_index":index})
        if b.get("unit") not in ("件","双") or not b.get("unit_evidence_id"):
            issues.append({"code":"UNIT_AND_EVIDENCE_NOT_CONFIRMED","binding_index":index})
        if not b.get("effective_from") or not b.get("effective_to"):
            issues.append({"code":"BINDING_EFFECTIVE_DATE_NOT_CONFIRMED","binding_index":index})
        else:
            start,end=_date(b["effective_from"]),_date(b["effective_to"])
            if start>_date(days[0]) or end<_date(days[-1]):
                issues.append({"code":"BINDING_NOT_EFFECTIVE_ALL_MONTH","binding_index":index})
        total=0
        missing=0
        for child in children:
            for day in days:
                key=(business,market,day,child)
                if key in used:
                    issues.append({"code":"BUSINESS_DENOMINATOR_REUSED","binding_index":index,"key":list(key)})
                used.add(key)
                row=fact_index.get(key)
                if row is None:
                    missing+=1
                elif type(row.get("ordered_product_units")) is int and row["ordered_product_units"]>=0:
                    total+=row["ordered_product_units"]
        if missing:
            issues.append({"code":"MISSING_BUSINESS_CHILD_DAY_NOT_ZERO_PROOF",
                           "binding_index":index,"unobserved_days":missing})
        output.append({"ad_account_id":ad,"business_account_id":business,"marketplace":market,
                       "financial_product_id":product,"operator_group":b.get("operator_group"),
                       "style":b.get("style"),"unit":b.get("unit"),
                       "observed_child_day_rows":len(children)*len(days)-missing,
                       "observed_units":total,"denominator":None,
                       "status":"PENDING_BUSINESS_COVERAGE_AND_FINANCE_APPROVAL",
                       "financial_cost_moved":False})
    result={"scope":scope,"binding_count":len(bindings),"fact_count":len(business_facts),
            "products":output,"issues":issues,
            "complete_child_daily_coverage_proven":False,
            "authoritative_mapping_verified":False,
            "business_denominator_approved":False,
            "cost_accounting_unchanged":True,"may_compute_business_cpo":False}
    result["audit_hash"]=digest(result)
    return result
