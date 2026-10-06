"""验收：广告侧多路径兜底覆盖率 + 归因侧剩余缺口 + 业务侧新数据缺口。

只读。用法：backend/.venv/bin/python _mapping_verify.py
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


def rows(sql: str, prefix: str = "PG", timeout: int = 180) -> list[list[str]]:
    proc = subprocess.run(
        ["psql", "-h", os.environ[f"{prefix}HOST"], "-p", os.environ[f"{prefix}PORT"],
         "-U", os.environ[f"{prefix}USER"], "-d", os.environ[f"{prefix}DATABASE"],
         "-X", "-q", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    return [ln.split("\t") for ln in proc.stdout.strip().split("\n") if ln]


def pct(a: float, b: float) -> str:
    return "—" if not b else f"{a / b * 100:.2f}%"


# ---------- 映射索引 ----------
pm = {r[0]: (r[1], r[2]) for r in
      rows("SELECT parent_asin, product_code, operator_group FROM app.product_mapping;")}
apm = {r[0]: (r[1], r[3]) for r in rows(
    "SELECT parent_asin, product_code, COALESCE(brand,''), COALESCE(owner_group,'') "
    "FROM app.asin_parent_map;")}
cam_rows = rows("SELECT account_scope, child_asin, product_code, COALESCE(parent_asin,''), "
                "operator_group FROM app.child_asin_mapping;")
cam_child: dict[str, list] = defaultdict(list)      # child_asin -> [(scope, pc, par, grp)]
cam_parent: dict[str, list] = defaultdict(list)     # parent_asin -> [(scope, pc, grp)]
for scope, child, pc, par, grp in cam_rows:
    cam_child[child].append((scope, pc, par, grp))
    if par:
        cam_parent[par].append((scope, pc, grp))

print("=" * 90)
print("验收 1 · 广告侧《推广的商品》多路径兜底")
print("=" * 90)
adv = rows("""SELECT COALESCE(advertised_product_parent_id,'<NULL>'),
                     COALESCE(advertised_product_id,'<NULL>'),
                     COALESCE(advertised_product_brand,''),
                     COALESCE(advertised_product_name,''),
                     account_name, sum(spend)::text
              FROM core.report_advertised_product_daily GROUP BY 1,2,3,4,5;""", "RDS_PG")

stat: dict[str, float] = defaultdict(float)
resid: dict[tuple, float] = defaultdict(float)
tot = 0.0
for par, asin, brand, nm, acct, sp in adv:
    s = float(sp or 0)
    tot += s
    if par in ("<NULL>", "-1", ""):
        if asin in cam_child:
            stat["P1 父ASIN缺失 → 靠子ASIN命中 child_mapping"] += s
        elif asin in pm:
            stat["P2 父ASIN缺失 → 子ASIN本身就是已映射父ASIN"] += s
        else:
            stat["P4 父ASIN缺失且子ASIN也无映射（残留）"] += s
            resid[(par, asin, brand, acct, nm[:48])] += s
    else:
        if par in pm:
            stat["P0 父ASIN直接命中 product_mapping"] += s
        elif par in cam_parent:
            stat["P3 父ASIN命中 child_mapping.parent_asin（新增可用）"] += s
        elif asin in cam_child:
            stat["P1' 父ASIN未命中 → 靠子ASIN兜底"] += s
        else:
            stat["P4' 父ASIN未命中且子ASIN无映射（残留）"] += s
            resid[(par, asin, brand, acct, nm[:48])] += s

print(f"总花费 ${tot:,.2f}")
for k in sorted(stat):
    print(f"  {k:<50} ${stat[k]:>13,.2f}  {pct(stat[k], tot):>7}")
covered = tot - sum(v for k, v in stat.items() if k.startswith("P4"))
print(f"  {'-' * 50}")
print(f"  {'可映射合计':<50} ${covered:>13,.2f}  {pct(covered, tot):>7}")
print(f"  {'未映射残留':<50} ${tot - covered:>13,.2f}  {pct(tot - covered, tot):>7}")

if resid:
    print()
    print(f"  残留明细（{len(resid)} 组）：")
    print(f"  {'父ASIN':<12}{'子ASIN':<26}{'花费':>12}  {'账户':<18}商品名")
    for (par, asin, brand, acct, nm), s in sorted(resid.items(), key=lambda x: -x[1])[:20]:
        print(f"  {par:<12}{asin[:24]:<26}{s:>12,.2f}  {acct[:17]:<18}{nm}")

print()
print("=" * 90)
print("验收 2 · 归因侧剩余缺口按账户/品牌归集")
print("=" * 90)
pur = rows("""SELECT COALESCE(purchased_product_id,'<NULL>'),
                     COALESCE(purchased_product_parent_id,'<NULL>'),
                     COALESCE(purchased_product_brand,''),
                     COALESCE(purchased_product_name,''),
                     account_name, sum(units)::text
              FROM core.report_purchased_product_daily GROUP BY 1,2,3,4,5;""", "RDS_PG")
by_acct: dict[str, float] = defaultdict(float)
by_kind: dict[str, float] = defaultdict(float)
by_brand: dict[str, float] = defaultdict(float)
tot_u = 0.0
for asin, par, brand, nm, acct, u in pur:
    v = float(u or 0)
    tot_u += v
    if asin in cam_child or asin in pm or par in pm or par in cam_parent:
        continue
    by_acct[acct] += v
    by_brand[brand or "(空)"] += v
    low = nm.lower()
    kind = ("拖鞋/凉鞋 slippers/slides" if ("slipper" in low or "slide" in low or "sandal" in low)
            else "鞋垫 insole" if "insole" in low
            else "童鞋 kids/toddler" if ("toddler" in low or "kids" in low or "little" in low)
            else "行走/跑步鞋 walking/running" if ("walking" in low or "running" in low or "tennis" in low)
            else "barefoot/宽楦" if ("barefoot" in low or "wide toe" in low or "wide width" in low)
            else "其他")
    by_kind[kind] += v

print(f"总归因件数 {tot_u:,.0f}    未映射 {sum(by_acct.values()):,.0f} ({pct(sum(by_acct.values()), tot_u)})")
print()
print("  按账户：")
for k, v in sorted(by_acct.items(), key=lambda x: -x[1]):
    print(f"    {k:<20} {v:>7,.0f} 件")
print("  按品牌：")
for k, v in sorted(by_brand.items(), key=lambda x: -x[1]):
    print(f"    {k[:18]:<20} {v:>7,.0f} 件")
print("  按品类（从商品名推断）：")
for k, v in sorted(by_kind.items(), key=lambda x: -x[1]):
    print(f"    {k:<28} {v:>7,.0f} 件")

print()
print("=" * 90)
print("验收 3 · 业务侧新数据（child_asin_daily，342,859 行）覆盖情况")
print("=" * 90)
biz = rows("""SELECT child_asin, COALESCE(parent_asin,''), COALESCE(title,''),
                     sum(ordered_product_units)::text
              FROM core.report_business_child_asin_daily GROUP BY 1,2,3;""", "RDS_PG")
b_tot = 0.0
b_miss = 0.0
b_miss_set: dict[str, float] = defaultdict(float)
for child, par, title, u in biz:
    v = float(u or 0)
    b_tot += v
    if child in cam_child or child in pm or par in pm or par in cam_parent:
        continue
    b_miss += v
    b_miss_set[child] += v
print(f"业务侧订购量合计 {b_tot:,.0f}")
print(f"  可映射 {b_tot - b_miss:,.0f} ({pct(b_tot - b_miss, b_tot)})")
print(f"  未映射 {b_miss:,.0f} ({pct(b_miss, b_tot)})  —— {len(b_miss_set)} 个 ASIN")
if b_miss_set:
    print(f"  Top10（业务侧有量但映射表里没有）：")
    for k, v in sorted(b_miss_set.items(), key=lambda x: -x[1])[:10]:
        print(f"    {k:<14}{v:>8,.0f} 件")
