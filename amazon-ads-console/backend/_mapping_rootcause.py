"""根因诊断：把未映射的成交 ASIN 按业务报告的 parent_asin 归集，找出"整条没登记的产品线"。

只读。用法：backend/.venv/bin/python _mapping_rootcause.py
"""
import os
import subprocess
import sys
from collections import defaultdict
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings


def configure_pg_env(database_url: str, prefix: str) -> None:
    p = urlsplit(database_url)
    os.environ[f"{prefix}HOST"] = p.hostname
    os.environ[f"{prefix}PORT"] = str(p.port or 5432)
    os.environ[f"{prefix}USER"] = unquote(p.username)
    os.environ[f"{prefix}DATABASE"] = unquote(p.path.lstrip("/"))
    if p.password is not None:
        os.environ[f"{prefix}PASSWORD"] = unquote(p.password)
    q = parse_qs(p.query)
    if q.get("sslmode"):
        os.environ[f"{prefix}SSLMODE"] = q["sslmode"][-1]
    if q.get("sslrootcert"):
        os.environ[f"{prefix}SSLROOTCERT"] = q["sslrootcert"][-1]


configure_pg_env(settings.database_url, "PG")
configure_pg_env(settings.data_database_url, "RDS_PG")


def rows(sql: str, prefix: str = "RDS_PG", timeout: int = 180) -> list[list[str]]:
    proc = subprocess.run(
        ["psql", "-h", os.environ[f"{prefix}HOST"], "-p", os.environ[f"{prefix}PORT"],
         "-U", os.environ[f"{prefix}USER"], "-d", os.environ[f"{prefix}DATABASE"],
         "-X", "-q", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    return [ln.split("\t") for ln in proc.stdout.strip().split("\n") if ln]


pm = {r[0] for r in rows("SELECT parent_asin FROM app.product_mapping;", "PG")}
cam_rows = rows("SELECT DISTINCT child_asin, COALESCE(parent_asin,'') FROM app.child_asin_mapping;", "PG")
cam_child = {r[0] for r in cam_rows}
cam_parent = {r[1] for r in cam_rows if r[1]}

# ---- 未映射的成交 ASIN ----
pur = rows("""SELECT COALESCE(purchased_product_id,''), COALESCE(purchased_product_parent_id,''),
                     account_name, sum(units)::text
              FROM core.report_purchased_product_daily GROUP BY 1,2,3;""")
miss_asin: dict[str, float] = defaultdict(float)
for asin, par, acct, u in pur:
    if not asin or asin in cam_child or asin in pm or par in pm or par in cam_parent:
        continue
    miss_asin[asin] += float(u or 0)

# ---- 这些 ASIN 在业务报告里的 parent_asin ----
parent_of: dict[str, str] = {}
child_of_parent: dict[str, set] = defaultdict(set)
parent_units: dict[str, float] = defaultdict(float)
parent_title: dict[str, str] = {}
if miss_asin:
    inlist = ",".join("'" + a.replace("'", "''") + "'" for a in miss_asin)
    biz = rows(f"""SELECT child_asin, COALESCE(parent_asin,''), COALESCE(title,''),
                          sum(ordered_product_units)::text
                   FROM core.report_business_child_asin_daily
                   WHERE child_asin IN ({inlist}) GROUP BY 1,2,3;""")
    for child, par, title, u in biz:
        if not par:
            continue
        parent_of[child] = par
        child_of_parent[par].add(child)
        parent_units[par] += float(u or 0)
        parent_title.setdefault(par, title)

print("=" * 108)
print("根因：未映射成交 ASIN 按业务报告 parent_asin 归集")
print("=" * 108)

# 按父 ASIN 分组
groups: dict[str, dict] = {}
orphan: dict[str, float] = defaultdict(float)
for asin, units in miss_asin.items():
    par = parent_of.get(asin)
    if par:
        g = groups.setdefault(par, {"asin": set(), "units": 0.0, "all_child": set(), "reg_child": set()})
        g["asin"].add(asin)
        g["units"] += units
    else:
        orphan[asin] = units

# 补全：每个父 ASIN 在业务报告下的全部子 ASIN
for par in list(groups):
    tot = rows(f"""SELECT count(DISTINCT child_asin), sum(ordered_product_units)::text
                   FROM core.report_business_child_asin_daily WHERE parent_asin='{par}';""")
    if tot:
        g = groups[par]
        g["total_child"] = int(tot[0][0] or 0)
        g["total_units"] = float(tot[0][1] or 0)
    subs = rows(f"""SELECT child_asin FROM core.report_business_child_asin_daily
                    WHERE parent_asin='{par}' GROUP BY 1;""")
    for (c,) in subs:
        g["all_child"].add(c)
        if c in cam_child or c in pm:
            g["reg_child"].add(c)

print(f"{'父ASIN':<14}{'未映射子ASIN':>10}{'未映射件数':>11}{'该父ASIN总子数':>13}{'已登记子数':>11}{'父ASIN在映射表':>14}  标题")
print("-" * 108)
tot_g = 0.0
for par, g in sorted(groups.items(), key=lambda x: -x[1]["units"]):
    tot_g += g["units"]
    in_map = "是" if (par in pm or par in cam_parent or par in cam_child) else "❌ 否"
    print(f"{par:<14}{len(g['asin']):>10}{g['units']:>11,.0f}{g.get('total_child', 0):>13}"
          f"{len(g['reg_child']):>11}{in_map:>14}  {parent_title.get(par, '')[:44]}")

print("-" * 108)
print(f"共 {len(groups)} 个父 ASIN 整条未登记，涉及未映射成交 {tot_g:,.0f} 件")
if orphan:
    print(f"另有 {len(orphan)} 个 ASIN / {sum(orphan.values()):,.0f} 件 在业务报告也查不到父 ASIN（孤岛）：")
    for a, u in sorted(orphan.items(), key=lambda x: -x[1])[:10]:
        print(f"  {a:<14}{u:>6,.0f} 件")

# ---- 业务侧全量同口径 ----
print()
print("=" * 108)
print("业务侧全量：未映射订购量按 parent_asin 归集（含无广告归因的部分）")
print("=" * 108)
allbiz = rows("""SELECT child_asin, COALESCE(parent_asin,''), COALESCE(title,''),
                        sum(ordered_product_units)::text
                 FROM core.report_business_child_asin_daily GROUP BY 1,2,3;""")
b_miss_p: dict[str, dict] = {}
b_orphan: dict[str, float] = defaultdict(float)
for child, par, title, u in allbiz:
    v = float(u or 0)
    if child in cam_child or child in pm or par in pm or par in cam_parent:
        continue
    if par:
        g = b_miss_p.setdefault(par, {"units": 0.0, "n": 0, "title": title})
        g["units"] += v
        g["n"] += 1
    else:
        b_orphan[child] += v

print(f"{'父ASIN':<14}{'未映射子数':>10}{'未映射订购量':>13}  {'父ASIN在映射表':<14}标题")
print("-" * 108)
for par, g in sorted(b_miss_p.items(), key=lambda x: -x[1]["units"])[:25]:
    in_map = "是" if (par in pm or par in cam_parent or par in cam_child) else "❌ 否"
    print(f"{par:<14}{g['n']:>10}{g['units']:>13,.0f}  {in_map:<14}{g['title'][:44]}")
print("-" * 108)
print(f"共 {len(b_miss_p)} 个父 ASIN 涉及未映射订购量 {sum(g['units'] for g in b_miss_p.values()):,.0f} 件")
if b_orphan:
    print(f"父ASIN为空：{len(b_orphan)} 个子 ASIN / {sum(b_orphan.values()):,.0f} 件")
