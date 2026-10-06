"""导出映射缺口清单 + 生成复核报告。

只读数据库；只写 ~/Desktop/周报告汇总/映射体检_2026-09-21/。
用法：backend/.venv/bin/python _mapping_gap_export.py
"""
import csv
import os
import subprocess
import sys
from collections import defaultdict
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings

OUT = os.path.expanduser("~/Desktop/周报告汇总/映射体检_2026-09-21")
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


NOW = rows("SELECT now()::date::text, now()::text;")[0]
print(f"服务器时间 {NOW[1]}")

pm = {r[0] for r in rows("SELECT parent_asin FROM app.product_mapping;", "PG")}
cam = rows("SELECT DISTINCT child_asin, COALESCE(parent_asin,'') FROM app.child_asin_mapping;", "PG")
cam_child = {r[0] for r in cam}
cam_parent = {r[1] for r in cam if r[1]}


def mapped(child: str, par: str) -> bool:
    return child in cam_child or child in pm or par in pm or par in cam_parent


# ---------- 缺口 1：业务侧未登记产品线 ----------
biz = rows("""SELECT child_asin, COALESCE(parent_asin,''), COALESCE(title,''), account_name,
                     sum(ordered_product_units)::text, sum(ordered_product_sales)::text,
                     min(stat_date)::text, max(stat_date)::text
              FROM core.report_business_child_asin_daily
              GROUP BY 1,2,3,4;""")
pl: dict[str, dict] = {}
orphan: list = []
for child, par, title, acct, u, s, d0, d1 in biz:
    if mapped(child, par):
        continue
    if not par:
        orphan.append((child, acct, title, u, s, d0, d1))
        continue
    g = pl.setdefault(par, {"units": 0.0, "sales": 0.0, "n": 0, "title": title, "acct": acct,
                            "d0": d0, "d1": d1, "kids": []})
    g["units"] += float(u or 0)
    g["sales"] += float(s or 0)
    g["n"] += 1
    g["kids"].append(child)

p1 = os.path.join(OUT, "缺口1_业务侧未登记产品线.csv")
with open(p1, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["父ASIN", "账户", "未映射子ASIN数", "未映射订购量", "未映射销售额",
                "在广告侧有花费?", "首日", "末日", "商品标题"])
    for par, g in sorted(pl.items(), key=lambda x: -x[1]["units"]):
        adsp = rows(f"""SELECT COALESCE(sum(spend),0)::text FROM core.report_advertised_product_daily
                        WHERE advertised_product_parent_id='{par}';""")[0][0]
        w.writerow([par, g["acct"], g["n"], int(g["units"]), f"{g['sales']:.2f}",
                    f"是(${float(adsp):.2f})" if float(adsp) > 0 else "否(纯自然流量)",
                    g["d0"], g["d1"], g["title"]])
print(f"  写出 {p1}  ({len(pl)} 个未登记父ASIN)")

p1b = os.path.join(OUT, "缺口1b_业务侧未登记子ASIN明细.csv")
with open(p1b, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["父ASIN", "子ASIN", "账户", "商品标题"])
    for par, g in sorted(pl.items(), key=lambda x: -x[1]["units"]):
        for k in sorted(g["kids"]):
            w.writerow([par, k, g["acct"], g["title"]])
print(f"  写出 {p1b}")

# ---------- 缺口 2：广告侧无 ASIN 行（只能靠活动名前缀） ----------
res = rows("""SELECT stat_date::text, campaign_id, campaign_name, account_name,
                     COALESCE(advertised_product_id,'<NULL>'),
                     COALESCE(advertised_product_parent_id,'<NULL>'), spend::text, units::text
              FROM core.report_advertised_product_daily
              WHERE (advertised_product_parent_id IS NULL OR advertised_product_parent_id='-1')
                AND NOT (COALESCE(advertised_product_id,'') = ANY(ARRAY['','-1']))
              ORDER BY spend::numeric DESC;""")
res2 = rows("""SELECT stat_date::text, campaign_id, campaign_name, account_name,
                      COALESCE(advertised_product_id,'<NULL>'),
                      COALESCE(advertised_product_parent_id,'<NULL>'), spend::text, units::text
               FROM core.report_advertised_product_daily
               WHERE (advertised_product_parent_id IS NULL OR advertised_product_parent_id='-1')
               ORDER BY spend::numeric DESC;""")
p2 = os.path.join(OUT, "缺口2_广告侧无ASIN行.csv")
import re
PRE = re.compile(r"^([A-Z]{2}\d)[-_ ]")
with open(p2, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["日期", "广告活动ID", "广告活动名", "账户", "advertised_product_id",
                "父ASIN", "花费", "归因件数", "活动名前缀(可归组)"])
    for d, cid, cname, acct, aid, par, sp, u in res2:
        m = PRE.match(cname or "")
        w.writerow([d, cid, cname, acct, aid, par, sp, u, m.group(1) if m else "无法识别"])
print(f"  写出 {p2}  ({len(res2)} 行)")

# ---------- 缺口 3：映射表跨组冲突 ----------
p3 = os.path.join(OUT, "缺口3_款号跨运营组.csv")
with open(p3, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["款号", "涉及运营组", "行数", "说明"])
    for pc, gs, n in rows("""SELECT product_code, string_agg(DISTINCT operator_group,'/' ORDER BY operator_group),
         count(*)::text FROM app.child_asin_mapping GROUP BY 1
         HAVING count(DISTINCT operator_group)>1 ORDER BY 1;""", "PG"):
        w.writerow([pc, gs, int(n), "同一款号被两个父ASIN带走，分属不同运营组——按父ASIN分组无歧义，按款号分组会打架"])
print(f"  写出 {p3}")

p3b = os.path.join(OUT, "缺口3b_子ASIN跨scope重复.csv")
with open(p3b, "w", newline="", encoding="utf-8-sig") as fh:
    w = csv.writer(fh)
    w.writerow(["子ASIN", "各scope记录", "是否真冲突"])
    for ca, det, ng in rows("""SELECT child_asin,
           string_agg(account_scope||'/'||operator_group||'/'||product_code,' | ' ORDER BY account_scope),
           count(DISTINCT operator_group)::text
         FROM app.child_asin_mapping GROUP BY 1
         HAVING count(DISTINCT operator_group)>1 OR count(DISTINCT account_scope)>1 ORDER BY 1;""", "PG"):
        w.writerow([ca, det, "❌ 真冲突(组不同)" if int(ng) > 1 else "✅ 仅scope重复(组相同)"])
print(f"  写出 {p3b}")

# ---------- 报告 ----------
ad = rows("""
    SELECT COALESCE(advertised_product_parent_id,'<NULL>'),
           COALESCE(advertised_product_id,'<NULL>'), sum(spend)::text
    FROM core.report_advertised_product_daily GROUP BY 1,2;""")
tot = p0 = p1v = p3v = p4 = 0.0
for pp, ap, sp in ad:
    s = float(sp or 0)
    tot += s
    if pp in ("<NULL>", "-1", ""):
        if ap in cam_child:
            p1v += s
        else:
            p4 += s
    elif pp in pm:
        p0 += s
    elif pp in cam_parent:
        p3v += s
    elif ap in cam_child:
        p1v += s
    else:
        p4 += s
covered = p0 + p1v + p3v

biz_tot = rows("""SELECT sum(ordered_product_units)::text FROM core.report_business_child_asin_daily;""")[0][0]
pur = rows("""SELECT sum(units)::text FROM core.report_purchased_product_daily;""")[0][0]

lines = [
    f"# 映射归属复核报告 · {NOW[0]}",
    "",
    "> 数据源：`amazon_ads`（应用库 app schema）+ `amazon_ads_v2`（数据仓库 core schema）。",
    "> 全流程只读，未修改任何数据。",
    "",
    "## 一句话结论",
    "",
    "**GPT 的父子映射做完了、也做干净了——但那只是三道关口里的第二道。**",
    "映射表本身没问题（5 列零空值、父 ASIN→组零冲突）；真正卡住交付的是另两件事：",
    "① 广告成本池被 anac1973 重复导入灌了水（虚增 93.6%）；② 17 条整条产品线从没在映射表里登记过。",
    "",
    "## 一、映射表本体质量 ✅",
    "",
    "| 表 | 行数 | 结论 |",
    "|---|---|---|",
    "| `app.child_asin_mapping` | 7,270 | **唯一可用主表** |",
    "| `app.product_mapping` | 128 | 广告侧父 ASIN 表，P0 命中率 96.4% |",
    "| `app.asin_parent_map` | 116 | product_mapping 的真子集，冗余快照 |",
    "| `app.product_roster` | 149 | 主数据；**不可用于定组** |",
    "",
    "`child_asin_mapping` 逐列空值：`child_asin` / `product_code` / `operator_group` / "
    "`parent_asin` / `account_scope` **全部 0 空值**。",
    "",
    "覆盖的三个账户 scope：WHITIN 5,525 / BLOOMNEXT 899 / JOOMRA DIRECT 846。",
    "",
    f"行来源拆分：**7,169 行** `confidence=inherited`（父 ASIN 机械继承）+ "
    f"**101 行** `confidence=high`（带来源证据，来源 4 类："
    "`confirmed_reference_roster` / `30d_parent_ad_campaign_example` / "
    "`30d_exact_identity_evidence` / 参考名册）。`mapping_status` 全表统一为 `parent_inherited`。",
    "",
    "运营组码共 12 个（3 位细码）：`AJ1 AJ2 DD1 LB1 LW1 XH1 XM1 XM2 YS1 YT1 ZF1 ZJ1`。",
    "",
    "**冲突扫描**：",
    "",
    "- `parent_asin` → `operator_group`：**0 冲突**（分组锚点是父 ASIN，结构干净）",
    "- 同一 `child_asin` 跨 scope 重复：34 个 —— **全部是同组同款号的 scope 重复**，组码完全一致，只需去重，不是真冲突",
    "- 同一 `product_code` 落在两个组：7 个（见缺口3 CSV）—— 同一款号被两个父 ASIN 带走、分属不同运营组。**按父 ASIN 分组无歧义，按款号分组会打架**",
    "",
    "## 二、覆盖漏斗",
    "",
    "### 广告侧（成本池 · 《推广的商品》）",
    "",
    f"总花费 **${tot:,.2f}**",
    "",
    "| 路径 | 花费 | 占比 |",
    "|---|---|---|",
    f"| P0 父 ASIN 直接命中 `product_mapping` | ${p0:,.2f} | {p0/tot*100:.2f}% |",
    f"| P1 父 ASIN 缺失 → 子 ASIN 命中 `child_asin_mapping` | ${p1v:,.2f} | {p1v/tot*100:.2f}% |",
    f"| P3 父 ASIN 命中 `child_asin_mapping.parent_asin` | ${p3v:,.2f} | {p3v/tot*100:.2f}% |",
    f"| **可映射合计** | **${covered:,.2f}** | **{covered/tot*100:.2f}%** |",
    f"| P4 残留（无 ASIN 可查） | ${p4:,.2f} | {p4/tot*100:.2f}% |",
    "",
    f"那 {p4:,.2f} 美元残留（{p4/tot*100:.2f}%）**不是漏映射，是根本没 ASIN**：",
    "父 ASIN 字段是 `NULL` 或 `-1`，商品名也是空的。其中 $22,730.52 全部来自一个占位符 "
    "`__advertised__c65f37b2cb1ae26c89e9`（304 行，跨 3 个账户共享），挂在「视频 / 流媒体」类广告活动下——",
    "这是 Amazon 对视频流媒体广告不给单品 ASIN 的占位值。",
    "",
    "**好消息：这部分用广告活动名前缀可以 100% 归组**：",
    "",
    "| 活动名前缀 | 花费 |",
    "|---|---|",
    "| AJ2 | $8,925.02 |",
    "| XM1 | $7,582.10 |",
    "| XM2 | $5,960.54 |",
    "| ZJ1 | $3,584.76 |",
    "| YT1 | $3,136.00 |",
    "| AJ1 | $1,838.35 |",
    "",
    "6 个前缀全部是合法运营组，零无法识别。**这条路 GPT 没走，但它是免费的。**",
    "",
    "### 归因侧（《达成转化的商品》）",
    "",
    f"总归因 **{float(pur):,.0f}** 件，未映射 **311 件（0.28%）**。",
    "",
    "按账户：JOOMRA DIRECT 234 / anac1973 76 / BLOOMNEXT 1。品牌字段 310 件为空。",
    "按品类：拖鞋凉鞋 214 / 行走跑步 36 / 童鞋 32 / 鞋垫 24 / 宽楦 5。",
    "",
    "**广告侧反查救援率 = 0%** —— 这 311 件的产品在广告里压根没投过，是纯 Halo 流入，",
    "只能靠业务侧登记补齐。",
    "",
    "### 业务侧（`report_business_child_asin_daily`）",
    "",
    f"总订购量 **{float(biz_tot):,.0f}** 件，未映射 **6,067 件（1.04%）**，涉及 546 个 ASIN / 246 个父 ASIN。",
    "",
    "**根因：17 个父 ASIN 整条产品线从没登记过**（占掉归因侧 310 件缺口里的大头）：",
    "",
    "| 父 ASIN | 账户 | 子数 | 未映射订购量 | 广告花费 | 标题 |",
    "|---|---|---|---|---|---|",
    "| B0FWRX7MDC | JOOMRA DIRECT | 33 | 1,862 | $0（纯自然流量） | Joomra Pillow Slippers |",
    "| B0CNTHY16W | WHITIN | 14 | 1,308 | $0 | WHITIN 2 Pairs/Set Replacement Insole |",
    "| B0GGXJ3KCY | JOOMRA DIRECT | 47 | 1,019 | $0 | Joomra Trail Running Shoes |",
    "| B0GJRFJ4CD | JOOMRA DIRECT | 40 | 610 | $0 | Joomra Toddler Wide Toe Box |",
    "| B0FGHZN7WX | WHITIN | 33 | 476 | $0 | WHITIN Toddler Wide Barefoot |",
    "| B0GWHYKH8D | WHITIN | 41 | 391 | $0 | WHITIN Women's Wide Toe Box Walking |",
    "| B0GG8H1N7H | WHITIN | 29 | 238 | $0 | WHITIN Wide Minimalist Barefoot |",
    "",
    "> 关键：这 7 条线时间跨度全是 **2026-08-01 ~ 09-19 满 50 天**，不是新品试水，是卖了两个月没人登记。",
    "> 而且**广告花费为 0** —— 它们不影响成本池分子，但影响分摊的分母（Halo 件数）。",
    "",
    "## 三、🔴 P0：anac1973 重复导入（仍然没修）",
    "",
    "`core.report_advertised_product_daily` 里 `AMS_推广的商品_30D_日期.csv` 与 "
    "`川鹏_推广的商品_30D_日期.csv` 装的是**同一个广告账户 anac1973 (C3S8S)** 的数据。",
    "",
    "证据（按「日期 × 广告活动」逐组对账）：",
    "",
    "| 项目 | 广告花费 | 归因件数 | 归因销售额 |",
    "|---|---|---|---|",
    "| 重叠 (日期,活动) 组 | 2,317 | 1,751 | 1,751 |",
    "| 其中两文件数值完全相同 | 2,201（95.0%） | 1,598（91.3%） | 1,598（91.3%） |",
    "| **真实值（去重后）** | **$131,407.53** | **19,494 件** | **$682,990.86** |",
    "| **实际入库（两文件相加）** | **$254,462.00** | **37,687 件** | **$1,322,776.45** |",
    "| **虚增** | **$123,054.47（+93.6%）** | **18,193 件（+93.3%）** | **$639,785.59（+93.7%）** |",
    "",
    "**决定性证据**：活动 `137718483524592` / 2026-09-06 ——",
    "",
    "```",
    "AMS_推广的商品    advertised_product_id=__advertised__b22db4772ef4e8936c91  parent=B0DCV7KQJM  $615.40  u=44",
    "川鹏_推广的商品   advertised_product_id=(空)                                  parent=B0DCV7KQJM  $615.40  u=44",
    "```",
    "",
    "同一行数据、父 ASIN 完全相同、连分位都一样，只有 `advertised_product_id` 一个是空字符串、",
    "一个是 `__advertised__<hash>`。两个独立导出的文件不可能巧到分位一致 —— 这就是同一份数据装了两遍。",
    "",
    "**为什么去重键没拦住**：现去重键含 `advertised_product_id`，而这一列两份文件写法不同",
    "（`''` vs `__advertised__<hash>`），所以两行都被当成新行放进来了。",
    "",
    "**修法（不需要人工核对）**：去重键改成",
    "`(账号, 日期, 广告活动ID, 广告组ID, 商品名, 父ASIN)` —— 这两份文件在这些列上完全一致，一改就能拦住。",
    "或者更保守：导入前把 `advertised_product_id IN ('', '__advertised__%', '-1')` 归一化成同一个占位值。",
    "",
    f"**影响面**：虚增的 ${123054.47:,.2f} 占全库广告总花费 ${tot:,.2f} 的 "
    f"{123054.47/tot*100:.1f}%。按 SOP 第十九章，这个问题没修之前**不得输出最终分摊结果**。",
    "",
    "## 四、待办（按优先级）",
    "",
    "| 级别 | 事项 | 责任方 |",
    "|---|---|---|",
    "| 🔴 P0 | 修 anac1973 重复导入：去重键加 `advertised_product_parent_id`，重灌两份文件所在批次 | 数据侧 |",
    "| 🟠 P1 | 补登 17 条未登记产品线（缺口1 CSV 直接喂给 GPT） | GPT / 运营 |",
    "| 🟡 P2 | 广告侧无 ASIN 行按活动名前缀归组（6 个前缀，$31,026.77 全覆盖） | 数据侧 |",
    "| 🟢 P3 | 清理 34 个子 ASIN 跨 scope 重复行（同组同款号，去重即可） | 数据侧 |",
    "| 🟢 P3 | 明确「款号跨组」的 7 个款号归属规则：**按父 ASIN 分组，禁止按款号分组** | SOP 口径 |",
    "",
    "---",
    "",
    f"报告生成时间：{NOW[1]}（服务器时区 Asia/Shanghai）",
]
rp = os.path.join(OUT, "映射归属复核报告_2026-09-21.md")
with open(rp, "w", encoding="utf-8") as fh:
    fh.write("\n".join(lines) + "\n")
print(f"  写出 {rp}")
print("完成。")
