#!/usr/bin/env python3
"""广告事实「窗口遗漏」探测器 —— 只读。

以「业务报告（report_business_child_asin_daily）里出现过的日期」为该账户的**应有日期集**，
逐张广告事实表比对，列出最近 N 天内的缺口日期。

为什么用业务报告当基准：川鹏/欧德思/洁博利的业务报告是每天独立入库的（不是滚动窗口），
它们的日期集合天然反映了「亚马逊那边这一天确实有数据」。广告事实表是 30D 滚动窗口灌进来的，
很容易在某段没跑到的日子里留下空洞。

用法
----
  python3 check_ad_gap.py                 # 默认最近 35 天
  python3 check_ad_gap.py --days 40
  python3 check_ad_gap.py --json          # 机器可读，供自动化消费
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys

sys.path.insert(0, "/Users/panjinlong/Documents/amazon-ads-data/src")
from amazon_ads_data.config import load_config  # noqa: E402
from amazon_ads_data.db import connect  # noqa: E402

# 广告事实表：account_name → 表名
AD_TABLES = [
    "report_campaign_daily",
    "report_placement_daily",
    "report_targeting_daily",
    "report_search_term_daily",
    "report_advertised_product_daily",
    "report_purchased_product_daily",
]
BUSINESS_TABLE = "report_business_child_asin_daily"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=35, help="回看天数（默认 35）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    since = dt.date.today() - dt.timedelta(days=args.days)
    conn = connect(load_config(), read_only=True)
    cur = conn.cursor()

    cur.execute(
        f"""SELECT account_name, stat_date::text d FROM core.{BUSINESS_TABLE}
            WHERE stat_date >= DATE '{since.isoformat()}'
            GROUP BY 1,2 ORDER BY 1,2"""
    )
    expected: dict[str, set[str]] = {}
    for r in cur.fetchall():
        expected.setdefault(r["account_name"], set()).add(r["d"])

    report: list[dict] = []
    for acct in sorted(expected):
        for tbl in AD_TABLES:
            cur.execute(
                f"""SELECT stat_date::text d FROM core.{tbl}
                    WHERE account_name = %s AND stat_date >= DATE '{since.isoformat()}'
                    GROUP BY 1""",
                (acct,),
            )
            have = {r["d"] for r in cur.fetchall()}
            missing = sorted(expected[acct] - have)
            if not missing:
                continue
            # 建议的历史生成日 D：30D 窗口要同时盖住 lo 和 hi
            #   D - 30 <= lo  且  D - 1 >= hi   →  D ∈ [hi+1, lo+30]
            # 取最靠右的那个（生成得最晚 = 归因最成熟），且不能超过今天。
            lo = dt.date.fromisoformat(missing[0])
            hi = dt.date.fromisoformat(missing[-1])
            suggest = min(lo + dt.timedelta(days=30), dt.date.today())
            # 一份 30D 历史副本能否一次盖住整个缺口
            recoverable = suggest >= hi + dt.timedelta(days=1)
            gap_days = (dt.date.today() - suggest).days
            report.append(
                {
                    "account": acct,
                    "table": tbl,
                    "missingDates": missing,
                    "missingCount": len(missing),
                    "window": [missing[0], missing[-1]],
                    "suggestHistoryCreatedDate": suggest.isoformat(),
                    "recoverable": recoverable,
                    "historyAgeDays": gap_days,
                    "historyRetentionRisk": gap_days > 20,
                }
            )
    conn.close()

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    print(f"回看 {args.days} 天（基准日 {since} 起）；基准 = 业务报告出现过的日期\n")
    if not report:
        print("  ✓ 没有发现任何广告事实缺口")
        return 0
    by_acct: dict[str, list[dict]] = {}
    for row in report:
        by_acct.setdefault(row["account"], []).append(row)
    for acct, rows in by_acct.items():
        print(f"  -- {acct} --")
        for row in rows:
            if not row["recoverable"]:
                flag = "⚠️缺口宽于 30 天，需按窗口拆成多段补"
            elif row["historyRetentionRisk"]:
                flag = f"🟡可补，但历史副本已生成 {row['historyAgeDays']} 天，趁早抓"
            else:
                flag = "✅可补"
            print(
                f"     ✗ {row['table']:38s} 缺 {row['missingCount']:>3} 天 "
                f"({row['window'][0]} .. {row['window'][1]})  {flag}"
                f"  建议历史生成日={row['suggestHistoryCreatedDate']}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
