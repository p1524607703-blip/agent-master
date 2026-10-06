#!/usr/bin/env python3
"""按「日期区间」把历史副本切片后灌进 canonical 事实层（补窗口遗漏用）。

背景
----
Amazon Ads 的 30D 订阅报告是**滚动窗口**：今天下载只覆盖「今天往回数 30 天」。
如果某个账户在窗口滚动过去之前没有成功入库，那段日期就永久缺失（30D 再也回不去）。

但亚马逊的「报告历史记录」页会**按天留存**每一份生成过的报告（报告期 = 最近 30 天），
所以只要有**任意一天**在缺口之后 30 天内生成过，就能把缺口盖住。本脚本就是
「把那份历史副本切片 → 只灌缺口那几天」，避免用旧快照覆盖已经更新的日子。

命名约定（与 import_account_30d_reports.detect_spec 一致）
--------------------------------------------------------
源文件（历史副本）: <源目录>/川鹏_<标记>_30D_日期_Copy.csv
切片产物（暂存）  : <暂存根>/<账户>/<账户>_<标记>_30D_日期.csv

用法
----
  python3 backfill_gap.py --from 2026-09-01 --to 2026-09-05 \
      --account 川鹏 --types campaign,purchased_product --dry-run
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import importlib.util
import json
import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path("/Users/panjinlong/Documents/amazon-ads-data")
IMPORTER = REPO / "scripts" / "import_account_30d_reports.py"
VENV_PY = REPO / ".venv" / "bin" / "python"
STAGING_ROOT = REPO / "data" / "raw" / "account_30d_gap"
ZINIAO_ROOT = Path(
    "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser"
)

# 标记 → canonical report key（与加载器 REPORT_BY_FILENAME 同源）
MARKERS = [
    ("campaign", "广告活动"),
    ("placement", "广告位"),
    ("targeting", "投放"),
    ("search_term", "搜索词"),
    ("advertised_product", "推广的商品"),
    ("purchased_product", "达成转化的商品"),
]
MARKER_BY_KEY = dict(MARKERS)
DATE_RE = re.compile(r"^(\d{4})年(\d{1,2})月(\d{1,2})日$")


def log(msg: str) -> None:
    print(msg, flush=True)


def parse_csv_date(text: str) -> dt.date | None:
    m = DATE_RE.match((text or "").strip())
    if not m:
        return None
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))


def find_source(src_dir: Path, account: str, marker: str) -> Path | None:
    """优先历史副本 `_Copy.csv`，退回常规落盘名。"""
    for name in (
        f"{account}_{marker}_30D_日期_Copy.csv",
        f"{account}_{marker}_30D_日期.csv",
    ):
        p = src_dir / name
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def slice_file(src: Path, dst: Path, lo: dt.date, hi: dt.date) -> tuple[int, int, str | None, str | None]:
    """流式过滤「日期」列，只保留 [lo, hi]。返回 (总行, 保留行, min, max)。"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    total = kept = 0
    dmin = dmax = None
    with src.open(encoding="utf-8-sig", errors="replace", newline="") as fin, \
            dst.open("w", encoding="utf-8-sig", newline="") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        header = next(reader)
        writer.writerow(header)  # 表头原样保留，加载器靠它认字段
        di = next((i for i, h in enumerate(header) if h.strip() == "日期"), None)
        if di is None:
            raise ValueError(f"{src.name}: 找不到『日期』列")
        for row in reader:
            total += 1
            if di >= len(row):
                continue
            d = parse_csv_date(row[di])
            if d is None or not (lo <= d <= hi):
                continue
            writer.writerow(row)
            kept += 1
            dmin = d if dmin is None or d < dmin else dmin
            dmax = d if dmax is None or d > dmax else dmax
    return total, kept, dmin.isoformat() if dmin else None, dmax.isoformat() if dmax else None


def load_importer():
    spec = importlib.util.spec_from_file_location("account30d", IMPORTER)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["account30d"] = mod
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="lo", required=True, help="缺口起始日 YYYY-MM-DD（含）")
    ap.add_argument("--to", dest="hi", required=True, help="缺口结束日 YYYY-MM-DD（含）")
    ap.add_argument("--account", default="川鹏", help="canonical 账户目录名/文件名前缀，如 川鹏")
    ap.add_argument("--store-dir", default="", help="紫鸟下载目录（默认 川鹏2号）")
    ap.add_argument("--types", default=",".join(k for k, _ in MARKERS),
                    help="要补的 report key，逗号分隔；默认全部 6 类")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--keep-staging", action="store_true", help="保留切片文件供人工核查")
    args = ap.parse_args()

    lo = dt.date.fromisoformat(args.lo)
    hi = dt.date.fromisoformat(args.hi)
    if hi < lo:
        raise SystemExit("--to 必须 >= --from")
    store_dir = Path(args.store_dir) if args.store_dir else ZINIAO_ROOT / "川鹏2号"
    if not store_dir.is_dir():
        raise SystemExit(f"源目录不存在: {store_dir}")

    wanted = [t.strip() for t in args.types.split(",") if t.strip()]
    unknown = [t for t in wanted if t not in MARKER_BY_KEY]
    if unknown:
        raise SystemExit(f"不认识的 report key: {unknown}（可选 {list(MARKER_BY_KEY)}）")

    staging = STAGING_ROOT / args.account
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)

    log(f"缺口区间: {lo} .. {hi}   （共 {(hi - lo).days + 1} 天）")
    log(f"源目录  : {store_dir}")
    log(f"暂存目录: {staging}")
    log("")

    staged: list[Path] = []
    for key in wanted:
        marker = MARKER_BY_KEY[key]
        src = find_source(store_dir, args.account, marker)
        if src is None:
            log(f"  ✗ {key:20s} 缺源文件（找 {args.account}_{marker}_30D_日期_Copy.csv）")
            continue
        dst = staging / f"{args.account}_{marker}_30D_日期.csv"
        total, kept, dmin, dmax = slice_file(src, dst, lo, hi)
        if kept == 0:
            log(f"  ✗ {key:20s} {src.name} 里 {lo}..{hi} 一行都没有（源区间可能不含缺口）")
            dst.unlink(missing_ok=True)
            continue
        log(f"  ✓ {key:20s} {src.name}  总 {total:,} 行 → 保留 {kept:,} 行（{dmin} .. {dmax}）")
        staged.append(dst)

    if not staged:
        raise SystemExit("没有任何可导入的切片。")
    log("")

    if args.dry_run:
        log("--- dry-run：逐份校验（不写库）---")
        mod = load_importer()
        for p in staged:
            print(json.dumps(mod.import_single_file(p, dry_run=True), ensure_ascii=False))
        return 0

    mod = load_importer()
    rc = 0
    for p in staged:
        try:
            print(json.dumps(mod.import_single_file(p), ensure_ascii=False))
        except Exception as exc:  # noqa: BLE001
            rc = 1
            log(f"  ✗ 导入失败 {p.name}: {type(exc).__name__}: {exc}")
    if not args.keep_staging:
        shutil.rmtree(staging, ignore_errors=True)
        log(f"\n已清理暂存 {staging}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
