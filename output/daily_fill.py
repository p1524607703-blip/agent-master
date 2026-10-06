#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
daily_fill.py
==============
自动扫描每日 Amazon 业务报告 + 推广商品报告，按产品配置把最新一天数据
回填到各产品记录表（如 S600广告记录.csv）末尾。

设计约束
--------
- 原有 CSV 记录表的表头、列结构、历史数据保持不变，只追加新行。
- 支持两行表头（Excel 合并单元格导出效果）。
- 支持原表中「单量 / 已购买」列中途插入导致的列漂移。
- 可 dry-run，可备份，失败时跳过单个产品不影响其他产品。

输入
----
1. 业务报告 CSV：按父 ASIN 取 全部订单（已订购商品数量）和 流量（会话数 - 总计）。
2. 推广商品报告 CSV：按广告活动名称关键词聚合 费用 与 购买量。
3. 产品映射配置 JSON：每个产品绑定 记录表路径、父 ASIN、广告活动关键词。

输出
----
- 直接更新各产品记录表（追加一行）。
- 生成汇总日志 output/daily_fill_YYYYMMDD.log。
- 可选生成归一化汇总表 output/daily_summary_YYYYMMDD.csv。

用法
----
    python daily_fill.py --config config/products.json --date 2026/8/25 --dry-run
    python daily_fill.py --config config/products.json --yesterday
"""

import argparse
import csv
import json
import os
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# 常量：原表列结构（基于 S600广告记录.csv 解析结果）
# ---------------------------------------------------------------------------
# 表头第 2 行（明细字段）的列索引
COL_DATE = 0
COL_COST_MANUAL = 1
COL_COST_AUTO = 2
COL_COST_HEADLINE = 3
COL_COST_VIDEO = 4
COL_COST_DISPLAY = 5
COL_ORD_MANUAL = 6
COL_ORD_AUTO = 7
COL_ORD_HEADLINE = 8
COL_ORD_VIDEO = 9
COL_ORD_DISPLAY = 10
COL_AVG_MANUAL = 11
COL_AVG_AUTO = 12
COL_AVG_HEADLINE = 13
COL_AVG_VIDEO = 14
COL_AVG_DISPLAY = 15
COL_TOTAL_COST = 16
COL_TOTAL_AD_ORD = 17
COL_ALL_ORD = 18
COL_NATURAL = 19
COL_AVG_COST = 20
COL_TRAFFIC = 21
COL_CVR = 22
COL_NOTE1 = 23
COL_NOTE2 = 24
COL_VOLUME = 25          # 单量，约 4/1 后插入
COL_PURCHASED = 26       # 已购买，4/1 后从 col25 移到 col26

COST_COLS = [COL_COST_MANUAL, COL_COST_AUTO, COL_COST_HEADLINE, COL_COST_VIDEO, COL_COST_DISPLAY]
ORD_COLS = [COL_ORD_MANUAL, COL_ORD_AUTO, COL_ORD_HEADLINE, COL_ORD_VIDEO, COL_ORD_DISPLAY]
AVG_COLS = [COL_AVG_MANUAL, COL_AVG_AUTO, COL_AVG_HEADLINE, COL_AVG_VIDEO, COL_AVG_DISPLAY]
TYPE_LABELS = ["手动", "自动", "头条", "视频", "展示"]


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def parse_num(x):
    """把 CSV 中的数字字符串转成 float；空值/百分号/逗号都处理。"""
    if x is None:
        return None
    s = str(x).strip().replace(",", "").replace("%", "").replace("US$", "").replace("$", "")
    if s == "":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fmt_money(v):
    """金额保留两位小数；空值返回空字符串。"""
    if v is None or v == "":
        return ""
    return f"{round(float(v), 2):.2f}"


def fmt_int(v):
    if v is None or v == "":
        return ""
    return str(int(round(float(v))))


def fmt_pct(v, decimals=2):
    if v is None or v == "":
        return ""
    return f"{round(float(v), decimals):.{decimals}f}%"


def format_like(value, sample):
    """按照 sample 字符串的样式（百分号、千分位、小数位）格式化数值。"""
    if value is None or value == "":
        return ""
    if sample is None or sample == "":
        return str(value)
    sample = str(sample).strip()
    has_pct = "%" in sample
    has_comma = "," in sample

    # 检测 sample 的小数位数
    m = re.search(r"[\d,]+(\.\d+)", sample)
    decimals = len(m.group(1)) - 1 if m else 0

    if has_pct:
        formatted = f"{float(value):.{decimals}f}%"
    elif decimals > 0:
        formatted = f"{float(value):.{decimals}f}"
    else:
        formatted = f"{int(round(float(value)))}"

    # 千分位（百分比不补千分位）
    if has_comma and not has_pct:
        if decimals > 0:
            int_part, dec_part = formatted.split(".")
            int_part = f"{int(int_part):,}"
            formatted = f"{int_part}.{dec_part}"
        else:
            formatted = f"{int(round(float(value))):,}"
    return formatted


def classify_campaign(name):
    """根据广告活动名称判断广告类型。"""
    if not name:
        return "其他"
    n = name.lower()
    # 优先级：展示 > 视频/头条 > 自动 > 手动
    if "展示" in name or "display" in n or "sd" in n:
        return "展示"
    if "视频" in name or "video" in n or "sbv" in n:
        return "视频"
    if "头条" in name or "brand" in n or n.startswith("sb"):
        return "头条"
    if "自动" in name or "auto" in n:
        return "自动"
    if "手动" in name or "manual" in n:
        return "手动"
    return "其他"


def date_str_to_file_date(ds):
    """把配置/参数里的 2026/8/25 转成文件名用的 20260825。"""
    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(ds, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    raise ValueError(f"无法解析日期: {ds}")


def file_date_to_table_date(ds):
    """把 20260825 转成原表风格的 2026/8/25。"""
    d = datetime.strptime(ds, "%Y%m%d")
    return f"{d.year}/{d.month}/{d.day}"


# ---------------------------------------------------------------------------
# 报告读取
# ---------------------------------------------------------------------------
def load_business_report(path, parent_asin):
    """
    从业务报告读取指定父 ASIN 的 全部订单 和 流量。
    返回 dict: {units_ordered, sessions, ordered_product_sales, cvr}
    """
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return None
    hdr = rows[0]
    # 列名可能带 BOM 或空格，做归一化映射
    col_map = {h.strip(): i for i, h in enumerate(hdr)}

    def col(*candidates):
        for c in candidates:
            if c in col_map:
                return col_map[c]
        raise KeyError(f"业务报告缺少列: {candidates}")

    asin_col = col("（父）ASIN", "(父)ASIN", "ASIN", "(父) ASIN")
    sessions_col = col("会话数 - 总计", "Sessions", "会话数")
    units_col = col("已订购商品数量", "Units Ordered", "已订购商品数量")
    sales_col = col("已订购商品销售额", "Ordered Product Sales", "已订购商品销售额")

    for r in rows[1:]:
        if not r:
            continue
        if r[asin_col].strip() == parent_asin:
            sessions = parse_num(r[sessions_col])
            units = parse_num(r[units_col])
            sales = parse_num(r[sales_col])
            cvr = (units / sessions * 100) if sessions else None
            return {
                "units_ordered": units,
                "sessions": sessions,
                "ordered_product_sales": sales,
                "cvr": cvr,
            }
    return None


def load_advertised_product_report(path, campaign_keyword):
    """
    从推广商品报告按广告活动名称关键词聚合。
    返回按广告类型分类的费用/购买量，以及总费用/总购买量。
    """
    with open(path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    if not rows:
        return None
    hdr = rows[0]
    col_map = {h.strip(): i for i, h in enumerate(hdr)}

    def col(*candidates):
        for c in candidates:
            if c in col_map:
                return col_map[c]
        raise KeyError(f"推广商品报告缺少列: {candidates}")

    campaign_col = col("广告活动名称", "Campaign Name")
    cost_col = col("总成本", "Spend", "Cost")
    pur_col = col("购买量", "Purchases", "Orders")

    summary = defaultdict(lambda: {"cost": 0.0, "orders": 0.0})
    for r in rows[1:]:
        if not r or not r[campaign_col]:
            continue
        campaign = r[campaign_col]
        if campaign_keyword and campaign_keyword not in campaign:
            continue
        ctype = classify_campaign(campaign)
        cost = parse_num(r[cost_col]) or 0.0
        orders = parse_num(r[pur_col]) or 0.0
        summary[ctype]["cost"] += cost
        summary[ctype]["orders"] += orders

    # 总费用/总单量只统计五大类型，不包含"其他"
    total_cost = sum(summary[t]["cost"] for t in TYPE_LABELS)
    total_orders = sum(summary[t]["orders"] for t in TYPE_LABELS)

    return {
        "by_type": {t: summary[t] for t in TYPE_LABELS + ["其他"]},
        "total_cost": total_cost,
        "total_orders": total_orders,
    }


# ---------------------------------------------------------------------------
# 记录表操作
# ---------------------------------------------------------------------------
def detect_table_width(rows):
    """返回记录表当前最大列数，用于决定新行宽度。"""
    return max((len(r) for r in rows if r), default=0)


def find_last_date_row(rows):
    """找到最后一个有有效日期的数据行索引。"""
    last_idx = None
    for i, r in enumerate(rows):
        if r and r[0] and "/" in r[0]:
            last_idx = i
    return last_idx


def find_last_valid_sample_row(rows):
    """找到最后一个日期行且 总费用 非空（即有真实数据）的行索引。"""
    for i in range(len(rows) - 1, -1, -1):
        r = rows[i]
        if r and r[0] and "/" in r[0]:
            if len(r) > COL_TOTAL_COST and r[COL_TOTAL_COST].strip():
                return i
    return None


def date_exists(rows, date_str):
    """检查 date_str 是否已存在于记录表中。"""
    for r in rows:
        if r and r[0] == date_str:
            return True
    return False


def build_new_row(date_str, biz, ads, table_width, sample_row=None, fill_purchased=True):
    """
    根据业务数据和广告数据，构造符合原表结构的新行。
    table_width: 当前表的列数，用于兼容旧表（无单量列）和新表（有单量列）。
    sample_row: 上一行数据，用于模仿其数字格式（千分位、小数位、百分号）。
    fill_purchased: 是否回填「已购买」与「自然单」。
    """
    sample = sample_row or []

    # 各类型费用/单量
    cost = {}
    orders = {}
    for i, t in enumerate(TYPE_LABELS):
        cost[t] = ads["by_type"][t]["cost"]
        orders[t] = ads["by_type"][t]["orders"]

    total_cost = ads["total_cost"]
    total_orders = ads["total_orders"]
    units = biz["units_ordered"] if biz else None
    sessions = biz["sessions"] if biz else None
    cvr = biz["cvr"] if biz else None

    # 平均费用/单（按广告类型）：0/0 视为 0.00，与运营表保持一致
    avg = {}
    for t in TYPE_LABELS:
        if orders[t]:
            avg[t] = cost[t] / orders[t]
        else:
            avg[t] = 0.0

    # 混合平均费用 = 总费用 / 全部订单
    blended_cpo = (total_cost / units) if (total_cost and units) else None

    # 已购买与自然单
    purchased = total_orders if (fill_purchased and total_orders) else None
    natural = None
    if fill_purchased and units is not None and purchased is not None:
        natural = units - purchased

    def cell(idx, value):
        """用 sample_row 同列的格式输出 value；sample 为空时用列类型默认格式。"""
        if value is None or value == "":
            return ""
        samp = sample[idx] if (sample and idx < len(sample)) else ""
        if samp:
            return format_like(value, samp)
        # fallback 默认格式
        if idx in (COST_COLS + AVG_COLS + [COL_TOTAL_COST, COL_AVG_COST]):
            return f"{float(value):.2f}"
        if idx == COL_CVR:
            return f"{float(value):.2f}%"
        if idx in (ORD_COLS + [COL_TOTAL_AD_ORD, COL_ALL_ORD, COL_NATURAL, COL_PURCHASED]):
            return f"{int(round(float(value)))}"
        if idx == COL_TRAFFIC:
            v = int(round(float(value)))
            return f"{v:,}"
        return str(value)

    row = [""] * max(table_width, COL_PURCHASED + 1)
    row[COL_DATE] = date_str

    # 广告费用
    for i, t in enumerate(TYPE_LABELS):
        row[COST_COLS[i]] = cell(COST_COLS[i], cost[t])
    # 广告单量
    for i, t in enumerate(TYPE_LABELS):
        row[ORD_COLS[i]] = cell(ORD_COLS[i], orders[t])
    # 平均费用/单
    for i, t in enumerate(TYPE_LABELS):
        row[AVG_COLS[i]] = cell(AVG_COLS[i], avg[t])

    row[COL_TOTAL_COST] = cell(COL_TOTAL_COST, total_cost) if total_cost else cell(COL_TOTAL_COST, 0.0)
    row[COL_TOTAL_AD_ORD] = cell(COL_TOTAL_AD_ORD, total_orders) if total_orders else cell(COL_TOTAL_AD_ORD, 0)
    row[COL_ALL_ORD] = cell(COL_ALL_ORD, units) if units is not None else ""
    row[COL_NATURAL] = cell(COL_NATURAL, natural) if natural is not None else ""
    row[COL_AVG_COST] = cell(COL_AVG_COST, blended_cpo) if blended_cpo is not None else ""
    row[COL_TRAFFIC] = cell(COL_TRAFFIC, sessions) if sessions is not None else ""
    row[COL_CVR] = cell(COL_CVR, cvr) if cvr is not None else ""

    # 单量 / 已购买
    if table_width > COL_VOLUME:
        row[COL_VOLUME] = ""  # 含义不明，保持手工可控
    if table_width > COL_PURCHASED:
        row[COL_PURCHASED] = cell(COL_PURCHASED, purchased) if purchased is not None else ""

    return row


def append_to_record(record_path, new_row, backup=True, dry_run=False):
    """把新行追加到记录表。若 dry_run 则不写文件。"""
    with open(record_path, encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))

    width = detect_table_width(rows)
    # 补齐新行宽度
    if len(new_row) < width:
        new_row = new_row + [""] * (width - len(new_row))
    elif len(new_row) > width:
        new_row = new_row[:width]

    if dry_run:
        return rows, new_row

    # 备份原文件
    if backup:
        backup_path = str(record_path) + ".bak"
        shutil.copy2(record_path, backup_path)

    # 找到第一个空白行追加，或追加到文件末尾
    insert_idx = len(rows)
    for i in range(2, len(rows)):  # 从表头之后开始
        if not rows[i] or not any(rows[i]):
            insert_idx = i
            break

    if insert_idx < len(rows):
        rows[insert_idx] = new_row
    else:
        rows.append(new_row)

    with open(record_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(rows)

    return rows, new_row


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="每日自动回填产品记录表")
    parser.add_argument("--config", required=True, help="产品映射 JSON 配置文件")
    parser.add_argument("--date", help="目标日期，格式 2026/8/25；默认昨天")
    parser.add_argument("--yesterday", action="store_true", help="使用昨天日期")
    parser.add_argument("--dry-run", action="store_true", help="试运行，不修改原表")
    parser.add_argument("--no-backup", action="store_true", help="不备份原表")
    parser.add_argument("--summary", action="store_true", help="同时输出归一化汇总表")
    args = parser.parse_args()

    # 确定目标日期
    if args.yesterday:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
    elif args.date:
        target_date = args.date
    else:
        target_date = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")

    file_date = date_str_to_file_date(target_date)
    table_date = file_date_to_table_date(file_date)

    # 加载配置
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    # 解析报告路径模板
    biz_pattern = config.get("reports", {}).get("business", "./daily_reports/business_report_{date}.csv")
    adv_pattern = config.get("reports", {}).get("advertised_product", "./daily_reports/advertised_product_{date}.csv")

    biz_path = biz_pattern.format(date=file_date)
    adv_path = adv_pattern.format(date=file_date)

    if not os.path.exists(biz_path):
        print(f"[错误] 业务报告不存在: {biz_path}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(adv_path):
        print(f"[错误] 推广商品报告不存在: {adv_path}", file=sys.stderr)
        sys.exit(1)

    products = config.get("products", [])
    if not products:
        print("[警告] 配置中未找到产品映射", file=sys.stderr)
        sys.exit(0)

    summary_rows = []
    log_lines = [f"daily_fill 运行时间: {datetime.now().isoformat()}",
                 f"目标日期: {table_date}",
                 f"业务报告: {biz_path}",
                 f"推广商品报告: {adv_path}",
                 ""]

    for p in products:
        name = p.get("name", "未命名")
        record_file = p.get("record_file")
        parent_asin = p.get("parent_asin")
        keyword = p.get("campaign_keyword", "")

        print(f"\n>>> 处理产品: {name} (ASIN={parent_asin}, keyword={keyword})")
        log_lines.append(f"产品: {name} | ASIN={parent_asin} | keyword={keyword}")

        if not record_file or not os.path.exists(record_file):
            msg = f"[跳过] 记录表不存在: {record_file}"
            print(msg)
            log_lines.append(msg)
            continue

        # 读取记录表并检查日期是否已存在
        with open(record_file, encoding="utf-8-sig") as f:
            record_rows = list(csv.reader(f))
        if date_exists(record_rows, table_date):
            msg = f"[跳过] 日期 {table_date} 已存在于 {record_file}"
            print(msg)
            log_lines.append(msg)
            continue

        # 读取两份报告
        biz = load_business_report(biz_path, parent_asin)
        ads = load_advertised_product_report(adv_path, keyword)

        if biz is None:
            msg = f"[警告] 业务报告中未找到 ASIN {parent_asin}"
            print(msg)
            log_lines.append(msg)
            # 仍然继续填充广告数据，业务数据留空
        if ads is None:
            msg = f"[警告] 推广商品报告中未找到 keyword={keyword} 的数据"
            print(msg)
            log_lines.append(msg)
            continue

        # 构造新行并追加
        table_width = detect_table_width(record_rows)
        sample_idx = find_last_valid_sample_row(record_rows)
        sample_row = record_rows[sample_idx] if sample_idx is not None else None
        fill_purchased = p.get("fill_purchased_and_natural", True)
        new_row = build_new_row(table_date, biz, ads, table_width, sample_row, fill_purchased)
        _, written_row = append_to_record(
            record_file, new_row,
            backup=not args.no_backup, dry_run=args.dry_run
        )

        action = "[dry-run 预览]" if args.dry_run else "[已追加]"
        print(f"{action} {record_file}: {table_date}")
        print(f"    总费用={ads['total_cost']:.2f} 总广告单={ads['total_orders']:.0f} "
              f"全部订单={biz['units_ordered'] if biz else '-'} 流量={biz['sessions'] if biz else '-'}")
        log_lines.append(
            f"{action} {record_file}: 总费用={ads['total_cost']:.2f} "
            f"总广告单={ads['total_orders']:.0f} 全部订单={biz['units_ordered'] if biz else '-'} "
            f"流量={biz['sessions'] if biz else '-'}"
        )

        summary_rows.append({
            "date": table_date,
            "product": name,
            "parent_asin": parent_asin,
            "total_cost": round(ads["total_cost"], 2) if ads["total_cost"] else None,
            "total_ad_orders": int(round(ads["total_orders"])) if ads["total_orders"] else None,
            "units_ordered": int(round(biz["units_ordered"])) if biz and biz["units_ordered"] is not None else None,
            "sessions": int(round(biz["sessions"])) if biz and biz["sessions"] is not None else None,
            "cvr": round(biz["cvr"], 2) if biz and biz["cvr"] is not None else None,
            "blended_cpo": round(ads["total_cost"] / biz["units_ordered"], 2) if (biz and biz["units_ordered"]) else None,
        })

    # 写日志
    log_dir = Path(config.get("output_dir", "./output"))
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"daily_fill_{file_date}.log"
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"\n日志已写入: {log_path}")

    # 可选输出归一化汇总表
    if args.summary and summary_rows:
        summary_path = log_dir / f"daily_summary_{file_date}.csv"
        with open(summary_path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=[
                "date", "product", "parent_asin", "total_cost", "total_ad_orders",
                "units_ordered", "sessions", "cvr", "blended_cpo"
            ])
            w.writeheader()
            w.writerows(summary_rows)
        print(f"汇总表已写入: {summary_path}")


if __name__ == "__main__":
    main()
