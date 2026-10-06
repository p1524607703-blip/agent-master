"""广告侧残留：能否靠 campaign_name 前缀定组（SOP 第八/七章允许的第 2 顺位证据）。

只读。用法：backend/.venv/bin/python _mapping_campaign_prefix.py
"""
import os
import re
import subprocess
import sys
from collections import defaultdict
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

VALID_GROUPS = {"ZJ1", "XH1", "LB1", "DD1", "XM1", "XM2", "YS1", "ZF1",
                "LW1", "AJ1", "AJ2", "YT1"}


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
configure_pg_env(settings.data_account_url if False else settings.data_database_url, "RDS_PG")


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
cam = rows("SELECT DISTINCT child_asin, COALESCE(parent_asin,'') FROM app.child_asin_mapping;", "PG")
cam_child = {r[0] for r in cam}
cam_parent = {r[1] for r in cam if r[1]}

resid = rows("""SELECT account_name, campaign_id, campaign_name, ad_product,
                       COALESCE(advertised_product_parent_id,'<NULL>'),
                       COALESCE(advertised_product_id,'<NULL>'),
                       sum(spend)::text
                FROM core.report_advertised_product_daily
                WHERE COALESCE(advertised_product_parent_id,'<NULL>') IN ('<NULL>','-1')
                GROUP BY 1,2,3,4,5,6 ORDER BY 7 DESC;""")

print("=" * 100)
print("广告侧残留明细 + campaign_name 前缀可识别性")
print("=" * 100)
print(f"{'账户':<18}{'广告类型':<18}{'父':<8}{'子ASIN':<28}{'花费':>10}  组码(名称前缀)  Campaign")
print("-" * 100)

tot = 0.0
by_prefix: dict[str, float] = defaultdict(float)
unrecognized: list = []
for acct, cid, cname, adp, par, asin, sp in resid:
    s = float(sp or 0)
    tot += s
    # 兜底：子ASIN 能否命中
    fallback = asin in cam_child or asin in pm or par in cam_parent
    prefix = cname.split("-")[0].strip() if cname else ""
    ok = prefix in VALID_GROUPS
    if ok:
        by_prefix[prefix] += s
    else:
        unrecognized.append((acct, adp, par, asin, s, cname))
    flag = prefix if ok else ("(子ASIN兜底)" if fallback else "?? 无法识别")
    print(f"{acct[:17]:<18}{adp[:17]:<18}{par[:7]:<8}{asin[:26]:<28}{s:>10,.2f}  {flag:<14}  {cname[:40]}")

print("-" * 100)
print(f"残留合计 ${tot:,.2f}")
print()
print("按 campaign_name 前缀归组（可直接定组）：")
covered = 0.0
for g, v in sorted(by_prefix.items(), key=lambda x: -x[1]):
    print(f"  {g:<6} ${v:>12,.2f}")
    covered += v
print(f"  {'小计':<6} ${covered:>12,.2f}  ({covered / tot * 100:.2f}%)")
print()
if unrecognized:
    print(f"⚠️ 名称前缀无法识别：{len(unrecognized)} 条 / ${sum(x[4] for x in unrecognized):,.2f}")
    for acct, adp, par, asin, s, cname in unrecognized[:15]:
        print(f"  {acct[:17]:<18}{adp[:16]:<18}{par[:7]:<8}{asin[:26]:<28}{s:>10,.2f}  {cname[:40]}")
else:
    print("✅ 全部残留均可通过 campaign_name 前缀定组")
