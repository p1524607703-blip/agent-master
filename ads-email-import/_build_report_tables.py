#!/usr/bin/env python3
"""按「一份报告一张表」重建 amazon_ads_v2 的广告事实层。

设计原则
  1. 新表列 = ODS 中该 data_level 实测非空的列 + 主键列 + 血缘列 —— 不保留任何死列
  2. 主键用业务自然键；导入用普通 INSERT（不写 ON CONFLICT），冲突就报错，杜绝静默覆盖
  3. batch_id 建真外键指向 core.import_batches，血缘列从 import_batches 回填
  4. 只建表不删表：原 core.ad_daily / core.search_term_daily 保留为 ODS

产出：sql/003_report_tables.sql（可审查）+ 直接执行
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 2026-09-30：数据库已从阿里云 RDS 迁至腾讯云服务器自建 PostgreSQL。
# 实际连接一律走本机 SSH 隧道（127.0.0.1:15432）；本脚本只生成 DDL 文件、不直接连库，
# 这里的常量仅作占位与文档用途。旧值 pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com 已作废。
HOST = "127.0.0.1"
PORT = "15432"
DB = "amazon_ads_v2"
USER = "amazon_ads_admin"
OUT = Path(__file__).resolve().parent / "sql" / "003_report_tables.sql"

# ODS 里跨报告通用的列，不算业务列
META = {
    "account_id", "ad_product", "data_level", "grain_level", "campaign_id",
    "ad_group_id", "stat_date", "dimension_key", "row_hash",
    "first_imported_at", "updated_at", "batch_id", "source_file_name", "source_file_hash",
}

# 每条报告的：新表名 / ODS 来源 data_level / 主键列 / 报告中文名
REPORTS = [
    ("core.report_campaign_daily", "campaign",
     ["account_id", "ad_product", "campaign_id", "stat_date"], "广告活动报告"),
    ("core.report_placement_daily", "placement",
     ["account_id", "ad_product", "campaign_id", "ad_group_id", "placement", "stat_date"], "广告位报告"),
    ("core.report_targeting_daily", "targeting",
     ["account_id", "ad_product", "campaign_id", "ad_group_id", "target_id", "stat_date"], "投放报告"),
    ("core.report_advertised_product_daily", "advertised_product",
     ["account_id", "ad_product", "campaign_id", "ad_group_id", "advertised_product_id", "stat_date"], "推广的商品报告"),
    ("core.report_purchased_product_daily", "purchased_product",
     ["account_id", "ad_product", "campaign_id", "ad_group_id", "purchased_product_id", "stat_date"], "达成转化的商品报告"),
]

# 主键里可能为 NULL 的文本列，统一 COALESCE 成空串（NOT NULL）
NULLABLE_KEYS = {"ad_group_id", "target_id", "advertised_product_id", "purchased_product_id"}
# 建索引的列
INDEX_SPECS = {
    "core.report_campaign_daily":            [["account_id", "stat_date"], ["campaign_id"]],
    "core.report_placement_daily":           [["account_id", "stat_date"], ["campaign_id", "ad_group_id"]],
    "core.report_targeting_daily":           [["account_id", "stat_date"], ["campaign_id", "ad_group_id"], ["target_id"]],
    "core.report_advertised_product_daily":  [["account_id", "stat_date"], ["campaign_id", "ad_group_id"]],
    "core.report_purchased_product_daily":   [["account_id", "stat_date"], ["campaign_id", "ad_group_id"], ["purchased_product_id"]],
    "core.report_search_term_daily":         [["account_id", "stat_date"], ["campaign_id", "ad_group_id"], ["search_term"]],
}


def psql(sql: str, db: str = DB) -> list[list[str]]:
    proc = subprocess.run(
        ["psql", "-w", "-h", HOST, "-U", USER, "-d", db,
         "-X", "-q", "-t", "-A", "-F", "|", "-v", "ON_ERROR_STOP=1", "-c", sql],
        capture_output=True, text=True, timeout=180,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return [ln.split("|") for ln in proc.stdout.strip().split("\n") if ln]


def used_columns(level: str) -> tuple[list[str], int]:
    """返回该 data_level 实测非空的业务列（已排除 META），以及行数。"""
    cols = [r[0] for r in psql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='core' AND table_name='ad_daily' ORDER BY ordinal_position")]
    expr = ", ".join(f'count("{c}")' for c in cols)
    row = psql(f"SELECT count(*), {expr} FROM core.ad_daily WHERE data_level='{level}'")[0]
    n = int(row[0])
    counts = [int(x) for x in row[1:]]
    biz = [c for c, v in zip(cols, counts) if v > 0 and c not in META]
    return biz, n


def build() -> str:
    out: list[str] = []
    out.append("-- 003_report_tables.sql")
    out.append("-- 按「一份报告一张表」重建广告事实层。由 _build_report_tables.py 生成，可重复执行（先 DROP）。")
    out.append("-- 原则：只保留实测有值的列，不保留死列；主键=业务自然键；batch_id 建真外键。")
    out.append("")
    out.append("BEGIN;")
    out.append("")

    summary: list[tuple[str, int, int, list[str]]] = []

    for table, level, keys, cn in REPORTS:
        biz, n = used_columns(level)
        metrics = [c for c in biz if c not in keys]
        exprs = [f"COALESCE(b.{k}, '') AS {k}" if k in NULLABLE_KEYS else f"b.{k}" for k in keys]
        exprs += [f"b.{c}" for c in metrics]
        exprs += [
            "ib.file_name AS source_file_name",
            "ib.file_hash AS source_file_hash",
            "b.row_hash",
            "b.batch_id",
            "b.first_imported_at",
            "NOW() AS loaded_at",
        ]
        out.append(f"-- ===== {cn}（{level}）源行数 {n:,} / 业务列 {len(metrics)} =====")
        out.append(f"DROP TABLE IF EXISTS {table};")
        out.append(f"CREATE TABLE {table} AS")
        out.append("SELECT")
        out.append("    " + ",\n    ".join(exprs))
        out.append("FROM   core.ad_daily b")
        out.append("LEFT   JOIN core.import_batches ib ON ib.batch_id = b.batch_id")
        out.append(f"WHERE  b.data_level = '{level}';")
        out.append("")
        for k in keys:
            out.append(f"ALTER TABLE {table} ALTER COLUMN {k} SET NOT NULL;")
        for m in ("row_hash", "batch_id", "source_file_name", "source_file_hash"):
            out.append(f"ALTER TABLE {table} ALTER COLUMN {m} SET NOT NULL;")
        out.append(f"ALTER TABLE {table} ADD PRIMARY KEY ({', '.join(keys)});")
        cname = table.split(".")[1]
        out.append(f"ALTER TABLE {table} ADD CONSTRAINT fk_{cname}_batch "
                   f"FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);")
        for spec in INDEX_SPECS[table]:
            nm = f"idx_{cname}_{'_'.join(spec)}"
            out.append(f"CREATE INDEX {nm} ON {table} ({', '.join(spec)});")
        out.append(f"COMMENT ON TABLE {table} IS "
                   f"'{cn}日粒度事实表（{level}）。来自 ODS core.ad_daily，只保留本报告有值的列。';")
        out.append("")
        summary.append((table, n, len(metrics), keys))

    # ---- 搜索词报告：源为 core.search_term_daily，需回填 ad_product ----
    st_cols = [r[0] for r in psql(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='core' AND table_name='search_term_daily' ORDER BY ordinal_position")]
    counts_expr = ", ".join(f'count("{c}")' for c in st_cols)
    row = psql(f"SELECT count(*), {counts_expr} FROM core.search_term_daily")[0]
    st_n = int(row[0])
    st_counts = [int(x) for x in row[1:]]
    st_biz = [c for c, v in zip(st_cols, st_counts) if v > 0 and c not in META]
    st_keys = ["account_id", "ad_product", "campaign_id", "ad_group_id", "search_term", "stat_date"]
    st_metrics = [c for c in st_biz if c not in st_keys]

    out.append(f"-- ===== 搜索词报告（search_term）源行数 {st_n:,} / 业务列 {len(st_metrics)} =====")
    out.append("-- 搜索词报表源 CSV 无「广告产品」列，ad_product 原为空串；")
    out.append("-- 这里从广告活动报告（6 份报表中唯一带该列的）按 (account_id, campaign_id) 回填。")
    out.append("DROP TABLE IF EXISTS core.report_search_term_daily;")
    out.append("CREATE TABLE core.report_search_term_daily AS")
    out.append("SELECT")
    st_exprs = ["COALESCE(cm.ad_product, '') AS ad_product"]
    st_exprs += [f"s.{k}" for k in st_keys if k != "ad_product"]
    st_exprs += [f"s.{c}" for c in st_metrics]
    st_exprs += [
        "ib.file_name AS source_file_name",
        "ib.file_hash AS source_file_hash",
        "s.row_hash",
        "s.batch_id",
        "s.first_imported_at",
        "NOW() AS loaded_at",
    ]
    out.append("    " + ",\n    ".join(st_exprs))
    out.append("FROM   core.search_term_daily s")
    out.append("LEFT   JOIN (SELECT DISTINCT account_id, campaign_id, ad_product")
    out.append("           FROM core.ad_daily WHERE data_level='campaign' AND ad_product <> '') cm")
    out.append("       ON cm.account_id = s.account_id AND cm.campaign_id = s.campaign_id")
    out.append("LEFT   JOIN core.import_batches ib ON ib.batch_id = s.batch_id;")
    out.append("")
    for k in st_keys:
        out.append(f"ALTER TABLE core.report_search_term_daily ALTER COLUMN {k} SET NOT NULL;")
    for m in ("row_hash", "batch_id", "source_file_name", "source_file_hash"):
        out.append(f"ALTER TABLE core.report_search_term_daily ALTER COLUMN {m} SET NOT NULL;")
    out.append(f"ALTER TABLE core.report_search_term_daily ADD PRIMARY KEY ({', '.join(st_keys)});")
    out.append("ALTER TABLE core.report_search_term_daily ADD CONSTRAINT fk_report_search_term_daily_batch "
               "FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);")
    for spec in INDEX_SPECS["core.report_search_term_daily"]:
        nm = f"idx_report_search_term_daily_{'_'.join(spec)}"
        out.append(f"CREATE INDEX {nm} ON core.report_search_term_daily ({', '.join(spec)});")
    out.append("COMMENT ON TABLE core.report_search_term_daily IS "
               "'搜索词报告日粒度事实表（search_term）。ad_product 由活动报告回填。';")
    out.append("")
    summary.append(("core.report_search_term_daily", st_n, len(st_metrics), st_keys))

    out.append("COMMIT;")
    out.append("")
    out.append("-- ===== 汇总 =====")
    for t, n, m, _ in summary:
        out.append(f"-- {t:<44} 预期 {n:>7,} 行 / {m:>2} 个业务列")
    return "\n".join(out), summary


if __name__ == "__main__":
    sql, summary = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(sql, encoding="utf-8")
    print(f"已生成 {OUT}  ({len(sql):,} 字符)\n")
    for t, n, m, keys in summary:
        print(f"  {t:<44} {n:>7,} 行  {m:>2} 业务列  PK={','.join(keys)}")
