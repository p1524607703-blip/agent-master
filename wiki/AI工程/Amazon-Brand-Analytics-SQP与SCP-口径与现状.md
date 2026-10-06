---
tags: [AI工程, 亚马逊广告, 数据库, BrandAnalytics]
date: 2026-09-21
status: 现行
---

# Amazon Brand Analytics — SQP 与 SCP 口径与现状

> [!summary] 摘要
> 亚马逊品牌分析（Brand Analytics）里最容易被混为一谈的两份报告：**SQP（搜索查询绩效 / Search Query Performance）**和
> **SCP（搜索目录绩效 / Search Catalog Performance）**。一句话区分 —— **SQP 按「搜索词」切，SCP 按「ASIN / 目录条目」切**。
> 现状：SQP 已在现行主库 `amazon_ads_v2` 有表有数据有加载器；**SCP 在现行主库没有归宿**（无表、无加载器），
> 旧库退役前最后一次成功入库是 2026-08-29。

## 核心知识

### 1. 一张表看懂区别

| | SQP 搜索查询绩效 | SCP 搜索目录绩效 |
|---|---|---|
| 英文 | Search Query Performance | Search Catalog Performance |
| 切片维度 | **搜索词（query）** | **ASIN / 目录条目** |
| 回答的问题 | 「这个词下，我的品牌占多少曝光/点击/加购/购买的份额？」 | 「我这个 ASIN 在整个类目/购物漏斗里表现如何？」 |
| 对手侧 | 全类目该词的总量 → 可算 **份额（share）** | 同目录条目的对比基准 → 可算 **相对位置** |
| 典型用途 | 词级选品、投放词价值、品牌词蚕食诊断、TIB 优化 | 单品 Listing/价格/配送竞争力诊断、选品基线 |
| 单周行数量级 | 单品牌单周上限 **1000** 行（Amazon 硬限） | 实测 **5290** 行/周（无 1000 硬限） |
| 新库表 | `core.search_query_performance_weekly` / `_monthly` ✅ | **不存在** ❌ |
| 加载器 | `amazon-ads-data/scripts/import_sqp_v2.py --mode weekly` | 无 |

### 2. SCP 到底用来干什么

SCP 是 BA 里**唯一以「商品（ASIN）」为行主键的绩效报告**，把 SQP 的「份额」思路搬到商品维度：

- **漏斗定位**：给一个 ASIN 在「曝光 → 点击 → 加购 → 购买」四层的数值与转化率，判断卡在哪一层。
- **相对类目定位**：因为 BA 的报告口径里同时给出「总量」与「本品牌」两组数，可以算出**该 ASIN 在同类目条目里的相对份额** ——
  这是站内其他报表（广告报表只看投放、业务报告只看自己）给不了的。
- **竞争力归因（价格/配送/库存）**：SCP 的关键价值不在金额，而在它把**展示时的价格、配送速度、可售状态**和漏斗数字放在同一行 ——
  于是「转化差」可以直接落到「是价格带没竞争力 / 配送慢 / 断货」，而不是只能猜。
- **与前台的衔接**：`app.product_roster`（在售产品主数据，149 行）+ `app.child_asin_mapping`（子 ASIN → 运营组）
  正好能接住 SCP 的 ASIN 主键 → **SCP = 唯一能直接和运营组归属主数据对齐的 BA 报告**。

> [!note] 结论（任务「确认 SCP 是用来干什么的」）
> SCP 不是「SQP 的替代」，而是它的**商品维度互补**：SQP 告诉你「哪些词值得抢」，SCP 告诉你「哪些 ASIN 抢不动、卡在哪一层、是不是价格/配送的锅」。

### 3. 现状：SCP 在现行架构里是「悬空」的

- 旧库 `121.41.134.56`（已整机退役）曾有 `core.search_catalog_performance_weekly`：
  **30,177 行，2024-08-31 → 2026-08-29**，每周约 5,290 行 —— 现已随旧库一起不可访问。
- 现行主库 `amazon_ads_v2` 的 `information_schema` 里**没有**任何 `search_catalog_performance_*`。
  参见 [[阿里云RDS-amazon_ads_v2-库表结构]] 的对象总览（只有 sqp 两张，没有 scp）。
- **后果**：任何「BA 覆盖度」「目录绩效」类分析目前**只能做 SQP 的一半**，SCP 侧是空的。
- **要复活需要三步**（尚未执行）：
  1. 写一个「**只 CREATE 不 DROP**」的 migration 建 `core.search_catalog_performance_weekly`
     —— ⚠️ 千万别直接跑 `ba-export/sql/create_tables.sql`，它含 `DROP TABLE ... CASCADE`，会把 sqp 一起删掉。
  2. 加加载器（参照 `import_sqp_v2.py`，加表头别名层；新格式表头是 `曝光：曝光总量` 全角冒号 + 首行元数据）。
  3. 每周下载任务接一条 SCP 分支（下载侧 `ba_sqp_weekly.py` 已能驱动，加报告类型即可）。

### 4. 下载侧现状

| 任务 | 状态 |
|---|---|
| SQP 周更（WHITIN） | ✅ 现行：`ba-export/ba_sqp_weekly.py` + `import_sqp_v2.py --mode weekly`，WHITIN **29 周 / 29,000 行，max 2026-09-26** |
| SCP 周更 | ❌ 无归宿，任务里已不跑（跑了也没表可灌） |
| BRONAX / JOOMRA 的 SQP | ⚠️ 停在 26 周 / 2026-09-05（只跑 WHITIN 是当前约定） |

### 5. 下载管理器（DM）清理的真相 —— 它根本删不掉

> [!warning] 2026-09-27 实测结论：Amazon BA 下载管理器**没有任何删除入口**
> - 该行**永远只有「下载」一个控件**；表头那 8 个 `more_vert` 图标全是**列宽拖拽把手**（`role=separator`），不是菜单。
> - 悬停 / 派发真实 `pointerover`+`mouseover` 事件，**不会**揭示隐藏的删除菜单。
> - 因此 `node.remove()` 只对**当前这份 DOM** 生效；`goto_dm()` 一刷新，行就被服务端数据重新渲染回来。
>   实测：日志写「已移除」→ 37 秒后刷新页面，行**原样还在**。
> - 那些条目由 **Amazon 自行过期回收**（2026-09-21 那轮"清掉"的 23 行，09-27 看已不在，但**不是我们删的**）。

**对自动化的影响：几乎为零**，因为防重复靠的不是 DM 清理，而是两道幂等闸门：
1. 下载侧只按**目标周**匹配（`endDate == week_slash`）→ 陈旧周条目不会被误点；
2. 灌库侧 `import_batches.file_hash` 去重 + `ON CONFLICT (marketplace, brand_name, week_start_date, week_end_date, search_query) DO UPDATE`。

**已做的措辞纠正**：`ba_sqp_weekly.py` 的 `remove_dm_row()` / `prune_dm()` 日志不再宣称"已清理 DM"，
改为「已从当前页面摘掉（客户端，刷新会重现）」，避免后续排障被假信号误导。

## 关联

- [[阿里云RDS-amazon_ads_v2-库表结构]]
- [[阿里云RDS-amazon_ads-库表结构]]
- [[亚马逊TIB与广告报告数据沉淀方案]]
- [[亚马逊广告数据优化-主线工作全景]]

## 来源

- 现场查询 `amazon_ads_v2` 的 `information_schema.tables`（2026-09-21）
- `amazon-ads-data/scripts/import_sqp_v2.py`、`ba-export/ba_sqp_weekly.py`
- DM 无删除入口的结论：2026-09-27 对 `/brand-analytics/download-manager` 的 DOM 实测（列宽把手识别 + 真实 pointer 悬停 + 刷新复现）
- 旧库归档页 [[阿里云RDS-amazon_ads-库表结构]]（SCP 旧表行数与日期区间）
- Amazon Brand Analytics 官方报告定义（SQP / SCP 口径）
