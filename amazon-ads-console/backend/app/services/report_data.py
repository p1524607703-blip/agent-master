"""业务数据服务：全部查询走「一份报告一张表」的新事实层。

数据仓库 amazon_ads_v2 中的事实表：
  core.report_campaign_daily                广告活动报告
  core.report_placement_daily               广告位报告
  core.report_targeting_daily               投放报告
  core.report_advertised_product_daily      推广的商品报告
  core.report_purchased_product_daily       达成转化的商品报告（无 spend/impressions —— 转化侧）
  core.report_search_term_daily             搜索词报告
  core.report_business_parent_asin_period   业务报告「按父商品」（Seller Central，CPO 分母来源）

应用库 amazon_ads 中的主数据：
  app.product_roster                        在售产品主数据（款号 ↔ 运营组）

口径纪律（本模块强制遵守）：
  1. 投放指标（花费/展示/点击）只能取 report_campaign_daily 或 report_targeting_daily，
     绝不同时 SUM 两张表 —— 它们是同一事实的不同切面，相加会重复计数。
  2. report_purchased_product_daily 没有花费列，天然不可能被拿来算 ACOS。
  3. 业务侧指标（全部订单 / 总销售额 / CPO / TACOS）来自业务报告，按**父 ASIN** 与广告侧配对。
     ⚠️ 广告账户（anac1973）与业务报告的 Seller 账户（WHITIN / BLOOMNEXT）不是同一个 ID，
     配对只能靠 ASIN，不能靠 account_id —— 这一条用质量标记 `ad_business_account_mismatch` 对外显式声明。
     业务报告缺失的日期/ASIN 一律返回 None，绝不用假数填充。

运营归属桥（parent ASIN → 运营组）：
  广告活动名第 2 段带款号（如 `ZJ1-W30 头条 低价` → 款号 `W30`），
  而款号在 `app.product_roster` 里能查到运营组 → 由此把父 ASIN 归到运营组。
  实测 37 个广告父 ASIN 中 31 个可桥（84%）；剩 6 个是款号带性别后缀（`W51女`/`S71W`/`W823男`），
  已在 `_norm_code()` 里做后缀剥离再匹配。
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Optional

from .app_db import query_rows as app_query_rows
from .rds_query import query_one, query_rows

# 运营组前缀（campaign_name 首段）→ 运营姓名
OPERATOR_NAMES = {
    "ZJ": "子娟", "AJ": "爱菊", "YT": "雅婷", "XM": "雪敏",
    "DD": "丹丹", "YS": "雨珊", "LB": "丽斌", "XH": "鑫华",
    "LW": "林文", "ZF": "珍凤",
}
# campaign_name → 二级广告类型
L2_RULES = [
    ("视频", r"视频|video"),
    ("头条", r"头条"),
    ("展示", r"展示|display"),
    ("商品页", r"商品页|detail|商品集"),
]
KNOWN_L1 = ("SP", "SB", "SD", "STV")
L1_FROM_PRODUCT = {
    "Sponsored Products": "SP", "Sponsored Brands": "SB",
    "Sponsored Display": "SD", "Sponsored TV": "STV",
}
BUSINESS_TABLE = "core.report_business_parent_asin_period"
# 业务报告已入库；但仍需对外声明「广告账户 ≠ 业务报告账户」这一事实
BUSINESS_FLAG = "ad_business_account_mismatch"

ANCHOR_SQL = "core.report_campaign_daily"
_CODE_SUFFIX_RE = re.compile(r"(女|男|[WM])$")


def _norm_code(code: str) -> str:
    """款号归一化：剥掉结尾的性别/款式后缀（W51女 → W51、S71W → S71、W823男 → W823）。"""
    c = (code or "").strip()
    for _ in range(2):
        m = _CODE_SUFFIX_RE.search(c)
        if not m:
            break
        c = c[: m.start()]
    return c


def _code_of(campaign_name: str) -> str:
    """广告活动名第 2 段取款号：`ZJ1-W30 头条 低价` → `W30`。"""
    parts = (campaign_name or "").split("-")
    if len(parts) < 2:
        return ""
    return _norm_code(parts[1].strip().split(" ")[0])


def asin_operator_map() -> dict[str, str]:
    """父 ASIN → 运营组。靠「活动名款号 ↔ 主数据款号」搭桥（跨库，在应用层做）。"""
    pairs = query_rows(f"""
        SELECT DISTINCT split_part(btrim(split_part(c.campaign_name,'-',2)),' ',1) AS raw_code,
                        p.advertised_product_parent_id AS asin
        FROM   {ANCHOR_SQL} c
        JOIN   core.report_advertised_product_daily p ON p.campaign_id = c.campaign_id
        WHERE  c.campaign_name LIKE '%-%'
          AND  p.advertised_product_parent_id NOT IN ('', '-1')
    """)
    roster = app_query_rows(f"""
        SELECT DISTINCT product_code, owner_group
        FROM app.product_roster
        WHERE owner_group IS NOT NULL AND owner_group <> ''
    """)
    by_code: dict[str, str] = {}
    for r in roster:
        for k in {r["product_code"].strip(), _norm_code(r["product_code"])}:
            if k:
                by_code.setdefault(k, r["owner_group"])
    out: dict[str, str] = {}
    for r in pairs:
        g = by_code.get(_norm_code(r["raw_code"]))
        if g:
            out.setdefault(r["asin"], g)
    return out


def _asin_values_sql(mapping: dict[str, str]) -> str:
    return ",".join(f"('{a}','{g}')" for a, g in mapping.items() if a and g)


def _business_for_date(day: str, asins: list[str] | None = None) -> dict[str, Any]:
    """取某日的业务报告汇总（单日快照 report_start_date = report_end_date）。"""
    extra = ""
    if asins:
        lst = ",".join("'" + a.replace("'", "''") + "'" for a in asins)
        extra = f" AND parent_asin IN ({lst})"
    return query_one(f"""
        SELECT count(DISTINCT parent_asin)::int AS asin_cnt,
               COALESCE(sum(ordered_product_units),0)::float8 AS total_orders,
               COALESCE(sum(ordered_product_sales),0)::float8 AS total_sales,
               COALESCE(sum(sessions_total),0)::float8 AS sessions
        FROM {BUSINESS_TABLE}
        WHERE report_start_date = report_end_date AND report_start_date = DATE '{day}'{extra}
    """) or {}


# ---------------------------------------------------------------- 账户与日期

def accounts() -> list[dict[str, Any]]:
    return query_rows(f"""
        SELECT account_id, max(account_name) AS account_name,
               min(stat_date)::text AS min_date, max(stat_date)::text AS max_date,
               count(*)::int AS rows
        FROM {ANCHOR_SQL} GROUP BY account_id ORDER BY max(stat_date) DESC
    """)


def _resolve(account_id: Optional[str], wanted_date: Optional[str]) -> dict[str, Any]:
    """解析账户与日期。请求的账户/日期没数据时回落到最新有数据的，并标注 fallback。"""
    accs = accounts()
    if not accs:
        raise RuntimeError("数据仓库里没有广告活动数据（core.report_campaign_daily 为空）")
    by_id = {a["account_id"]: a for a in accs}
    fallback = False
    acc = by_id.get(account_id or "")
    if acc is None:
        acc = accs[0]
        fallback = bool(account_id)
    day = wanted_date
    if not day or not (acc["min_date"] <= day <= acc["max_date"]):
        latest = query_one(
            f"SELECT max(stat_date)::text AS d FROM {ANCHOR_SQL} WHERE account_id='{acc['account_id']}'")
        day = (latest or {}).get("d") or acc["max_date"]
        fallback = fallback or bool(wanted_date)
    return {"account_id": acc["account_id"], "account_name": acc["account_name"],
            "day": day, "min_date": acc["min_date"], "max_date": acc["max_date"], "fallback": fallback}


def _period_range(anchor: str, period: str) -> tuple[str, str]:
    d = date.fromisoformat(anchor)
    if period == "weekly":
        monday = d - timedelta(days=d.weekday())
        return monday.isoformat(), (monday + timedelta(days=6)).isoformat()
    if period == "monthly":
        start = d.replace(day=1)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start.isoformat(), (nxt - timedelta(days=1)).isoformat()
    return d.isoformat(), d.isoformat()


def _l2_expr(col: str = "campaign_name") -> str:
    whens = " ".join(
        f"WHEN {col} ~* '{pat}' THEN '{label}'" for label, pat in L2_RULES
    )
    return f"CASE {whens} ELSE '其他' END"


def _l1_expr(product_col: str = "ad_product", name_col: str = "campaign_name") -> str:
    return f"""CASE
        WHEN {product_col} = 'Sponsored Products' THEN 'SP'
        WHEN {product_col} = 'Sponsored Brands'   THEN 'SB'
        WHEN {product_col} = 'Sponsored Display'  THEN 'SD'
        WHEN {product_col} = 'Sponsored TV'       THEN 'STV'
        WHEN {name_col} ~* '(流媒体|streaming[ ]?tv|sponsored[ ]?tv)' THEN 'STV'
        WHEN {name_col} ~* '(sponsored[ ]?display|展示)' THEN 'SD'
        WHEN {name_col} ~* '(sponsored[ ]?brand|头条|sbv)' THEN 'SB'
        ELSE 'UNCLASSIFIED' END"""


def _op_expr(col: str = "campaign_name") -> str:
    return f"upper(substring({col} from '^([A-Za-z]{{2}}[0-9])'))"


# ---------------------------------------------------------------- 看板

def dashboard_overview(account_id: Optional[str] = None, stat_date: Optional[str] = None) -> dict[str, Any]:
    ctx = _resolve(account_id, stat_date)
    aid, day = ctx["account_id"], ctx["day"]

    totals = query_one(f"""
        SELECT count(*)::int AS ad_rows,
               COALESCE(sum(spend),0)::float8  AS ad_spend,
               COALESCE(sum(purchases),0)::float8 AS ad_orders,
               COALESCE(sum(sales),0)::float8  AS ad_sales
        FROM {ANCHOR_SQL} WHERE account_id='{aid}' AND stat_date=DATE '{day}'
    """) or {}

    typed = query_rows(f"""
        WITH t AS (
          SELECT {_l1_expr()} AS l1, {_l2_expr()} AS l2, spend, purchases
          FROM {ANCHOR_SQL} WHERE account_id='{aid}' AND stat_date=DATE '{day}'
        )
        SELECT l1, l2, COALESCE(sum(spend),0)::float8 spend,
               COALESCE(sum(purchases),0)::float8 orders
        FROM t GROUP BY l1, l2 ORDER BY l1, spend DESC
    """)

    buckets: dict[str, list[dict]] = {k: [] for k in KNOWN_L1}
    unclassified = {"spend": 0.0, "orders": 0.0, "sales": 0.0}
    for r in typed:
        spend = float(r["spend"] or 0)
        orders = float(r["orders"] or 0)
        rec = {"name": r["l2"], "spend": round(spend, 2), "orders": round(orders, 2),
               "cpo": round(spend / orders, 2) if orders else None}
        if r["l1"] in buckets:
            buckets[r["l1"]].append(rec)
        else:
            unclassified["spend"] += spend
            unclassified["orders"] += orders

    ad_types = []
    for l1 in KNOWN_L1:
        kids = buckets[l1]
        sp = sum(x["spend"] for x in kids)
        od = sum(x["orders"] for x in kids)
        ad_types.append({"l1": l1, "spend": round(sp, 2), "orders": round(od, 2),
                         "sales": None, "cpo": round(sp / od, 2) if od else None, "children": kids})

    spend = float(totals.get("ad_spend") or 0)
    ad_orders = float(totals.get("ad_orders") or 0)
    ad_sales = float(totals.get("ad_sales") or 0)

    # 业务侧：只统计「当日有广告投放」的那些父 ASIN，保证分子分母同口径
    ad_asins = [r["asin"] for r in query_rows(f"""
        SELECT DISTINCT advertised_product_parent_id AS asin
        FROM core.report_advertised_product_daily
        WHERE account_id='{aid}' AND stat_date=DATE '{day}'
          AND advertised_product_parent_id NOT IN ('', '-1')
    """)]
    biz = _business_for_date(day, ad_asins)
    total_orders = float(biz.get("total_orders") or 0) or None
    total_sales = float(biz.get("total_sales") or 0) or None
    biz_sessions = float(biz.get("sessions") or 0) or None
    matched = int(biz.get("asin_cnt") or 0)

    flags = ["organic_orders_disabled_by_sop_v3_5"]
    if ad_asins and matched:
        flags.append(BUSINESS_FLAG)   # 广告账户 ≠ 业务报告账户，配对靠 ASIN
    elif ad_asins and not matched:
        flags.append("business_report_missing_for_date")
    if unclassified["spend"]:
        flags.append("ad_type_unclassified_rows_present")
    if ctx["fallback"]:
        flags.append("requested_account_or_date_had_no_data_fell_back_to_latest")

    return {
        "data_source": "rds",
        "fact_source": "报告分表",
        "fact_table": ANCHOR_SQL,
        "account_id": aid, "account_name": ctx["account_name"], "store": ctx["account_name"],
        "data_date": day, "date_range": [ctx["min_date"], ctx["max_date"]],
        "ad_fact_rows": int(totals.get("ad_rows") or 0),
        "business_report_rows": int(biz.get("asin_cnt") or 0),
        "ad_spend": round(spend, 2),
        "ad_orders": round(ad_orders, 2),
        "ad_sales": round(ad_sales, 2),
        "ad_asin_count": len(ad_asins),
        "business_matched_asin_count": matched,
        # 业务侧：来自业务报告，按父 ASIN 与广告侧同口径配对
        "total_orders": total_orders, "total_sales": total_sales,
        "cpo": round(spend / total_orders, 2) if total_orders else None,
        "tacos_pct": round(spend / total_sales * 100, 2) if total_sales else None,
        "roas": round(ad_sales / spend, 2) if spend else None,
        "business_sessions": biz_sessions,
        "estimated_organic_orders": None, "estimated_organic_share": None,
        "ad_types": ad_types,
        "unclassified": {k: round(v, 2) for k, v in unclassified.items()},
        "performance": [],
        "performance_data_source": "moved_to_operator_cpo",
        "quality_flags": flags,
        "note": "广告侧来自 core.report_campaign_daily；全部订单 / 总销售额来自业务报告 "
                "core.report_business_parent_asin_period，**按父 ASIN 与广告侧同口径配对**"
                "（只统计当日有广告投放的那些 ASIN，避免分母被非投放商品稀释）。"
                "⚠️ 广告账户与业务报告的 Seller 账户不是同一 ID，配对只能靠 ASIN。",
    }


def dashboard_trend(account_id: Optional[str] = None, end_date: Optional[str] = None, days: int = 14):
    """每日趋势。花费只取活动层（口径唯一）；业务侧按「窗口内被投放过的父 ASIN」限定分母。"""
    ctx = _resolve(account_id, end_date)
    end = date.fromisoformat(ctx["day"])
    start = (end - timedelta(days=max(1, min(int(days or 14), 90)) - 1)).isoformat()
    aid = ctx["account_id"]

    asins = [r["asin"] for r in query_rows(f"""
        SELECT DISTINCT advertised_product_parent_id AS asin
        FROM core.report_advertised_product_daily
        WHERE account_id='{aid}' AND stat_date BETWEEN DATE '{start}' AND DATE '{end}'
          AND advertised_product_parent_id NOT IN ('', '-1')
    """)]
    scope = ""
    if asins:
        lst = ",".join("'" + a.replace("'", "''") + "'" for a in asins)
        scope = f" AND parent_asin IN ({lst})"

    return query_rows(f"""
        WITH adc AS (   -- 花费：活动层（唯一口径）
          SELECT stat_date, sum(spend)::numeric AS spend
          FROM {ANCHOR_SQL}
          WHERE account_id='{aid}' AND stat_date BETWEEN DATE '{start}' AND DATE '{end}'
          GROUP BY stat_date
        ), adp AS (     -- 广告单 / 广告销售额：推广的商品层
          SELECT stat_date, sum(purchases)::numeric AS ad_orders, sum(sales)::numeric AS ad_sales
          FROM core.report_advertised_product_daily
          WHERE account_id='{aid}' AND stat_date BETWEEN DATE '{start}' AND DATE '{end}'
          GROUP BY stat_date
        ), biz AS (     -- 业务侧：单日快照，且限定在窗口内被投放过的父 ASIN
          SELECT report_start_date AS stat_date,
                 sum(ordered_product_units)::numeric AS total_orders,
                 sum(ordered_product_sales)::numeric AS total_sales
          FROM {BUSINESS_TABLE}
          WHERE report_start_date = report_end_date
            AND report_start_date BETWEEN DATE '{start}' AND DATE '{end}'{scope}
          GROUP BY report_start_date
        )
        SELECT to_char(c.stat_date,'MM/DD') AS date,
               round(c.spend,2)::float8 AS spend,
               COALESCE(p.ad_orders,0)::float8 AS "adOrders",
               CASE WHEN b.total_orders > 0
                    THEN round((c.spend / b.total_orders)::numeric,2)::float8 END AS cpo,
               CASE WHEN c.spend > 0
                    THEN round((COALESCE(p.ad_sales,0) / c.spend)::numeric,2)::float8 END AS roas,
               NULL::float8 AS "organicOrders",
               CASE WHEN b.total_sales > 0
                    THEN round((c.spend / b.total_sales * 100)::numeric,2)::float8 END AS tacos,
               CASE WHEN b.total_orders IS NULL THEN '缺业务报告' ELSE '业务+广告' END AS maturity
        FROM   adc c
        LEFT   JOIN adp p ON p.stat_date = c.stat_date
        LEFT   JOIN biz b ON b.stat_date = c.stat_date
        ORDER  BY c.stat_date
    """)


# ---------------------------------------------------------------- 报告覆盖

REPORT_SPECS = [
    ("广告活动", "core.report_campaign_daily", "spend"),
    ("广告位", "core.report_placement_daily", "spend"),
    ("投放", "core.report_targeting_daily", "spend"),
    ("推广的商品", "core.report_advertised_product_daily", "spend"),
    ("达成转化的商品", "core.report_purchased_product_daily", None),
    ("搜索词", "core.report_search_term_daily", "spend"),
]


def reports():
    out = []
    for label, table, metric in REPORT_SPECS:
        metric_sql = f"COALESCE(sum({metric}),0)::float8" if metric else "NULL::float8"
        for r in query_rows(f"""
            SELECT account_id, max(account_name) AS account_name,
                   min(stat_date)::text AS min_date, max(stat_date)::text AS max_date,
                   count(*)::int AS rows, {metric_sql} AS metric_sum,
                   count(source_file_name)::int AS lineage_rows
            FROM {table} GROUP BY account_id ORDER BY account_name
        """):
            out.append({
                "account": r["account_name"], "account_id": r["account_id"],
                "type": label, "table": table,
                "date": r["max_date"], "min_date": r["min_date"], "rows": r["rows"],
                "status": "READY", "source": "rds",
                "lineage": "完整（source_file_name 已回填）"
                           if r["lineage_rows"] == r["rows"] else "缺失",
            })
    return out


# ---------------------------------------------------------------- 产品维度

def products(account_id: Optional[str] = None, stat_date: Optional[str] = None, limit: int = 50):
    ctx = _resolve(account_id, stat_date)
    aid, day = ctx["account_id"], ctx["day"]
    lim = max(1, min(int(limit or 50), 200))
    rows = query_rows(f"""
        WITH ad AS (
          SELECT advertised_product_parent_id AS parent_asin,
                 max(advertised_product_parent_id) AS asin,
                 sum(spend)::float8 spend, sum(purchases)::float8 ad_orders, sum(sales)::float8 ad_sales
          FROM core.report_advertised_product_daily
          WHERE account_id='{aid}' AND stat_date=DATE '{day}'
            AND advertised_product_parent_id IS NOT NULL AND advertised_product_parent_id<>''
          GROUP BY 1
        )
        SELECT parent_asin, parent_asin AS code, NULL::text AS group_code, parent_asin AS title,
               round(spend::numeric,2)::float8 spend,
               ad_orders, round(ad_sales::numeric,2)::float8 ad_sales,
               CASE WHEN spend>0 THEN round((ad_sales/spend)::numeric,2)::float8 END roas,
               NULL::float8 total_orders, NULL::float8 total_sales, NULL::float8 sessions,
               NULL::float8 cpo, NULL::float8 tacos
        FROM ad ORDER BY spend DESC LIMIT {lim}
    """)
    for r in rows:
        r["organic_orders"] = None
    return {
        "data_source": "rds", "fact_source": "report_advertised_product_daily",
        "account_id": aid, "account_name": ctx["account_name"], "store": ctx["account_name"],
        "data_date": day, "allocation_status": "parent_asin_preview", "final_cpo": False,
        "rows": rows,
        "warning": "按「推广的商品父级编号」聚合（38 个父 ASIN 可用）。"
                   "全部订单 / 综合 CPO / TACOS 由业务报告提供（按父 ASIN 配对）。",
        "note": "注意：推广的商品报告不提供子 ASIN（advertised_product_id 上游为空），父级 ASIN 可用。",
    }


# ---------------------------------------------------------------- 运营单双

def operator_period_options() -> dict[str, Any]:
    days = [r["d"] for r in query_rows(
        f"SELECT DISTINCT stat_date::text AS d FROM {ANCHOR_SQL} ORDER BY 1 DESC")]
    daily = [{"value": d, "label": d, "start": d, "end": d} for d in days]

    seen, weekly = set(), []
    for d in days:
        anchor = date.fromisoformat(d)
        monday = anchor - timedelta(days=anchor.weekday())
        key = monday.isoformat()
        if key in seen:
            continue
        seen.add(key)
        sunday = monday + timedelta(days=6)
        weekly.append({"value": key, "label": f"{key} ~ {sunday.isoformat()}（周）",
                       "start": key, "end": sunday.isoformat()})

    seen_m, monthly = set(), []
    for d in days:
        key = d[:8] + "01"
        if key in seen_m:
            continue
        seen_m.add(key)
        monthly.append({"value": key, "label": d[:7], "start": key, "end": d})
    for m in monthly:
        month_end = query_one(f"""
            SELECT max(stat_date)::text AS d FROM {ANCHOR_SQL}
            WHERE stat_date BETWEEN DATE '{m['start']}' AND (DATE '{m['start']}' + INTERVAL '1 month - 1 day')
        """)
        m["end"] = (month_end or {}).get("d") or m["end"]

    return {"daily": daily, "weekly": weekly, "monthly": monthly,
            "latestDate": days[0] if days else None,
            "weekRule": "周一至周日",
            "note": "日期范围来自 core.report_campaign_daily 的实际入库日期。"}


def _operator_rows(aid: str, start: str, end: str) -> list[dict[str, Any]]:
    """按运营组汇总（单账户口径，管理页用）。

    广告侧与业务侧**都用同一套 ASIN → 运营组 归属**，避免两端口径不一致。
    aid 传 None 时跨全部广告账户汇总（运营页「我的 CPO」用）。
    """
    mapping = asin_operator_map()
    vals = _asin_values_sql(mapping)
    if not vals:
        return []
    # aid=None → 不限定账户；否则只看单一账户（管理页原口径）
    ad_scope = f" AND p.account_id='{aid}'" if aid else ""
    biz_scope = ""

    ad = query_rows(f"""
        WITH m(asin, grp) AS (VALUES {vals})
        SELECT COALESCE(m.grp, '未归属') AS grp,
               COALESCE(sum(p.spend),0)::float8 spend,
               COALESCE(sum(p.purchases),0)::float8 ad_orders,
               COALESCE(sum(p.sales),0)::float8 ad_sales,
               count(DISTINCT p.advertised_product_parent_id)::int AS asins
        FROM   core.report_advertised_product_daily p
        LEFT   JOIN m ON m.asin = p.advertised_product_parent_id
        WHERE  p.stat_date BETWEEN DATE '{start}' AND DATE '{end}'{ad_scope}
          AND  p.advertised_product_parent_id NOT IN ('', '-1')
        GROUP  BY 1
    """)
    biz = query_rows(f"""
        WITH m(asin, grp) AS (VALUES {vals})
        SELECT m.grp,
               COALESCE(sum(b.ordered_product_units),0)::float8 total_orders,
               COALESCE(sum(b.ordered_product_sales),0)::float8 total_sales,
               count(DISTINCT b.parent_asin)::int AS matched_asins
        FROM   {BUSINESS_TABLE} b
        JOIN   m ON m.asin = b.parent_asin
        WHERE  b.report_start_date = b.report_end_date
          AND  b.report_start_date BETWEEN DATE '{start}' AND DATE '{end}'
        GROUP  BY 1
    """)
    biz_by = {r["grp"]: r for r in biz}

    out = []
    for r in ad:
        grp = (r["grp"] or "").upper()
        b = biz_by.get(r["grp"]) or {}
        spend = float(r["spend"] or 0)
        ad_sales = float(r["ad_sales"] or 0)
        total_orders = float(b.get("total_orders") or 0)
        total_sales = float(b.get("total_sales") or 0)
        has_biz = total_orders > 0
        out.append({
            "name": OPERATOR_NAMES.get(grp[:2], grp) if grp != "未归属" else "未归属",
            "group": grp,
            "spend": round(spend, 2),
            "adOrders": round(float(r["ad_orders"] or 0), 2),
            "adSales": round(ad_sales, 2),
            "roas": round(ad_sales / spend, 2) if spend else None,
            "totalOrders": round(total_orders, 2) if has_biz else None,
            "totalSales": round(total_sales, 2) if has_biz else None,
            "cpo": round(spend / total_orders, 2) if has_biz else None,
            "tacos": round(spend / total_sales * 100, 2) if total_sales else None,
            "products": int(r["asins"] or 0),
            "dataProducts": int(b.get("matched_asins") or 0) if has_biz else None,
            "organic": None, "organicShare": None, "maturity": None, "change": None,
            "status": "已配对" if has_biz else "缺业务侧",
            "scope": "广告侧与业务侧均按同一套 ASIN→运营组 归属；CPO = 广告花费 / 该组全部订单",
        })
    # 同名运营（如 AJ1+AJ2 都归爱菊）合并
    merged: dict[str, dict] = {}
    for r in out:
        key = r["name"]
        if key not in merged:
            merged[key] = dict(r)
            merged[key]["groups"] = [r["group"]]
            continue
        m = merged[key]
        m["groups"].append(r["group"])
        for k in ("spend", "adOrders", "adSales", "products"):
            m[k] += r[k]
        to = (m.get("totalOrders") or 0) + (r.get("totalOrders") or 0)
        ts = (m.get("totalSales") or 0) + (r.get("totalSales") or 0)
        m["totalOrders"] = round(to, 2) if to else None
        m["totalSales"] = round(ts, 2) if ts else None
        m["cpo"] = round(m["spend"] / to, 2) if to else None
        m["tacos"] = round(m["spend"] / ts * 100, 2) if ts else None
        m["roas"] = round(m["adSales"] / m["spend"], 2) if m["spend"] else None
        m["status"] = "已配对" if to else "缺业务侧"
    return sorted(merged.values(), key=lambda x: -x["spend"])


def operator_cpo_summary(stat_date: Optional[str] = None, period: str = "daily",
                         all_accounts: bool = False) -> dict[str, Any]:
    period = period if period in ("daily", "weekly", "monthly") else "daily"
    anchor = stat_date
    if not anchor:
        latest = query_one(f"SELECT max(stat_date)::text AS d FROM {ANCHOR_SQL}")
        anchor = (latest or {}).get("d")
    if not anchor:
        return {"data_source": "rds", "period": period, "operators": [], "note": "数据仓库为空。",
                "coverageDays": 0, "expectedDays": 0, "account_split": False}
    start, end = _period_range(anchor, period)
    ctx = _resolve(None, anchor)
    aid = ctx["account_id"]

    rows = _operator_rows(None if all_accounts else aid, start, end)
    covered = int(query_one(f"""
        SELECT count(DISTINCT stat_date)::int AS n FROM {ANCHOR_SQL}
        WHERE stat_date BETWEEN DATE '{start}' AND DATE '{end}'
        {" " if all_accounts else f"AND account_id='{aid}' "}""")["n"] or 0)
    expected = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1

    label = {"daily": "日", "weekly": "周", "monthly": "月"}[period]
    return {
        "data_source": "report_tables_operator_rollup",
        "data_date": anchor, "period": period, "period_start": start, "period_end": end,
        "coverageDays": covered, "expectedDays": expected, "account_split": False,
        "scope": "all_accounts" if all_accounts else "single_account",
        "operators": rows,
        "note": f"{label}快照 {start}~{end}，覆盖 {covered}/{expected} 天。"
                f"运营组取自 campaign_name 首段（如 ZJ1）；AJ1/AJ2 同归爱菊，XM1/XM2 同归雪敏。"
                f"广告花费/广告单/ROAS/全部订单/CPO/TACOS 均为实测值。运营归属与业务侧配对都走「活动名款号 → 主数据款号 → 运营组」同一条桥。",
        "qualityFlags": [BUSINESS_FLAG, "operator_dimension_derived_from_campaign_name"],
    }


def operator_group_of(operator_code: Optional[str]) -> str:
    """运营账号代码 → 运营组前缀。`ZJ1` → `ZJ`；`XM2` → `XM`（与 OPERATOR_NAMES 的键一致）。"""
    return (operator_code or "").strip().upper()[:2]


def my_cpo_summary(operator_code: Optional[str], stat_date: Optional[str] = None,
                   period: str = "daily") -> dict[str, Any]:
    """运营本人视图：跨全部广告账户汇总后，只保留自己的那一行。

    与「运营单双情况」（管理页）的区别：管理页只取单个账户，这里跨账户合并，
    否则运营自己的量会分散在多个账户里看不到。
    """
    prefix = operator_group_of(operator_code)
    data = operator_cpo_summary(stat_date, period, all_accounts=True)
    if not prefix:
        return {**data, "operators": [], "me": None,
                "note": "当前账号没有绑定运营组（operator_code），无法定位个人数据。"}

    def _mine(row: dict[str, Any]) -> bool:
        groups = row.get("groups") or [row.get("group")]
        return any(str(g or "").upper()[:2] == prefix for g in groups)

    rows = [r for r in data.get("operators", []) if _mine(r)]
    label = {"daily": "日", "weekly": "周", "monthly": "月"}[period]
    me = {"operatorCode": (operator_code or "").strip().upper(), "group": prefix,
          "name": OPERATOR_NAMES.get(prefix, prefix)}
    note = (f"我的{label}快照 {data.get('period_start')}~{data.get('period_end')}，"
            f"覆盖 {data.get('coverageDays')}/{data.get('expectedDays')} 天；"
            f"跨全部广告账户按运营组（{prefix}）汇总，只能看到本人的数据。")
    if not rows:
        note += " 该区间没有归属到本运营组的广告数据。"
    return {**data, "operators": rows, "me": me, "note": note, "scope": "own_operator_all_accounts"}


def operator_cpo_detail(name: str, stat_date: Optional[str] = None, period: str = "daily") -> dict[str, Any]:
    period = period if period in ("daily", "weekly", "monthly") else "daily"
    anchor = stat_date or (query_one(f"SELECT max(stat_date)::text AS d FROM {ANCHOR_SQL}") or {}).get("d")
    if not anchor:
        return {"data_source": "rds", "operator": name, "products": [], "summary": {}}
    start, end = _period_range(anchor, period)
    ctx = _resolve(None, anchor)
    aid = ctx["account_id"]

    # name → 该运营名下的 2 字符前缀（数据里的组码是 ZJ1/AJ2 这种 3 字符，按前缀匹配）
    groups = [g for g, n in OPERATOR_NAMES.items() if n == name] or [name.upper()]
    grp_filter = ",".join(f"'{g}'" for g in groups)
    op_sql = _op_expr()

    rows = query_rows(f"""
        WITH ad AS (
          SELECT p.advertised_product_parent_id AS parent_asin,
                 sum(p.spend)::float8 spend, sum(p.purchases)::float8 ad_orders,
                 sum(p.sales)::float8 ad_sales
          FROM core.report_advertised_product_daily p
          WHERE p.account_id='{aid}' AND p.stat_date BETWEEN DATE '{start}' AND DATE '{end}'
            AND left({_op_expr('p.campaign_name')}, 2) IN ({grp_filter})
            AND p.advertised_product_parent_id IS NOT NULL AND p.advertised_product_parent_id<>''
          GROUP BY 1
        )
        SELECT parent_asin, spend, ad_orders, ad_sales,
               CASE WHEN spend>0 THEN round((ad_sales/spend)::numeric,2)::float8 END roas
        FROM ad ORDER BY spend DESC
    """)

    groups_cov = query_rows(f"""
        SELECT {op_sql} AS grp, count(DISTINCT campaign_id)::int AS campaigns,
               COALESCE(sum(spend),0)::float8 spend
        FROM {ANCHOR_SQL}
        WHERE account_id='{aid}' AND stat_date BETWEEN DATE '{start}' AND DATE '{end}'
          AND left({op_sql}, 2) IN ({grp_filter})
        GROUP BY 1 ORDER BY 1
    """)

    prod_out = []
    for r in rows:
        spend = float(r["spend"] or 0)
        ad_orders = float(r["ad_orders"] or 0)
        prod_out.append({
            "code": r["parent_asin"], "parentAsin": r["parent_asin"], "title": r["parent_asin"],
            "spend": round(spend, 2), "adOrders": round(ad_orders, 2),
            "totalOrders": None, "organic": None, "cpo": None, "tacos": None,
            "roas": r["roas"], "maturity": None,
            "adTypeSpend": {"DSP": None, "SP": 0, "SB": round(spend, 2), "SD": 0, "STV": 0},
            "adTypeOrders": {"DSP": None, "SP": 0, "SB": round(ad_orders, 2), "SD": 0, "STV": 0},
            "daily": [], "weekly": [],
        })
    s_spend = sum(p["spend"] for p in prod_out)
    s_orders = sum(p["adOrders"] for p in prod_out)
    s_sales = sum(float(r["ad_sales"] or 0) for r in rows)
    return {
        "data_source": "rds", "fact_source": "report_advertised_product_daily",
        "allocation_status": "parent_asin_preview", "final_cpo": False,
        "operator": name, "groups": groups,
        "account": f"{ctx['account_name']}（父 ASIN 预览）",
        "range": f"{start}~{end}" if period != "daily" else anchor,
        "data_date": anchor, "period": period,
        "summary": {
            "spend": round(s_spend, 2), "adOrders": round(s_orders, 2),
            "adSales": round(s_sales, 2),
            "roas": round(s_sales / s_spend, 2) if s_spend else None,
            "totalOrders": None, "organic": None, "organicShare": None, "cpo": None,
            "tacos": None, "maturity": None,
        },
        "groupsCoverage": groups_cov,
        "products": prod_out,
        "warning": "按推广的商品父级 ASIN 预览；业务侧（全部订单 / CPO / TACOS）由业务报告提供。",
        "qualityFlags": [BUSINESS_FLAG, "advertised_product_id_upstream_empty_using_parent_id"],
    }
