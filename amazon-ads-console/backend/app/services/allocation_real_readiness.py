"""Offline, read-only September fact source inventory; NEVER certifies completeness.

Receives an immutable capture and a separately compiled list of expected file
requests. All observations are evidence, not the authority for negative claims.
"""
from collections import defaultdict
from datetime import date
from .allocation_sources import TABLES, AD_PRODUCTS, validate_scope, audit_snapshot_quality
from .allocation_store import digest

# Known account IDs from dated preparatory evidence, not live registry approval.
SEPTEMBER_CANDIDATES = {
    "WHITIN": "amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh",
    "anac1973 (C3S8S)": "amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz",
}
AUDIT_MONTH = "2026-09"


class AllocationReadinessError(ValueError):
    pass


def _day(x):
    if not isinstance(x, str):
        raise AllocationReadinessError("SOURCE_DATE_INVALID")
    try:
        d = date.fromisoformat(x)
    except ValueError as ex:
        raise AllocationReadinessError("SOURCE_DATE_INVALID") from ex
    if d.isoformat() != x:
        raise AllocationReadinessError("SOURCE_DATE_INVALID")
    return d


def audit_import_inventory(captured, expected_requests):
    if not isinstance(captured, dict) or not isinstance(expected_requests, list):
        raise AllocationReadinessError("CAPTURE_AND_REQUEST_LEDGER_REQUIRED")
    h = captured.get("content_hash")
    if h != digest({k: v for k, v in captured.items() if k != "content_hash"}):
        raise AllocationReadinessError("CAPTURE_HASH_MISMATCH")
    try:
        scope = validate_scope(captured["scope"])
    except (KeyError, ValueError, TypeError) as ex:
        raise AllocationReadinessError("SOURCE_SCOPE_INVALID") from ex
    if captured["scope"] != scope:
        raise AllocationReadinessError("CANONICAL_SCOPE_REQUIRED")
    if set(captured.get("facts", {})) != set(TABLES):
        raise AllocationReadinessError("FACT_TABLES_MISMATCH")
    quality = audit_snapshot_quality(captured)
    if quality["issue_count"]:
        raise AllocationReadinessError("SOURCE_QUALITY_ISSUES")
    observed = defaultdict(list)
    for table, rows in captured["facts"].items():
        if not isinstance(rows, list):
            raise AllocationReadinessError("INVALID_FACT_ROWS")
        for row in rows:
            key = (table, row.get("account_id"), row.get("ad_product"))
            if key[1] not in scope["account_ids"] or key[2] not in [AD_PRODUCTS[x] for x in scope["ad_products"]]:
                raise AllocationReadinessError("OBSERVED_FACT_OUTSIDE_SCOPE")
            if not str(row.get("stat_date", "")).startswith(scope["period"] + "-"):
                raise AllocationReadinessError("OBSERVED_DATE_OUTSIDE_SCOPE")
            observed[key].append(row)

    request_keys = set()
    request_report = []
    issues = []
    for n, req in enumerate(expected_requests):
        if not isinstance(req, dict):
            raise AllocationReadinessError("EXPECTED_REQUEST_INVALID")
        table = req.get("source_table")
        account = req.get("account_id")
        product = req.get("ad_product")
        if product in AD_PRODUCTS:product = AD_PRODUCTS[product]
        if table not in TABLES or account not in scope["account_ids"] or product not in AD_PRODUCTS.values():
            raise AllocationReadinessError("EXPECTED_REQUEST_OUTSIDE_SCOPE")
        key = (table, account, product)
        if key[2] not in {AD_PRODUCTS[p] for p in scope["ad_products"]}:
            raise AllocationReadinessError("EXPECTED_AD_PRODUCT_OUTSIDE_SCOPE")
        start, end = _day(req.get("report_start")), _day(req.get("report_end"))
        if start > end or start.strftime("%Y-%m") != scope["period"] or end.strftime("%Y-%m") != scope["period"]:
            raise AllocationReadinessError("REPORT_RANGE_OUTSIDE_MONTH")
        request_id = req.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            raise AllocationReadinessError("REQUEST_ID_REQUIRED")
        full_key = (key, request_id)
        if full_key in request_keys:
            raise AllocationReadinessError("DUPLICATE_REPORT_REQUEST")
        request_keys.add(full_key)
        requested_file = req.get("source_file_hash")
        if requested_file is not None and (not isinstance(requested_file,str) or not requested_file):
            raise AllocationReadinessError("INVALID_EXPECTED_FILE_HASH")
        matched = [r for r in observed[key] if
                   (requested_file is None or r.get("source_file_hash")==requested_file)
                   and start <= _day(str(r["stat_date"])) <= end]
        files = sorted({str(r["source_file_hash"]) for r in matched if r.get("source_file_hash")})
        statuses = sorted({str(r.get("manifest_batch_metadata",{}).get("request_status") or "UNKNOWN")
                           for r in matched if isinstance(r.get("manifest_batch_metadata",{}),dict)})
        state = "ROWS_OBSERVED_PENDING_REPORT_VERIFICATION" if matched else "MISSING_OR_LEGITIMATELY_EMPTY_UNRESOLVED"
        if not matched:
            issues.append({"code":"REPORT_REQUEST_NOT_OBSERVED", "request_id":request_id,
                           "source_table":table,"account_id":account})
        if matched and any(r.get("manifest_file_hash") and r.get("manifest_file_hash")!=r.get("source_file_hash") for r in matched):
            issues.append({"code":"BATCH_SOURCE_FILE_CONFLICT","request_id":request_id})
        request_report.append({"request_id":request_id,"source_table":table,"account_id":account,
                               "ad_product":product,"report_start":start.isoformat(),"report_end":end.isoformat(),
                               "observed_rows":len(matched),"observed_source_files":files,
                               "batch_statuses":statuses,"status":state,
                               "coverage_approved":False,"negative_eligibility_proven":False})
    matrix=[]
    for table in TABLES:
        for account in scope["account_ids"]:
            for short in scope["ad_products"]:
                product = AD_PRODUCTS[short];key=(table,account,product)
                reports=[r for r in request_report if (r["source_table"],r["account_id"],r["ad_product"])==key]
                if not reports:
                    issues.append({"code":"NO_EXPECTED_REPORT_REQUEST_DEFINED","source_table":table,
                                   "account_id":account,"ad_product":product})
                matrix.append({"source_table":table,"account_id":account,"ad_product":product,
                               "observed_fact_rows":len(observed[key]),"request_count":len(reports),
                               "all_requests_approved":False})
    result={"period":scope["period"],"scope":scope,"capture_hash":h,"requests":request_report,
            "matrix":matrix,"issues":issues,"real_data_verified":False,
            "publication_allowed":False,"negative_eligibility_proven":False,
            "source": "OFFLINE_CAPTURE_PLUS_EXPLICIT_EXPECTED_REQUESTS"}
    result["audit_hash"]=digest(result)
    return result


def sept2026_scope(*, confirmed=False):
    """Suggested scope only; never claims these account IDs have approved billing status."""
    return {"period":AUDIT_MONTH, "report_timezone":"America/Los_Angeles","currency":"USD",
            "account_ids":sorted(SEPTEMBER_CANDIDATES.values()),"ad_products":["SP","SB","SD","STV"],
            "account_registry_approved":False,"candidate_only":True}
