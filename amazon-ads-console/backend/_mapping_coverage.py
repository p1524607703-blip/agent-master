"""映射覆盖率体检：SOP 口径（ASIN/SKU → 产品款式 → 运营小组）能不能真正跑通。

只读。两库不能跨库 JOIN，故分别拉取后在内存里比对。
用法：backend/.venv/bin/python _mapping_coverage.py
"""
import os
import subprocess
import sys
from collections import defaultdict
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings


def configure_pg_env(database_url: str, prefix: str) -> None:
    parsed = urlsplit(database_url)
    os.environ[f"{prefix}HOST"] = parsed.hostname
    os.environ[f"{prefix}PORT"] = str(parsed.port or 5432)
    os.environ[f"{prefix}USER"] = unquote(parsed.username)
    os.environ[f"{prefix}DATABASE"] = unquote(parsed.path.lstrip("/"))
    if parsed.password is not None:
        os.environ[f"{prefix}PASSWORD"] = unquote(parsed.password)
    q = parse_qs(parsed.query)
    if q.get("sslmode"):
        os.environ[f"{prefix}SSLMODE"] = q["sslmode"][-1]
    if q.get("sslrootcert"):
        os.environ[f"{prefix}SSLROOTCERT"] = q["sslrootcert"][-1]


configure_pg_env(settings.database_url, "PG")
configure_pg_env(settings.data_database_url, "RDS_PG")


def rows(sql: str, prefix: str = "PG", timeout: int = 120) -> list[list[str]]:
    proc = subprocess.run(
        ["psql", "-h", os.environ[f"{prefix}HOST"], "-p", os.environ[f"{prefix}PORT"],
         "-U", os.environ[f"{prefix}USER"], "-d", os.environ[f"{prefix}DATABASE"],
         "-X", "-q", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    out = []
    for line in proc.stdout.strip().split("\n"):
        if line:
            out.append(line.split("\t"))
    return out


def pct(a: float, b: float) -> str:
    return "—" if not b else f"{a / b * 100:.1f}%"


def main() -> None:
    # ---------- 1. 拉映射表 ----------
    pm = rows("SELECT parent_asin, product_code, operator_group, status FROM app.product_mapping;")
    apm = rows("SELECT parent_asin, product_code, COALESCE(brand,''), COALESCE(owner_group,''), "
               "COALESCE(child_asin,''), match_signal, confidence, status FROM app.asin_parent_map;")
    cam = rows("SELECT account_scope, child_asin, product_code, COALESCE(parent_asin,''), "
               "COALESCE(brand,''), operator_group, mapping_status, confidence FROM app.child_asin_mapping;")
    roster = rows("SELECT brand, product_code, COALESCE(parent_asin,''), operator_text, "
                  "COALESCE(owner_group,''), is_listed::text FROM app.product_roster;")

    pm_parent = {r[0]: r for r in pm}
    pm_child: dict[str, list[list[str]]] = defaultdict(list)
    for r in pm:
        pm_child[r[0]].append(r)
    apm_parent = {r[0]: r for r in apm}
    cam_child = {r[1]: r for r in cam}
    roster_pc = {(r[0], r[1]): r for r in roster}

    print("=" * 78)
    print("映射表清单（应用库 amazon_ads）")
    print("=" * 78)
    for name, data, key in (
        ("app.product_mapping", pm, "parent_asin"),
        ("app.asin_parent_map", apm, "parent_asin"),
        ("app.child_asin_mapping", cam, "child_asin"),
        ("app.product_roster", roster, "brand+product_code"),
    ):
        keys = {r[0] if key == "parent_asin" else r[1] for r in data}
        print(f"  {name:<26} {len(data):>6} 行   {len(keys):>6} 个唯一键 ({key})")

    # ---------- 2. 拉广告侧事实（按父ASIN加权花费） ----------
    adv = rows("""SELECT COALESCE(advertised_product_parent_id,'<NULL>'),
                         COALESCE(advertised_product_id,'<NULL>'),
                         COALESCE(advertised_product_sku,'<NULL>'),
                         sum(spend)::text, count(*)::text
                  FROM core.report_advertised_product_daily
                  GROUP BY 1,2,3;""", "RDS_PG")

    # ---------- 3. 拉归因侧事实（按成交ASIN加权件数） ----------
    pur = rows("""SELECT COALESCE(purchased_product_id,'<NULL>'),
                         COALESCE(purchased_product_parent_id,'<NULL>'),
                         COALESCE(advertised_product_sku,'<NULL>'),
                         sum(units)::text, sum(purchases)::text, count(*)::text
                  FROM core.report_purchased_product_daily
                  GROUP BY 1,2,3;""", "RDS_PG")

    print()
    print("=" * 78)
    print("检验 A · 广告侧《推广的商品》：父ASIN 能否落到运营小组")
    print("=" * 78)
    tot_spend = cov_spend = 0.0
    miss_spend: dict[str, float] = defaultdict(float)
    for par, _aid, _sku, spend, _n in adv:
        s = float(spend or 0)
        tot_spend += s
        if par in pm_parent:
            cov_spend += s
        elif par in apm_parent:
            cov_spend += s
        else:
            miss_spend[par] += s
    print(f"  总花费         ${tot_spend:,.2f}")
    print(f"  可映射花费     ${cov_spend:,.2f}  ({pct(cov_spend, tot_spend)})")
    print(f"  未映射花费     ${tot_spend - cov_spend:,.2f}  ({pct(tot_spend - cov_spend, tot_spend)})")
    top = sorted(miss_spend.items(), key=lambda x: -x[1])[:10]
    if top:
        print("  未映射 Top10（父ASIN / 花费）:")
        for k, v in top:
            print(f"    {k:<16} ${v:,.2f}")

    print()
    print("=" * 78)
    print("检验 B · 归因侧《达成转化的商品》：成交ASIN 能否落到运营小组")
    print("=" * 78)
    tot_u = cov_u = 0.0
    tot_p = cov_p = 0.0
    miss_u: dict[str, float] = defaultdict(float)
    for asin, par, _sku, units, purchases, _n in pur:
        u = float(units or 0)
        p = float(purchases or 0)
        tot_u += u
        tot_p += p
        hit = asin in cam_child or asin in pm_parent or par in pm_parent or par in apm_parent
        if hit:
            cov_u += u
            cov_p += p
        else:
            miss_u[asin] += u
    print(f"  总归因件数(units)   {tot_u:,.0f}")
    print(f"  可映射件数          {cov_u:,.0f}  ({pct(cov_u, tot_u)})")
    print(f"  未映射件数          {tot_u - cov_u:,.0f}  ({pct(tot_u - cov_u, tot_u)})")
    print(f"  购买量(purchases)   {tot_p:,.0f}   可映射 {cov_p:,.0f} ({pct(cov_p, tot_p)})")
    top = sorted(miss_u.items(), key=lambda x: -x[1])[:10]
    if top:
        print("  未映射 Top10（成交ASIN / 件数）:")
        for k, v in top:
            print(f"    {k:<16} {v:,.0f} 件")

    print()
    print("=" * 78)
    print("检验 C · child_asin_mapping 的 account_scope 分布")
    print("=" * 78)
    scope: dict[str, int] = defaultdict(int)
    for r in cam:
        scope[r[0]] += 1
    for k, v in sorted(scope.items(), key=lambda x: -x[1]):
        print(f"  {k:<20} {v:>6}")

    print()
    print("=" * 78)
    print("检验 D · product_mapping 与 asin_parent_map 的一致性（同一父ASIN 是否冲突）")
    print("=" * 78)
    both = set(pm_parent) & set(apm_parent)
    only_pm = set(pm_parent) - set(apm_parent)
    only_apm = set(apm_parent) - set(pm_parent)
    print(f"  两表都有 {len(both)}   仅 product_mapping {len(only_pm)}   仅 asin_parent_map {len(only_apm)}")
    conflict = []
    for par in sorted(both):
        a, b = pm_parent[par], apm_parent[par]
        if (a[1], a[2]) != (b[1], b[3]):
            conflict.append((par, a[1], a[2], b[1], b[3]))
    print(f"  ⚠️ 冲突（product_code / owner_group 不一致）：{len(conflict)}")
    for par, pc1, g1, pc2, g2 in conflict[:20]:
        print(f"    {par:<14} product_mapping=({pc1},{g1})  asin_parent_map=({pc2},{g2})")

    print()
    print("=" * 78)
    print("检验 E · 运营小组个数一致性")
    print("=" * 78)
    g_pm = {r[2] for r in pm}
    g_apm = {r[3] for r in apm if r[3]}
    g_cam = {r[5] for r in cam}
    g_roster = {r[4] for r in roster if r[4]}
    allg = g_pm | g_apm | g_cam | g_roster
    print(f"  {'组码':<8}{'product_mapping':>16}{'asin_parent_map':>17}{'child_mapping':>15}{'roster':>9}")
    for g in sorted(allg):
        print(f"  {g:<8}{('Y' if g in g_pm else '-'):>16}"
              f"{('Y' if g in g_apm else '-'):>17}{('Y' if g in g_cam else '-'):>15}"
              f"{('Y' if g in g_roster else '-'):>9}")
    print(f"  合计: pm={len(g_pm)} apm={len(g_apm)} cam={len(g_cam)} roster={len(g_roster)}")


if __name__ == "__main__":
    main()
