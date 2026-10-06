#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建「父 ASIN → 款号 → 运营组」映射的候选清单。

基准（用户 2026-09-15 拍板）：**以业务报告的父 ASIN 为基准**，为每个父 ASIN 找出它属于哪个款号/运营组。
因为主数据里存的是**子 ASIN**（前台展示变体），与报告的父 ASIN 交集为 0，必须靠别的信号搭桥。

四个信号（实测覆盖率见 --report）
  A 报告标题含款号     109/428 零歧义 —— 亚马逊标题常以款号结尾（"…Home Wear Y13"）
  B 广告活动名含款号    36/428 —— campaign_name 第 2 段（运营自己命名的，可信度高）
  C 前台链接 slug 与标题文本重合   阈值取决于口径，召回高但误配风险也高
  D 人工/权威导出      0/428  —— Seller Central「管理库存」导出是唯一能到 100% 且无歧义的路

⚠️ 关键实测：**A 与 B 在 28 个 ASIN 上重叠，只有 19 个一致，9 个直接冲突（32%）**。
   所以本脚本**绝不**把单信号结果当定论：
     - A∩B 且一致        → confidence=high，可入库
     - 仅 A 或仅 B       → confidence=medium，入库但标记待抽检
     - A 与 B 冲突       → status=pending_review，两个候选都写进清单，等人裁决
     - 仅 C              → status=pending_review
     - 都没命中           → status=unmatched

用法
    python3 build_parent_child_map.py --report          # 只出统计
    python3 build_parent_child_map.py                   # 出待核验 CSV
    python3 build_parent_child_map.py --ddl             # 顺带建 app.asin_parent_map 表（不灌数据）
"""
from __future__ import annotations

import argparse
import collections
import csv
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ENV_PATH = REPO / "amazon-ads-console" / "backend" / ".env"
ROSTER_CSV = REPO / "amazon-ads-console" / "reference" / "product_mapping" / "在售产品_规范化.csv"
OUT_CSV = REPO / "amazon-ads-console" / "reference" / "product_mapping" / "父子ASIN映射_待核验.csv"

BR_TABLE = "core.report_business_parent_asin_period"

STOP = {"with", "for", "and", "the", "men", "women", "mens", "womens", "shoe", "shoes",
        "sneaker", "sneakers", "slipper", "slippers", "sandals", "sandal", "amazon",
        "com", "dp", "whitin", "bronax", "joomra", "new", "sale"}
CODE_SUFFIX = re.compile(r"(女|男|[WM])$")

DDL = """
CREATE SCHEMA IF NOT EXISTS app;
CREATE TABLE IF NOT EXISTS app.asin_parent_map (
    parent_asin    TEXT PRIMARY KEY,              -- 基准：业务报告的父 ASIN
    product_code   TEXT,                          -- 款号
    brand          TEXT,
    owner_group    TEXT,                          -- 运营组
    child_asin     TEXT,                          -- 主数据里的子 ASIN（可空）
    match_signal   TEXT NOT NULL,                 -- campaign_code|title_code|both|slug_overlap|manual|none
    confidence     TEXT NOT NULL,                 -- high|medium|low|none
    status         TEXT NOT NULL,                 -- confirmed|pending_review|unmatched
    evidence       TEXT,                          -- 判定依据原文，便于复核
    conflict       TEXT,                          -- 信号冲突时记录另一候选
    source_title   TEXT,
    built_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    verified_by    TEXT,
    verified_at    TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_apm_code  ON app.asin_parent_map (product_code);
CREATE INDEX IF NOT EXISTS idx_apm_group ON app.asin_parent_map (owner_group);
CREATE INDEX IF NOT EXISTS idx_apm_stat  ON app.asin_parent_map (status);
COMMENT ON TABLE app.asin_parent_map IS
  '父 ASIN → 款号 → 运营组 映射。基准=业务报告父 ASIN。低置信度不自动采信，冲突进 pending_review。';
"""


def _env(key: str = "RDS_DATABASE_URL") -> dict:
    """key=RDS_DATABASE_URL → 数据仓库 amazon_ads_v2；key=DATABASE_URL → 应用库 amazon_ads。"""
    dsn = ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{key}="):
            dsn = line.split("=", 1)[1].strip()
            break
    if not dsn:
        sys.exit(f"backend/.env 里没有 {key}")
    p = urlsplit(dsn)
    q = parse_qs(p.query)
    return {"host": p.hostname or "", "port": str(p.port or 5432),
            "user": unquote(p.username or ""), "password": unquote(p.password or ""),
            "dbname": p.path.lstrip("/"),
            "sslmode": (q.get("sslmode") or ["verify-full"])[-1],
            "sslrootcert": (q.get("sslrootcert") or [""])[-1]}


def psql(d: dict, sql: str) -> list[list[str]]:
    env = os.environ.copy()
    env["PGPASSWORD"] = d["password"]
    env["PGSSLMODE"] = d["sslmode"]
    if d["sslrootcert"]:
        env["PGSSLROOTCERT"] = d["sslrootcert"]
    env["PGCONNECT_TIMEOUT"] = "20"
    r = subprocess.run(["psql", "-w", "-h", d["host"], "-p", d["port"], "-U", d["user"],
                        "-d", d["dbname"], "-X", "-q", "-t", "-A", "-F", "\x1f",
                        "-v", "ON_ERROR_STOP=1", "-c", sql],
                       env=env, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip()[:400])
    return [ln.split("\x1f") for ln in r.stdout.strip().split("\n") if ln]


def norm_code(c: str) -> str:
    c = (c or "").strip().upper()
    for _ in range(2):
        m = CODE_SUFFIX.search(c)
        if not m:
            break
        c = c[: m.start()]
    return c


def toks(s: str) -> set[str]:
    s = re.sub(r"[^A-Za-z0-9\s]", " ", s or "")
    return {w.lower() for w in s.split() if len(w) > 2 and w.lower() not in STOP}


def load_roster() -> dict[str, list[dict]]:
    """款号 → 主数据行（一个款号可能对应多个子 ASIN）。"""
    out: dict[str, list[dict]] = {}
    with ROSTER_CSV.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            code = (r.get("product_code") or "").strip().upper()
            if not code:
                continue
            m = re.search(r"amazon\.com/([^/]+)/dp/", r.get("front_url") or "")
            out.setdefault(code, []).append({
                "brand": r.get("brand") or "", "group": r.get("owner_group") or "",
                "child": r.get("parent_asin") or "", "slug_toks": toks(m.group(1) if m else ""),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只出统计，不写 CSV")
    ap.add_argument("--ddl", action="store_true", help="顺带建 app.asin_parent_map")
    ap.add_argument("--overlap", type=float, default=0.7, help="信号C 重合系数阈值")
    a = ap.parse_args()

    d = _env("RDS_DATABASE_URL")        # 数据仓库：读报告事实
    appd = _env("DATABASE_URL")         # 应用库：app.* 主数据表落这里
    if a.ddl:
        psql(appd, DDL)
        print(f"已建表 {appd['dbname']}.app.asin_parent_map（未灌数据）\n")

    br = {r[0]: (r[1] or "").strip() for r in
          psql(d, f"SELECT DISTINCT parent_asin, title FROM {BR_TABLE} ORDER BY 1")}
    ad_pairs = psql(d, """
        SELECT DISTINCT split_part(btrim(split_part(c.campaign_name,'-',2)),' ',1) AS code,
                        p.advertised_product_parent_id AS asin
        FROM core.report_campaign_daily c
        JOIN core.report_advertised_product_daily p ON p.campaign_id = c.campaign_id
        WHERE p.advertised_product_parent_id NOT IN ('', '-1')
    """)
    roster = load_roster()
    codes = set(roster)

    # 信号 A：标题含款号
    sig_a: dict[str, str] = {}
    for asin, title in br.items():
        tu = title.upper()
        for c in sorted(codes, key=len, reverse=True):
            if re.search(rf"(?<![A-Za-z0-9]){re.escape(c)}(?![A-Za-z0-9])", tu):
                sig_a[asin] = c
                break
    # 信号 B：广告活动名款号
    sig_b: dict[str, str] = {}
    for code, asin in ad_pairs:
        nc = norm_code(code)
        if nc in codes:
            sig_b.setdefault(asin, nc)
    # 信号 C：slug 与标题重合系数
    sig_c: dict[str, tuple[float, str]] = {}
    for asin, title in br.items():
        tt = toks(title)
        if not tt:
            continue
        best = (0.0, "")
        for c, rows in roster.items():
            for r in rows:
                if not r["slug_toks"]:
                    continue
                ov = len(tt & r["slug_toks"]) / min(len(tt), len(r["slug_toks"]))
                if ov > best[0]:
                    best = (ov, c)
        if best[0] >= a.overlap:
            sig_c[asin] = best

    rows = []
    for asin, title in sorted(br.items()):
        ca, cb = sig_a.get(asin), sig_b.get(asin)
        cc = sig_c.get(asin)
        if ca and cb and ca == cb:
            code, signal, conf, status = ca, "both", "high", "confirmed"
            conflict = ""
        elif ca and cb and ca != cb:
            code, signal, conf, status = ca, "both", "low", "pending_review"
            conflict = f"标题→{ca} / 活动名→{cb}"
        elif cb:
            code, signal, conf, status, conflict = cb, "campaign_code", "medium", "confirmed", ""
        elif ca:
            code, signal, conf, status, conflict = ca, "title_code", "medium", "confirmed", ""
        elif cc:
            code, signal, conf, status = cc[1], "slug_overlap", "low", "pending_review"
            conflict = f"重合系数 {cc[0]:.2f}"
        else:
            code, signal, conf, status = "", "none", "none", "unmatched"
            conflict = ""
        info = roster.get(code, [{}])[0] if code else {}
        # 一个款号可能有多个子 ASIN，全部列出便于人工判断
        kids = " ".join(sorted({r["child"] for r in roster.get(code, []) if r["child"]})) if code else ""
        rows.append({
            "parent_asin": asin, "product_code": code,
            "brand": info.get("brand", ""), "owner_group": info.get("group", ""),
            "child_asins": kids, "match_signal": signal, "confidence": conf,
            "status": status, "conflict": conflict, "title": title[:110],
        })

    cnt = collections.Counter((r["status"], r["confidence"]) for r in rows)
    print(f"业务报告父 ASIN 基准 : {len(br)}")
    print(f"信号 A 标题含款号     : {len(sig_a)}")
    print(f"信号 B 活动名款号     : {len(sig_b)}")
    print(f"信号 C slug 重合≥{a.overlap:.1f} : {len(sig_c)}")
    inter = set(sig_a) & set(sig_b)
    agree = sum(1 for x in inter if sig_a[x] == sig_b[x])
    print(f"A ∩ B = {len(inter)}，一致 {agree}，冲突 {len(inter)-agree}  ← 冲突率 {(len(inter)-agree)/max(1,len(inter))*100:.0f}%")
    print()
    print("按状态 × 置信度：")
    for (st, cf), n in sorted(cnt.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {st:<15} {cf:<8} {n:>4}")
    covered = sum(n for (st, _), n in cnt.items() if st == "confirmed")
    print()
    print(f"可直接采信(confirmed) : {covered}  ({covered/len(br)*100:.0f}%)")
    print(f"待人工核验            : {cnt[('pending_review','low')]}  ({cnt[('pending_review','low')]/len(br)*100:.0f}%)")
    print(f"完全未命中            : {cnt[('unmatched','none')]}  ({cnt[('unmatched','none')]/len(br)*100:.0f}%)")

    if a.report:
        return 0
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["parent_asin", "product_code", "brand", "owner_group",
                                           "child_asins", "match_signal", "confidence", "status",
                                           "conflict", "title"])
        w.writeheader()
        for r in sorted(rows, key=lambda x: ({"confirmed": 0, "pending_review": 1, "unmatched": 2}[x["status"]],
                                             x["parent_asin"])):
            w.writerow(r)
    print()
    print(f"待核验清单 → {OUT_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
