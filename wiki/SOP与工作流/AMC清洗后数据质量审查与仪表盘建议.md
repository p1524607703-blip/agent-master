---
tags: [SOP与工作流, 亚马逊广告, AMC, 数据清洗, 仪表盘]
date: 2026-05-22
status: 现行
---

# AMC清洗后数据质量审查与仪表盘建议

> [!summary] 摘要
> 本页记录飞书多维表格《清洗后的 AMC 数据》的字段规范审查、仪表盘设计策略、2026-05-22 的 V2 重建结果，以及 2026-05-26 补导入的两张路径分析表。当前已完成关键数值字段样式修复、6 张仪表盘辅助表创建、7 张 V2 仪表盘重建；仍需后续处理文本金额、文本日期、ID 类型和部分后台元数据字段的长期规范化。

## 核心知识

### 表结构概览

| 表名 | 记录量 | 适合定位 |
|---|---:|---|
| `00_Dashboard` | 16 | 指标摘要，不建议作为正式仪表盘事实表 |
| `01_Cleaning_Log` | 13 | 清洗过程记录 |
| `02_Campaign_Master` | 10 | 广告活动级核心分析 |
| `03_SearchTerm_Detail` | 20000 | 搜索词/定向明细，适合深度筛选，不适合直接全量上图 |
| `04_SearchTerm_Summary` | 1436 | 搜索词聚合分析，适合仪表盘 |
| `05_Targeting_Summary` | 140 | 定向/广告组聚合分析，适合仪表盘 |
| `06_Frequency_Efficiency` | 49 | 频次效率分析，适合仪表盘 |
| `07_Negative_Candidates` | 16 | 否定词候选清单，适合操作型视图 |
| `08_Data_Quality` | 24 | 数据质量与时间范围校验，适合质量看板 |
| `09_Backend_Campaign_Meta` | 50 | 后台广告活动元数据，需先修字段类型 |
| `10_Portfolio_Meta` | 22 | 广告组合分析，适合仪表盘 |
| `11_Source_Directory` | 16 | 数据源目录 |
| `12_Dashboard_KPI_Summary` | 1 | V2 仪表盘总览指标辅助表 |
| `13_Dashboard_SearchTerm_Attribution_Top` | 84 | 搜索词归因问题 Top N 辅助表 |
| `14_Dashboard_Traffic_Quality_Segments` | 200 | 流量质量分层辅助表 |
| `15_Dashboard_Funnel_Stages` | 3 | 展示、点击、订单漏斗辅助表 |
| `16_Dashboard_Targeting_Frequency_Score` | 35 | Targeting 与频次评分辅助表 |
| `17_Dashboard_Data_Health_Timeline` | 26 | 数据健康检查辅助表 |
| `18_AMC_Targeting_First_Last_Assist` | 291 | Targeting 首触、助攻、末触路径角色分析 |
| `19_Campaign_Path_Wide` | 18 | Campaign 路径宽表，按触点角色看转化事件、订单、销售额和平均路径步数 |

### 需要优先修改的问题

| 优先级 | 问题 | 代表字段 | 建议 |
|---|---|---|---|
| 高 | 比例字段是普通小数，未设为百分比显示 | `ctr`, `cvr`, `acos`, `ntb_order_rate`, `user_purchase_rate`, `CTR`, `ACOS` | 保留底层值为 0-1，小数位 2-4，字段样式设为百分比 |
| 高 | 金额字段未统一货币和千分位 | `spend`, `sales`, `product_sales`, `attrib_sales`, `cpc`, `cpm`, `支出(USD)`, `销量(USD)` | 字段名保留 `(USD)` 或统一英文后缀，数值字段启用千分位，金额保留 2 位小数 |
| 高 | 仍有金额/计数字段是文本 | `09_Backend_Campaign_Meta` 的 `支出(USD)`, `销售额(USD)`, `CPC(USD)`, `订单`；`10_Portfolio_Meta` 的 `预算(USD)`, `广告活动数量` | 清洗出纯数字字段，不建议直接覆盖原字段；先新增规范字段再迁移 |
| 高 | 日期和时间仍是文本 | `start_date`, `event_date`, `min_event_dt_utc`, `max_event_dt_utc`, `广告活动开始日期`, `预算开始日期` | 转为日期/日期时间字段，统一时区说明 |
| 中 | ID 字段被设为数字 | `campaign_id_numeric`, `campaign_id` | ID 不参与计算，应改为文本，避免精度和展示风险 |
| 中 | 份额字段存在 `<5%` 文本 | `top_search_impression_share`, `搜索结果首页首位展示量份额` | 增加规范字段：`share_bucket` 单选 + `share_min`/`share_max` 数字 |
| 中 | 高基数字段被做成单选 | `03_SearchTerm_Detail.campaign`, `ad_group` | 明细表中建议使用文本或关联字段；单选适合低枚举，不适合持续新增广告活动 |
| 中 | 重复/冲突字段 | `状态` 与 `状态__2` | 保留一个标准状态字段，另一个改名为来源状态或删除 |
| 中 | 00_Dashboard 的 `数值` 混合多种单位 | `数值` | 增加 `单位类型`、`展示值`、`指标口径`，否则指标卡容易误读 |

### 建议的字段单位规范

| 字段类型 | 字段示例 | 底层值 | 展示格式 |
|---|---|---|---|
| 金额 | `spend_usd`, `sales_usd`, `product_sales_usd` | 1234.56 | USD，2 位小数，千分位 |
| 单次成本 | `cpc_usd`, `cpm_usd` | 1.23 | USD，2 位小数 |
| 比例 | `ctr`, `cvr`, `acos`, `ntb_order_rate` | 0.1234 | 12.34% |
| 倍数 | `roas` | 3.45 | 2 位小数，不设百分比 |
| 计数 | `clicks`, `impressions`, `orders`, `purchases` | 12345 | 整数，千分位 |
| ID | `campaign_id`, `campaign_id_string_amc` | 字符串 | 文本 |
| 日期 | `start_date`, `event_date` | 日期对象 | `YYYY-MM-DD` |
| 日期时间 | `min_event_dt_utc`, `max_event_dt_utc` | 日期时间对象 | `YYYY-MM-DD HH:mm:ss UTC` |

### 适合做仪表盘的表

| 表 | 推荐程度 | 推荐图表 | 原因 |
|---|---|---|---|
| `02_Campaign_Master` | 高 | 指标卡、柱状图、散点图 | Campaign 级别最适合做管理视角：花费、销售、ROAS、ACOS、CTR、CVR、NTB 贡献 |
| `04_SearchTerm_Summary` | 高 | Top N 柱状图、漏斗/矩阵、否词候选列表 | 已聚合到搜索词级别，比 2 万行明细更适合图表；适合找浪费词和高价值词 |
| `05_Targeting_Summary` | 高 | 柱状图、二维对比表 | 适合比较 targeting、match type、ad group 的投放效率 |
| `06_Frequency_Efficiency` | 高 | 折线图/柱状图 | 记录量小、分桶明确，适合看频次与购买率、ACOS、ROAS 的关系 |
| `10_Portfolio_Meta` | 中高 | 指标卡、柱状图、饼图 | 适合预算和组合层面的管理复盘，但需先修预算字段 |
| `08_Data_Quality` | 中 | 指标卡、表格组件 | 适合做数据健康看板：数据时间范围、行数、缺失与来源状态 |
| `07_Negative_Candidates` | 中 | 表格/清单视图 | 更适合运营动作清单，不适合复杂图表 |
| `03_SearchTerm_Detail` | 低 | 不建议直接仪表盘化 | 2 万行明细会造成图表噪音；应先聚合到 Summary 或建立筛选视图 |
| `09_Backend_Campaign_Meta` | 中 | 暂缓 | 后台字段有文本金额、重复状态、文本日期，先清洗再做图 |
| `00_Dashboard` | 低 | 不建议作为图表源 | 它是摘要表，不是事实明细；更适合作为手工说明或临时总览 |

### 重建前仪表盘问题

#### 2026-05-22 复查：DeepSeek 创建后的仪表盘

当前飞书 Base 中已有 9 个仪表盘：

| 仪表盘 | 组件数 | 判断 |
|---|---:|---|
| `📊 Campaign 效果全景` | 11 | 方向正确，适合作为主仪表盘，但 ACOS、CTR、CVR、NTB 订单占比仍显示小数 |
| `🔍 搜索词优化看板` | 9 | 比原先合理，使用了 `04_SearchTerm_Summary`，但 Top 搜索词图需要限制 Top N |
| `🎯 定向效率分析` | 9 | 方向正确，但 ACOS、CTR、CVR 字段未百分比化 |
| `📈 频次效率看板` | 9 | 方向正确，适合分析频次桶，但购买率和 ACOS 未百分比化 |
| `💰 组合预算看板` | 8 | 适合组合层复盘，但 ACOS、NTB 订单占比仍为小数 |
| `🩺 数据健康监控` | 7 | 可保留，用于检查行数、展示、点击、购买和数据来源 |
| `🚫 否定词决策看板` | 4 | 可作为运营动作清单入口，但需要补候选词明细视图 |
| `👣 用户广告路径分析` | 8 | 名称偏大，目前实际只是 Campaign 层漏斗和 CTR/CVR/CPC，不是真正 AMC 用户路径 |
| `🧠 综合诊断与建议` | 7 | 目前主要是文本说明，适合作为决策页，但需要连接真实指标 |

单位复查结论：字段单位没有完成规范化。全 Base 仍有大量字段存在样式问题：

- 比例字段仍未设置为百分比显示：`ctr`、`cvr`、`acos`、`attrib_acos`、`exact_acos`、`ntb_order_rate_ref`、`user_purchase_rate`、`ACOS`、`CTR`、`NTB 订单数量百分比`。
- 比例字段小数位仍过长，多数为 `precision=9`。
- 金额字段未启用千分位：`spend`、`product_sales`、`sales`、`attrib_sales`、`exact_sales`、`ntb_sales_ref`、`支出(USD)`、`销量(USD)`、`NTB 销售额(USD)`。
- 计数字段未启用千分位：`impressions`、`clicks`、`orders`、`purchases`、`reached_users`、`rows_count`。
- 部分字段仍是文本：`start_date`、`event_date`、`min_event_dt_utc`、`max_event_dt_utc`、`CPC(USD)`、`支出(USD)`、`销售额(USD)`、`预算(USD)`。

因此，仪表盘显示小数点不是仪表盘本身的问题，而是底层字段样式未修，图表继承了这些未格式化字段。

当前已有 `AMC数据仪表盘`，包含 5 个柱状图：

- `各广告活动的ROAS`：数据源 `02_Campaign_Master`，按 `campaign` 分组，平均 `exact_roas`。方向可用，但只有 10 条 Campaign 记录，建议同时加花费和销售额辅助判断。
- `搜索词转化效率`：数据源 `03_SearchTerm_Detail`，按 `cvr` 分组，平均 `roas`。业务解释较弱；建议改为按 `customer_search_term` 或 `decision_flag` 分组。
- `搜索词点击次数统计`：按 `customer_search_term` 汇总 clicks。方向可用，但需要 Top N 限制，否则 2 万行会过载。
- `各广告活动的转化次数`：按 `campaign` 汇总 `exact_purchases`。可用。
- `广告活动花费统计`：按 `campaign` 汇总 `spend`。可用。

### 推荐第一版仪表盘结构

1. 总览指标卡：总花费、总销售额、总订单、ROAS、ACOS、CTR、CVR。
2. Campaign 对比：按 Campaign 展示 spend、sales、ROAS、ACOS、purchases。
3. 搜索词 Top N：按 spend 降序看浪费词；按 sales/ROAS 看高价值词。
4. 否定词候选：直接引用 `07_Negative_Candidates`，按优先级排序。
5. 频次效率：按 `frequency_bucket` 展示 user_purchase_rate、ACOS、ROAS。
6. 数据质量：数据源数量、行数、时间范围、维度缺失记录数。

### 2026-05-22 实施结果：V2 仪表盘重建

本次执行采用“删除旧仪表盘后重建”的方案。执行前已将旧仪表盘配置备份到本地临时目录，并将 `lark-cli` 从 `1.0.32` 更新到 `1.0.38`，同时更新飞书 Skills。

#### 字段样式修复

- 已修复关键分析表中的金额、比例、计数和倍数字段样式。
- `spend`、`sales`、`product_sales`、`attrib_sales`、`cpc`、`cpm` 等字段按 USD 金额显示。
- `ctr`、`cvr`、`acos`、`ntb_*_rate`、`user_purchase_rate` 等字段按百分比显示。
- `impressions`、`clicks`、`orders`、`purchases`、`rows_count` 等字段按整数千分位显示。
- `roas` 保留为普通小数，不设百分比。
- 额外修复 `09_Backend_Campaign_Meta` 中 `展示量`、`点击量`、`点击率`、`ACOS`、`平均预算内活跃时间` 5 个核心数值字段。

#### 新增仪表盘辅助表

| 表名 | 行数 | 用途 |
|---|---:|---|
| `12_Dashboard_KPI_Summary` | 1 | 总览指标卡：花费、销售额、ROAS、ACOS、订单、点击、CTR、CVR |
| `13_Dashboard_SearchTerm_Attribution_Top` | 84 | 搜索词归因问题 Top N：高销售、高花费低转化、低 CTR、低 CVR、NTB 拉新 |
| `14_Dashboard_Traffic_Quality_Segments` | 200 | 流量质量分层：高质量、中性、低质量、样本不足 |
| `15_Dashboard_Funnel_Stages` | 3 | 展示量 → 点击量 → 订单漏斗 |
| `16_Dashboard_Targeting_Frequency_Score` | 35 | 匹配类型、重点 Targeting、频次区间评分 |
| `17_Dashboard_Data_Health_Timeline` | 26 | 数据健康检查项、问题类型、影响行数 |

#### 新建 V2 仪表盘

| 仪表盘 | 组件数 | 图表类型 |
|---|---:|---|
| `01_AMC经营总览_V2` | 9 | 文本、指标卡、组合图、环形图、散点图 |
| `02_Campaign诊断_V2` | 7 | 文本、指标卡、条形图、散点图、组合图、环形图 |
| `03_搜索词归因问题_V2` | 9 | 文本、指标卡、条形图、散点图、环形图、词云 |
| `04_流量质量_V2` | 9 | 文本、指标卡、漏斗图、散点图、条形图、环形图 |
| `05_定向与频次_V2` | 6 | 文本、组合图、条形图、折线图、雷达图、散点图 |
| `06_否定词决策_V2` | 6 | 文本、指标卡、条形图、环形图、组合图 |
| `07_数据健康_V2` | 7 | 文本、指标卡、环形图、条形图、面积图 |

所有 V2 仪表盘的第一块均为文本说明，用于告诉新手先看什么、如何解释图表。旧的 9 个 DeepSeek 仪表盘已删除，避免和 V2 看板混淆。

#### 配套操作视图

- 已在 `07_Negative_Candidates` 创建/更新视图：`否定词候选_按优先级`。
- 视图按 `negative_priority` 升序、`spend` 降序排序，用于人工审核候选否定词。
- 该视图只做分析和审核，不自动修改亚马逊广告后台。

#### 仍需后续处理

- `09_Backend_Campaign_Meta` 中仍有部分金额、订单、日期字段是文本，建议后续新增规范数字/日期字段再迁移，不建议直接覆盖原字段。
- `start_date`、`event_date`、`min_event_dt_utc`、`max_event_dt_utc` 等日期字段仍需统一为日期/日期时间字段。
- `campaign_id_numeric`、`campaign_id` 等 ID 字段仍建议长期改为文本，避免 ID 被当作可计算数值。
- 本次看板只做分析展示和教学，不自动执行预算、竞价、否定词或广告状态修改。

### 2026-05-26 补导入路径分析表

- 已将 Sheet `AMC_Targeting_First_Last_Assist` 导入为 `18_AMC_Targeting_First_Last_Assist`。
- 已将 Sheet `Campaign 路径宽表` 导入为 `19_Campaign_Path_Wide`。
- 导入后 `18_AMC_Targeting_First_Last_Assist` 中 `conversion_events` 和 `orders` 被飞书误识别为单选字段，已按 `单选 -> 文本 -> 数字` 的白名单路径修正为数字字段。
- 这两张表使新版 Base 可以回答“哪个 Targeting 是首触/助攻/末触”“路径步数是否过长”“Campaign 是否只是最后点击强，还是也承担铺路价值”等问题。
- 新人教程已单独规划为 [[AMC新版查询结果表新人入门规划]]。

## 关联

- [[AMC查询用例与自动化对接方案]]
- [[AMC新版查询结果表新人入门规划]]
- [[亚马逊广告营销优化规划方案与学习路径]]
- [[亚马逊广告组合模块教学]]
- [[亚马逊广告活动页操作教程]]

## 来源

- 飞书多维表格：清洗后的 AMC 数据，https://my.feishu.cn/base/SkeGbjBLhasz7Ls9VdXcC4lFnge
- 新导入 Sheet：AMC_Targeting_First_Last_Assist，https://my.feishu.cn/sheets/PBY5sRc4RhINMptWcQrcRebGnnc
- 新导入 Sheet：Campaign 路径宽表，https://my.feishu.cn/sheets/A55ps6KEGhIeBRtsJgpcEnDqn1d
- 只读审查时间：2026-05-22
- V2 仪表盘重建时间：2026-05-22
- 路径分析表补导入时间：2026-05-26
- 本地备份目录：`/tmp/amc_feishu_dashboard_rebuild_2026-05-22T08-47-08-040Z`、`/tmp/amc_feishu_dashboard_v2_2026-05-22T09-03-33-070Z`
