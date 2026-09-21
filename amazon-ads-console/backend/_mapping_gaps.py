"""产出：未映射缺口 CSV + 可计算映射视图 SQL（只读，不改库）。"""
import os
import subprocess
import sys
from collections import defaultdict
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

OUT = "/Users/panjinlong/Desktop/周报告汇总/映射体检_2026-09-19"
os.makedirs(OUT, exist_ok=True)


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


pm = {r[0]: (r[1], r[2]) for r in
      rows("SELECT parent_asin, product_code, operator_group FROM app.product_mapping;")}
cam = {(r[0], r[1]): (r[2], r[5]) for r in
       rows("SELECT account_scope, child_asin, product_code, COALESCE(parent_asin,''), "
            "COALESCE(brand,''), operator_group FROM app.child_asin_mapping;")}
cam_child: dict[str, list] = defaultdict(list)
for (scope, child), v in cam.items():
    cam_child[child].append((scope, v))

# ---- 缺口1：成交ASIN 未映射 ----
pur = rows("""SELECT COALESCE(purchased_product_id,'<NULL>'), COALESCE(purchased_product_parent_id,''),
                     COALESCE(purchased_product_brand,''), COALESCE(purchased_product_name,''),
                     account_name, sum(units)::text, sum(purchases)::text
              FROM core.report_purchased_product_daily GROUP BY 1,2,3,4,5;""", "RDS_PG")
g1 = {}
for asin, par, brand, nm, acct, u, p in pur:
    if asin in cam_child or asin in pm or par in pm:
        continue
    e = g1.setdefault(asin, {"u": 0.0, "p": 0.0, "brand": set(), "acct": set(), "nm": ""})
    e["u"] += float(u or 0)
    e["p"] += float(p or 0)
    e["brand"].add(brand)
    e["acct"].add(acct)
    e["nm"] = e["nm"] or nm
with open(f"{OUT}/缺口1_未映射成交ASIN.csv", "w", encoding="utf-8-sig") as f:
    f.write("成交ASIN,归因件数,购买量,品牌,账户,商品名\n")
    for k, v in sorted(g1.items(), key=lambda x: -x[1]["u"]):
        f.write(f'{k},{v["u"]:.0f},{v["p"]:.0f},{"/".join(sorted(v["brand"]))},'
                f'{" / ".join(sorted(v["acct"]))},"{v["nm"]}"\n')

# ---- 缺口2：广告父ASIN 未映射 ----
adv = rows("""SELECT COALESCE(advertised_product_parent_id,'<NULL>'), COALESCE(advertised_product_id,''),
                     COALESCE(advertised_product_brand,''), COALESCE(advertised_product_name,''),
                     account_name, sum(spend)::text
              FROM core.report_advertised_product_daily GROUP BY 1,2,3,4,5;""", "RDS_PG")
g2 = {}
for par, asin, brand, nm, acct, sp in adv:
    if par in pm or (par, asin) in cam:
        continue
    key = (par, asin)
    e = g2.setdefault(key, {"sp": 0.0, "brand": set(), "acct": set(), "nm": ""})
    e["sp"] += float(sp or 0)
    e["brand"].add(brand)
    e["acct"].add(acct)
    e["nm"] = e["nm"] or nm
with open(f"{OUT}/缺口2_未映射广告父ASIN.csv", "w", encoding="utf-8-sig") as f:
    f.write("父ASIN,子ASIN,花费,品牌,账户,商品名\n")
    for (par, asin), v in sorted(g2.items(), key=lambda x: -x[1]["sp"]):
        f.write(f'{par},{asin},{v["sp"]:.2f},{"/".join(sorted(v["brand"]))},'
                f'{" / ".join(sorted(v["acct"]))},"{v["nm"]}"\n')

# ---- 缺口3：roster 组码对照 ----
r2m = rows("""SELECT owner_group, count(*) FROM app.product_roster
              WHERE owner_group IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;""")
with open(f"{OUT}/缺口3_roster组码不一致.csv", "w", encoding="utf-8-sig") as f:
    f.write("roster组码,行数,映射表对应写法,是否可直接JOIN\n")
    fix = {"AJ": "AJ1 / AJ2（不可区分）", "XM": "XM1 / XM2（不可区分）",
           "LW": "LW1", "ZF": "ZF1"}
    for g, n in r2m:
        g = g or ""
        if g in fix:
            f.write(f'{g},{n},{fix[g]},否\n')
        else:
            f.write(f'{g},{n},{g},是\n')

print("已输出到:", OUT)
for fn in sorted(os.listdir(OUT)):
    p = os.path.join(OUT, fn)
    print(f"  {fn}  ({os.path.getsize(p)} bytes, "
          f"{sum(1 for _ in open(p, encoding='utf-8-sig')) - 1} 行)")
print(f"\n缺口1 未映射成交ASIN: {len(g1)} 个 / {sum(v['u'] for v in g1.values()):,.0f} 件")
print(f"缺口2 未映射广告父ASIN: {len(g2)} 组 / ${sum(v['sp'] for v in g2.values()):,.2f}")
