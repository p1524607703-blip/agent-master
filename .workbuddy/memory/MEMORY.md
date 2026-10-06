# 项目长期记忆 · Amazon 多店铺数据中台（索引）

> 用户 = Amazon 多店铺卖家（川鹏2号/欧德思/洁博利/美国AMS）。🔴 **红线：AI 只读+下载，绝不改广告投放设置**。
> 本文件**只是索引**。细节全在 `PLAYBOOK-运营手册.md`：§A 库｜§B 表核验｜§C 控制台｜§D 管线｜§E 业务报告｜§F 变更历史｜§G FBA重测｜§H DSP｜§I 六张事实表｜§J 主数据｜§K 业务报告入库｜§L 父子ASIN｜§M 角色/CPO｜§N 分摊口径(.7/.7.1/.7.2/.7.3)｜§O 映射体检｜**§P 环境/时区/凭证/实体矩阵/紫鸟坐标**｜**§Q DSP建单页崩溃**｜**§R 健康度快照**。过程见 `memory/YYYY-MM-DD.md`。

## 0 仓库与库
- 仓库：数据/导入器 `~/Documents/amazon-ads-data`；控制台 `agent-master/amazon-ads-console`。密码走 keychain。
- 唯一在跑库 = **腾讯云自建 PG18.6**（2026-09-30 迁入），只监听服务器本地 → 本机走常驻 SSH 隧道 `127.0.0.1:15432`、`sslmode=disable`。密码走 keychain（`ads_ingest`/`ads_readonly`/`amazon_ads_admin`）。旧阿里云 RDS **已停写**、`121.41.134.56` **已整机退役**。
- 架构 = **分库**：`amazon_ads`（iam/app.*）+ `amazon_ads_v2`（core.*）→ 跨库不能 JOIN，覆盖计算在 Python 做。
- 账户：川鹏2号=WHITIN｜欧德思=BLOOMNEXT｜洁博利=JOOMRA DIRECT｜美国AMS=anac1973。

## 1 🔴 四条铁律
1. **归因禁用 `purchased_product_parent_id` 直筛**（anac1973 该列 **50.3% 为空**）→ 必须 `purchased_product_id IN (该父全部子ASIN)`。广告侧 `advertised_product_parent_id` 可用。
2. **唯一"能算"的映射表 = `app.child_asin_mapping`**（7270 行、零空值、覆盖 99.7%；12 个 3 位细码）。`product_roster` **不能定组**（2 位粗码）。判定链 = 子ASIN ──唯一──▶ 父ASIN ──唯一──▶ 运营组；**款号不进分组键**。
3. 🔴 **P0 未修**：anac1973 事实表重复导入（`川鹏_*` vs `AMS_*` 同账户两份）→ 虚增 **$123,054.47**（全库花费 **14.3%**）→ **按 SOP §19 当前不得输出最终分摊结果**。见 §O.2。
   - 🔴 **2026-10-06 订正措辞**：`~/Desktop/报销单/川鹏广告活动报告/川鹏_*.csv` **不是川鹏账户的数据**——文件头实测 `广告主账户 ID=amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz / 名称=anac1973 (C3S8S)`，与 `data/raw/account_30d/2026-09-15/AMS/AMS_*` 是同数据两副本。所以标 anac1973 **没错**；病根是「同一批事实存在两份」（老表 `core.ad_daily` 批次 #51–55 + 新表 `core.report_*_daily`）。⇒ 修法是**去重/停用老表消费方**，⛔ **绝不能把这些文件改名成 WHITIN 再灌**（等于把 AMS 花费灌进 WHITIN）。
4. CPO 报告（`每日CPO单双计算`）**已报废**：内容**等同于「推广的商品」**、7 天窗口、不进事实层；2026-09-23 移出自动化，**2026-10-05 用户已在控制台关闭订阅**。→ 4 店 **24 份**（**各 6 类 30D，2026-10-05 起川鹏补齐搜索词**）。**别再加回来、别按规律推断某店"应该有 CPO"**。

## 2 导出管线（→ §D–G）
| 管线 | 脚本 | 删本地? | 定时(本地) |
|---|---|---|---|
| 广告订阅 4店24份 | skill `ziniao-ad-report-download` → `ad-reports-export/ziniao_30d_to_report_daily.py` | ❌ | 每日 22:30 |
| BA 周报 sqp | `ba-export/ba_sqp_weekly.py` | ✅ | 周日 22:30 |
| FBA 退货 | `fba-returns/` | ❌ | 每日 21:00 |
| 广告变更历史 | `ad-change-history/` | ❌ | skill |
| 业务报告按父商品 | `business-report/` | ❌ | 日榜 21:30 / 周榜周二 |

- ✅ 现行广告链路 = 紫鸟下载 → `ziniao_30d_to_report_daily.py` → `import_account_30d_reports.py` → `core.report_*_daily`（**4 账户，含川鹏/WHITIN**）。`subscribed_reports_to_rds.py` 已废弃；邮件渠道被 macOS TCC **-10004** 拦死。
- ✅ **WHITIN 广告事实断档已修并上线（2026-10-06）**：`STORE_TO_ACCOUNT` 已加 `"川鹏2号":"川鹏"`（提交 `cd6b97a`），控制台 `AD_ACCOUNTS` 已含 WHITIN，服务器 `release.json commit=cd6b97a` + 服务 active。回灌批次 #578–583（09-06..10-05 六表）+ #454/#456（08-01..08-31）。实测 2026-09-20 WHITIN spend $26,799.21、`LB1/LW1/ZF1/XH1-*` 前缀全部归 WHITIN。
  - ✅ **残留 5 天洞已于 2026-10-06 回检补平**：`campaign` 补 2,940 行、`purchased_product` 补 19,976 行 → **CPO 可算天数 45 → 50（2026-08-16..2026-10-04）**。
    ⭐ **机制（用户点破，务必记住）：控制台「报告历史记录」页（点报告名进 `reporting/history?reportId=…`）会【按天留存】每一份生成过的报告**，报告期标「最近 30 天」，**30D 副本窗口 = `[D-30, D-1]`**。
    ⇒ 缺口 `[lo,hi]` 只要满足 `D ∈ [hi+1, lo+30]` 就能用一份副本盖住，取 `D = min(lo+30, 今天)`。页面上还能看到 `Custom (08/01/2026 - 08/31/2026)` 这类自定义区间副本。
    ⭐ 工具三件套：`check_ad_gap.py`（缺口探测，以「业务报告出现过的日期」为应有集）→ `fetch_history_copy.js`（抓 D 日副本）→ `backfill_gap.py`（按日期切片灌库，只灌缺口、不覆盖已更新日）。**已固化进自动化步骤 3。**
  - 🔴 两条红线：① **绝不点「创建报告/编辑订阅/取消订阅」**，只点报告名与该行「下载」；② **绝不拿别的账户的文件改名冒充**（典型诱饵 `~/Desktop/报销单/川鹏广告活动报告/川鹏_*.csv` 实为 anac1973 数据）。
  - ⭐ 两条认知纠偏：**「我那天跑过了怎么会缺？」** → 那轮只覆盖它自己的 30 天窗口，那一段从没被任何一轮覆盖就是真空洞；**「上午回灌了怎么还没数据？」** → 回灌只能灌「文件里有的行」，判「灌没灌成功」用**库内行数 vs 源文件行数 1:1 比对**，不要用「有没有数据」。
  - ⭐ 那 5 天**花费来源（`advertised_product`）4 家齐**，只缺 `达成转化的商品`——而它在 CPO 里**只做归因校验**、不参与花费/单量。⇒ 最小修复＝**让 GPT 放宽 `_complete_days()` 的 `p` 门槛**（标「校验不可用」），别伪造数据。
  - ⚠️ 副作用：月度选 2026-09 会**静默按 25/30 天**聚合；API 有回 `coverageDays/expectedDays/final_cpo=False`，UI 需显示。
  - ⭐ 与 anac1973 在新表**存在非零交集是正常的**（`advertised_product` 79 行 / `purchased_product` 12,611 行共享 id）：AMS 这个广告账户本来就在投 WHITIN 品牌产品（转化商品名实测 `WHITIN Toddler Shoes ...`）；`campaign_name` 层交集仍为 0。

- 🔑 **30D = 滚动 30 天窗口 → 补缺口跑一次即补齐**，不用逐日回灌。
- ⚠️ 订阅名是「人随时能改的标签」→ 比对须归一化（抹空白 + 抹结尾 `Copy` + 唯一后缀命中）。同名重复订阅按「上次修改时间」择优（**正常的自动裁决**）。
- 🔴 **别按命名规律推断订阅存在；也别凭一次 `MISSING` 就断定"没有"**——ag-grid 虚拟滚动只渲染 ~11 行，`probe_report_links/rows.py`、`discover_reports.js` 会同时少报且互相印证。**判定一律用 `probe_pick.js`**（复用下载脚本同一套 `__pick`，只读）。2026-10-05 就靠它翻案：川鹏**有**「搜索词 30D 日期」，此前被误记为"无订阅"而从 config 删了。
- 🔴 **「早跑污染」会造出假绿灯**：同一美东日已有一轮运行（mtime <2h）时，20h 跳过规则会让正式轮全跳过，verify 拿旧文件验旧文件报"0 个有问题"。开工先看 `.freshness_state.json` 的 `checkedAt`，命中就做 overwrite 抽样探针。
- 🔴 **表头漂移 = 整文件拒收**（`import_one()` 首行 fail-fast，不是逐行跳过）。
- ⭐ `min(stat_date)` = **残留探测器**（六表只 upsert、无 TRUNCATE）。
- ☠️ `create_tables.sql` 含 `DROP TABLE … CASCADE` → 原样跑会连 sqp 一起删。
- FBA 退货：外发件 Title 脱敏（`FBA_KEEP_TITLE=1` 可关）；日报最新 1~2 退款日是临时值。

## 3 其他热点（细节全在 PLAYBOOK，别在此展开）
- **控制台** → §C/§M：⚠️ venv 是 **Python 3.9**（禁 `str | None`）；🔴 前端 `client.ts` 全 `catch→fallback` **静默吞错 → 排查看后端日志，别信 UI**。
- **时区** → §P.1：本机 America/New_York；rrule `BYHOUR` 按**本地**解释、无 TZID；DST 切换 2026-11-01 / 2027-03-14。
- **紫鸟 / Bridge** → §P.5：Bridge `127.0.0.1:9480/9481`。**前置三件套（进程/端口/登录态）任一不满足 → 直接报失败，不要反复重试**。自检 `ziniao-cli doctor` + `zclaw extract_data running` 应见 4 店。
- **DSP** → §H/§Q：⚠️ **RDS 完全不含 DSP** → 任何"DSP 占比 0%"都是假的；待办 P0 建 `core.dsp_campaign_daily`。建单页崩溃**至今未定因，动手前先读 §Q**（6 条假说已翻车）。
- **环境坑** → §P.2：`stat_date` 不是 `report_date`；BSD grep 不支持 `\|`；一条 SQL 报错整事务 abort（批量体检须新建连接）；`import_batches` 主键是 `batch_id` 且列可 NULL → 先 `str()` 兜底。
- **主数据** → §J：149 行、⚠️ **无 ASIN 列**（藏在「前台链接」`/dp/<ASIN>`，是**子 ASIN**）、唯一键 `(brand,款号)`。
