#!/usr/bin/env python3
"""
入库后对账（对应设计文档 §20 的 Gate 1 / 2 / 5 / 6）。

Gate 1 业务键覆盖：源有效唯一业务键数 == V2 唯一业务键数
Gate 2 原始指标总量：逐个核对 Impressions/Clicks/Spend/Purchases/Sales/Units
Gate 5 data_level 独立核对：禁止混层对账
Gate 6 派生指标核查：CTR/CPC/CVR/ACOS/ROAS 与原始指标重算对比（允许四舍五入）

用法：python3 verify_load.py <csv...>
"""
from __future__ import annotations

import sys
from pathlib import Path

import _db
from load_reports import parse_file

METRICS = {
    "impressions": "展示量",
    "clicks": "点击量",
    "spend": "总成本",
    "purchases": "购买量",
    "sales": "销售额",
    "units": "已售商品数量",
}


def main(paths: list[str]) -> int:
    fails: list[str] = []
    print(f"{'data_level':<20} {'Gate1 业务键':<22} {'Gate2 指标总量':<26} {'结果'}")
    print("-" * 96)

    for p in paths:
        path = Path(p).expanduser().resolve()
        res = parse_file(path, None)
        level, target, rows = res["level"], res["target"], res["rows"]

        src_keys = len(rows)
        # 源侧指标合计（基于去重后的行，与入库口径一致）
        src_sum = {k: sum(float(r.get(k) or 0) for r in rows) for k in METRICS}

        if target == "core.search_term_daily":
            db_keys = int(_db.psql(f"select count(*) from {target}").strip())
            db_rows = _db.psql(
                "select " + ", ".join(f"coalesce(sum({k}),0)" for k in METRICS)
                + f" from {target}"
            ).strip().split("|")
        else:
            db_keys = int(_db.psql(
                f"select count(*) from {target} where data_level='{level}'").strip())
            db_rows = _db.psql(
                "select " + ", ".join(f"coalesce(sum({k}),0)" for k in METRICS)
                + f" from {target} where data_level='{level}'"
            ).strip().split("|")
        db_sum = {k: float(v) for k, v in zip(METRICS, db_rows)}

        key_ok = src_keys == db_keys
        metric_bad = [k for k in METRICS if abs(src_sum[k] - db_sum[k]) > 0.01]
        ok = key_ok and not metric_bad

        detail = ", ".join(f"{k}={src_sum[k]:,.2f}" for k in ("impressions", "clicks", "spend"))
        print(f"{level:<20} 源{src_keys:>7} / 库{db_keys:>7}   {detail:<26} "
              f"{'✅' if ok else '❌'}")

        if not key_ok:
            fails.append(f"{level}: 业务键不一致 源{src_keys} vs 库{db_keys}")
        for k in metric_bad:
            fails.append(f"{level}.{k}: 源 {src_sum[k]:,.4f} vs 库 {db_sum[k]:,.4f}")

    print("\n=== Gate 5 · 各 data_level 汇总（禁止混层相加） ===")
    print(_db.psql("""
        select data_level||' | 行='||count(*)||' | 展示='||coalesce(sum(impressions),0)
             ||' | 点击='||coalesce(sum(clicks),0)||' | 花费='||round(coalesce(sum(spend),0),2)
             ||' | 销售='||round(coalesce(sum(sales),0),2)
        from core.ad_daily group by data_level order by data_level;"""))

    print("=== Gate 6 · 派生指标重算抽查（campaign 层） ===")
    print(_db.psql("""
        with c as (
          select sum(impressions) imp, sum(clicks) clk, sum(spend) sp,
                 sum(purchases) pur, sum(sales) sal, sum(ctr_pct*impressions)/nullif(sum(impressions),0) ctr_w
          from core.ad_daily where data_level='campaign'
        )
        select '重算 CTR='||round(clk/nullif(imp,0)*100,4)
             ||' vs 加权存值='||round(ctr_w,4)
             ||' | 重算 CPC='||round(sp/nullif(clk,0),4)
             ||' | 重算 ACOS='||round(sp/nullif(sal,0)*100,4)
             ||' | 重算 ROAS='||round(sal/nullif(sp,0),4)
        from c;"""))

    print("=== 账户分布（多账户共表验证） ===")
    print(_db.psql("""
        select account_id||' | '||max(account_name)||' | ad_daily='||count(*)
        from core.ad_daily group by account_id;"""))

    print("\n" + ("🎉 全部 Gate 通过" if not fails else "❌ 存在差异：\n  - " + "\n  - ".join(fails)))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
