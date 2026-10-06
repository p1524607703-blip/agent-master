#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把紫鸟下载的 Amazon Ads「30D 日期」报告灌进 amazon_ads_v2 的 core.report_*_daily。

为什么需要这个脚本
------------------
「每日广告报告」这条链路原本缺了后半截：

    ziniao-ad-report-download/pipeline.sh   →  只下载 + 校验新鲜度，【不写库】
    download_account_30d_mail_reports.py    →  走 Apple Mail 取预签名直链再 curl
                                               （真正喂 core.report_* 的那条，2026-09-21 起被 macOS TCC 拦死）

而 `ad-reports-export/subscribed_reports_to_rds.py` 灌的是 `core.subscribed_*_daily`
—— 那套表在现行主库 amazon_ads_v2 里已经不存在了。

于是「下载成功」和「库里有钱」之间是断的。本脚本就是补上这一段：把紫鸟下载目录里的
CSV 按加载器要求的命名搬进 `data/raw/account_30d_ziniao/<账户>/`，再调
`amazon-ads-data/scripts/import_account_30d_reports.py` 落库。

关键认知：30D 报告是【滚动 30 天窗口】
-------------------------------------
所以补数据缺口不需要「一天一份」地回灌 —— 只要成功跑通一次，最近 30 天（含所有漏掉的
日子）会一次性补齐并 upsert 覆盖。这也是为什么本脚本不怕某家店掉登录：缺的那家等下一轮
跑，窗口仍然盖得住。

用法
----
    python3 ziniao_30d_to_report_daily.py                 # 全流程：搬文件 → 灌库 → 报状态
    python3 ziniao_30d_to_report_daily.py --dry-run        # 只体检+搬文件，不写库
    python3 ziniao_30d_to_report_daily.py --keep-staging    # 灌完不删暂存目录（排障）
    python3 ziniao_30d_to_report_daily.py --accounts AMS    # 只处理指定账户

退出码
    0 = 全部完成（或 dry-run 无问题）
    2 = 执行错误（配置/路径问题）
    3 = 所有待处理店铺都不齐 → 一个都没灌（通常 = 全部掉登录，需人工）
    4 = 部分账户不齐，但齐的那些已灌成功（可用，缺的下轮补）
    5 = 灌库失败

安全约束
    只读紫鸟下载目录 + 只往 RDS 写 core.report_*_daily。**不碰任何 Amazon 账号或广告设置。**
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SKILL_CONFIG = HOME / ".workbuddy/skills/ziniao-ad-report-download/config.json"
REPO = HOME / "Documents/amazon-ads-data"
IMPORTER = REPO / "scripts/import_account_30d_reports.py"
VENV_PY = REPO / ".venv/bin/python"

# 紫鸟 storeName → canonical 加载器期望的账户目录名 / 文件名前缀
STORE_TO_ACCOUNT = {
    "川鹏2号": "川鹏",
    "欧德思美站": "欧德思",
    "洁博利美站": "洁博利",
    "美国AMS": "AMS",
}

# ⚠️ 2026-10-05 订正：旧注释写「川鹏当前没有搜索词订阅」是【错误记载】。
# 实测（probe_pick.js 两次只读探针：2026-09-29 / 2026-10-05）川鹏2号**有**「川鹏 搜索词 30D 日期 Copy」在跑。
# 当年的 MISSING 是 ag-grid 虚拟滚动只渲染 ~11 行造成的探针误报。config.json 已把它加回 → 4 店各 6 类 = 24 份。
# 但它仍留在 OPTIONAL 里是【刻意的】：川鹏偶尔会掉这一项，缺了不该让整家店判定「不齐」而整批丢弃。
# 其余三家继续要求 6 类齐全。
OPTIONAL_REPORT_TYPES_BY_STORE = {
    "川鹏2号": {"search_term"},
}

# 加载器 detect_spec() 认的 6 类标记（目标文件名里必须出现 "_<标记>_"）
# 同时给出紫鸟侧的「逻辑名」—— 即 config.json 里 reportNames 的写法，落盘名就是它 + '.csv'
REPORTS = [
    # (type, 短标记, 紫鸟侧逻辑名)
    ("campaign", "广告活动", "广告活动 30D 日期"),
    ("placement", "广告位", "广告位 30D 日期"),
    ("targeting", "投放", "投放 30D 日期"),
    ("search_term", "搜索词", "搜索词 30D 日期"),
    ("advertised_product", "推广的商品", "推广的商品 30D 日期"),
    ("purchased_product", "达成转化的商品", "达成转化的商品 30D 日期"),
]
LOGICAL_ORDER = [r[2] for r in REPORTS]

DATE_RE = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")


def log(msg: str) -> None:
    print(msg, flush=True)


def load_skill_accounts() -> list[dict]:
    if not SKILL_CONFIG.exists():
        raise SystemExit(f"[error] 找不到紫鸟下载配置: {SKILL_CONFIG}")
    with SKILL_CONFIG.open(encoding="utf-8") as fh:
        cfg = json.load(fh)
    accounts = cfg.get("accounts") or [cfg]
    if not accounts:
        raise SystemExit("[error] 紫鸟下载配置里没有任何账户")
    return accounts


def find_source_file(download_dir: Path, report_name: str) -> Path | None:
    """控制台落盘名 = 逻辑名 + '.csv'；孤儿下载可能还是下划线版，作为兜底。"""
    for candidate in (
        download_dir / f"{report_name}.csv",
        download_dir / f"{report_name.replace(' ', '_')}.csv",
    ):
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    return None


def scan_date_range(path: Path) -> tuple[str | None, str | None, int]:
    """流式扫「日期」列，返回 (最小, 最大, 行数)。大文件不能整读进内存。"""
    lo = hi = None
    n = 0
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as fh:
        reader = csv.reader(fh)
        try:
            header = next(reader)
        except StopIteration:
            return None, None, 0
        cols = [i for i, h in enumerate(header) if h.strip() == "日期"]
        if not cols:
            return None, None, 0
        di = cols[0]
        for row in reader:
            if len(row) <= di:
                continue
            m = DATE_RE.search(row[di] or "")
            if not m:
                continue
            d = "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
            n += 1
            lo = d if lo is None or d < lo else lo
            hi = d if hi is None or d > hi else hi
    return lo, hi, n


def stage_account(account: dict, staging_root: Path, store_name: str, acct: str,
                  max_age_days: int) -> tuple[bool, list[str]]:
    """把一家店的 6 类报告搬进暂存目录。返回 (是否齐全且新鲜, 不合格的类别列表)。

    ⚠️ 必须同时卡「文件存在」和「数据日期够新」。
    紫鸟下载目录里会长期躺着上一次成功下载的旧文件（实测 2026-09-08 那批仍在）。
    若只判存在，某家店掉登录 → 下载失败 → 旧文件原地不动 → 本脚本会把它当「齐了」
    灌进库，而它其实是 13 天前的快照。30D 报告正常只会覆盖到美东 T-1，
    所以「最新数据日期 < 今天 - max_age_days」一律判不合格。
    """
    download_dir = Path(account.get("downloadDir") or "")
    dest_dir = staging_root / acct
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    from datetime import date, timedelta
    cutoff = (date.today() - timedelta(days=max_age_days)).isoformat()

    bad: list[str] = []
    log(f"\n== {store_name} → {acct} ==")
    log(f"   下载目录: {download_dir}")
    optional_types = OPTIONAL_REPORT_TYPES_BY_STORE.get(store_name, set())
    for _type, short, report_name in REPORTS:
        src = find_source_file(download_dir, report_name)
        if src is None:
            if _type in optional_types:
                log(f"   - {short:<6} 未订阅（本账户非必需）")
                continue
            bad.append(short)
            log(f"   ✗ {short:<6} 缺文件（找 {report_name}.csv）")
            continue
        lo, hi, n = scan_date_range(src)
        size_mb = src.stat().st_size / 1048576
        if not hi or hi < cutoff:
            bad.append(short)
            log(f"   ✗ {short:<6} {size_mb:8.1f} MB  数据只到 {hi or '-'}（判过期，要求 ≥ {cutoff}）"
                f"  ← 下载大概没成功，这是旧快照")
            continue
        dst = dest_dir / f"{acct}_{short}_30D_日期.csv"
        shutil.copy2(src, dst)
        log(f"   ✓ {short:<6} {size_mb:8.1f} MB  {n:>7} 行  数据日期 {lo or '-'} .. {hi}")
    if bad:
        # 不齐就把这家的暂存清掉，避免给加载器一份半拉数据
        shutil.rmtree(dest_dir, ignore_errors=True)
    return (not bad), bad


def run_importer(staging_root: Path, dry_run: bool, accounts: list[str]) -> int:
    """保持标准账户6类完整校验；川鹏5类由本脚本校验后走canonical单文件入口。"""
    env = dict(os.environ)
    env["ADS_DB_NAME"] = "amazon_ads_v2"
    for acct in accounts:
        account_dir = staging_root / acct
        if acct == "川鹏":
            snippet = (
                "import importlib.util,json,pathlib,sys;"
                f"p={str(IMPORTER)!r};d=pathlib.Path({str(account_dir)!r});"
                "s=importlib.util.spec_from_file_location('account30d',p);"
                "m=importlib.util.module_from_spec(s);sys.modules['account30d']=m;s.loader.exec_module(m);"
                f"dry={dry_run!r};"
                "[print(json.dumps(m.import_single_file(f,dry_run=dry),ensure_ascii=False)) "
                "for f in sorted(d.glob('*.csv'))]"
            )
            cmd = [str(VENV_PY), "-c", snippet]
        else:
            cmd = [str(VENV_PY), str(IMPORTER), "--base-dir", str(account_dir)]
            if dry_run:
                cmd.append("--dry-run")
        log("\n>>> " + " ".join(cmd[:3]) + (" ..." if len(cmd) > 3 else ""))
        rc = subprocess.run(cmd, env=env, cwd=str(REPO)).returncode
        if rc != 0:
            return rc
    return 0


STATUS_SQL = r"""
select account_name,
       max(stat_date) as max_date,
       min(stat_date) as min_date,
       count(*)       as rows
from core.report_campaign_daily
group by 1
order by 1
"""


def print_rds_status() -> None:
    if not VENV_PY.exists():
        return
    snippet = (
        "import sys;sys.path.insert(0,%r);"
        "from amazon_ads_data.config import load_config;"
        "from amazon_ads_data.db import connect;"
        "cfg=load_config();c=connect(cfg,role='amazon_ads_admin',read_only=True);"
        "print('---- core.report_campaign_daily 各账户覆盖 ----');"
        "rows=c.execute(%r).fetchall();"
        "[print('   %%-18s %%s .. %%s  %%8d 行'%%(r['account_name'],r['min_date'],r['max_date'],r['rows'])) for r in rows]"
        % (str(REPO / "src"), STATUS_SQL)
    )
    log("\n>>> RDS 现状")
    subprocess.run([str(VENV_PY), "-c", snippet], cwd=str(REPO))


def main() -> int:
    ap = argparse.ArgumentParser(description="紫鸟 30D 广告报告 → amazon_ads_v2 core.report_*_daily")
    ap.add_argument("--staging-root", type=Path,
                    default=REPO / "data/raw/account_30d_ziniao",
                    help="暂存根目录（每账户一个子目录）")
    ap.add_argument("--accounts", default="",
                    help="只处理指定账户（逗号分隔，如 AMS,欧德思）")
    ap.add_argument("--dry-run", action="store_true", help="只搬文件+解析体检，不写库")
    ap.add_argument("--keep-staging", action="store_true", help="灌库后保留暂存目录")
    ap.add_argument("--max-age-days", type=int, default=3,
                    help="源文件最新数据日期必须 ≥ 今天-N 天，否则判过期不灌（默认 3）")
    args = ap.parse_args()

    if not IMPORTER.exists():
        log(f"[error] 找不到加载器: {IMPORTER}")
        return 2
    if not VENV_PY.exists():
        log(f"[error] 找不到仓库 venv: {VENV_PY}")
        return 2

    wanted = {a.strip() for a in args.accounts.split(",") if a.strip()}
    staging_root: Path = args.staging_root.expanduser().resolve()
    # 上一轮灌库失败会原样保留暂存目录；不清干净的话加载器会把陈旧文件一起算进去。
    if staging_root.exists() and not args.keep_staging:
        shutil.rmtree(staging_root, ignore_errors=True)
    staging_root.mkdir(parents=True, exist_ok=True)

    accounts = load_skill_accounts()
    complete: list[str] = []
    incomplete: list[tuple[str, list[str]]] = []
    skipped: list[str] = []

    for account in accounts:
        store_name = account.get("storeName") or account.get("storeId") or "?"
        acct = STORE_TO_ACCOUNT.get(store_name)
        if acct is None or (wanted and acct not in wanted):
            skipped.append(store_name)
            continue
        ok, missing = stage_account(account, staging_root, store_name, acct, args.max_age_days)
        if ok:
            complete.append(acct)
        else:
            incomplete.append((acct, missing))

    if skipped:
        log(f"\n（跳过，不参与 core.report_* 体系: {', '.join(skipped)}）")
    for acct, missing in incomplete:
        log(f"[warn] {acct} 报告不齐，本轮不灌: 缺 {', '.join(missing)}")

    if not complete:
        log("\n[error] 没有任何一家店的报告是齐的 —— 一个都没灌。"
            "常见原因：该店掉登录 / 订阅被删 / 报告还没生成。")
        return 3

    rc = run_importer(staging_root, args.dry_run, complete)
    if rc != 0:
        log(f"\n[error] 加载器退出码 {rc}；暂存目录保留在 {staging_root} 供排查。")
        return 5

    if not args.keep_staging:
        shutil.rmtree(staging_root, ignore_errors=True)
        log(f"\n已清理暂存目录 {staging_root}")

    if not args.dry_run:
        print_rds_status()

    if incomplete:
        log(f"\n[info] 已完成 {len(complete)} 家：{', '.join(complete)}；"
            f"待补 {len(incomplete)} 家：{', '.join(a for a, _ in incomplete)}")
        return 4
    log(f"\n[ok] 全部完成：{', '.join(complete)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
