"""7 个跨组款号的归属规则核验。

用户口径（2026-09-21）：
- S71 (XM1/XM2)          → 算同组
- W30/W63/W85 (YS1/ZJ1)  → 按运营自己推广的父 ASIN 算，可由子 ASIN 推父 ASIN；
                            同一款被两个运营拿走同时投广告，但子 ASIN 绝对会区分开来
- W75V2/W81V2/W81V5 (XH1/ZJ1) → 有男女款区别

本脚本只读，验证「子 ASIN 绝对会区分开来」是否成立。
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


def rows(sql: str, prefix: str = "PG", timeout: int = 300) -> list[list[str]]:
    proc = subprocess.run(
        ["psql", "-h", os.environ[f"{prefix}HOST"], "-p", os.environ[f"{prefix}PORT"],
         "-U", os.environ[f"{prefix}USER"], "-d", os.environ[f"{prefix}DATABASE"],
         "-X", "-q", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    return [ln.split("\t") for ln in proc.stdout.strip().split("\n") if ln]


GROUPS = {
    "S71": ["XM1", "XM2"],
    "W30": ["YS1", "ZJ1"],
    "W63": ["YS1", "ZJ1"],
    "W85": ["YS1", "ZJ1"],
    "W75V2": ["XH1", "ZJ1"],
    "W81V2": ["XH1", "ZJ1"],
    "W81V5": ["XH1", "ZJ1"],
}
CODE_LIST = ",".join(f"'{k}'" for k in GROUPS)

# ---------- 拉这些款号的全部映射行 ----------
cam = rows(f"""SELECT child_asin, product_code, parent_asin, operator_group, account_scope,
                      COALESCE(brand,''), COALESCE(confidence,'')
               FROM app.child_asin_mapping WHERE product_code IN ({CODE_LIST})
               ORDER BY product_code, operator_group, parent_asin, child_asin;""")

print("=" * 108)
print("① 7 个跨组款号：父 ASIN × 组 的完整分布")
print("=" * 108)
by_pc: dict[str, dict] = defaultdict(lambda: defaultdict(list))
for child, pc, par, grp, scope, brand, conf in cam:
    by_pc[pc][(par, grp, scope)].append(child)

for pc in sorted(by_pc):
    print(f"\n【款号 {pc}】  规则应得组 = {'/'.join(GROUPS[pc])}")
    for (par, grp, scope), kids in sorted(by_pc[pc].items()):
        print(f"  父ASIN {par:<13} 组 {grp:<6} scope {scope:<15} {len(kids):>4} 个子ASIN")

# ---------- 核心验算：子 ASIN 是否唯一归属 ----------
print()
print("=" * 108)
print("② 核心验算：同一子 ASIN 是否跨父 ASIN / 跨组出现（验「子ASIN绝对会区分开来」）")
print("=" * 108)
child_owners: dict[str, set] = defaultdict(set)
child_groups: dict[str, set] = defaultdict(set)
for child, pc, par, grp, scope, brand, conf in cam:
    child_owners[child].add((par, grp, scope))
    child_groups[child].add(grp)

multi_owner = {c: o for c, o in child_owners.items() if len(o) > 1}
multi_group = {c: g for c, g in child_groups.items() if len(g) > 1}
print(f"  这 7 个款号共 {len(child_owners):,} 个子 ASIN")
print(f"  跨父ASIN/跨scope 出现的子 ASIN：{len(multi_owner)}")
if multi_owner:
    for c, o in sorted(multi_owner.items())[:20]:
        print(f"    {c:<13}{' | '.join(f'{p}/{g}/{s}' for p, g, s in sorted(o))}")
print(f"  ❗ 跨运营组出现的子 ASIN：{len(multi_group)}")
if multi_group:
    for c, g in sorted(multi_group.items())[:20]:
        print(f"    {c:<13}{' / '.join(sorted(g))}")

# ---------- 全局同口径验算（不只这 7 个款号） ----------
print()
print("=" * 108)
print("③ 全局验算：整个 child_asin_mapping 里，有无子 ASIN 真正跨组")
print("=" * 108)
allrows = rows("""SELECT child_asin, parent_asin, operator_group, account_scope, product_code
                  FROM app.child_asin_mapping;""")
g_child: dict[str, set] = defaultdict(set)
g_parent: dict[str, set] = defaultdict(set)
for child, par, grp, scope, pc in allrows:
    g_child[child].add(grp)
    g_parent[child].add(par)
cross_grp = {c: v for c, v in g_child.items() if len(v) > 1}
cross_par = {c: v for c, v in g_parent.items() if len(v) > 1}
print(f"  全表 {len(g_child):,} 个子 ASIN")
print(f"  映射到 >1 个运营组的：{len(cross_grp)}")
for c, v in sorted(cross_grp.items()):
    print(f"    ❗ {c:<13}{' / '.join(sorted(v))}")
print(f"  映射到 >1 个父ASIN 的：{len(cross_par)}")
for c, v in sorted(cross_par.items())[:15]:
    print(f"    {c:<13}{' | '.join(sorted(v))}")

# ---------- 广告侧/归因侧：同子ASIN是否落两组 ----------
print()
print("=" * 108)
print("④ 实证：广告侧 & 归因侧实际数据里，同子ASIN有无跨组花费/成交")
print("=" * 108)
cam_by_child: dict[str, set] = defaultdict(set)
for child, par, grp, scope, pc in allrows:
    cam_by_child[child].add(grp)

pur = rows("""SELECT COALESCE(purchased_product_id,''), COALESCE(purchased_product_parent_id,''),
                     account_name, sum(units)::text, sum(sales)::text
              FROM core.report_purchased_product_daily GROUP BY 1,2,3;""", "RDS_PG")
hit_grp: dict[str, dict] = defaultdict(lambda: defaultdict(float))
for asin, par, acct, u, s in pur:
    gs = cam_by_child.get(asin)
    if not gs:
        continue
    for g in gs:
        hit_grp[asin][g] += float(u or 0)
conflict = {a: v for a, v in hit_grp.items() if len(v) > 1}
print(f"  归因侧成交 ASIN 中，映射到多组的：{len(conflict)}（即为 0 则「子ASIN绝对区分」成立）")

for pc in ("W30", "W63", "W85"):
    print()
    print(f"  —— 款号 {pc} 的实际成交分布（验证「两个运营同时投广告」）——")
    for (par, grp, scope), kids in sorted(by_pc.get(pc, {}).items()):
        tot_u = 0.0
        tot_s = 0.0
        for asin, p, acct, u, s in pur:
            if asin in kids:
                tot_u += float(u or 0)
                tot_s += float(s or 0)
        print(f"    父ASIN {par:<13} 组 {grp:<6} 子ASIN {len(kids):>3} 个  "
              f"归因 {tot_u:>8,.0f} 件  ${tot_s:>11,.2f}")

# ---------- 男女款线索 ----------
print()
print("=" * 108)
print("⑤ 男女款线索：XH1/ZJ1 的 3 个款号，子 ASIN 标题里有没有男女区分")
print("=" * 108)
for pc in ("W75V2", "W81V2", "W81V5"):
    kids = [c for c, p, g, s, q in allrows if q == pc]
    print(f"\n【款号 {pc}】")
    for (par, grp, scope), ks in sorted(by_pc.get(pc, {}).items()):
        pass
    # 从业务报告取标题
    if kids:
        inlist = ",".join("'" + k + "'" for k in kids)
        t = rows(f"""SELECT child_asin, parent_asin, max(title)
                     FROM core.report_business_child_asin_daily
                     WHERE child_asin IN ({inlist}) GROUP BY 1,2;""", "RDS_PG")
        cnt = {"men": 0, "women": 0, "kids": 0, "unknown": 0}
        samples: dict[str, list] = defaultdict(list)
        for child, par, title in t:
            low = (title or "").lower()
            if "women" in low or "woman" in low:
                k = "women"
            elif "men's" in low or "mens" in low or " men " in low or "for men" in low:
                k = "men"
            elif "toddler" in low or "kids" in low or "little" in low:
                k = "kids"
            else:
                k = "unknown"
            cnt[k] += 1
            if len(samples[k]) < 2:
                samples[k].append(f"{child} @{par}")
        print(f"   标题词命中：{cnt}")
        for k, v in samples.items():
            for x in v:
                print(f"     {k:<8}{x}")
