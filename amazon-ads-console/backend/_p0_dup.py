"""P0 重复导入：按源文件 + 按 (campaign-day, 商品名) 双口径对账。

只读。用法：backend/.venv/bin/python _p0_dup.py
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


def rows(sql: str, prefix: str = "RDS_PG", timeout: int = 300) -> list[list[str]]:
    proc = subprocess.run(
        ["psql", "-h", os.environ[f"{prefix}HOST"], "-p", os.environ[f"{prefix}PORT"],
         "-U", os.environ[f"{prefix}USER"], "-d", os.environ[f"{prefix}DATABASE"],
         "-X", "-q", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    return [ln.split("\t") for ln in proc.stdout.strip().split("\n") if ln]


for tab, spend_col, unit_col in (
    ("report_advertised_product_daily", "spend", "units"),
    ("report_purchased_product_daily", "sales", "units"),
):
    print("=" * 104)
    print(f"源文件对账 · core.{tab}")
    print("=" * 104)
    print(f"{'源文件':<46}{'行数':>9}{'日期区间':>26}{'账户':<20}")
    for f, n, drange, acct in rows(f"""
        SELECT COALESCE(source_file_name,'(空)'), count(*)::text,
               min(stat_date)::text || ' ~ ' || max(stat_date)::text,
               string_agg(DISTINCT account_name, ',' ORDER BY account_name)
        FROM core.{tab} GROUP BY 1 ORDER BY 2 DESC;"""):
        print(f"  {f[:44]:<44}{int(n):>9}{drange:>26}  {acct[:34]}")
    print()

    print(f"  同一 (日期, 广告活动, 广告组, 商品名) 出现 >1 行 = 重复导入：")
    r = rows(f"""
        WITH g AS (
          SELECT stat_date, campaign_id, ad_group_id,
                 COALESCE(advertised_product_name,'') AS pname, account_name,
                 count(*) AS n, sum({spend_col}) AS amt, sum({unit_col}) AS u
          FROM core.{tab} GROUP BY 1,2,3,4,5
        )
        SELECT count(*)::text,
               sum(CASE WHEN n>1 THEN 1 ELSE 0 END)::text,
               sum(amt)::text,
               sum(CASE WHEN n>1 THEN amt ELSE 0 END)::text,
               sum(u)::text,
               sum(CASE WHEN n>1 THEN u ELSE 0 END)::text
        FROM g;""")[0]
    tot_n, dup_n, tot_a, dup_a, tot_u, dup_u = r
    print(f"    组数 {int(tot_n):,}  重复组 {int(dup_n):,}")
    print(f"    {spend_col} 合计 {float(tot_a):,.2f}  其中重复组多算 {float(dup_a):,.2f}")
    print(f"    {unit_col} 合计 {float(tot_u):,.0f}  其中重复组多算 {float(dup_u):,.0f}")
    print()

    print(f"    —— 按广告活动看：重复活动 Top12 ——")
    for cid, cname, acct, n, extra in rows(f"""
        WITH g AS (
          SELECT stat_date, campaign_id, ad_group_id, COALESCE(advertised_product_name,'') AS pname,
                 account_name, count(*) AS n, sum({spend_col}) AS amt
          FROM core.{tab} GROUP BY 1,2,3,4,5
        )
        SELECT campaign_id, max(cname) , max(account_name), sum(n-1)::text, (sum(amt) - sum(amt/n))::text
        FROM (SELECT g.*, (SELECT campaign_name FROM core.{tab} t2
                           WHERE t2.campaign_id=g.campaign_id LIMIT 1) AS cname FROM g) x
        WHERE n>1 GROUP BY campaign_id ORDER BY 5 DESC LIMIT 12;"""):
        print(f"      {cid[:30]:<32}{cname[:30]:<32}{acct[:16]:<18}多 {int(n):>5} 行  ${float(extra):>11,.2f}")
    print()
