"""归因侧缺口能否通过"广告侧出现记录 + campaign_name 前缀"反推归属。

只读。用法：backend/.venv/bin/python _mapping_rescue.py
"""
import os
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


# ---- 映射索引 ----
pm = {r[0] for r in rows("SELECT parent_asin FROM app.product_mapping;", "PG")}
cam_rows = rows("SELECT DISTINCT child_asin, COALESCE(parent_asin,'') FROM app.child_asin_mapping;", "PG")
cam_child = {r[0] for r in cam_rows}
cam_parent = {r[1] for r in cam_rows if r[1]}

# ---- 归因侧未映射 ----
pur = rows("""SELECT COALESCE(purchased_product_id,'<NULL>'),
                     COALESCE(purchased_product_parent_id,'<NULL>'),
                     COALESCE(purchased_product_name,''),
                     account_name, sum(units)::text
              FROM core.report_purchased_product_daily GROUP BY 1,2,3,4;""")
miss: dict[str, dict] = {}
for asin, par, nm, acct, u in pur:
    if asin in cam_child or asin in pm or par in pm or par in cam_parent:
        continue
    e = miss.setdefault(asin, {"u": 0.0, "nm": nm, "acct": set(), "par": par})
    e["u"] += float(u or 0)
    e["acct"].add(acct)

# ---- 广告侧：这些 ASIN 出现在哪些 campaign ----
advmap: dict[str, set] = defaultdict(set)
if miss:
    inlist = ",".join("'" + a.replace("'", "''") + "'" for a in miss)
    adv = rows(f"""SELECT COALESCE(advertised_product_id,''), campaign_name, ad_product,
                          COALESCE(advertised_product_parent_id,'')
                   FROM core.report_advertised_product_daily
                   WHERE advertised_product_id IN ({inlist})
                   GROUP BY 1,2,3,4;""")
    for asin, cname, adp, par in adv:
        prefix = cname.split("-")[0].strip() if cname else ""
        advmap[asin].add((cname, prefix, adp, par))

print("=" * 104)
print("归因侧缺口补救分析（100 个未映射成交 ASIN / 311 件）")
print("=" * 104)
print(f"{'成交ASIN':<14}{'件数':>6}  {'账户':<16}{'广告侧出现':<10}{'唯一组码':<14}判定")
print("-" * 104)

rescue_ok: dict[str, float] = defaultdict(float)
rescue_no: dict[str, float] = defaultdict(float)
unresolved: list = []
for asin, e in sorted(miss.items(), key=lambda x: -x[1]["u"]):
    info = advmap.get(asin, set())
    groups = {p for _, p, _, _ in info if p in VALID_GROUPS}
    if info and len(groups) == 1:
        g = groups.pop()
        verdict = f"✅ 可反推 → {g}"
        rescue_ok[g] += e["u"]
    elif info and len(groups) > 1:
        verdict = f"⚠️ 多组冲突 {sorted(groups)}"
        unresolved.append((asin, e, sorted(groups), "冲突"))
    elif info:
        verdict = "⚠️ 广告侧有记录但前缀无组码"
        unresolved.append((asin, e, [], "无组码"))
    else:
        verdict = "❌ 广告侧无记录"
        unresolved.append((asin, e, [], "无记录"))
    if not (info and len(groups) == 1):
        rescue_no["未解决"] += e["u"]
    print(f"{asin:<14}{e['u']:>6,.0f}  {'/'.join(sorted(e['acct']))[:15]:<16}"
          f"{len(info):>10}{'':<14}{verdict}")

print("-" * 104)
tot_miss = sum(v["u"] for v in miss.values())
rescued = sum(rescue_ok.values())
print(f"未映射合计 {tot_miss:,.0f} 件")
print(f"  可反推救回 {rescued:,.0f} 件 ({rescued / tot_miss * 100:.1f}%)")
for g, v in sorted(rescue_ok.items(), key=lambda x: -x[1]):
    print(f"    {g:<6}{v:>7,.0f} 件")
print(f"  仍未解决   {tot_miss - rescued:,.0f} 件 ({(tot_miss - rescued) / tot_miss * 100:.1f}%)")
if unresolved:
    print()
    print("  未解决明细（按原因）：")
    for reason in ("冲突", "无组码", "无记录"):
        items = [x for x in unresolved if x[3] == reason]
        if not items:
            continue
        print(f"    [{reason}] {len(items)} 个 ASIN / {sum(x[1]['u'] for x in items):,.0f} 件")
        for asin, e, gs, _ in items[:8]:
            print(f"      {asin:<14}{e['u']:>6,.0f} 件  {e['nm'][:58]}")
