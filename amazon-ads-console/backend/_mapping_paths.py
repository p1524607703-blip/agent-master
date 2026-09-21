"""精确路径分析：每笔归因到底靠哪条路径映射成功，以及未映射的究竟是谁。

只读。用法：backend/.venv/bin/python _mapping_paths.py
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


def main() -> None:
    pm = {r[0]: (r[1], r[2]) for r in
          rows("SELECT parent_asin, product_code, operator_group FROM app.product_mapping;")}
    cam = {(r[0], r[1]): (r[2], r[4], r[5]) for r in
           rows("SELECT account_scope, child_asin, product_code, COALESCE(parent_asin,''), "
                "COALESCE(brand,''), operator_group FROM app.child_asin_mapping;")}
    cam_by_child: dict[str, list[tuple]] = defaultdict(list)
    for (scope, child), v in cam.items():
        cam_by_child[child].append((scope, v))

    pur = rows("""SELECT COALESCE(purchased_product_id,'<NULL>'),
                         COALESCE(purchased_product_parent_id,'<NULL>'),
                         COALESCE(purchased_product_brand,''),
                         COALESCE(purchased_product_name,''),
                         account_name,
                         sum(units)::text
                  FROM core.report_purchased_product_daily
                  GROUP BY 1,2,3,4,5;""", "RDS_PG")

    print("=" * 92)
    print("归因件数的映射路径分析（《达成转化的商品》全窗口）")
    print("=" * 92)

    stat: dict[str, dict] = defaultdict(lambda: {"units": 0.0, "items": 0})
    unmapped: dict[str, dict] = defaultdict(lambda: {"units": 0.0, "brand": "", "name": "", "acct": set()})
    conflicts: list[tuple] = []

    for asin, par, brand, name, acct, units_s in pur:
        u = float(units_s or 0)
        hit_child = cam_by_child.get(asin, [])
        hit_self = pm.get(asin)
        hit_par = pm.get(par)

        if hit_child:
            # 若同一 child ASIN 出现在多个 scope，检查归属是否一致
            grps = {v[2] for _, v in hit_child}
            if len(grps) > 1:
                stat["P1_child_asm_多scope冲突"]['units'] += u
                stat["P1_child_asm_多scope冲突"]['items'] += 1
                continue
            if hit_par and hit_child[0][1][2] != hit_par[1]:
                conflicts.append((asin, par, hit_child[0][1][2], hit_par[1], u))
            stat["P1_child_asm 命中"]["units"] += u
            stat["P1_child_asm 命中"]["items"] += 1
        elif hit_self:
            stat["P2_成交ASIN 本身是父ASIN"]["units"] += u
            stat["P2_成交ASIN 本身是父ASIN"]["items"] += 1
        elif hit_par:
            stat["P3_靠父ASIN 命中"]["units"] += u
            stat["P3_靠父ASIN 命中"]["items"] += 1
        else:
            stat["P4_未映射"]["units"] += u
            stat["P4_未映射"]["items"] += 1
            e = unmapped[asin]
            e["units"] += u
            e["brand"] = brand
            e["name"] = name[:60]
            e["acct"].add(acct)

    tot_u = sum(v["units"] for v in stat.values())
    print(f"{'路径':<28}{'条目':>8}{'件数':>12}{'占比':>9}")
    print("-" * 92)
    for k in sorted(stat):
        v = stat[k]
        print(f"{k:<28}{v['items']:>8}{v['units']:>12,.0f}{v['units']/tot_u*100:>8.1f}%")
    print("-" * 92)
    print(f"{'合计':<28}{sum(v['items'] for v in stat.values()):>8}{tot_u:>12,.0f}{100.0:>8.1f}%")

    print()
    print("=" * 92)
    print(f"未映射明细（{len(unmapped)} 个成交ASIN / {tot_u and stat['P4_未映射']['units']:,.0f} 件）")
    print("=" * 92)
    print(f"{'成交ASIN':<14}{'件数':>8}  {'品牌':<12}{'账户':<14}商品名")
    for asin, e in sorted(unmapped.items(), key=lambda x: -x[1]["units"]):
        print(f"{asin:<14}{e['units']:>8,.0f}  {e['brand'][:11]:<12}"
              f"{'/'.join(sorted(e['acct']))[:13]:<14}{e['name']}")

    if conflicts:
        print()
        print("=" * 92)
        print(f"⚠️ 路径冲突（子表归属 与 父ASIN归属 不一致）：{len(conflicts)} 条")
        print("=" * 92)
        for asin, par, g_child, g_par, u in conflicts[:30]:
            print(f"  {asin:<14} 父={par:<14} 子表组={g_child:<6} 父表组={g_par:<6} {u:,.0f} 件")

    # --------- 广告侧 NULL / -1 父ASIN 的构成 ---------
    print()
    print("=" * 92)
    print("广告侧未映射父ASIN 的构成（《推广的商品》）")
    print("=" * 92)
    bad = rows("""SELECT COALESCE(advertised_product_parent_id,'<NULL>') par,
                         COALESCE(advertised_product_id,'<NULL>') asin,
                         COALESCE(advertised_product_brand,'') brand,
                         COALESCE(advertised_product_name,'') nm,
                         account_name,
                         sum(spend)::text
                  FROM core.report_advertised_product_daily
                  WHERE COALESCE(advertised_product_parent_id,'<NULL>')
                        NOT IN (SELECT parent_asin FROM core.report_advertised_product_daily) IS NOT NULL
                  GROUP BY 1,2,3,4,5
                  HAVING COALESCE(advertised_product_parent_id,'<NULL>') IN ('<NULL>','-1')
                  ORDER BY sum(spend) DESC;""", "RDS_PG") if False else None
    # 上面的 SQL 依赖应用库映射表，改在内存里筛
    bad = rows("""SELECT COALESCE(advertised_product_parent_id,'<NULL>') par,
                         COALESCE(advertised_product_id,'<NULL>') asin,
                         COALESCE(advertised_product_brand,'') brand,
                         COALESCE(advertised_product_name,'') nm,
                         account_name,
                         sum(spend)::text
                  FROM core.report_advertised_product_daily
                  GROUP BY 1,2,3,4,5;""", "RDS_PG")
    print(f"{'父ASIN':<14}{'子ASIN':<14}{'花费':>12}  {'品牌':<12}{'账户':<14}商品名")
    agg: dict[tuple, float] = defaultdict(float)
    for par, asin, brand, nm, acct, sp in bad:
        if par in pm or (par, asin) in cam:
            continue
        agg[(par, asin, brand, acct, nm[:60])] += float(sp or 0)
    for (par, asin, brand, acct, nm), sp in sorted(agg.items(), key=lambda x: -x[1])[:25]:
        print(f"{par:<14}{asin:<14}{sp:>12,.2f}  {brand[:11]:<12}{acct[:13]:<14}{nm}")


if __name__ == "__main__":
    main()
