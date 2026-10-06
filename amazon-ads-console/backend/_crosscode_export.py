"""生成跨组款号裁决表 CSV（含用户口径 + 数据验证 + 偏差标注）。

只读数据库，只写 ~/Desktop/周报告汇总/跨组款号裁决表_2026-09-21.csv
"""
import csv
import os
import subprocess
import sys
from collections import defaultdict
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

OUT = os.path.expanduser("~/Desktop/周报告汇总/跨组款号裁决表_2026-09-21.csv")

RULE = {
    "S71": ("A 同人分细组", "算同组（XM1+XM2 合并）", "两细码同属胡雪敏"),
    "W30": ("B 双投共款", "按各父ASIN定组，可子ASIN反推", "子ASIN两边完全不重叠"),
    "W63": ("B 双投共款", "按各父ASIN定组，可子ASIN反推", "子ASIN两边完全不重叠"),
    "W85": ("B 双投共款", "按各父ASIN定组，可子ASIN反推", "子ASIN两边完全不重叠"),
    "W75V2": ("C 男女款分列", "按父ASIN定组（性别天然区分）", "XH1=女 / ZJ1=男"),
    "W81V2": ("C 男女款分列", "按父ASIN定组（性别天然区分）", "XH1=女 / ZJ1=男"),
    "W81V5": ("C 男女款分列", "按父ASIN定组（性别天然区分）", "XH1=女 / ZJ1=男"),
}
GENDER = {"B0BW4783S9": "女款", "B0DPWWH9LH": "男款",
          "B0FRNCXHZC": "女款", "B0CW13XPHN": "男款",
          "B0DLB3VG96": "女款", "B0DKBQTXWN": "男款", "B0HH3NKDBK": "男款"}


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
         "-X", "-q", "-t", "-A", "-F", "|~|", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    return [ln.split("|~|") for ln in proc.stdout.strip().split("\n") if ln]


CODES = "','".join(RULE)
cam = rows(f"""SELECT child_asin, product_code, parent_asin, operator_group, account_scope,
                      COALESCE(brand,'') FROM app.child_asin_mapping
               WHERE product_code IN ('{CODES}')
               ORDER BY product_code, operator_group, parent_asin;""")

# 每父 ASIN：子数
kids: dict[str, list] = defaultdict(list)
pc_pars: dict[str, set] = defaultdict(set)
for r in cam:
    kids[r[2]].append(r[0])
    pc_pars[r[1]].add(r[2])

spend = {}
for r in rows("""SELECT COALESCE(advertised_product_parent_id,''), COALESCE(sum(spend),0)::text
                 FROM core.report_advertised_product_daily GROUP BY 1;""", "RDS_PG"):
    if len(r) >= 2 and r[0] and r[0] != "-1":
        spend[r[0]] = float(r[1])

# 每个父 ASIN 的组内广告活动名（判断谁真在投）
with open(OUT, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow([
        "款号", "类别", "裁决规则", "裁决依据", "所涉运营组", "父ASIN", "该父ASIN子ASIN数",
        "账户scope", "广告花费", "是否在投广告", "性别", "数据偏差提示",
    ])
    for pc in sorted(RULE):
        cat, rule, basis = RULE[pc]
        for par in sorted(pc_pars[pc]):
            grp = next(r[3] for r in cam if r[2] == par)
            scope = next(r[4] for r in cam if r[2] == par)
            sp = spend.get(par, 0.0)
            nl = len(set(kids[par]))
            gender = GENDER.get(par, "")
            note = ""
            if cat.startswith("B") and sp == 0:
                note = "⚠️ 该组零投放：成交全为跨组Halo，Halo归属口径待业务确认"
            w.writerow([pc, cat, rule, basis, grp, par, nl, scope, f"{sp:.2f}",
                        "是" if sp > 0 else "否", gender, note])
print(f"写出 {OUT}")

print()
print("=" * 96)
print("跨组款号裁决表（控制台预览）")
print("=" * 96)
print(f"{'款号':<9}{'类别':<14}{'组':<6}{'父ASIN':<14}{'子数':>5}{'广告花费':>14}{'在投':<6}性别")
for pc in sorted(RULE):
    for par in sorted(pc_pars[pc]):
        grp = next(r[3] for r in cam if r[2] == par)
        sp = spend.get(par, 0.0)
        nl = len(set(kids[par]))
        print(f"{pc:<9}{RULE[pc][0]:<14}{grp:<6}{par:<14}{nl:>5}{sp:>14,.2f}"
              f"{'是' if sp > 0 else '否':<6}{GENDER.get(par,'')}")

print()
print("=" * 96)
print("类别 B 的 Halo 明细（YS1 侧成交挂在谁的活动下）")
print("=" * 96)
pur = rows("""SELECT COALESCE(purchased_product_id,''), campaign_name,
                     sum(units)::text, sum(sales)::text
              FROM core.report_purchased_product_daily GROUP BY 1,2;""", "RDS_PG")
for pc in ("W30", "W63", "W85"):
    ys_par = next(p for p in pc_pars[pc]
                  if next(r[3] for r in cam if r[2] == p) == "YS1")
    zj_par = next(p for p in pc_pars[pc]
                  if next(r[3] for r in cam if r[2] == p) == "ZJ1")
    ys_kids = set(kids[ys_par])
    zj_kids = set(kids[zj_par])
    agg: dict[tuple, list] = defaultdict(lambda: [0.0, 0.0])
    for asin, cname, u, s in pur:
        owner = "YS1" if asin in ys_kids else ("ZJ1" if asin in zj_kids else None)
        if not owner:
            continue
        cpre = (cname or "").split("-")[0].split("_")[0].strip()
        a = agg[(owner, cpre)]
        a[0] += float(u or 0)
        a[1] += float(s or 0)
    print(f"\n【{pc}】YS1={ys_par}({len(ys_kids)}子)  ZJ1={zj_par}({len(zj_kids)}子)")
    for (owner, cpre), (u, s) in sorted(agg.items()):
        same = (owner == cpre) or (owner == "YS1" and cpre.startswith("YS")) or \
               (owner == "ZJ1" and cpre.startswith("ZJ"))
        print(f"   {owner}子ASIN 成交挂【{cpre:<6}】活动  {u:>7,.0f} 件  ${s:>10,.2f}  "
              f"{'✅组内' if same else '⚠️跨组Halo'}")
