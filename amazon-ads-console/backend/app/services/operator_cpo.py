"""Operator CPO service based on explicit product mappings and the new one-report-one-table facts.

Hard rules enforced here:
- child/parent mappings are primary; exact operator-product campaign prefix is an ad-only identity fallback when Amazon omits usable advertised ASIN detail.
- product codes are exact identities; suffixes such as S71W/W81女/W823男 are never stripped.
- daily eligibility is the explicit mapped product intersected with the business-report parent ASINs present that day.
- spend/orders from advertised-product facts; purchased-product facts are a separate attribution validation source and are never added to spend.
- all physical ad accounts are pooled once; missing business-side data produces an explicit incomplete status instead of fake CPO.
"""
from __future__ import annotations

import re
import time

from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Optional
from fastapi import HTTPException
from app.core.observability import increment, update_context

from .app_db import query_rows as app_query_rows
from .build_cache import build_cache
from .rds_query import query_one, query_rows

OPERATOR_NAMES = {
    "ZJ": "子娟", "AJ": "爱菊", "YT": "雅婷", "XM": "雪敏",
    "DD": "丹丹", "YS": "雨珊", "LB": "丽斌", "XH": "鑫华",
    "LW": "林文", "ZF": "珍凤",
}
AD_TYPES = ("SP", "SB", "SD", "STV", "DSP")
AD_PRODUCT_TYPE_MAP = {
    "Sponsored Products": "SP",
    "SP": "SP",
    "Sponsored Brands": "SB",
    "SB": "SB",
    "Sponsored Display": "SD",
    "SD": "SD",
    "Sponsored TV": "STV",
    "STV": "STV",
    "Amazon DSP": "DSP",
    "DSP": "DSP",
}


def _classify_ad_type(ad_product: str) -> str:
    """Latest CPO rule: classify directly by Amazon ad product, never infer from campaign names."""
    return AD_PRODUCT_TYPE_MAP.get((ad_product or "").strip(), "")


def _operator_name(group: str) -> str:
    g = (group or "").strip().upper()
    return OPERATOR_NAMES.get(g[:2], g or "未归属")


def _period_range(anchor: str, period: str) -> tuple[str, str]:
    d = date.fromisoformat(anchor)
    if period == "weekly":
        start = d - timedelta(days=d.weekday())
        return start.isoformat(), (start + timedelta(days=6)).isoformat()
    if period == "monthly":
        start = d.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start.isoformat(), (nxt - timedelta(days=1)).isoformat()
    return d.isoformat(), d.isoformat()


def _mapping() -> dict[str, dict[str, str]]:
    rows = app_query_rows("""
        SELECT brand, product_code, parent_asin, operator_group, status
        FROM app.product_mapping
        WHERE status LIKE 'confirmed%'
          AND parent_asin IS NOT NULL AND parent_asin<>''
          AND product_code IS NOT NULL AND product_code<>''
          AND operator_group IS NOT NULL AND operator_group<>''
        ORDER BY parent_asin
    """)
    return {
        r["parent_asin"]: {
            "brand": r["brand"],
            "parentAsin": r["parent_asin"],
            "productCode": r["product_code"],
            "group": r["operator_group"],
            "operatorName": _operator_name(r["operator_group"]),
            "mappingStatus": r["status"],
        }
        for r in rows
    }


def _child_mapping() -> dict[tuple[str, str], dict[str, str]]:
    rows = app_query_rows("""
        SELECT account_scope, child_asin, product_code, parent_asin, brand,
               operator_group, mapping_status, source, confidence
        FROM app.child_asin_mapping
        WHERE mapping_status <> 'blocked_conflict'
          AND child_asin IS NOT NULL AND child_asin<>''
          AND product_code IS NOT NULL AND product_code<>''
          AND operator_group IS NOT NULL AND operator_group<>''
        ORDER BY account_scope, child_asin
    """)
    return {
        (r["account_scope"], r["child_asin"]): {
            "brand": r.get("brand") or "",
            "childAsin": r["child_asin"],
            "parentAsin": r.get("parent_asin") or "",
            "productCode": r["product_code"],
            "group": r["operator_group"],
            "operatorName": _operator_name(r["operator_group"]),
            "mappingStatus": r.get("mapping_status") or "parent_inherited",
            "mappingSource": r.get("source") or "",
            "confidence": r.get("confidence") or "",
        }
        for r in rows
    }


def _portfolio(mapping: dict[str, dict[str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for item in mapping.values():
        out[item["operatorName"]].add(item["productCode"])

    # Roster is the stable product portfolio. Only use rows whose owner_group
    # has already been resolved to a fine operator code (AJ1/XM2/etc.);
    # coarse historical groups remain excluded until they are reconciled.
    rows = app_query_rows("""
        SELECT product_code, owner_group
        FROM app.product_roster
        WHERE is_listed=true
          AND product_code IS NOT NULL AND product_code<>''
          AND owner_group ~ '^[A-Z]{2}[0-9]+$'
    """)
    for row in rows:
        out[_operator_name(row["owner_group"])].add(row["product_code"])
    return out


DIRECT_AD_TO_BUSINESS = {
    "WHITIN": "WHITIN",
    "BLOOMNEXT": "BLOOMNEXT",
    "JOOMRA DIRECT": "JOOMRA DIRECT",
}
AMS_AD_ACCOUNTS = ("anac1973 (C3S8S)",)
AD_ACCOUNTS = AMS_AD_ACCOUNTS + tuple(DIRECT_AD_TO_BUSINESS)
# Child-ASIN business facts are available for all three seller accounts.
BUSINESS_ACCOUNTS = ("WHITIN", "BLOOMNEXT", "JOOMRA DIRECT")


def _sql_names(values: tuple[str, ...]) -> str:
    return ",".join("'" + v.replace("'", "''") + "'" for v in values)


def _campaign_prefix(name: str) -> str:
    # Stable internal prefix, e.g. XM2-S71 / AJ1-HB001.
    # Token boundary prevents XM2-S71 from matching XM2-S713.
    m = re.search(r"(?i)(?<![A-Z0-9])([A-Z]{2}\d+-[A-Z0-9]+)(?![A-Z0-9])", name or "")
    return m.group(1).upper() if m else ""


def _direct_prefix_scopes() -> dict[str, set[str]]:
    rows = query_rows(f"""
        SELECT DISTINCT account_name, campaign_name
        FROM core.report_campaign_daily
        WHERE account_name IN ({_sql_names(BUSINESS_ACCOUNTS)})
          AND campaign_name IS NOT NULL AND campaign_name<>''
    """)
    out: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        prefix = _campaign_prefix(row.get("campaign_name") or "")
        if prefix:
            out[prefix].add(row["account_name"])
    return out


def _campaign_prefix_identity_map(
    parent_mapping: dict[str, dict[str, str]],
    child_mapping: dict[tuple[str, str], dict[str, str]],
) -> dict[str, dict[str, str]]:
    """Strict operator-product prefix -> unique product identity.

    This is an ad-only fallback for rows where Amazon supplies no usable
    advertised child/parent ASIN. It never classifies ad type and never
    applies to business denominators.
    """
    candidates: dict[str, dict[tuple[str, str, str], dict[str, str]]] = defaultdict(dict)

    def add(meta: dict[str, str]) -> None:
        group=(meta.get("group") or "").strip().upper()
        code=(meta.get("productCode") or "").strip().upper()
        if not group or not code:
            return
        prefix=f"{group}-{code}"
        ident=(meta.get("brand") or "", meta["productCode"], meta["group"])
        candidates[prefix][ident]={
            "brand": meta.get("brand") or "",
            "parentAsin": meta.get("parentAsin") or "",
            "productCode": meta["productCode"],
            "group": meta["group"],
            "operatorName": _operator_name(meta["group"]),
            "mappingStatus": meta.get("mappingStatus") or "confirmed",
        }

    for meta in parent_mapping.values():
        add(meta)
    for meta in child_mapping.values():
        add(meta)

    # Active roster extends coverage for products whose current parent has
    # changed but whose exact operator/product identity is already maintained.
    rows=app_query_rows("""
        SELECT brand, product_code, parent_asin, owner_group
        FROM app.product_roster
        WHERE is_listed=true
          AND product_code IS NOT NULL AND product_code<>''
          AND owner_group IS NOT NULL AND owner_group<>''
    """)
    for r in rows:
        add({
            "brand": r.get("brand") or "",
            "parentAsin": r.get("parent_asin") or "",
            "productCode": r["product_code"],
            "group": r["owner_group"],
            "mappingStatus": "roster_confirmed",
        })

    out: dict[str, dict[str, str]]={}
    for prefix, ids in candidates.items():
        # Brand/parent snapshots may differ across valid sources. Identity is
        # operator_group + exact product_code; if those are unique, merge the
        # metadata without guessing a brand/parent.
        op_codes={(m["group"].upper(),m["productCode"].upper()) for m in ids.values()}
        if len(op_codes)!=1:
            continue
        metas=list(ids.values())
        brands={m.get("brand") or "" for m in metas if m.get("brand")}
        parents={m.get("parentAsin") or "" for m in metas if m.get("parentAsin")}
        base=metas[0].copy()
        base["brand"]=next(iter(brands)) if len(brands)==1 else ""
        base["parentAsin"]=next(iter(parents)) if len(parents)==1 else ""
        base["mappingStatus"]="campaign_prefix_exact"
        out[prefix]=base
    return out


def _data_revision() -> str:
    row = query_one("""
        SELECT COALESCE(max(batch_id),0)::bigint revision
        FROM core.import_batches
        WHERE target_table IN (
            'core.report_business_child_asin_daily',
            'core.report_business_parent_asin_period',
            'core.report_advertised_product_daily',
            'core.report_purchased_product_daily'
        )
    """) or {}
    revision = str(row.get("revision") or 0)
    update_context(revision=revision)
    return revision


def _complete_days_uncached(start: Optional[str] = None, end: Optional[str] = None) -> list[str]:
    """Dates with complete ads plus either complete child-business or legacy parent-business."""
    c_range = ""
    b_range = ""
    a_range = ""
    p_range = ""
    if start:
        c_range += f" AND stat_date >= DATE '{start}'"
        b_range += f" AND report_start_date >= DATE '{start}'"
        a_range += f" AND stat_date >= DATE '{start}'"
        p_range += f" AND stat_date >= DATE '{start}'"
    if end:
        c_range += f" AND stat_date <= DATE '{end}'"
        b_range += f" AND report_start_date <= DATE '{end}'"
        a_range += f" AND stat_date <= DATE '{end}'"
        p_range += f" AND stat_date <= DATE '{end}'"
    rows = query_rows(f"""
        WITH bc AS (
          SELECT stat_date AS d
          FROM core.report_business_child_asin_daily
          WHERE account_name IN ({_sql_names(BUSINESS_ACCOUNTS)}){c_range}
          GROUP BY stat_date
          HAVING count(DISTINCT account_name) = {len(BUSINESS_ACCOUNTS)}
        ), bp AS (
          SELECT report_start_date AS d
          FROM core.report_business_parent_asin_period
          WHERE report_start_date=report_end_date
            AND account_name IN ({_sql_names(BUSINESS_ACCOUNTS)}){b_range}
          GROUP BY report_start_date
          HAVING count(DISTINCT account_name) = {len(BUSINESS_ACCOUNTS)}
        ), b AS (
          SELECT d FROM bc UNION SELECT d FROM bp
        ), a AS (
          SELECT r.stat_date AS d
          FROM core.report_advertised_product_daily r
          JOIN core.import_batches ib ON ib.batch_id=r.batch_id
             AND ib.target_table='core.report_advertised_product_daily'
          WHERE r.account_name IN ({_sql_names(AD_ACCOUNTS)}){a_range.replace("stat_date","r.stat_date")}
          GROUP BY r.stat_date
          HAVING count(DISTINCT r.account_name) = {len(AD_ACCOUNTS)}
        ), p AS (
          SELECT r.stat_date AS d
          FROM core.report_purchased_product_daily r
          JOIN core.import_batches ib ON ib.batch_id=r.batch_id
             AND ib.target_table='core.report_purchased_product_daily'
          WHERE r.account_name IN ({_sql_names(AD_ACCOUNTS)}){p_range.replace("stat_date","r.stat_date")}
          GROUP BY r.stat_date
          HAVING count(DISTINCT r.account_name) = {len(AD_ACCOUNTS)}
        )
        SELECT b.d::text d FROM b JOIN a USING(d) JOIN p USING(d) ORDER BY b.d
    """)
    return [r["d"] for r in rows]


def _complete_days(
    start: Optional[str] = None,
    end: Optional[str] = None,
    revision: Optional[str] = None,
) -> list[str]:
    revision = revision or _data_revision()
    return build_cache.get_or_set_complete_days(
        start,
        end,
        revision,
        lambda: _complete_days_uncached(start, end),
    )


def _date_filter(column: str, days: list[str]) -> str:
    if not days:
        return "1=0"
    return f"{column} IN (" + ",".join(f"DATE '{d}'" for d in days) + ")"


def _source_days(start: str, end: str, revision: Optional[str] = None) -> dict[str, Any]:
    days = _complete_days(start, end, revision)
    start_day, end_day = date.fromisoformat(start), date.fromisoformat(end)
    rows = query_rows(f"""
        SELECT 'businessChild' AS source, stat_date::text AS d, array_agg(DISTINCT account_name ORDER BY account_name) AS accounts
        FROM core.report_business_child_asin_daily
        WHERE stat_date BETWEEN DATE '{start}' AND DATE '{end}' AND account_name IN ({_sql_names(BUSINESS_ACCOUNTS)})
        GROUP BY stat_date
        UNION ALL
        SELECT 'businessParent', report_start_date::text, array_agg(DISTINCT account_name ORDER BY account_name)
        FROM core.report_business_parent_asin_period
        WHERE report_start_date=report_end_date AND report_start_date BETWEEN DATE '{start}' AND DATE '{end}'
          AND account_name IN ({_sql_names(BUSINESS_ACCOUNTS)}) GROUP BY report_start_date
        UNION ALL
        SELECT 'advertisedProduct', r.stat_date::text, array_agg(DISTINCT r.account_name ORDER BY r.account_name)
        FROM core.report_advertised_product_daily r JOIN core.import_batches ib ON ib.batch_id=r.batch_id
          AND ib.target_table='core.report_advertised_product_daily'
        WHERE r.stat_date BETWEEN DATE '{start}' AND DATE '{end}' AND r.account_name IN ({_sql_names(AD_ACCOUNTS)})
        GROUP BY r.stat_date
        UNION ALL
        SELECT 'purchasedProduct', r.stat_date::text, array_agg(DISTINCT r.account_name ORDER BY r.account_name)
        FROM core.report_purchased_product_daily r JOIN core.import_batches ib ON ib.batch_id=r.batch_id
          AND ib.target_table='core.report_purchased_product_daily'
        WHERE r.stat_date BETWEEN DATE '{start}' AND DATE '{end}' AND r.account_name IN ({_sql_names(AD_ACCOUNTS)})
        GROUP BY r.stat_date
    """)
    availability = {(row['source'], row['d']): set(row.get('accounts') or []) for row in rows}
    dates = [(start_day + timedelta(days=n)).isoformat() for n in range((end_day - start_day).days + 1)]
    complete: dict[str, list[str]] = {source: [] for source in ('business', 'advertisedProduct', 'purchasedProduct')}
    missing: dict[str, dict[str, list[str]]] = {source: {} for source in complete}
    for day in dates:
        child = availability.get(('businessChild', day), set())
        parent = availability.get(('businessParent', day), set())
        # Never combine partially covered child and parent reports into a
        # complete business date; this mirrors the CPO denominator fallback.
        business = child if set(BUSINESS_ACCOUNTS) <= child else parent if set(BUSINESS_ACCOUNTS) <= parent else max((child, parent), key=len)
        for source, expected, actual in (
            ('business', BUSINESS_ACCOUNTS, business),
            ('advertisedProduct', AD_ACCOUNTS, availability.get(('advertisedProduct', day), set())),
            ('purchasedProduct', AD_ACCOUNTS, availability.get(('purchasedProduct', day), set())),
        ):
            absent = sorted(set(expected) - actual)
            if absent:
                missing[source][day] = absent
            else:
                complete[source].append(day)
    return {
        "advertisedProductDays": len(complete['advertisedProduct']),
        "purchasedProductDays": len(complete['purchasedProduct']),
        "businessDays": len(complete['business']),
        "completeDays": len(days),
        "completeDates": days,
        "sourceDates": complete,
        "sourceMissingDates": {source: list(absent) for source, absent in missing.items()},
        "missingAccountsByDate": missing,
    }


def operator_period_options() -> dict[str, Any]:
    days = list(reversed(_complete_days()))
    daily = [{"value": d, "label": d, "start": d, "end": d} for d in days]
    weekly, seen_w = [], set()
    monthly, seen_m = [], set()
    for d in days:
        dt = date.fromisoformat(d)
        monday = dt - timedelta(days=dt.weekday())
        wk = monday.isoformat()
        if wk not in seen_w:
            seen_w.add(wk)
            sunday = monday + timedelta(days=6)
            weekly.append({"value": wk, "label": f"{wk} ~ {sunday.isoformat()}（周）", "start": wk, "end": sunday.isoformat()})
        mk = dt.replace(day=1).isoformat()
        if mk not in seen_m:
            seen_m.add(mk)
            nxt = (dt.replace(day=1) + timedelta(days=32)).replace(day=1)
            month_end = (nxt - timedelta(days=1)).isoformat()
            monthly.append({"value": mk, "label": mk[:7], "start": mk, "end": month_end})
    return {
        "daily": daily, "weekly": weekly, "monthly": monthly,
        "latestDate": days[0] if days else None, "weekRule": "周一至周日",
        "note": "仅列出业务报告 + 推广的商品 + 达成转化的商品三项都完整的日期；缺任一来源的日期不进入最终 CPO。",
    }


def _new_product(meta: dict[str, str]) -> dict[str, Any]:
    return {
        "code": meta["productCode"], "group": meta["group"], "operatorName": meta["operatorName"],
        "brand": meta.get("brand") or "", "mappingStatus": meta.get("mappingStatus") or "confirmed",
        "parentAsins": set(), "businessAccounts": set(), "adAccounts": set(),
        "title": "", "spend": 0.0, "adOrders": 0.0, "adPurchases": 0.0, "adSales": 0.0,
        "totalOrders": 0.0, "totalSales": 0.0, "sessions": 0.0,
        "businessRows": 0, "adRows": 0, "purchasedRows": 0,
        "purchasedValidationOrders": 0.0, "purchasedValidationSales": 0.0,
        "adTypeSpend": {k: 0.0 for k in AD_TYPES},
        "adTypeOrders": {k: 0.0 for k in AD_TYPES},
    }


def _build_uncached(start: str, end: str, revision: Optional[str] = None) -> dict[str, Any]:
    revision = revision or _data_revision()
    parent_mapping = _mapping()
    child_mapping = _child_mapping()
    blocked_child_keys = {
        (r["account_scope"], r["child_asin"])
        for r in app_query_rows("""
            SELECT account_scope, child_asin
            FROM app.child_asin_mapping
            WHERE mapping_status='blocked_conflict'
              AND child_asin IS NOT NULL AND child_asin<>''
        """)
    }
    direct_prefix_scopes = _direct_prefix_scopes()
    campaign_prefix_identities = _campaign_prefix_identity_map(parent_mapping, child_mapping)
    campaign_prefix_mapping_scopes: dict[str, set[str]] = defaultdict(set)
    for (scope, _child), meta in child_mapping.items():
        group=(meta.get("group") or "").strip().upper()
        code=(meta.get("productCode") or "").strip().upper()
        if scope and group and code:
            campaign_prefix_mapping_scopes[f"{group}-{code}"].add(scope)
    portfolio = _portfolio(parent_mapping)
    complete_days = _complete_days(start, end, revision)

    # A date uses exactly one business denominator source: child if all seller
    # accounts have child facts, otherwise the entire date falls back to legacy parent.
    child_day_rows = query_rows(f"""
        SELECT stat_date::text d
        FROM core.report_business_child_asin_daily
        WHERE account_name IN ({_sql_names(BUSINESS_ACCOUNTS)})
          AND {_date_filter("stat_date", complete_days)}
        GROUP BY stat_date
        HAVING count(DISTINCT account_name) = {len(BUSINESS_ACCOUNTS)}
    """) if complete_days else []
    child_days = {r["d"] for r in child_day_rows}
    parent_days = [d for d in complete_days if d not in child_days]

    products: dict[tuple[str, str, str], dict[str, Any]] = {}

    def bucket(meta: dict[str, str], account_scope: str) -> dict[str, Any]:
        # Product code may repeat across operators/accounts, so both boundaries
        # remain in the key. Parent is only a relationship snapshot/audit field.
        key = (account_scope, meta["group"], meta["productCode"])
        if key not in products:
            products[key] = _new_product(meta)
            products[key]["accountScope"] = account_scope
            products[key]["allocationMethods"] = set()
            products[key]["childAsins"] = set()
        return products[key]

    def child_meta(account_scope: str, child: str) -> Optional[dict[str, str]]:
        if not child or child in ("-1",) or child.startswith("__"):
            return None
        return child_mapping.get((account_scope, child))

    def resolve_meta(account_scope: str, child: str, parent: str) -> tuple[Optional[dict[str, str]], str]:
        cm = child_meta(account_scope, child)
        if cm:
            return cm, "child_exact"
        pm = parent_mapping.get(parent) if parent not in (None, "", "-1") else None
        if pm:
            return pm, "parent_fallback"
        return None, "unmapped"

    business_mapping_conflict_orders = 0.0
    business_mapping_conflict_parents: set[str] = set()
    business_out_of_scope_orders = 0.0
    business_out_of_scope_parents: set[str] = set()
    business_audit = {
        "childRows": 0, "childExactRows": 0, "parentFallbackRows": 0,
        "mappingConflictRows": 0, "outOfScopeRows": 0,
        "childDays": len(child_days), "parentFallbackDays": len(parent_days),
    }

    if child_days:
        business_rows = query_rows(f"""
            SELECT account_id, account_name, child_asin, parent_asin, max(title) title,
                   COALESCE(sum(ordered_product_units),0)::float8 total_orders,
                   COALESCE(sum(ordered_product_sales),0)::float8 total_sales,
                   COALESCE(sum(sessions_total),0)::float8 sessions, count(*)::int rows
            FROM core.report_business_child_asin_daily
            WHERE account_name IN ({_sql_names(BUSINESS_ACCOUNTS)})
              AND {_date_filter("stat_date", sorted(child_days))}
            GROUP BY account_id,account_name,child_asin,parent_asin
        """)
        for row in business_rows:
            business_audit["childRows"] += int(row.get("rows") or 0)
            account_scope = row.get("account_name") or ""
            meta, method = resolve_meta(account_scope, row.get("child_asin") or "", row.get("parent_asin") or "")
            if not meta:
                key=(account_scope, row.get("child_asin") or "")
                if key in blocked_child_keys:
                    business_audit["mappingConflictRows"] += int(row.get("rows") or 0)
                    business_mapping_conflict_orders += float(row.get("total_orders") or 0)
                    if row.get("parent_asin"):
                        business_mapping_conflict_parents.add(row["parent_asin"])
                else:
                    # Product whitelist rule: business rows with no confirmed
                    # Child/Parent identity are outside the maintained product
                    # portfolio intersection. Disclose them, but do not force
                    # them into an operator or the CPO denominator.
                    business_audit["outOfScopeRows"] += int(row.get("rows") or 0)
                    business_out_of_scope_orders += float(row.get("total_orders") or 0)
                    if row.get("parent_asin"):
                        business_out_of_scope_parents.add(row["parent_asin"])
                continue
            if method == "child_exact":
                business_audit["childExactRows"] += int(row.get("rows") or 0)
            else:
                business_audit["parentFallbackRows"] += int(row.get("rows") or 0)
            p = bucket(meta, account_scope)
            if row.get("child_asin"): p["childAsins"].add(row["child_asin"])
            if row.get("parent_asin"): p["parentAsins"].add(row["parent_asin"])
            p["allocationMethods"].add(method)
            p["businessAccounts"].add(account_scope or row.get("account_id") or "")
            p["title"] = p["title"] or (row.get("title") or "")
            p["totalOrders"] += float(row.get("total_orders") or 0)
            p["totalSales"] += float(row.get("total_sales") or 0)
            p["sessions"] += float(row.get("sessions") or 0)
            p["businessRows"] += int(row.get("rows") or 0)

    if parent_days:
        legacy_rows = query_rows(f"""
            SELECT account_id, max(account_name) account_name, parent_asin, max(title) title,
                   COALESCE(sum(ordered_product_units),0)::float8 total_orders,
                   COALESCE(sum(ordered_product_sales),0)::float8 total_sales,
                   COALESCE(sum(sessions_total),0)::float8 sessions, count(*)::int rows
            FROM core.report_business_parent_asin_period
            WHERE report_start_date=report_end_date
              AND account_name IN ({_sql_names(BUSINESS_ACCOUNTS)})
              AND {_date_filter("report_start_date", parent_days)}
            GROUP BY account_id,parent_asin
        """)
        for row in legacy_rows:
            meta = parent_mapping.get(row.get("parent_asin"))
            if not meta:
                business_audit["outOfScopeRows"] += int(row.get("rows") or 0)
                business_out_of_scope_orders += float(row.get("total_orders") or 0)
                if row.get("parent_asin"):
                    business_out_of_scope_parents.add(row["parent_asin"])
                continue
            account_scope = row.get("account_name") or ""
            p = bucket(meta, account_scope)
            p["parentAsins"].add(row["parent_asin"])
            p["allocationMethods"].add("legacy_parent_business")
            p["businessAccounts"].add(account_scope or row.get("account_id") or "")
            p["title"] = p["title"] or (row.get("title") or "")
            p["totalOrders"] += float(row.get("total_orders") or 0)
            p["totalSales"] += float(row.get("total_sales") or 0)
            p["sessions"] += float(row.get("sessions") or 0)
            p["businessRows"] += int(row.get("rows") or 0)

    # Business-presence maps resolve AMS ad-only rows to a seller scope.
    child_scopes_by_day: dict[tuple[str, str], set[str]] = defaultdict(set)
    parent_scopes_by_day: dict[tuple[str, str], set[str]] = defaultdict(set)
    if child_days:
        rows = query_rows(f"""
            SELECT stat_date::text stat_date, child_asin, parent_asin, account_name
            FROM core.report_business_child_asin_daily
            WHERE account_name IN ({_sql_names(BUSINESS_ACCOUNTS)})
              AND {_date_filter("stat_date", sorted(child_days))}
            GROUP BY stat_date,child_asin,parent_asin,account_name
        """)
        for row in rows:
            scope=row.get("account_name"); day=row.get("stat_date")
            if scope and day and row.get("child_asin"):
                child_scopes_by_day[(day,row["child_asin"])].add(scope)
            if scope and day and row.get("parent_asin"):
                parent_scopes_by_day[(day,row["parent_asin"])].add(scope)
    if parent_days:
        rows = query_rows(f"""
            SELECT report_start_date::text stat_date, parent_asin, account_name
            FROM core.report_business_parent_asin_period
            WHERE report_start_date=report_end_date
              AND account_name IN ({_sql_names(BUSINESS_ACCOUNTS)})
              AND {_date_filter("report_start_date", parent_days)}
            GROUP BY report_start_date,parent_asin,account_name
        """)
        for row in rows:
            if row.get("account_name") and row.get("stat_date") and row.get("parent_asin"):
                parent_scopes_by_day[(row["stat_date"],row["parent_asin"])].add(row["account_name"])

    ams_scope_audit = {"prefix_exact":0,"child_fallback":0,"parent_fallback":0,"mapping_scope_fallback":0,"conflict":0,"unmapped":0}

    def _unique_business_scope_from_fact(child: str, parent: str, stat_day: str) -> tuple[str, str]:
        if child and child not in ("-1",) and not child.startswith("__"):
            scopes = child_scopes_by_day.get((stat_day, child), set())
            if len(scopes) == 1:
                return next(iter(scopes)), "child_fallback"
            if len(scopes) > 1:
                return "__AMS_SCOPE_CONFLICT__", "conflict"
        scopes = parent_scopes_by_day.get((stat_day, parent), set())
        if len(scopes) == 1:
            return next(iter(scopes)), "parent_fallback"
        if len(scopes) > 1:
            return "__AMS_SCOPE_CONFLICT__", "conflict"
        return "__AMS_NO_BUSINESS__", "unmapped"

    def resolve_ad_scope(ad_account: str, child: str, parent: str, stat_day: str, campaign_name: str = "") -> str:
        direct = DIRECT_AD_TO_BUSINESS.get(ad_account)
        if direct:
            return direct
        if ad_account in AMS_AD_ACCOUNTS:
            prefix = _campaign_prefix(campaign_name)
            prefix_scopes = direct_prefix_scopes.get(prefix, set()) if prefix else set()
            fact_scope, fact_method = _unique_business_scope_from_fact(child, parent, stat_day)

            if len(prefix_scopes) > 1:
                ams_scope_audit["conflict"] += 1
                return "__AMS_SCOPE_CONFLICT__"
            if len(prefix_scopes) == 1:
                scope = next(iter(prefix_scopes))
                if fact_scope and not fact_scope.startswith("__AMS_") and fact_scope != scope:
                    ams_scope_audit["conflict"] += 1
                    return "__AMS_SCOPE_CONFLICT__"
                ams_scope_audit["prefix_exact"] += 1
                return scope

            if fact_method in ("child_fallback","parent_fallback"):
                ams_scope_audit[fact_method] += 1
                return fact_scope
            if fact_method == "conflict":
                ams_scope_audit["conflict"] += 1
                return fact_scope

            mapping_scopes=campaign_prefix_mapping_scopes.get(prefix,set()) if prefix else set()
            if len(mapping_scopes)==1:
                ams_scope_audit["mapping_scope_fallback"] += 1
                return next(iter(mapping_scopes))
            if len(mapping_scopes)>1:
                ams_scope_audit["conflict"] += 1
                return "__AMS_SCOPE_CONFLICT__"

            ams_scope_audit["unmapped"] += 1
            return "__AMS_NO_BUSINESS__"
        return ""


    ad_rows = query_rows(f"""
        SELECT r.stat_date::text stat_date, r.account_id, r.account_name,
               r.campaign_name, r.advertised_product_id child_asin, r.advertised_product_parent_id parent_asin, r.ad_product,
               COALESCE(sum(r.spend),0)::float8 spend,
               COALESCE(sum(r.units),0)::float8 ad_orders,
               COALESCE(sum(r.purchases),0)::float8 ad_purchases,
               COALESCE(sum(r.sales),0)::float8 ad_sales, count(*)::int rows
        FROM core.report_advertised_product_daily r
        JOIN core.import_batches ib ON ib.batch_id=r.batch_id
           AND ib.target_table='core.report_advertised_product_daily'
        WHERE r.account_name IN ({_sql_names(AD_ACCOUNTS)})
          AND {_date_filter("r.stat_date", complete_days)}
        GROUP BY r.stat_date,r.account_id,r.account_name,r.campaign_name,r.advertised_product_id,r.advertised_product_parent_id,r.ad_product
    """)
    unmapped_ad = {"spend":0.0,"orders":0.0,"sales":0.0,"parents":set(),"rows":0}
    unknown_ad_types: set[str] = set()
    ad_audit={"childExactRows":0,"parentFallbackRows":0,"campaignPrefixRows":0,"unmappedRows":0,"ambiguousScopeRows":0}
    for row in ad_rows:
        parent=row.get("parent_asin") or ""; child=row.get("child_asin") or ""
        ad_account=row.get("account_name") or ""
        account_scope=resolve_ad_scope(ad_account,child,parent,row.get("stat_date") or "",row.get("campaign_name") or "")
        if not account_scope or account_scope.startswith("__AMS_"):
            ad_audit["ambiguousScopeRows"] += int(row.get("rows") or 0)
            unmapped_ad["spend"] += float(row.get("spend") or 0); unmapped_ad["orders"] += float(row.get("ad_orders") or 0); unmapped_ad["sales"] += float(row.get("ad_sales") or 0); unmapped_ad["rows"] += int(row.get("rows") or 0)
            if parent: unmapped_ad["parents"].add(parent)
            continue
        meta,method=resolve_meta(account_scope,child,parent)
        if not meta:
            prefix=_campaign_prefix(row.get("campaign_name") or "")
            prefix_meta=campaign_prefix_identities.get(prefix) if prefix else None
            if prefix_meta:
                meta=prefix_meta
                method="campaign_prefix_exact"
        if not meta:
            ad_audit["unmappedRows"] += int(row.get("rows") or 0)
            unmapped_ad["spend"] += float(row.get("spend") or 0); unmapped_ad["orders"] += float(row.get("ad_orders") or 0); unmapped_ad["sales"] += float(row.get("ad_sales") or 0); unmapped_ad["rows"] += int(row.get("rows") or 0)
            if parent: unmapped_ad["parents"].add(parent)
            continue
        if method=="child_exact":
            ad_audit["childExactRows"] += int(row.get("rows") or 0)
        elif method=="parent_fallback":
            ad_audit["parentFallbackRows"] += int(row.get("rows") or 0)
        else:
            ad_audit["campaignPrefixRows"] += int(row.get("rows") or 0)
        p=bucket(meta,account_scope)
        if child and child not in ("-1",) and not child.startswith("__"): p["childAsins"].add(child)
        if parent: p["parentAsins"].add(parent)
        p["allocationMethods"].add(method)
        p["adAccounts"].add(ad_account or row.get("account_id") or "")
        spend=float(row.get("spend") or 0); orders=float(row.get("ad_orders") or 0)
        p["spend"] += spend; p["adOrders"] += orders; p["adPurchases"] += float(row.get("ad_purchases") or 0); p["adSales"] += float(row.get("ad_sales") or 0); p["adRows"] += int(row.get("rows") or 0)
        ad_type=_classify_ad_type(row.get("ad_product") or "")
        if ad_type in AD_TYPES:
            p["adTypeSpend"][ad_type] += spend; p["adTypeOrders"][ad_type] += orders
        else:
            unknown_ad_types.add(row.get("ad_product") or "")

    # Purchased-product remains attribution validation. SB-collection purchased-ASIN
    # cost allocation is deliberately not claimed as implemented here.
    purchased_rows = query_rows(f"""
        SELECT r.stat_date::text stat_date, r.account_id, r.account_name, r.campaign_name,
               r.advertised_product_id child_asin, r.advertised_product_parent_id parent_asin,
               COALESCE(sum(r.purchases),0)::float8 purchases,
               COALESCE(sum(r.sales),0)::float8 sales, count(*)::int rows
        FROM core.report_purchased_product_daily r
        JOIN core.import_batches ib ON ib.batch_id=r.batch_id
           AND ib.target_table='core.report_purchased_product_daily'
        WHERE r.account_name IN ({_sql_names(AD_ACCOUNTS)})
          AND {_date_filter("r.stat_date", complete_days)}
        GROUP BY r.stat_date,r.account_id,r.account_name,r.campaign_name,r.advertised_product_id,r.advertised_product_parent_id
    """)
    purchased_unmapped_rows=0
    for row in purchased_rows:
        parent=row.get("parent_asin") or ""; child=row.get("child_asin") or ""; ad_account=row.get("account_name") or ""
        scope=resolve_ad_scope(ad_account,child,parent,row.get("stat_date") or "",row.get("campaign_name") or "")
        if not scope or scope.startswith("__AMS_"):
            purchased_unmapped_rows += int(row.get("rows") or 0); continue
        meta,_=resolve_meta(scope,child,parent)
        if not meta:
            purchased_unmapped_rows += int(row.get("rows") or 0); continue
        p=bucket(meta,scope)
        p["purchasedRows"] += int(row.get("rows") or 0)
        p["purchasedValidationOrders"] += float(row.get("purchases") or 0)
        p["purchasedValidationSales"] += float(row.get("sales") or 0)

    # No synthetic mapping-only missing-business buckets: with child business
    # facts for all seller accounts, only real ad/business rows decide status.

    out=[]
    for p in products.values():
        has_business=p["businessRows"]>0; has_ad=p["adRows"]>0
        total_orders=p["totalOrders"]; total_sales=p["totalSales"]; spend=p["spend"]
        if has_business and has_ad: status="有数据"
        elif has_business: status="仅业务数据"
        elif p.get("mappingStatus")=="confirmed_no_business": status="缺业务报告"
        elif has_ad: status="缺业务侧"
        else: status="无数据"
        out.append({
            "code":p["code"],"group":p["group"],"operatorName":p["operatorName"],"brand":p.get("brand") or "",
            "mappingStatus":p.get("mappingStatus") or "confirmed",
            "parentAsin":" | ".join(sorted(p["parentAsins"])),"parentAsins":sorted(p["parentAsins"]),
            "childAsins":sorted(p.get("childAsins",set())),"allocationMethods":sorted(p.get("allocationMethods",set())),
            "title":p["title"] or p["code"],"businessAccounts":sorted(x for x in p["businessAccounts"] if x),
            "adAccounts":sorted(x for x in p["adAccounts"] if x),"spend":round(spend,2),
            "adOrders":round(p["adOrders"],2),"adPurchases":round(p["adPurchases"],2),"adSales":round(p["adSales"],2),
            "totalOrders":round(total_orders,2) if has_business else None,"totalSales":round(total_sales,2) if has_business else None,
            "cpo":round(spend/total_orders,2) if has_business and total_orders>0 else None,
            "roas":round(p["adSales"]/spend,2) if spend>0 else None,
            "tacos":round(spend/total_sales*100,2) if has_business and total_sales>0 else None,
            "sessions":round(p["sessions"],2) if has_business else None,"dataStatus":status,
            "adTypeSpend":{k:round(float(v),2) for k,v in p["adTypeSpend"].items()},
            "adTypeOrders":{k:round(float(v),2) for k,v in p["adTypeOrders"].items()},
            "purchasedValidationRows":p["purchasedRows"],"purchasedValidationOrders":round(p["purchasedValidationOrders"],2),
            "purchasedValidationSales":round(p["purchasedValidationSales"],2),"daily":[],"weekly":[],
        })
    out.sort(key=lambda r:(r["operatorName"],-r["spend"],r["code"]))
    business_source = "child_asin_daily" if complete_days and not parent_days else ("mixed_child_parent_fallback" if child_days else "legacy_parent_asin_daily")
    return {
        "products":out,"portfolio":portfolio,"unmappedAd":unmapped_ad,
        # Backward-compatible blocker field: only true mapping conflicts.
        "businessUnmappedOrders":round(business_mapping_conflict_orders,2),
        "businessUnmappedParents":sorted(business_mapping_conflict_parents),
        "businessMappingConflictOrders":round(business_mapping_conflict_orders,2),
        "businessMappingConflictParents":sorted(business_mapping_conflict_parents),
        "businessOutOfScopeOrders":round(business_out_of_scope_orders,2),
        "businessOutOfScopeParents":sorted(business_out_of_scope_parents),
        "purchasedUnmappedRows":purchased_unmapped_rows,"unknownAdTypes":sorted(unknown_ad_types),
        "mappingCount":len(parent_mapping),"childMappingCount":len(child_mapping),"sourceDays":_source_days(start,end,revision),
        "businessSource":business_source,"businessAudit":business_audit,"adMappingAudit":ad_audit,
        "amsScopeAudit":ams_scope_audit,"canonicalAdLineage":True,
    }


def _build(start: str, end: str) -> dict[str, Any]:
    revision = _data_revision()
    def loader():
        started = time.perf_counter()
        try:
            return _build_uncached(start, end, revision)
        finally:
            increment('build_ms', (time.perf_counter() - started) * 1000)
    return build_cache.get_or_set(
        start,
        end,
        revision,
        loader,
    )


def _summarize(data: dict[str, Any]) -> list[dict[str, Any]]:
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in data["products"]:
        by_name[p["operatorName"]].append(p)
    names = sorted(set(data["portfolio"]) | set(by_name))
    rows = []
    for name in names:
        ps = by_name.get(name, [])
        if not ps:
            continue
        business_ps = [p for p in ps if p["totalOrders"] is not None]
        missing_report_ps = [p for p in ps if p.get("mappingStatus") == "confirmed_no_business"]
        missing_business_spend = sum(p["spend"] for p in ps if p["totalOrders"] is None)
        spend = sum(p["spend"] for p in ps)
        ad_orders = sum(p["adOrders"] for p in ps)
        ad_sales = sum(p["adSales"] for p in ps)
        total_orders = sum(float(p["totalOrders"] or 0) for p in business_ps)
        total_sales = sum(float(p["totalSales"] or 0) for p in business_ps)
        groups = sorted({p["group"] for p in ps})
        if business_ps and missing_report_ps:
            status = "部分缺业务报告"
        elif business_ps and missing_business_spend > 0.005:
            status = "部分缺业务侧"
        elif business_ps:
            status = "已配对"
        elif missing_report_ps:
            status = "缺业务报告"
        elif spend > 0:
            status = "缺业务侧"
        else:
            status = "无当日数据"
        calculation_ok = bool(business_ps) and missing_business_spend <= 0.005
        final_ok = calculation_ok and not missing_report_ps
        rows.append({
            "name": name, "group": groups[0] if groups else "", "groups": groups,
            "spend": round(spend, 2), "adOrders": round(ad_orders, 2), "adSales": round(ad_sales, 2),
            "totalOrders": round(total_orders, 2) if business_ps else None, "totalSales": round(total_sales, 2) if business_ps else None,
            "cpo": round(spend / total_orders, 2) if calculation_ok and total_orders > 0 else None,
            "roas": round(ad_sales / spend, 2) if spend > 0 else None,
            "tacos": round(spend / total_sales * 100, 2) if calculation_ok and total_sales > 0 else None,
            "products": len(data["portfolio"].get(name, set())),
            "dataProducts": len({p["code"] for p in business_ps}),
            "missingBusinessProducts": len({(p["code"], p.get("parentAsin")) for p in missing_report_ps}),
            "status": status, "finalCpo": final_ok, "unpairedAdSpend": round(missing_business_spend, 2),
            "purchasedValidationOrders": round(sum(p["purchasedValidationOrders"] for p in ps), 2),
            "scope": "Child ASIN优先→产品代号→运营；缺Child映射时才安全回退Parent；账户边界保留。",
        })
    rows.sort(key=lambda r: -float(r["spend"] or 0))
    unmapped = data["unmappedAd"]
    if unmapped["spend"] > 0.005 or unmapped["orders"] > 0.005:
        rows.append({
            "name": "未归属", "group": "未归属", "groups": ["未归属"],
            "spend": round(unmapped["spend"], 2), "adOrders": round(unmapped["orders"], 2),
            "adSales": round(unmapped["sales"], 2), "totalOrders": None, "totalSales": None,
            "cpo": None, "roas": round(unmapped["sales"] / unmapped["spend"], 2) if unmapped["spend"] else None,
            "tacos": None, "products": len(unmapped["parents"]), "dataProducts": None,
            "status": "缺产品映射", "unpairedAdSpend": round(unmapped["spend"], 2),
            "scope": "无明确Child/Parent映射的数据不猜测归属，不进入任何运营CPO。",
        })
    return rows


def _latest_complete_date() -> Optional[str]:
    days = _complete_days()
    return days[-1] if days else None


def _quality_reasons(data: dict[str, Any], source: dict[str, Any], expected: int, period: str,
                     *, has_business: bool = True, missing_products: int = 0,
                     unpaired_spend: float = 0) -> list[str]:
    """Explain the existing final-CPO predicate without exposing global amounts."""
    reasons: list[str] = []
    complete = int(source.get("completeDays") or 0)
    if not complete:
        reasons.append("当前区间没有三项来源同时完整的可计算日期。")
    elif period != "daily" and complete != expected:
        reasons.append(f"三项来源同时完整日期覆盖 {complete}/{expected} 天；未覆盖日期不进入计算。")
    if not has_business:
        reasons.append("当前运营范围暂无可配对的业务侧订单记录，无法确认最终 CPO。")
    if missing_products:
        reasons.append(f"有 {missing_products} 个本组已确认产品缺业务侧记录，请核对产品清单。")
    if unpaired_spend > 0.005:
        reasons.append("本组部分广告花费尚未配对到业务侧订单，当前 CPO 不能认定为完整。")
    if float(data.get("unmappedAd", {}).get("spend") or 0) > 0.005:
        reasons.append("公司级广告产品归属尚未完成，最终 CPO 暂未确认；请由管理层核查未归属广告。")
    if float(data.get("businessUnmappedOrders") or 0) > 0.005:
        reasons.append("业务订单尚有未明确归属记录，最终 CPO 暂未确认；请由管理层核查产品映射与白名单。")
    return reasons


def operator_cpo_summary(stat_date: Optional[str] = None, period: str = "daily") -> dict[str, Any]:
    period = period if period in ("daily", "weekly", "monthly") else "daily"
    anchor = stat_date or _latest_complete_date()
    update_context(date=anchor, period=period)
    if not anchor:
        return {
            "data_source": "child_asin_first_three_report_cpo", "period": period,
            "operators": [], "coverageDays": 0, "expectedDays": 0, "account_split": False,
            "final_cpo": False, "note": "没有业务报告 + 推广的商品 + 达成转化的商品三项同时完整的日期。",
        }
    date.fromisoformat(anchor)
    start, end = _period_range(anchor, period)
    data = _build(start, end)
    rows = _summarize(data)
    expected = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    src = data["sourceDays"]
    complete_days = int(src.get("completeDays") or 0)
    mapping_clean = data["unmappedAd"]["spend"] <= 0.005 and data["businessUnmappedOrders"] <= 0.005
    period_complete = complete_days == expected
    final_cpo = bool(complete_days) and mapping_clean and (period == "daily" or period_complete)
    no_source_note = "" if complete_days else " 该区间没有三项来源同时完整的日期，因此不生成最终 CPO。"
    mapping_note = (
        " 当前仍有 $" + f"{data['unmappedAd']['spend']:.2f} 广告花费、"
        + f"{data['businessMappingConflictOrders']:.0f} 单业务订单存在映射冲突；页面 CPO 仅代表已明确映射部分，不作为最终单双。"
        if not mapping_clean else ""
    )
    whitelist_note = (
        f" 另有 {data['businessOutOfScopeOrders']:.0f} 单业务订单无法落入当前已确认产品白名单，"
        "已按“产品白名单 ∩ 当日业务报告”规则排除，不进入CPO分母；保留在质量审计中。"
        if data.get("businessOutOfScopeOrders", 0) > 0.005 else ""
    )
    return {
        "data_source": "child_asin_first_three_report_cpo", "data_date": anchor, "period": period,
        "period_start": start, "period_end": end, "coverageDays": complete_days, "expectedDays": expected,
        "account_split": True, "operators": rows, "sourceCompleteness": src, "final_cpo": final_cpo,
        "qualityReasons": _quality_reasons(data, src, expected, period),
        "mappingCount": data["mappingCount"], "childMappingCount": data.get("childMappingCount", 0),
        "businessSource": data.get("businessSource"), "businessAudit": data.get("businessAudit", {}),
        "adMappingAudit": data.get("adMappingAudit", {}),
        "businessUnmappedOrders": data["businessUnmappedOrders"],
        "businessMappingConflictOrders": data.get("businessMappingConflictOrders", 0),
        "businessOutOfScopeOrders": data.get("businessOutOfScopeOrders", 0),
        "businessOutOfScopeParents": data.get("businessOutOfScopeParents", []),
        "unmappedAdSpend": round(data["unmappedAd"]["spend"], 2),
        "excludedAdAccounts": [],
        "note": (
            f"{start}~{end}：只使用三项来源同时完整的日期。业务分母优先子ASIN日报，整日缺child才回退旧Parent报告；"
            f"BLOOMNEXT/JOOMRA DIRECT按同名业务账户配对；AMS/anac1973按广告活动前缀与大账户唯一匹配；无前缀匹配时才按同日Child/Parent业务账户唯一回退，冲突不猜。"
            f" 推广商品优先Child ASIN归属花费/广告单；达成转化商品当前仍作为独立校验，SB集合特殊分摊另行实现。"
            + no_source_note + mapping_note + whitelist_note
        ),
        "qualityFlags": [
            "three_source_complete_dates_only", "business_ad_account_pairing",
            "child_asin_mapping_first", "parent_mapping_fallback", "account_scoped_mapping", "ams_campaign_prefix_scope", "canonical_ad_lineage_only", "exact_product_code_no_suffix_stripping",
            "purchased_product_validation_separate", "business_whitelist_intersection", "out_of_scope_business_audited", "no_campaign_name_inference",
        ],
    }


def _merge_detail_products(products: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge account-boundary buckets for display only, after safe per-boundary pairing."""
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    for src in products:
        key = (src.get("group") or "", src.get("code") or "", src.get("parentAsin") or "")
        if key not in merged:
            row = dict(src)
            row["businessAccounts"] = list(src.get("businessAccounts") or [])
            row["adAccounts"] = list(src.get("adAccounts") or [])
            row["_has_business"] = src.get("totalOrders") is not None
            row["_has_missing_business_spend"] = (
                src.get("totalOrders") is None and float(src.get("spend") or 0) > 0.005
            )
            merged[key] = row
            continue
        row = merged[key]
        row["spend"] = round(float(row.get("spend") or 0) + float(src.get("spend") or 0), 2)
        row["adOrders"] = round(float(row.get("adOrders") or 0) + float(src.get("adOrders") or 0), 2)
        row["adSales"] = round(float(row.get("adSales") or 0) + float(src.get("adSales") or 0), 2)
        for field in ("totalOrders", "totalSales", "sessions"):
            if src.get(field) is not None:
                row[field] = round(float(row.get(field) or 0) + float(src.get(field) or 0), 2)
        row["purchasedValidationRows"] = int(row.get("purchasedValidationRows") or 0) + int(src.get("purchasedValidationRows") or 0)
        row["purchasedValidationOrders"] = round(
            float(row.get("purchasedValidationOrders") or 0) + float(src.get("purchasedValidationOrders") or 0), 2
        )
        row["purchasedValidationSales"] = round(
            float(row.get("purchasedValidationSales") or 0) + float(src.get("purchasedValidationSales") or 0), 2
        )
        row["businessAccounts"] = sorted(set(row["businessAccounts"]) | set(src.get("businessAccounts") or []))
        row["adAccounts"] = sorted(set(row["adAccounts"]) | set(src.get("adAccounts") or []))
        for field in ("adTypeSpend", "adTypeOrders"):
            for ad_type in AD_TYPES:
                a = row.get(field, {}).get(ad_type)
                b = src.get(field, {}).get(ad_type)
                if a is not None or b is not None:
                    row[field][ad_type] = round(float(a or 0) + float(b or 0), 2)
        row["_has_business"] = bool(row.get("_has_business")) or src.get("totalOrders") is not None
        row["_has_missing_business_spend"] = bool(row.get("_has_missing_business_spend")) or (
            src.get("totalOrders") is None and float(src.get("spend") or 0) > 0.005
        )

    out = []
    for row in merged.values():
        has_business = bool(row.pop("_has_business", False))
        has_missing = bool(row.pop("_has_missing_business_spend", False))
        spend = float(row.get("spend") or 0)
        orders = float(row.get("totalOrders") or 0) if row.get("totalOrders") is not None else 0
        sales = float(row.get("totalSales") or 0) if row.get("totalSales") is not None else 0
        if has_business and has_missing:
            row["dataStatus"] = "部分缺业务侧"
        elif has_business:
            row["dataStatus"] = "有数据" if spend > 0 else "仅业务数据"
        elif row.get("mappingStatus") == "confirmed_no_business":
            row["dataStatus"] = "缺业务报告"
        elif spend > 0:
            row["dataStatus"] = "缺业务侧"
        else:
            row["dataStatus"] = "无数据"
        row["cpo"] = round(spend / orders, 2) if has_business and not has_missing and orders > 0 else None
        row["tacos"] = round(spend / sales * 100, 2) if has_business and not has_missing and sales > 0 else None
        row["roas"] = round(float(row.get("adSales") or 0) / spend, 2) if spend > 0 else None
        out.append(row)
    out.sort(key=lambda p: (-float(p.get("spend") or 0), p.get("code") or "", p.get("parentAsin") or ""))
    return out


def canonical_operator_name(name: Optional[str]) -> str:
    """Accept either a real operator name or an internal group code such as LW/LW1."""
    raw = (name or "").strip()
    prefix = raw.upper()[:2]
    return OPERATOR_NAMES.get(prefix, raw)


def operator_cpo_detail(name: str, stat_date: Optional[str] = None, period: str = "daily") -> dict[str, Any]:
    name = canonical_operator_name(name)
    period = period if period in ("daily", "weekly", "monthly") else "daily"
    anchor = stat_date or _latest_complete_date()
    update_context(date=anchor, period=period)
    if not anchor:
        return {
            "data_source": "explicit_parent_mapping_three_report_cpo", "operator": name,
            "products": [], "summary": {}, "account_split": False, "final_cpo": False,
        }
    date.fromisoformat(anchor)
    start, end = _period_range(anchor, period)
    data = _build(start, end)
    raw_ps = [p for p in data["products"] if p["operatorName"] == name]
    portfolio_count = len(data["portfolio"].get(name, set()))
    business_ps_raw = [p for p in raw_ps if p["totalOrders"] is not None]
    missing_business_spend = sum(p["spend"] for p in raw_ps if p["totalOrders"] is None)
    ps = _merge_detail_products(raw_ps)
    business_ps = [p for p in ps if p["totalOrders"] is not None]
    missing_report_ps = [p for p in ps if p.get("mappingStatus") == "confirmed_no_business"]
    spend = sum(p["spend"] for p in raw_ps)
    ad_orders = sum(p["adOrders"] for p in raw_ps)
    ad_sales = sum(p["adSales"] for p in raw_ps)
    total_orders = sum(float(p["totalOrders"] or 0) for p in business_ps_raw)
    total_sales = sum(float(p["totalSales"] or 0) for p in business_ps_raw)
    src = data["sourceDays"]
    expected = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    complete_days = int(src.get("completeDays") or 0)
    final_ok = (
        bool(business_ps_raw)
        and complete_days > 0
        and missing_business_spend <= 0.005
        and data["unmappedAd"]["spend"] <= 0.005
        and data["businessUnmappedOrders"] <= 0.005
        and not missing_report_ps
        and (period == "daily" or complete_days == expected)
    )
    return {
        "data_source": "explicit_parent_mapping_three_report_cpo", "operator": name,
        "groups": sorted({p["group"] for p in raw_ps}), "account": "已配对业务/广告账户合并",
        "range": anchor if period == "daily" else f"{start}~{end}", "data_date": anchor, "period": period,
        "period_start": start, "period_end": end, "coverageDays": complete_days, "expectedDays": expected,
        "account_split": False, "final_cpo": final_ok, "allocation_status": "explicit_parent_asin_mapping",
        "qualityReasons": _quality_reasons(data, src, expected, period, has_business=bool(business_ps_raw),
             missing_products=len({(p["code"], p.get("parentAsin")) for p in missing_report_ps}),
             unpaired_spend=missing_business_spend),
        "summary": {
            "spend": round(spend, 2), "adOrders": round(ad_orders, 2), "adSales": round(ad_sales, 2),
            "totalOrders": round(total_orders, 2) if business_ps_raw else None,
            "totalSales": round(total_sales, 2) if business_ps_raw else None,
            "cpo": round(spend / total_orders, 2) if business_ps_raw and missing_business_spend <= 0.005 and total_orders > 0 else None,
            "roas": round(ad_sales / spend, 2) if spend > 0 else None,
            "tacos": round(spend / total_sales * 100, 2) if business_ps_raw and missing_business_spend <= 0.005 and total_sales > 0 else None,
            "products": portfolio_count, "dataProducts": len({p["code"] for p in business_ps}),
            "missingBusinessProducts": len({(p["code"], p.get("parentAsin")) for p in missing_report_ps}),
            "unpairedAdSpend": round(missing_business_spend, 2),
            "purchasedValidationOrders": round(sum(p["purchasedValidationOrders"] for p in raw_ps), 2),
        },
        "products": ps, "sourceCompleteness": src,
        "businessMappingConflictOrders": data.get("businessMappingConflictOrders", 0),
        "businessOutOfScopeOrders": data.get("businessOutOfScopeOrders", 0),
        "warning": (
            "只使用三项来源同时完整的日期；业务侧按已确认产品白名单与当日Child业务报告取交集，"
            "无确认身份的业务商品不猜运营、不进入CPO分母，但保留质量审计。"
            "广告侧未归属花费或明确映射冲突仍会阻断最终CPO。"
        ),
        "qualityFlags": [
            "three_source_complete_dates_only", "business_ad_account_pairing",
            "child_asin_mapping_first", "parent_mapping_fallback", "account_scoped_mapping", "ams_campaign_prefix_scope", "canonical_ad_lineage_only", "exact_product_code_no_suffix_stripping",
            "purchased_product_validation_separate", "business_whitelist_intersection", "out_of_scope_business_audited", "no_campaign_name_inference",
        ],
    }


def operator_group_of(operator_code: Optional[str]) -> str:
    raw = (operator_code or "").strip().upper()
    return raw[:2] if re.fullmatch(r'[A-Z]{2}[0-9]+', raw) and raw[:2] in OPERATOR_NAMES else ''


def my_cpo_summary(
    operator_code: Optional[str],
    stat_date: Optional[str] = None,
    period: str = "daily",
    display_name: Optional[str] = None,
) -> dict[str, Any]:
    """Operator view reuses the same management CPO service, filtered only by group."""
    prefix = operator_group_of(operator_code)
    if not prefix:
        raise HTTPException(status_code=403, detail='An active operator group is required')
    data = operator_cpo_summary(stat_date, period)
    group_name = OPERATOR_NAMES.get(prefix, prefix)
    rows = [
        r for r in data.get("operators", [])
        if any(str(g or "").upper()[:2] == prefix for g in (r.get("groups") or [r.get("group")]))
    ]
    detail = operator_cpo_detail(group_name, data.get("data_date") or stat_date, period)
    me = {
        "operatorCode": (operator_code or "").strip().upper(),
        "group": prefix, "groupName": group_name,
        "name": (display_name or "").strip() or group_name,
    }
    return {
        **{key: data[key] for key in ('data_source', 'data_date', 'period', 'period_start', 'period_end',
           'coverageDays', 'expectedDays', 'account_split', 'sourceCompleteness', 'qualityFlags') if key in data},
        "operators": rows,
        "me": me,
        "products": detail.get("products", []),
        "detailSummary": detail.get("summary", {}),
        "final_cpo": bool(detail.get("final_cpo")),
        "qualityReasons": detail.get("qualityReasons", []),
        "scope": "own_operator_group_all_paired_accounts",
        "note": (
            f"{me['name']} 登录 → {prefix} 运营组 → 本组全部 ASIN；组内成员共享同一组数据。 "
            + "只使用业务报告、推广商品报告、达成转化商品报告三项完整日期；仅展示本组已确认产品。"
        ),
    }
