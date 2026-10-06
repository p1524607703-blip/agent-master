"""P0 决定性对账：同一账户两个源文件，按 (日期, 广告活动) 比花费/件数是否互为副本。

只读。用法：backend/.venv/bin/python _p0_cmp.py
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


def cmp_table(tab: str, metric: str, label: str) -> None:
    print("=" * 104)
    print(f"{label} · core.{tab}（账户 anac1973 (C3S8S)，两个源文件按 日期+广告活动 对比）")
    print("=" * 104)
    data = rows(f"""
        SELECT stat_date::text, campaign_id, source_file_name, sum({metric})::text
        FROM core.{tab}
        WHERE account_name = 'anac1973 (C3S8S)'
        GROUP BY 1,2,3;""")
    bykey: dict[tuple, dict] = defaultdict(dict)
    files: set = set()
    for d, cid, f, v in data:
        bykey[(d, cid)][f] = float(v or 0)
        files.add(f)
    f_list = sorted(files)
    print("  源文件：")
    for f in f_list:
        print(f"    {f}")
    if len(f_list) != 2:
        print(f"  ⚠ 源文件数 = {len(f_list)}，无法做二源对照。")
        print()
        return

    f1, f2 = f_list
    both = {k: v for k, v in bykey.items() if f1 in v and f2 in v}
    only1 = {k: v for k, v in bykey.items() if f1 in v and f2 not in v}
    only2 = {k: v for k, v in bykey.items() if f2 in v and f1 not in v}
    print(f"  两者都有的 (日期,活动) 组：{len(both):,}")
    print(f"  只有【{f1[:28]}】：{len(only1):,}")
    print(f"  只有【{f2[:28]}】：{len(only2):,}")

    def s(d, f): return sum(v.get(f, 0) for v in d.values())

    print()
    print(f"  【{f1[:40]}】  合计 {s(bykey, f1):,.2f}")
    print(f"  【{f2[:40]}】  合计 {s(bykey, f2):,.2f}")
    if both:
        eq = sum(1 for v in both.values() if abs(v[f1] - v[f2]) < 0.01)
        print()
        print(f"  重叠组里两文件数值完全相等的：{eq:,} / {len(both):,}  ({eq/len(both)*100:.1f}%)")
        ex = sorted(both.items(), key=lambda x: -max(x[1].values()))[:8]
        print(f"  {'日期':<12}{'广告活动':<26}{f1[:16]:>14}{f2[:16]:>14}  是否同值")
        for (d, cid), v in ex:
            same = "✅ 相同" if abs(v[f1] - v[f2]) < 0.01 else "❌ 不同"
            print(f"  {d:<12}{cid[:24]:<26}{v[f1]:>14,.2f}{v[f2]:>14,.2f}  {same}")
    print()


cmp_table("report_advertised_product_daily", "spend", "① 广告花费")
cmp_table("report_purchased_product_daily", "units", "② 归因件数")

# ---- 只看聚合口径下的总额 ----
print("=" * 104)
print("③ 账户级日总额（判断是否有整段重复）")
print("=" * 104)
print(f"{'账户':<22}{'日期':<13}{'源文件':<34}{'花费':>14}")
for acct in ("anac1973 (C3S8S)", "BLOOMNEXT", "JOOMRA DIRECT"):
    for d, f, sp in rows(f"""
        SELECT stat_date::text, source_file_name, sum(spend)::text
        FROM core.report_advertised_product_daily WHERE account_name='{acct}'
        GROUP BY 1,2 ORDER BY 1 DESC LIMIT 12;"""):
        print(f"  {acct[:20]:<22}{d:<13}{f[:32]:<34}{float(sp):>14,.2f}")
    print()
