#!/usr/bin/env python3
"""
把 Amazon Ads「已订阅报告」导出的中文 CSV 载入 core.ad_daily。

用法：
    python3 load_report.py <csv路径> [--data-level campaign|advertised_product|...]
                           [--account-id <覆盖值>] [--dry-run]

流程（对应设计文档 §16 导入流程）：
    算 file_hash → file_hash 是否已导入 → staging → 字段标准化 → 业务键去重
    → 算 dimension_key / row_hash → 与正式表比对 → INSERT / UPDATE / SKIP
    → 写 import_batches 审计
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import _db

# ---------------------------------------------------------------------------
# 列映射：中文表头（去空格、去 BOM）→ core.ad_daily 英文列
# ---------------------------------------------------------------------------
DIM_MAP = {
    "预算货币": "budget_currency",
    "广告主账户 ID": "account_id",
    "广告主账户名称": "account_name",
    "广告产品": "ad_product",
    "广告组合编号": "portfolio_id",
    "广告组合名称": "portfolio_name",
    "广告活动编号": "campaign_id",
    "广告活动名称": "campaign_name",
    "广告活动投放状态": "campaign_state",
    "广告组编号": "ad_group_id",
    "广告组名称": "ad_group_name",
    "推广的商品编号": "advertised_product_id",
    "推广的商品名称": "advertised_product_name",
    "推广的商品父级编号": "advertised_product_parent_id",
    "推广的商品品牌": "advertised_product_brand",
    "推广的商品品类": "advertised_product_category",
    "推广的商品子品类": "advertised_product_subcategory",
    "推广的商品组": "advertised_product_group",
    "推广的商品 SKU": "advertised_product_sku",
    "推广的商品站点": "advertised_product_marketplace",
    "达成转化的商品编号": "purchased_product_id",
    "达成转化的商品名称": "purchased_product_name",
    "达成转化的商品站点": "purchased_product_marketplace",
    "广告位": "placement",
    "匹配类型": "target_match_type",
    "投放": "target_text",
    "投放编号": "target_id",
    "投放状态": "target_status",
    "日期": "stat_date",
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
    "浏览点击率 (vCTR)": "vctr_pct",
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

# 插入 core.ad_daily 的列顺序（与 DDL 对应；技术列由脚本填）
INSERT_COLS = [
    "account_id", "account_name", "manager_account", "ad_product",
    "portfolio_id", "portfolio_name", "campaign_id", "campaign_name",
    "campaign_state", "global_campaign_id", "ad_group_id", "ad_group_name",
    "stat_date", "budget_currency", "data_level", "grain_level", "dimension_key",
    "placement", "target_id", "target_text", "target_match_type", "target_bid",
    "target_type", "target_status",
    "advertised_product_id", "advertised_product_name", "advertised_product_parent_id",
    "advertised_product_brand", "advertised_product_category",
    "advertised_product_subcategory", "advertised_product_group",
    "advertised_product_sku", "advertised_product_marketplace",
    "purchased_product_id", "purchased_product_name", "purchased_product_marketplace",
    "impressions", "viewable_impressions", "clicks", "spend", "purchases", "sales", "units",
    "promoted_purchases", "promoted_sales", "promoted_units",
    "halo_purchases", "halo_sales", "halo_units",
    "new_to_brand_purchases", "new_to_brand_sales", "new_to_brand_units",
    "long_term_sales", "detail_page_views",
    "ctr_pct", "vctr_pct", "cpc", "cvr_pct", "cpa", "acos_pct", "roas",
    "promoted_cpa", "promoted_cvr_pct", "promoted_acos_pct", "promoted_roas",
    "new_to_brand_cpa", "new_to_brand_cvr_pct", "new_to_brand_acos_pct", "new_to_brand_roas",
    "long_term_roas", "cost_per_detail_page_view", "detail_page_view_rate_pct",
    "row_hash", "batch_id", "source_file_name", "source_file_hash",
]

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
    """去掉 Excel `="..."` 包装、首尾空白。"""
    if v is None:
        return ""
    v = v.strip().strip("\ufeff")
    m = EXCEL_WRAP.match(v)
    if m and v.startswith('="'):
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
    """把 '0.6098%' / '1,234.56' 转成纯数值字符串；空→''（后续按 NULL 处理）。"""
    v = norm_text(v)
    if v == "" or v == "-" or v == "--":
        return ""
    v = v.replace("%", "").replace(",", "").replace("$", "").strip()
    if v in ("", "-"):
        return ""
    try:
        float(v)
    except ValueError:
        return ""
    return v


def detect_data_level(header: list[str]) -> str:
    h = set(header)
    if "搜索词" in h:
        return "search_term"
    if "投放" in h:
        return "targeting"
    if "成交的广告位" in h or "广告位" in h:
        return "placement"
    if "达成转化的商品编号" in h or "已售商品编号" in h:
        return "purchased_product"
    if "推广的商品编号" in h or "推广的商品名称" in h:
        return "advertised_product"
    if "广告活动编号" in h and "广告组编号" not in h:
        return "campaign"
    raise SystemExit(f"无法识别的报表类型，表头：{header[:8]}...")


def build_dimension_key(level: str, row: dict) -> str:
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
    """Amazon 未提供的高频派生指标在此补齐（设计文档 §7.2 保存规则 2）。"""
    def f(k):
        v = row.get(k)
        if v in (None, ""):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    imp, clk, spend = f("impressions"), f("clicks"), f("spend")
    pur, sales, dpv = f("purchases"), f("sales"), f("detail_page_views")
    vib = f("viewable_impressions")

    def put(key, val, digits=6):
        if row.get(key) in (None, "") and val is not None:
            row[key] = f"{val:.{digits}f}"

    # 注意：spend 可能为 0（纯自然/光环出单），所有除法都必须防零
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


ROW_HASH_COLS = [
    "account_id", "ad_product", "data_level", "grain_level", "campaign_id",
    "ad_group_id", "stat_date", "dimension_key",
    "impressions", "viewable_impressions", "clicks", "spend", "purchases", "sales", "units",
    "promoted_purchases", "promoted_sales", "promoted_units",
    "halo_purchases", "halo_sales", "halo_units",
    "new_to_brand_purchases", "new_to_brand_sales", "new_to_brand_units",
    "long_term_sales", "detail_page_views",
    "ctr_pct", "vctr_pct", "cpc", "cvr_pct", "cpa", "acos_pct", "roas",
]


def row_hash(row: dict) -> str:
    payload = "|".join(str(row.get(c, "") or "") for c in ROW_HASH_COLS)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def parse_file(path: Path, data_level: str | None, account_id: str | None):
    raw = path.read_bytes()
    file_hash = hashlib.sha256(raw).hexdigest()
    text = raw.decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    header = [norm_text(h) for h in next(reader)]
    level = data_level or detect_data_level(header)

    col_index: dict[str, int] = {}
    for i, h in enumerate(header):
        key = h
        # 「推广的商品 SKU-Advertised product SKU」这类带英文后缀的列，取破折号前半段匹配
        if key not in DIM_MAP and "-" in key:
            key = key.split("-")[0].strip()
        col_index.setdefault(key, i)

    rows_out = []
    skipped_no_key = 0
    dup_map: dict[tuple, int] = {}
    dup_dropped = 0

    for raw_row in reader:
        if not raw_row or all(not c.strip() for c in raw_row):
            continue
        row: dict[str, str] = {c: "" for c in INSERT_COLS}

        for cn, en in DIM_MAP.items():
            i = col_index.get(cn)
            if i is not None and i < len(raw_row):
                row[en] = norm_text(raw_row[i])
        for cn, en in METRIC_MAP.items():
            i = col_index.get(cn)
            if i is not None and i < len(raw_row):
                row[en] = norm_num(raw_row[i])
        for cn, en in DERIVED_MAP.items():
            i = col_index.get(cn)
            if i is not None and i < len(raw_row):
                val = norm_num(raw_row[i])
                if val != "" and not row.get(en):
                    row[en] = val

        row["stat_date"] = norm_date(row.get("stat_date", "")) or ""
        if not row["stat_date"]:
            skipped_no_key += 1
            continue
        if account_id:
            row["account_id"] = account_id
        if not row["account_id"] or not row["campaign_id"]:
            skipped_no_key += 1
            continue

        row["data_level"] = level
        row["grain_level"] = "ad_group" if row.get("ad_group_id") else "campaign"
        row["ad_group_id"] = row.get("ad_group_id") or ""
        row["ad_product"] = row.get("ad_product") or ""
        row["dimension_key"] = build_dimension_key(level, row)
        compute_derived(row)
        row["source_file_name"] = path.name
        row["source_file_hash"] = file_hash

        # 同批业务键去重：优先保留维度完整且指标非零的记录（设计文档 §9.1）
        key = (row["account_id"], row["ad_product"], row["data_level"], row["grain_level"],
               row["campaign_id"], row["ad_group_id"], row["stat_date"], row["dimension_key"])
        if key in dup_map:
            prev = rows_out[dup_map[key]]
            prev_score = (bool(prev.get("advertised_product_name")),
                          bool(prev.get("advertised_product_parent_id")),
                          float(prev.get("impressions") or 0) + float(prev.get("spend") or 0))
            new_score = (bool(row.get("advertised_product_name")),
                         bool(row.get("advertised_product_parent_id")),
                         float(row.get("impressions") or 0) + float(row.get("spend") or 0))
            if new_score > prev_score:
                rows_out[dup_map[key]] = row
            dup_dropped += 1
            continue
        dup_map[key] = len(rows_out)
        rows_out.append(row)

    for r in rows_out:
        r["row_hash"] = row_hash(r)

    return {
        "file_hash": file_hash,
        "data_level": level,
        "header": header,
        "rows": rows_out,
        "source_rows": len(rows_out) + dup_dropped + skipped_no_key,
        "dup_dropped": dup_dropped,
        "skipped_no_key": skipped_no_key,
    }


def write_tsv(rows: list[dict], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t", quoting=csv.QUOTE_MINIMAL)
        for r in rows:
            w.writerow([r.get(c, "") if r.get(c) is not None else "" for c in INSERT_COLS])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_path")
    ap.add_argument("--data-level", default=None)
    ap.add_argument("--account-id", default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--target-table", default="core.ad_daily")
    args = ap.parse_args()

    path = Path(args.csv_path).expanduser().resolve()
    result = parse_file(path, args.data_level, args.account_id)
    rows = result["rows"]

    print(f"文件            : {path.name}")
    print(f"file_hash       : {result['file_hash']}")
    print(f"data_level      : {result['data_level']}")
    print(f"源数据行        : {result['source_rows']}")
    print(f"同批重复丢弃    : {result['dup_dropped']}")
    print(f"缺主键跳过      : {result['skipped_no_key']}")
    print(f"待入库唯一行    : {len(rows)}")

    if rows:
        accs = {r["account_id"] for r in rows}
        names = {r["account_name"] for r in rows}
        dates = sorted({r["stat_date"] for r in rows})
        print(f"账户            : {accs}")
        print(f"账户名          : {names}")
        print(f"日期区间        : {dates[0]} ~ {dates[-1]}  ({len(dates)} 天)")
        print(f"Campaign 数     : {len({r['campaign_id'] for r in rows})}")

    if args.dry_run:
        print("\n[dry-run] 未写库。")
        return 0

    staging = "stg.ad_daily_load"
    _db.psql("CREATE SCHEMA IF NOT EXISTS stg;")
    _db.psql(f"DROP TABLE IF EXISTS {staging};")
    _db.psql(f"CREATE UNLOGGED TABLE {staging} ("
             + ", ".join(f'"{c}" text' for c in INSERT_COLS) + ");")

    tsv = Path("/tmp") / f"ad_daily_{result['file_hash'][:12]}.tsv"
    write_tsv(rows, tsv)

    copy_sql = (f"\\copy {staging} FROM '{tsv}' WITH (FORMAT csv, DELIMITER E'\\t', HEADER false)")
    _db.psql(copy_sql, tuples_only=False, timeout=1800)

    date_min, date_max = min(r["stat_date"] for r in rows), max(r["stat_date"] for r in rows)
    _db.psql(f"SELECT core.ensure_ad_daily_partition(DATE '{date_min}');")
    _db.psql(f"SELECT core.ensure_ad_daily_partition(DATE '{date_max}');")

    batch = _db.psql(
        "INSERT INTO core.import_batches "
        "(account_id, account_name, source_kind, source_path, file_name, file_hash, "
        " report_type, data_level, target_table, report_start_date, report_end_date, "
        " source_row_count, valid_row_count, import_status) VALUES ("
        f" '{sorted({r['account_id'] for r in rows})[0]}',"
        f" '{sorted({r['account_name'] for r in rows})[0]}',"
        f" 'file', '{path}', '{path.name}', '{result['file_hash']}',"
        f" '{result['data_level']}', '{result['data_level']}', '{args.target_table}',"
        f" DATE '{date_min}', DATE '{date_max}',"
        f" {result['source_rows']}, {len(rows)}, 'loading') RETURNING batch_id;"
    ).strip()
    print(f"batch_id        : {batch}")

    sel = ", ".join(f'NULLIF(s."{c}", \'\')' if c in (NUMERIC_COLS | INT_COLS) else f's."{c}"'
                    for c in INSERT_COLS if c != "batch_id")
    update_set = ", ".join(
        f'"{c}" = EXCLUDED."{c}"'
        for c in INSERT_COLS
        if c not in {"account_id", "ad_product", "data_level", "grain_level",
                     "campaign_id", "ad_group_id", "stat_date", "dimension_key",
                     "row_hash", "batch_id", "first_imported_at"}
    )
    sql = (
        f"INSERT INTO {args.target_table} ({', '.join(INSERT_COLS)}) "
        f"SELECT {sel}, {batch} FROM {staging} s "
        f"ON CONFLICT (account_id, ad_product, data_level, grain_level, campaign_id, "
        f"ad_group_id, stat_date, dimension_key) DO UPDATE SET {update_set}, "
        f"updated_at = now() WHERE {args.target_table}.row_hash IS DISTINCT FROM EXCLUDED.row_hash;"
    )
    _db.psql(sql, tuples_only=False, timeout=1800)

    counts = _db.psql(
        f"SELECT import_status||'|'||inserted_row_count FROM core.import_batches WHERE batch_id={batch};"
    ).strip()
    print(f"batch 状态      : {counts}")
    print(f"[OK] 已载入 {args.target_table}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
