"""Read-only canonical capture, deliberately separate from financial normalization.

One PostgreSQL statement freezes the actual selected fact and mapping values
under one MVCC snapshot. No inference of source eligibility or sales bindings.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from .allocation_store import canonical, digest
from .fact_scope import CLEAN_BATCH_FILTER_SQL

TABLES = ("report_campaign_daily", "report_advertised_product_daily", "report_purchased_product_daily")
AD_PRODUCTS = {"SP": "Sponsored Products", "SB": "Sponsored Brands", "SD": "Sponsored Display", "STV": "Sponsored TV"}
COMMON_COLUMNS = "account_id,account_name,ad_product,campaign_id,campaign_name,stat_date,budget_currency,spend,purchases,units,source_file_name,source_file_hash,source_line,row_hash,batch_id,key_policy_version"
FACT_COLUMNS = {
    "report_campaign_daily": COMMON_COLUMNS,
    "report_advertised_product_daily": COMMON_COLUMNS + ",ad_group_id,advertised_product_id,advertised_product_parent_id,advertised_product_sku,advertised_product_marketplace",
    "report_purchased_product_daily": COMMON_COLUMNS.replace(",spend", "") + ",ad_group_id,purchased_product_id,purchased_product_parent_id,purchased_product_marketplace,advertised_product_id,advertised_product_parent_id,advertised_product_sku,advertised_product_marketplace",
}


def _quote(value):
    if not isinstance(value, str) or not value or len(value) > 256 or "\x00" in value:
        raise ValueError("SOURCE_ID_INVALID")
    return "'" + value.replace("'", "''") + "'"


def validate_scope(scope):
    if set(scope) != {"period", "report_timezone", "currency", "account_ids", "ad_products"}:
        raise ValueError("EXPLICIT_SCOPE_REQUIRED")
    if datetime.strptime(scope["period"], "%Y-%m").strftime("%Y-%m") != scope["period"]:
        raise ValueError("SOURCE_PERIOD_INVALID")
    ZoneInfo(scope["report_timezone"])
    if scope["currency"] != "USD":
        raise ValueError("SOURCE_CURRENCY_UNSUPPORTED")
    for key in ("account_ids", "ad_products"):
        if not isinstance(scope[key], list) or not scope[key] or len(set(scope[key])) != len(scope[key]):
            raise ValueError("SOURCE_SCOPE_EMPTY_OR_DUPLICATE")
        for value in scope[key]:
            _quote(value)
    if set(scope["ad_products"]) - {"SP", "SB", "SD", "STV"}:
        raise ValueError("SOURCE_AD_PRODUCT_UNSUPPORTED")
    return dict(scope, account_ids=sorted(scope["account_ids"]), ad_products=sorted(scope["ad_products"]))


def snapshot_query(scope):
    scope = validate_scope(scope)
    accounts = ",".join(_quote(a) for a in scope["account_ids"])
    types = ",".join(_quote(AD_PRODUCTS[a]) for a in scope["ad_products"])
    start = _quote(scope["period"] + "-01")
    selections = []
    for table in TABLES:
        selected = ",".join("r." + col for col in FACT_COLUMNS[table].split(","))
        sql = ("SELECT COALESCE(json_agg(row_to_json(frozen)), '[]'::json) FROM "
               "(SELECT " + selected + ", ib.file_hash AS manifest_file_hash, ib.target_table AS manifest_target_table, ib.report_start_date AS manifest_start_date, "
               "ib.report_end_date AS manifest_end_date, ib.exported_at AS manifest_exported_at, "
               "ib.metadata AS manifest_batch_metadata FROM core." + table + " r "
               "JOIN core.import_batches ib ON ib.batch_id=r.batch_id "
               "WHERE " + CLEAN_BATCH_FILTER_SQL + " AND r.account_id IN (" + accounts + ") "
               "AND r.ad_product IN (" + types + ") AND r.stat_date >= " + start + "::date "
               "AND r.stat_date < (" + start + "::date + INTERVAL '1 month') "
               "ORDER BY r.account_id,r.ad_product,r.campaign_id,r.stat_date,r.row_hash) frozen")
        selections.extend([_quote(table), "(" + sql + ")"])
    scope_json = _quote(canonical(scope)) + "::json"
    return ("SELECT json_build_object('schema_version','canonical-capture-v1','database',current_database(),"
            "'role',current_user,'default_read_only',current_setting('default_transaction_read_only'),"
            "'database_timezone',current_setting('TimeZone'),'mvcc_snapshot',pg_current_snapshot()::text,"
            "'captured_at',CURRENT_TIMESTAMP,'scope'," + scope_json + ", 'facts',json_build_object(" + ",".join(selections) + "),"
            "'mappings',json_build_object('child', (SELECT COALESCE(json_agg(row_to_json(m)),'[]'::json) FROM "
            "(SELECT * FROM ops_products.child_asin_mapping ORDER BY account_scope,child_asin) m),"
            "'parent',(SELECT COALESCE(json_agg(row_to_json(m)),'[]'::json) FROM "
            "(SELECT * FROM ops_products.product_mapping ORDER BY operator_group,product_code,parent_asin) m)))")


def _exact(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float):
        raise ValueError("SOURCE_DECIMAL_ALREADY_LOST")
    if isinstance(value, dict):
        return {k: _exact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_exact(v) for v in value]
    return value


def capture(scope, query_json):
    scope = validate_scope(scope)
    raw = query_json(snapshot_query(scope))
    data = _exact(json.loads(raw, parse_float=Decimal))
    if data.get("database") != "amazon_ads_v2" or data.get("role") != "ads_readonly" or data.get("default_read_only") != "on" or data.get("scope") != scope:
        raise ValueError("READONLY_CANONICAL_SOURCE_NOT_VERIFIED")
    manifest = []
    for table in TABLES:
        rows = data["facts"][table]
        for row in rows:
            if not row.get("row_hash") or not row.get("source_file_hash") or row.get("batch_id") is None:
                raise ValueError("SOURCE_LINEAGE_INCOMPLETE")
            if row.get("account_id") not in scope["account_ids"] or row.get("ad_product") not in {AD_PRODUCTS[a] for a in scope["ad_products"]} or not row.get("stat_date", "").startswith(scope["period"] + "-"):
                raise ValueError("SOURCE_ROW_OUTSIDE_SCOPE")
            if row.get("budget_currency") != scope["currency"]:
                raise ValueError("SOURCE_CURRENCY_MISMATCH")
        manifest.append({"source_table": "core." + table, "row_count": len(rows), "content_hash": digest(rows),
                         "account_ids": sorted({r["account_id"] for r in rows}),
                         "batch_ids": sorted({str(r["batch_id"]) for r in rows}),
                         "purchases_sum": str(sum(int(r["purchases"]) for r in rows)) if all(r.get("purchases") is not None for r in rows) else None,
                         "units_sum": str(sum(int(r["units"]) for r in rows)) if all(r.get("units") is not None for r in rows) else None,
                         "spend_sum": str(sum((Decimal(r["spend"]) for r in rows), Decimal())) if all(r.get("spend") is not None for r in rows) else None,
                         "coverage_status": "PENDING_VERIFICATION"})
    data["manifest"] = manifest
    data["quality_audit"] = audit_snapshot_quality(data)
    data["capabilities"] = {"actual_rows_frozen": True, "financial_normalization_ready": False,
                            "eligibility_negatives_proven": False, "business_bindings_confirmed": False,
                            "formal_publication": False}
    data["content_hash"] = digest(data)
    return data


def save_capture(data, directory):
    content_hash = data.get("content_hash")
    if content_hash != digest({k: v for k, v in data.items() if k != "content_hash"}):
        raise ValueError("SNAPSHOT_HASH_MISMATCH")
    path = Path(directory) / ("canonical_" + content_hash + ".json")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = canonical(data).encode("utf-8")
    try:
        with path.open("xb") as file:
            file.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise ValueError("IMMUTABLE_SNAPSHOT_CONFLICT")
    return {"path": str(path), "sha256": hashlib.sha256(content).hexdigest(), "snapshot_hash": content_hash}


def audit_snapshot_quality(data):
    """Fail-closed quality inventory, not an approval or coverage certificate.

    Strict flags only when supplied rows contradict basic facts. Missing lineage
    metadata becomes an issue, not an invented default. The campaign report is
    the only authoritative advertising spend ledger.
    """
    issues = []
    facts = data.get("facts")
    if not isinstance(facts, dict):
        raise ValueError("SNAPSHOT_FACTS_REQUIRED")
    for table in TABLES:
        rows = facts.get(table)
        if not isinstance(rows, list):
            raise ValueError("SNAPSHOT_TABLE_MISSING:" + table)
        row_hashes = set()
        campaign_day_keys = set()
        for idx, row in enumerate(rows):
            if not isinstance(row, dict):
                issues.append({"code": "INVALID_SOURCE_ROW", "table": table, "row_index": idx})
                continue
            def flag(code):
                issues.append({"code": code, "table": table, "row_index": idx,
                               "account_id": str(row.get("account_id") or ""),
                               "campaign_id": str(row.get("campaign_id") or "")})
            row_hash = row.get("row_hash")
            if row_hash:
                identity = (str(row.get("account_id")), str(row.get("batch_id")), str(row_hash))
                if identity in row_hashes:
                    flag("DUPLICATE_SOURCE_ROW")
                row_hashes.add(identity)
            if table == "report_campaign_daily":
                grain = (str(row.get("account_id")), str(row.get("ad_product")),
                         str(row.get("campaign_id")), str(row.get("stat_date")))
                if not row.get("campaign_id"):
                    flag("CAMPAIGN_ID_MISSING")
                elif grain in campaign_day_keys:
                    flag("DUPLICATE_CAMPAIGN_DAY")
                campaign_day_keys.add(grain)
            target = row.get("manifest_target_table")
            if target and target != "core." + table:
                flag("BATCH_TARGET_TABLE_MISMATCH")
            if row.get("manifest_file_hash") and row.get("source_file_hash") and (
                    str(row["manifest_file_hash"]) != str(row["source_file_hash"])):
                flag("BATCH_FILE_HASH_MISMATCH")
            for field in ("purchases", "units"):
                value = row.get(field)
                if value is None:
                    flag("MISSING_" + field.upper())
                    continue
                if isinstance(value, bool) or isinstance(value, float):
                    flag("INVALID_" + field.upper())
                    continue
                try:
                    parsed = int(str(value))
                    if parsed < 0 or str(parsed) != str(value):
                        raise ValueError()
                except (ValueError, OverflowError):
                    flag("INVALID_" + field.upper())
            if table != "report_purchased_product_daily":
                value = row.get("spend")
                if value is None or isinstance(value, (bool, float)):
                    flag("SPEND_NOT_EXACT")
                else:
                    try:
                        money = Decimal(str(value))
                        if not money.is_finite() or money < 0:
                            raise ValueError()
                    except (ValueError, ArithmeticError):
                        flag("SPEND_NOT_EXACT")
            try:
                date_text = str(row.get("stat_date") or "")
                parsed_date = datetime.strptime(date_text, "%Y-%m-%d")
                if parsed_date.strftime("%Y-%m-%d") != date_text:
                    raise ValueError()
            except ValueError:
                flag("SOURCE_DATE_INVALID")
    return {"status": "ISSUES_FOUND" if issues else "NO_OBSERVED_QUALITY_ISSUES",
            "financial_approved": False, "complete_source_coverage_proven": False,
            "issue_count": len(issues), "issues": issues}
