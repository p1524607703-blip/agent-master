"""映射现状快照：表规模 + 重复导入残留 + __advertised__ 残留性质。

只读。用法：backend/.venv/bin/python _mapping_state.py
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


print("=" * 92)
print("① 映射表现状（应用库 amazon_ads / app schema）")
print("=" * 92)
for tab in ("product_mapping", "asin_parent_map", "child_asin_mapping", "product_roster",
            "operator_name_map"):
    try:
        n = rows(f"SELECT count(*)::text FROM app.{tab};")[0][0]
    except Exception as e:  # noqa: BLE001
        print(f"  app.{tab:<22} 读取失败: {str(e)[:60]}")
        continue
    print(f"  app.{tab:<22} {int(n):>8,} 行")

print()
print("  child_asin_mapping 按 account_scope 分布：")
for scope, n, ch, par in rows("""SELECT COALESCE(account_scope,'(空)'), count(*)::text,
                                        count(DISTINCT child_asin)::text,
                                        count(DISTINCT parent_asin)::text
                                 FROM app.child_asin_mapping GROUP BY 1 ORDER BY 2 DESC;"""):
    print(f"    {scope:<24}{int(n):>7,} 行   {int(ch):>6,} 子ASIN   {int(par):>5,} 父ASIN")
print("  child_asin_mapping 空值检查：")
for col in ("child_asin", "product_code", "operator_group", "parent_asin", "account_scope"):
    n = rows(f"SELECT count(*)::text FROM app.child_asin_mapping WHERE {col} IS NULL;")[0][0]
    print(f"    {col:<18} 空值 {int(n):>6,}")

print()
print("=" * 92)
print("② P0 重复导入：report_advertised_product_daily 同一 Campaign-day 多行")
print("=" * 92)
r = rows("""
    WITH g AS (
      SELECT stat_date, campaign_id, account_name, count(*) AS n,
             sum(spend) AS spend, count(DISTINCT advertised_product_id) AS n_asin
      FROM core.report_advertised_product_daily GROUP BY 1,2,3
    )
    SELECT count(*)::text, sum(CASE WHEN n>1 THEN 1 ELSE 0 END)::text,
           sum(spend)::text, sum(CASE WHEN n>1 THEN spend ELSE 0 END)::text
    FROM g;""", "RDS_PG")[0]
print(f"  Campaign-day 组数 {int(r[0]):,}   其中重复组 {int(r[1]):,}   总花费 ${float(r[2]):,.2f}")
print(f"  重复组涉及花费 ${float(r[3]):,.2f}")

print()
print("  重复组的 advertised_product_id 形态分布（按组去重后看每组的 id 组合）：")
r2 = rows("""
    WITH g AS (
      SELECT stat_date, campaign_id, account_name,
             array_agg(DISTINCT advertised_product_id ORDER BY advertised_product_id) AS ids,
             count(*) AS n, sum(spend) AS spend
      FROM core.report_advertised_product_daily GROUP BY 1,2,3
    ), k AS (
      SELECT CASE WHEN ids[1] IS NULL OR ids[1]='' THEN '空+' ELSE '有值+' END ||
             CASE WHEN ids[2] LIKE '__advertised__%' THEN '__advertised__'
                  WHEN ids[2] IS NULL OR ids[2]='' THEN '空'
                  ELSE '有值' END AS shape,
             n, spend
      FROM g WHERE n>1
    )
    SELECT shape, count(*)::text, sum(spend)::text FROM k GROUP BY 1 ORDER BY 2 DESC;""", "RDS_PG")
for shape, n, sp in r2:
    print(f"    {shape:<28}{int(n):>7,} 组   ${float(sp):>14,.2f}")

print()
print("  样例 5 组：")
for row in rows("""
    WITH g AS (
      SELECT stat_date, campaign_id, account_name, count(*) AS n
      FROM core.report_advertised_product_daily GROUP BY 1,2,3 HAVING count(*)>1
      ORDER BY 4 DESC LIMIT 5
    )
    SELECT d.stat_date::text, d.campaign_id, d.account_name,
           COALESCE(d.advertised_product_id,'<NULL>'), COALESCE(d.spend,0)::text
    FROM core.report_advertised_product_daily d
    JOIN g ON g.stat_date=d.stat_date AND g.campaign_id=d.campaign_id
          AND g.account_name=d.account_name
    ORDER BY d.stat_date, d.campaign_id;""", "RDS_PG"):
    print(f"    {row[0]}  {row[1][:34]:<36}{row[2][:18]:<20}{row[3][:30]:<32}${float(row[4]):>10,.2f}")

print()
print("=" * 92)
print("③ __advertised__ 残留：能否在别处找回真实 ASIN / 运营组")
print("=" * 92)
res = rows("""
    SELECT COALESCE(advertised_product_id,'<NULL>'), COALESCE(advertised_product_parent_id,'<NULL>'),
           account_name, sum(spend)::text, count(*)::text
    FROM core.report_advertised_product_daily
    WHERE advertised_product_id LIKE '__advertised__%'
       OR advertised_product_id IS NULL OR advertised_product_id=''
       OR advertised_product_id='-1'
    GROUP BY 1,2,3 ORDER BY 4 DESC LIMIT 25;""", "RDS_PG")
tot_bad = rows("""
    SELECT sum(spend)::text FROM core.report_advertised_product_daily
    WHERE advertised_product_id LIKE '__advertised__%'
       OR advertised_product_id IS NULL OR advertised_product_id=''
       OR advertised_product_id='-1';""", "RDS_PG")[0][0]
print(f"  非真实 ASIN 行合计花费 ${float(tot_bad or 0):,.2f}")
for a, p, acct, sp, n in res:
    print(f"    {a[:34]:<36}{p[:14]:<16}{acct[:18]:<20}${float(sp):>11,.2f}  {n} 行")

print()
print("  这些非真实 ASIN 行的 campaign_name 前缀是否落在已知运营组：")
for pre, n, sp in rows("""
    SELECT split_part(regexp_replace(campaign_name,'^(.*?)[-_].*$','\\1'),'_',1) AS pre,
           count(*)::text, sum(spend)::text
    FROM core.report_advertised_product_daily
    WHERE advertised_product_id LIKE '__advertised__%'
       OR advertised_product_id IS NULL OR advertised_product_id=''
       OR advertised_product_id='-1'
    GROUP BY 1 ORDER BY 3 DESC LIMIT 20;""", "RDS_PG"):
    print(f"    {pre[:32]:<34}{int(n):>6} 行   ${float(sp):>12,.2f}")
