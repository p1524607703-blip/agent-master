#!/usr/bin/env python3
"""
把 Amazon Ads 中文 CSV 报告载入 amazon_ads_v2 的 V2 结构。

目标表：
    campaign / placement / targeting / advertised_product / purchased_product → core.ad_daily
    search_term                                                              → core.search_term_daily

流程（对应设计文档 §16）：
    file_hash → 已导入则整文件跳过 → staging → 标准化 → 同批业务键去重
    → 算 dimension_key / row_hash → INSERT / UPDATE / SKIP → 写 import_batches

用法：
    python3 load_reports.py <csv...>            # 直接入库
    python3 load_reports.py <csv...> --dry-run  # 只解析统计，不写库
    python3 load_reports.py --backfill-ad-product   # 从 campaign 层补齐 ad_product
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import sys
from datetime import datetime
from pathlib import Path

import _db

# ---------------------------------------------------------------------------
# 列映射：中文表头 → 英文列（键为「破折号前的主名」，兼容 -英文后缀 / 全角括号）
# ---------------------------------------------------------------------------
DIM_MAP = {
    "预算货币": "budget_currency",
    "广告主账户 ID": "account_id",
    "广告主账户名称": "account_name",
    "管理员账户": "manager_account",
    "广告产品": "ad_product",
    "广告组合编号": "portfolio_id",
    "广告组合名称": "portfolio_name",
    "广告活动编号": "campaign_id",
    "广告活动名称": "campaign_name",
    "广告活动投放状态": "campaign_state",
    "全球广告活动 ID": "global_campaign_id",
    "广告组编号": "ad_group_id",
    "广告组名称": "ad_group_name",
    "日期": "stat_date",
    # Placement
    "广告位分类": "placement",
    "广告位": "placement",
    # Targeting
    "投放方案编号": "target_id",
    "投放方案": "target_text",
    "投放匹配类型": "target_match_type",
    "目标竞价": "target_bid",
    "投放类型": "target_type",
    "投放状态": "target_status",
    # Advertised product
    "推广的商品编号": "advertised_product_id",
    "推广的商品名称": "advertised_product_name",
    "推广的商品父级编号": "advertised_product_parent_id",
    "推广的商品品牌": "advertised_product_brand",
    "推广的商品品类": "advertised_product_category",
    "推广的商品子品类": "advertised_product_subcategory",
    "推广的商品组": "advertised_product_group",
    "推广的商品 SKU": "advertised_product_sku",
    "推广的商品站点": "advertised_product_marketplace",
    # Purchased product
    "达成转化的商品的编号": "purchased_product_id",
    "达成转化的商品的名称": "purchased_product_name",
    "转化的商品市场": "purchased_product_marketplace",
    "达成转化的商品编号": "purchased_product_id",
    "达成转化的商品名称": "purchased_product_name",
    "达成转化的商品市场": "purchased_product_marketplace",
    # Search term
    "搜索词": "search_term",
}

METRIC_MAP = {
    "展示量": "impressions",
    "可见展示量": "viewable_impressions",
    "点击量": "clicks",
    "总成本": "spend",
    "购买量": "purchases",
    "销售额": "sales",
    "已售商品数量": "units",
    "推广商品的购买量": "promoted_purchases",
    "推广商品的销量": "promoted_sales",
    "已售商品数量（推广）": "promoted_units",
    "购买量（光环）": "halo_purchases",
    "销售额（光环）": "halo_sales",
    "已售商品数量（光环）": "halo_units",
    "购买量（品牌新客）": "new_to_brand_purchases",
    "销售额（品牌新客）": "new_to_brand_sales",
    "已售商品数量（品牌新客）": "new_to_brand_units",
    "长期销售": "long_term_sales",
    "商品详情页浏览量": "detail_page_views",
}

DERIVED_MAP = {
    "点击率": "ctr_pct",
    "浏览点击率": "vctr_pct",
    "CPC": "cpc",
    "购买率": "cvr_pct",
    "点击转化率": "cvr_pct",
    "单次购买成本": "cpa",
    "ROAS": "roas",
    "推广商品的每次购买费用": "promoted_cpa",
    "购买率（推广的商品）": "promoted_cvr_pct",
    "推广商品的 ROAS": "promoted_roas",
    "每次购买成本（品牌新客）": "new_to_brand_cpa",
    "购买率（品牌新客）": "new_to_brand_cvr_pct",
    "ROAS（品牌新客）": "new_to_brand_roas",
    "长期 ROAS": "long_term_roas",
    "单次商品详情页浏览成本": "cost_per_detail_page_view",
    "商品详情页浏览率": "detail_page_view_rate_pct",
}

# 六种 data_level → 目标表
LEVEL_TABLE = {
    "campaign": "core.ad_daily",
    "placement": "core.ad_daily",
    "targeting": "core.ad_daily",
    "advertised_product": "core.ad_daily",
    "purchased_product": "core.ad_daily",
    "product_cpo": "core.ad_daily",
    "search_term": "core.search_term_daily",
}

_AD_COMMON = [
    "advertised_product_id", "advertised_product_name", "advertised_product_parent_id",
    "advertised_product_brand", "advertised_product_category",
    "advertised_product_subcategory", "advertised_product_group",
    "advertised_product_sku", "advertised_product_marketplace",
    "purchased_product_id", "purchased_product_name", "purchased_product_marketplace",
]
_METRICS_RAW = [
    "impressions", "viewable_impressions", "clicks", "spend", "purchases", "sales", "units",
    "promoted_purchases", "promoted_sales", "promoted_units",
    "halo_purchases", "halo_sales", "halo_units",
    "new_to_brand_purchases", "new_to_brand_sales", "new_to_brand_units",
    "long_term_sales", "detail_page_views",
]
_METRICS_DERIVED = [
    "ctr_pct", "vctr_pct", "cpc", "cvr_pct", "cpa", "acos_pct", "roas",
    "promoted_cpa", "promoted_cvr_pct", "promoted_acos_pct", "promoted_roas",
    "new_to_brand_cpa", "new_to_brand_cvr_pct", "new_to_brand_acos_pct", "new_to_brand_roas",
    "long_term_roas", "cost_per_detail_page_view", "detail_page_view_rate_pct",
]
_TECH = ["row_hash", "batch_id", "source_file_name", "source_file_hash"]

AD_DAILY_COLS = [
    "account_id", "account_name", "manager_account", "ad_product",
    "portfolio_id", "portfolio_name", "campaign_id", "campaign_name",
    "campaign_state", "global_campaign_id", "ad_group_id", "ad_group_name",
    "stat_date", "budget_currency", "data_level", "grain_level", "dimension_key",
    "placement", "target_id", "target_text", "target_match_type", "target_bid",
    "target_type", "target_status",
] + _AD_COMMON + _METRICS_RAW + _METRICS_DERIVED + _TECH

ST_DAILY_COLS = [
    "account_id", "account_name", "ad_product",
    "portfolio_id", "portfolio_name", "campaign_id", "campaign_name",
    "ad_group_id", "ad_group_name", "search_term", "stat_date", "budget_currency",
    "impressions", "clicks", "spend", "purchases", "sales", "units",
    "promoted_purchases", "promoted_sales", "promoted_units",
    "halo_purchases", "halo_sales", "halo_units",
    "new_to_brand_purchases", "new_to_brand_sales", "new_to_brand_units",
    "detail_page_views",
    "ctr_pct", "cpc", "cvr_pct", "cpa", "acos_pct", "roas",
] + _TECH

# ad_daily 的业务唯一键
AD_UK = ["account_id", "ad_product", "data_level", "grain_level",
         "campaign_id", "ad_group_id", "stat_date", "dimension_key"]
ST_UK = ["account_id", "ad_product", "campaign_id", "ad_group_id", "search_term", "stat_date"]

# 这些列在 DDL 里是 NOT NULL（多为 DEFAULT '' 的文本键）。
# ⚠️ COPY ... FORMAT csv 会把「未加引号的空字段」读成 NULL，
#    所以装载时必须对它们声明 FORCE_NOT_NULL，否则 '' 会变 NULL 撞非空约束。
NOT_NULL_TEXT = {"account_id", "ad_product", "data_level", "grain_level",
                 "dimension_key", "campaign_id", "ad_group_id", "row_hash", "search_term"}

NUMERIC_COLS = {
    "spend", "sales", "promoted_sales", "halo_sales", "new_to_brand_sales", "long_term_sales",
    "ctr_pct", "vctr_pct", "cpc", "cvr_pct", "cpa", "acos_pct", "roas",
    "promoted_cpa", "promoted_cvr_pct", "promoted_acos_pct", "promoted_roas",
    "new_to_brand_cpa", "new_to_brand_cvr_pct", "new_to_brand_acos_pct",
    "new_to_brand_roas", "long_term_roas", "cost_per_detail_page_view",
    "detail_page_view_rate_pct", "target_bid",
}
INT_COLS = {
    "impressions", "viewable_impressions", "clicks", "purchases", "units",
    "promoted_purchases", "promoted_units", "halo_purchases", "halo_units",
    "new_to_brand_purchases", "new_to_brand_units", "detail_page_views",
}

EXCEL_WRAP = re.compile(r'^="?(.*?)"?$')
DATE_CN = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")


def norm_text(v: str) -> str:
    if v is None:
        return ""
    v = v.strip().strip("\ufeff")
    if v.startswith('="'):
        m = EXCEL_WRAP.match(v)
        if m:
            v = m.group(1)
    return v.strip()


def norm_date(v: str) -> str | None:
    v = norm_text(v)
    if not v:
        return None
    m = DATE_CN.match(v)
    if m:
        y, mo, d = (int(x) for x in m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}"
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def norm_num(v: str) -> str:
    v = norm_text(v)
    if v in ("", "-", "--"):
        return ""
    v = v.replace("%", "").replace(",", "").replace("$", "").strip()
    if v in ("", "-"):
        return ""
    try:
        float(v)
    except ValueError:
        return ""
    return v


def build_col_index(header: list[str]) -> dict[str, int]:
    """建「主名 → 列号」索引；带 -英文后缀的列按破折号前主名登记。"""
    idx: dict[str, int] = {}
    for i, h in enumerate(header):
        for key in (h, h.split("-")[0].strip()):
            idx.setdefault(key, i)
    return idx


def detect_data_level(header: set[str]) -> str:
    if "搜索词" in header:
        return "search_term"
    if "投放方案" in header or "投放方案编号" in header:
        return "targeting"
    if "广告位分类" in header or "广告位" in header:
        return "placement"
    if "达成转化的商品的编号" in header or "达成转化的商品编号" in header:
        return "purchased_product"
    if "推广的商品编号" in header:
        return "advertised_product"
    if "广告活动编号" in header and "广告组编号" not in header:
        return "campaign"
    raise SystemExit(f"无法识别的报表类型，表头前 8 列：{sorted(header)[:8]}")


def dimension_key(level: str, row: dict) -> str:
    if level == "campaign":
        return "campaign"
    if level == "placement":
        return f"placement:{row.get('placement') or ''}"
    if level == "targeting":
        tid = row.get("target_id") or ""
        if tid:
            return f"target:{tid}"
        return (f"target:{row.get('target_type') or ''}|"
                f"{row.get('target_text') or ''}|{row.get('target_match_type') or ''}")
    if level == "advertised_product":
        return f"advprod:{row.get('advertised_product_id') or ''}"
    if level == "purchased_product":
        return f"purchased:{row.get('purchased_product_id') or ''}"
    if level == "product_cpo":
        return f"cpo:{row.get('advertised_product_id') or ''}"
    return level


def compute_derived(row: dict) -> None:
    def f(k):
        v = row.get(k)
        if v in (None, ""):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def put(k, val, digits=6):
        if row.get(k) in (None, "") and val is not None:
            row[k] = f"{val:.{digits}f}"

    imp, clk, spend = f("impressions"), f("clicks"), f("spend")
    pur, sales, dpv = f("purchases"), f("sales"), f("detail_page_views")
    vib = f("viewable_impressions")

    if imp and imp > 0:
        put("ctr_pct", clk / imp * 100 if clk is not None else None)
        put("vctr_pct", vib / imp * 100 if vib is not None else None)
        if dpv is not None:
            put("detail_page_view_rate_pct", dpv / imp * 100)
    if clk and clk > 0:
        put("cpc", spend / clk if spend is not None else None)
        put("cvr_pct", pur / clk * 100 if pur is not None else None)
    if pur and pur > 0:
        put("cpa", spend / pur if spend is not None else None)
    if sales and sales > 0:
        if spend is not None:
            put("acos_pct", spend / sales * 100)
        if spend and spend > 0:
            put("roas", sales / spend)
    if dpv and dpv > 0 and spend is not None:
        put("cost_per_detail_page_view", spend / dpv)


def parse_file(path: Path, level: str | None) -> dict:
    raw = path.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig")))
    header = [norm_text(h) for h in next(reader)]
    level = level or detect_data_level(set(header))
    target = LEVEL_TABLE[level]
    cols = ST_DAILY_COLS if target == "core.search_term_daily" else AD_DAILY_COLS
    uk = ST_UK if target == "core.search_term_daily" else AD_UK
    idx = build_col_index(header)

    hash_cols = [c for c in uk] + [c for c in _METRICS_RAW
                                   if c not in {"viewable_impressions", "long_term_sales"}] + _METRICS_DERIVED
    if target == "core.search_term_daily":
        hash_cols = uk + ["impressions", "clicks", "spend", "purchases", "sales", "units",
                          "ctr_pct", "cpc", "cvr_pct", "cpa", "acos_pct", "roas"]

    rows_out: list[dict] = []
    pos: dict[tuple, int] = {}
    dup_dropped = skipped = blank_term = 0

    for raw_row in reader:
        if not raw_row or all(not c.strip() for c in raw_row):
            continue
        row: dict[str, str] = {c: "" for c in cols}
        for cn, en in DIM_MAP.items():
            i = idx.get(cn)
            if i is not None and i < len(raw_row):
                row[en] = norm_text(raw_row[i])
        for cn, en in METRIC_MAP.items():
            i = idx.get(cn)
            if i is not None and i < len(raw_row):
                row[en] = norm_num(raw_row[i])
        for cn, en in DERIVED_MAP.items():
            i = idx.get(cn)
            if i is not None and i < len(raw_row):
                v = norm_num(raw_row[i])
                if v != "" and not row.get(en):
                    row[en] = v

        row["stat_date"] = norm_date(row.get("stat_date", "")) or ""
        if not row["stat_date"] or not row.get("account_id") or not row.get("campaign_id"):
            skipped += 1
            continue
        # 搜索词为空不代表脏数据：SB/商品页等非搜索来源行确实没有搜索词，
        # 但它们带真实花费与销售额（本批 146 行 / $2,021.96），必须保留为空串。
        if target == "core.search_term_daily":
            row["search_term"] = row.get("search_term") or ""
            if not row["search_term"]:
                blank_term += 1

        row["ad_group_id"] = row.get("ad_group_id") or ""
        row["ad_product"] = row.get("ad_product") or ""
        if target == "core.ad_daily":
            row["data_level"] = level
            row["grain_level"] = "ad_group" if row["ad_group_id"] else "campaign"
            row["dimension_key"] = dimension_key(level, row)
        compute_derived(row)

        key = tuple(row.get(c, "") for c in uk)
        if key in pos:
            prev = rows_out[pos[key]]
            score = lambda r: (bool(r.get("advertised_product_name")),
                               bool(r.get("advertised_product_parent_id")),
                               float(r.get("impressions") or 0) + float(r.get("spend") or 0),
                               float(r.get("sales") or 0))
            if score(row) > score(prev):
                rows_out[pos[key]] = row
            dup_dropped += 1
            continue
        pos[key] = len(rows_out)
        rows_out.append(row)

    for r in rows_out:
        r["row_hash"] = hashlib.sha256(
            "|".join(str(r.get(c, "") or "") for c in hash_cols).encode("utf-8")
        ).hexdigest()

    return {"file_hash": file_hash, "level": level, "target": target, "cols": cols,
            "uk": uk, "rows": rows_out, "source_rows": len(rows_out) + dup_dropped + skipped,
            "dup_dropped": dup_dropped, "skipped": skipped, "blank_term": blank_term}


def write_tsv(rows: list[dict], cols: list[str], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        for r in rows:
            w.writerow([r.get(c, "") if r.get(c) is not None else "" for c in cols])


def load_one(path: Path, level: str | None, dry: bool) -> dict:
    res = parse_file(path, level)
    rows, cols, uk = res["rows"], res["cols"], res["uk"]
    print(f"\n=== {path.name}")
    print(f"    data_level={res['level']}  →  {res['target']}")
    print(f"    源行 {res['source_rows']} | 同批重复丢弃 {res['dup_dropped']} | 缺键跳过 {res['skipped']}"
          f" | 待入库 {len(rows)}")
    if res.get("blank_term"):
        print(f"    （其中搜索词为空但保留 {res['blank_term']} 行：非搜索来源，带真实花费）")
    if rows:
        print(f"    账户 {sorted({r['account_id'] for r in rows})}"
              f" | 日期 {min(r['stat_date'] for r in rows)} ~ {max(r['stat_date'] for r in rows)}")
    if dry:
        return res

    # 只有「成功」的批次才算已导入；失败/中断留下的 processing 批次必须允许重试
    if _db.psql(f"select 1 from core.import_batches "
                f"where file_hash='{res['file_hash']}' and import_status='success'"):
        print("    ⏭️  该 file_hash 已成功导入过，整文件跳过（设计文档 §16）")
        return res
    _db.psql(f"delete from core.import_batches "
             f"where file_hash='{res['file_hash']}' and import_status <> 'success';")

    target = res["target"]
    stg = "stg.load_tmp"
    _db.psql("CREATE SCHEMA IF NOT EXISTS stg;")
    _db.psql(f"DROP TABLE IF EXISTS {stg};")
    _db.psql(f"CREATE UNLOGGED TABLE {stg} (" + ", ".join(f'"{c}" text' for c in cols) + ");")

    tsv = Path("/tmp") / f"load_{res['file_hash'][:12]}.tsv"
    write_tsv(rows, cols, tsv)
    force_cols = [c for c in cols if c in NOT_NULL_TEXT]
    copy_opts = "FORMAT csv, DELIMITER E'\\t', HEADER false"
    if force_cols:
        copy_opts += ", FORCE_NOT_NULL (" + ", ".join(f'"{c}"' for c in force_cols) + ")"
    _db.psql(f"\\copy {stg} FROM '{tsv}' WITH ({copy_opts})", tuples_only=False)

    d0, d1 = min(r["stat_date"] for r in rows), max(r["stat_date"] for r in rows)
    if target == "core.ad_daily":
        _db.psql(f"select core.ensure_ad_daily_partition(DATE '{d0}');")
        _db.psql(f"select core.ensure_ad_daily_partition(DATE '{d1}');")

    acct = sorted({r["account_id"] for r in rows})[0]
    aname = sorted({r["account_name"] for r in rows})[0]
    batch = _db.psql(
        "insert into core.import_batches (file_name, file_hash, source_path, report_type, "
        "report_start_date, report_end_date, source_row_count, valid_row_count, failed_row_count, "
        "import_status, metadata, account_id, account_name, source_kind, data_level, target_table) "
        f"values ('{path.name}', '{res['file_hash']}', '{path}', '{res['level']}', "
        f"DATE '{d0}', DATE '{d1}', {res['source_rows']}, {len(rows)}, 0, 'processing', "
        f"'{{\"dups_dropped\": {res['dup_dropped']}, \"skipped\": {res['skipped']}}}', "
        f"'{acct}', '{aname}', 'file', '{res['level']}', '{target}') returning batch_id;"
    ).strip()

    # 这些列在 DDL 里是 NOT NULL，且已在 staging 用 FORCE_NOT_NULL 保留空串
    def col_expr(c: str) -> str:
        # 必须严格按 cols 的顺序生成，batch_id 在列清单中间，不能拼到末尾
        if c == "batch_id":
            return str(batch)
        if c == "stat_date":
            return f's."{c}"::date'
        if c in NOT_NULL_TEXT:
            return f's."{c}"'
        if c in INT_COLS:
            return f'NULLIF(s."{c}", \'\')::bigint'
        if c in NUMERIC_COLS:
            return f'NULLIF(s."{c}", \'\')::numeric'
        return f'NULLIF(s."{c}", \'\')'

    sel = ", ".join(col_expr(c) for c in cols)
    upd = ", ".join(f'"{c}" = EXCLUDED."{c}"'
                    for c in cols if c not in set(uk) | {"row_hash", "batch_id"})
    _db.psql(
        f'insert into {target} ({", ".join(cols)}) '
        f'select {sel} from {stg} s '
        f'on conflict ({", ".join(uk)}) do update set {upd}, updated_at = now() '
        f'where {target}.row_hash is distinct from EXCLUDED.row_hash;',
        tuples_only=False,
    )
    cnt = _db.psql(f"select count(*) from {target};").strip()
    _db.psql(f"update core.import_batches set import_status='success', "
             f"inserted_row_count={len(rows)} where batch_id={batch};")
    print(f"    ✅ batch_id={batch}  已入库 | {target} 当前总计 {cnt} 行")
    tsv.unlink(missing_ok=True)
    return res


def backfill_ad_product() -> None:
    """设计文档 §2.2：明细报表没有「广告产品」列，用 account_id + campaign_id 从 campaign 层补齐。"""
    n = _db.psql("""
        update core.ad_daily t set ad_product = m.ad_product, updated_at = now()
        from (
          select distinct on (account_id, campaign_id) account_id, campaign_id, ad_product
          from core.ad_daily
          where data_level = 'campaign' and ad_product <> ''
          order by account_id, campaign_id, stat_date desc
        ) m
        where t.account_id = m.account_id and t.campaign_id = m.campaign_id
          and t.data_level <> 'campaign' and t.ad_product = ''
        returning 1;""")
    print(f"ad_product 补齐行数：{len(n.splitlines())}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_paths", nargs="*")
    ap.add_argument("--data-level", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backfill-ad-product", action="store_true")
    args = ap.parse_args()

    if args.backfill_ad_product:
        backfill_ad_product()
        return 0
    if not args.csv_paths:
        ap.error("至少要给一个 CSV 路径")

    for p in args.csv_paths:
        load_one(Path(p).expanduser().resolve(), args.data_level, args.dry_run)

    if not args.dry_run:
        backfill_ad_product()
    return 0


if __name__ == "__main__":
    sys.exit(main())
