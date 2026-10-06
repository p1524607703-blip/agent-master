"""P0 虚增量精确核算：两源文件 FULL OUTER JOIN，真值 / 入库值 / 虚增。

只读。用法：backend/.venv/bin/python _p0_excess.py
"""
import os
import subprocess
import sys
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


JOBS = (
    ("report_advertised_product_daily", "spend", "广告花费 $", "AMS_推广的商品_30D_日期.csv",
     "川鹏_推广的商品_30D_日期.csv"),
    ("report_purchased_product_daily", "units", "归因件数", "AMS_达成转化的商品_30D_日期.csv",
     "川鹏_达成转化的商品_30D_日期.csv"),
    ("report_purchased_product_daily", "sales", "归因销售额 $", "AMS_达成转化的商品_30D_日期.csv",
     "川鹏_达成转化的商品_30D_日期.csv"),
)

for tab, metric, label, f1, f2 in JOBS:
    q = f"""
    WITH a AS (SELECT stat_date, campaign_id, sum({metric}) AS s
               FROM core.{tab} WHERE source_file_name='{f1}' AND account_name='anac1973 (C3S8S)'
               GROUP BY 1,2),
         b AS (SELECT stat_date, campaign_id, sum({metric}) AS s
               FROM core.{tab} WHERE source_file_name='{f2}' AND account_name='anac1973 (C3S8S)'
               GROUP BY 1,2)
    SELECT count(*) FILTER (WHERE a.s IS NOT NULL AND b.s IS NOT NULL)::text,
           count(*) FILTER (WHERE a.s IS NOT NULL AND b.s IS NULL)::text,
           count(*) FILTER (WHERE b.s IS NOT NULL AND a.s IS NULL)::text,
           sum(COALESCE(a.s,b.s))::text,
           (sum(COALESCE(a.s,0))+sum(COALESCE(b.s,0)))::text,
           (sum(COALESCE(a.s,0))+sum(COALESCE(b.s,0)) - sum(COALESCE(a.s,b.s)))::text,
           sum(CASE WHEN a.s IS NOT NULL AND b.s IS NOT NULL AND abs(a.s-b.s)<0.01
                    THEN 1 ELSE 0 END)::text
    FROM a FULL OUTER JOIN b ON a.stat_date=b.stat_date AND a.campaign_id=b.campaign_id;"""
    ov, o1, o2, truth, loaded, excess, same = rows(q)[0]
    t, l, e = float(truth or 0), float(loaded or 0), float(excess or 0)
    print("=" * 92)
    print(f"{label} · core.{tab}")
    print("=" * 92)
    print(f"  重叠 (日期,活动) 组       {int(ov):>8,}   其中两文件数值相同 {int(same):,} "
          f"({int(same)/max(int(ov),1)*100:.1f}%)")
    print(f"  仅 AMS 有                {int(o1):>8,}")
    print(f"  仅 川鹏 有                {int(o2):>8,}")
    print(f"  ────────────────────────────────────────────")
    print(f"  真实值（去重后）           {t:>14,.2f}")
    print(f"  实际入库（两文件相加）      {l:>14,.2f}")
    print(f"  虚增                     {e:>14,.2f}   +{e/t*100 if t else 0:.1f}%")
    print()
