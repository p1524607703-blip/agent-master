#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修正业务报告中「日期范围选宽了」的批次。

背景（2026-09-15，用户确认 + 实测反解验证）
    business-report 拉取时 URL 左闭右开，单日 D 应传 fromDate=D&toDate=D+1。
    2026-09-13 21:31–21:44 的补拉窗口里有几份把 toDate 传成了 fromDate+2，导致多含一天：

        文件名                            实际覆盖            证据
        BR_._daily_2026-09-10.csv   →  (09-10, 09-11)    订单 10,619 = 5,622+4,997
        BR_._daily_2026-09-11.csv   →  (09-11, 09-12)    订单 10,590 = 4,997+5,593
        （09-12 文件 129 个 ASIN、5,593 单，落在邻居区间，视为正常单日）

    反解校验：F11 = b + c = 4,997 + 5,593 = 10,590，与文件实测精确吻合。
    集合证据：09-11 文件的 ASIN 集合**完整包含** 09-12 文件的 129 个。

修法
    不改数值、不删行，只把 report_end_date 从「D」改成真实结束日。
    因为所有「单日快照」查询都带 `report_start_date = report_end_date` 条件，
    改完之后这两天**自动退出 CPO 分母**，CPO 会显示「缺业务报告」而不是一个被放大 1.8 倍的错数。
    等重拉回正确单日文件后，新批次会自动覆盖回来。

用法
    python3 fix_wide_period_batches.py --dry     # 只看会改哪些
    python3 fix_wide_period_batches.py           # 执行
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).resolve().parent
ENV_PATH = HERE.parent / "amazon-ads-console" / "backend" / ".env"

# 文件名 → 真实结束日
FIXES = {
    "BR_川鹏2号_daily_2026-09-10.csv": "2026-09-11",
    "BR_欧德思美站_daily_2026-09-10.csv": "2026-09-11",
    "BR_川鹏2号_daily_2026-09-11.csv": "2026-09-12",
    "BR_欧德思美站_daily_2026-09-11.csv": "2026-09-12",
}
TABLE = "core.report_business_parent_asin_period"


def _env() -> dict:
    dsn = ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("RDS_DATABASE_URL="):
            dsn = line.split("=", 1)[1].strip()
            break
    if not dsn:
        sys.exit("backend/.env 里没有 RDS_DATABASE_URL")
    p = urlsplit(dsn)
    q = parse_qs(p.query)
    return {"host": p.hostname or "", "port": str(p.port or 5432),
            "user": unquote(p.username or ""), "password": unquote(p.password or ""),
            "dbname": p.path.lstrip("/"),
            "sslmode": (q.get("sslmode") or ["verify-full"])[-1],
            "sslrootcert": (q.get("sslrootcert") or [""])[-1]}


def psql(d: dict, sql: str) -> str:
    env = os.environ.copy()
    env["PGPASSWORD"] = d["password"]
    env["PGSSLMODE"] = d["sslmode"]
    if d["sslrootcert"]:
        env["PGSSLROOTCERT"] = d["sslrootcert"]
    env["PGCONNECT_TIMEOUT"] = "20"
    r = subprocess.run(["psql", "-w", "-h", d["host"], "-p", d["port"], "-U", d["user"],
                        "-d", d["dbname"], "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1",
                        "-c", sql], env=env, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:400])
    return r.stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    d = _env()
    print(f"目标库 {d['user']}@{d['host']}:{d['port']}/{d['dbname']}  {'[DRY]' if a.dry else ''}")
    print("-" * 88)

    total = 0
    for fname, real_end in FIXES.items():
        cur = psql(d, f"""
            SELECT b.batch_id, b.report_end_date::text, count(t.*)
            FROM core.import_batches b
            LEFT JOIN {TABLE} t ON t.source_batch_id = b.batch_id
            WHERE b.file_name = '{fname}'
            GROUP BY 1,2
        """)
        if not cur:
            print(f"  跳过 {fname:<38} 库里没有这个批次")
            continue
        bid, old_end, n = cur.split("|")
        if old_end == real_end:
            print(f"  已是正确值 {fname:<38} batch={bid} end={old_end}")
            continue
        # 先探冲突：改完后主键会不会撞
        clash = psql(d, f"""
            SELECT count(*) FROM {TABLE} x
            JOIN {TABLE} y ON y.account_id=x.account_id AND y.parent_asin=x.parent_asin
                          AND y.report_start_date=x.report_start_date
                          AND y.report_end_date=DATE '{real_end}'
            WHERE x.source_batch_id={bid} AND y.source_batch_id<>{bid}
        """)
        tag = "⛔ 主键会撞，跳过" if clash != "0" else "OK"
        print(f"  {fname:<38} batch={bid:<4} end {old_end} → {real_end}  {n} 行  冲突={clash} {tag}")
        if clash != "0" or a.dry:
            continue
        psql(d, f"UPDATE {TABLE} SET report_end_date=DATE '{real_end}', updated_at=now() "
                f"WHERE source_batch_id={bid}")
        total += int(n)

    print("-" * 88)
    print(f"{'（dry-run，未写入）' if a.dry else f'已修正 {total} 行'}")
    if not a.dry:
        print()
        print(psql(d, f"""
            SELECT '单日快照行数=' || count(*)::text FROM {TABLE}
            WHERE report_start_date = report_end_date
        """))
        print(psql(d, f"""
            SELECT '跨日行(应只含周快照+已修正的2天) 期间=' || string_agg(DISTINCT
                   report_start_date || '~' || report_end_date, ' , ')
            FROM {TABLE} WHERE report_start_date <> report_end_date
        """))
    return 0


if __name__ == "__main__":
    sys.exit(main())
