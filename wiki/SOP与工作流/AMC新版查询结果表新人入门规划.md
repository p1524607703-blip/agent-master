---
tags: [SOP与工作流, 亚马逊广告, AMC, 数据分析, 新人培训]
date: 2026-05-26
status: 现行
---

# AMC新版查询结果表新人入门规划

> [!summary] 摘要
> 本页面向新人重规划 AMC 查询结果表学习路径，并已同步创建新版飞书 Docx《AMC 新版查询结果表新人入门：从仪表盘到广告动作》。旧版《AMC 新手入门》围绕 22 张旧表讲解，已不适配新版飞书 Base《清洗后的 AMC 数据》。新版教程从表分层、核心字段、表间关联、仪表盘阅读、新人练习和 AI 分析路径展开，让新人先能看懂结果，再逐步理解 AMC 相对普通广告后台的价值。

## 核心知识

### 2026-05-26 当前状态

- 新版查询结果 Base：`清洗后的AMC数据`，链接为 <https://my.feishu.cn/base/SkeGbjBLhasz7Ls9VdXcC4lFnge>。
- 新版新人入门飞书 Docx 已创建：`AMC 新版查询结果表新人入门：从仪表盘到广告动作`，链接为 <https://my.feishu.cn/docx/F08Cd129aoe25BxnSRWci326nyh>。
- 旧版教程文档仍可保留“AMC vs 广告后台”的概念部分，但其中“22 张表中英文对照”和“优先看 04/05”的导航已经过时。
- 已将两张未导入的 Sheet 挂载到新版 Base：
  - `18_AMC_Targeting_First_Last_Assist`：来源 `AMC_Targeting_First_Last_Assist`，用于按 Campaign、Targeting、Touch Role 看首触、助攻、末触贡献。
  - `19_Campaign_Path_Wide`：来源 `Campaign 路径宽表`，用于按 Campaign、Touch Role 看路径贡献宽表。
- 导入后已修正 `18_AMC_Targeting_First_Last_Assist` 的 `conversion_events`、`orders` 两列，从误识别的单选字段转换为数字字段。

### 新人学习路径

1. 先理解普通广告后台指标。
   - 必须先会解释 `spend`、`impressions`、`clicks`、`CTR`、`CPC`、`CVR`、`orders/purchases`、`sales`、`ACOS`、`ROAS`。
   - 这一层解决“广告活动到底赚不赚钱、流量有没有点击、点击有没有转化”。

2. 再理解 AMC 比后台多出来的东西。
   - `ntb_orders`、`ntb_sales`、`ntb_order_rate`：判断广告是否带来新客。
   - `reached_users`、`frequency_bucket`、`impressions_per_reached_user`：判断触达频次是否过高或过低。
   - `touch_role`、`avg_path_steps`：判断一个 Campaign 或 Targeting 是首触、助攻还是末触。
   - `conversion_events`：按路径角色统计的转化事件数，不等同于后台最后点击口径。

3. 第三步看新版 Base 的表分层。
   - 目录与质量层：`01_Cleaning_Log`、`08_Data_Quality`、`11_Source_Directory`。
   - 核心分析层：`02_Campaign_Master`、`04_SearchTerm_Summary`、`05_Targeting_Summary`、`06_Frequency_Efficiency`、`18_AMC_Targeting_First_Last_Assist`、`19_Campaign_Path_Wide`。
   - 操作清单层：`07_Negative_Candidates`。
   - 后台补充层：`09_Backend_Campaign_Meta`、`10_Portfolio_Meta`。
   - 仪表盘辅助层：`12` 到 `17` 开头的 Dashboard 表。
   - 明细钻取层：`03_SearchTerm_Detail`，只在需要追溯具体搜索词明细时使用，不建议让新人一上来直接看全量明细。

4. 第四步学习表间关联。
   - Campaign 级关联：用 `campaign` 或 `campaign_id_string` 串起 `02_Campaign_Master`、`18_AMC_Targeting_First_Last_Assist`、`19_Campaign_Path_Wide` 和 `09_Backend_Campaign_Meta`。
   - 搜索词关联：用 `customer_search_term + campaign/ad_group/match_type` 串起 `04_SearchTerm_Summary`、`07_Negative_Candidates` 和 `03_SearchTerm_Detail`。
   - Targeting 关联：用 `campaign_id_string + targeting + match_type` 串起 `05_Targeting_Summary` 和 `18_AMC_Targeting_First_Last_Assist`。
   - 频次关联：用 `campaign + frequency_bucket` 解释 `06_Frequency_Efficiency`，判断是否存在曝光疲劳。
   - 后台元数据关联：用 `campaign`、`portfolio` 回看预算、状态、竞价方式，避免只看 AMC 结果却忽略后台是否可操作。

### 可以从表间关系推算出的内容

| 问题 | 推荐表 | 推算方法 |
|---|---|---|
| 哪些 Campaign 值得加预算 | `02_Campaign_Master` + `09_Backend_Campaign_Meta` | 看 ROAS/ACOS/销售额/订单，再结合预算、状态、竞价策略判断是否可放量 |
| 哪些搜索词该否定 | `04_SearchTerm_Summary` + `07_Negative_Candidates` | 高花费、低订单、低 CVR 或高 ACOS 的词进入人工审核清单 |
| 哪些词适合扩展手动广告 | `04_SearchTerm_Summary` | 高订单、高 ROAS、健康 ACOS 且非品牌误伤词，可作为手动精准或词组候选 |
| 哪些 Campaign 是拉新型 | `02_Campaign_Master` | 看 `ntb_order_rate_ref`、`ntb_sales_rate_ref` 与销售额、ROAS 是否同时成立 |
| 哪些 Targeting 是助攻型 | `05_Targeting_Summary` + `18_AMC_Targeting_First_Last_Assist` | `assist_touch` 高但 `last_touch` 不高时，不应只按最后点击否定 |
| 路径是否过长 | `18_AMC_Targeting_First_Last_Assist` + `19_Campaign_Path_Wide` | `avg_path_steps` 越高，说明转化前触点越多，要区分铺路价值和浪费触达 |
| 是否曝光过频 | `06_Frequency_Efficiency` | 频次上升但购买率、ROAS 不升，或 ACOS 变差，说明可能触达疲劳 |
| 数据是否可信 | `08_Data_Quality` + `11_Source_Directory` | 看来源文件、行数、时间范围、缺失字段和异常记录 |

### 仪表盘该怎么看

- `01_AMC经营总览_V2`：先看整体健康度，只回答“这批数据总体是否值得继续分析”。
- `02_Campaign诊断_V2`：用于定位优先优化的 Campaign。
- `03_搜索词归因问题_V2`：用于找浪费词、高价值词、低 CTR/CVR 词和 NTB 贡献词。
- `04_流量质量_V2`：用于理解展示、点击、订单之间的漏斗断点。
- `05_定向与频次_V2`：用于看 Targeting 和频次效率，配合新导入的路径表更有价值。
- `06_否定词决策_V2`：适合作为运营动作入口，但必须人工审核后再去广告后台操作。
- `07_数据健康_V2`：每次导入新数据后先看，确认数据是否完整、字段是否异常。

仪表盘仍有存在必要，但定位应从“事实源”改为“新人导航层”和“周报展示层”。真正的分析、复核和 AI 诊断仍应回到表字段本身，尤其是 `02`、`04`、`05`、`06`、`18`、`19`。

### 纯 AI 分析路径是否可行

纯 AI 分析可行，但只能作为“分析与建议生成”，不能自动替代投手执行广告动作。推荐路径如下：

1. AI 读取 Base 表清单和字段类型，先做字段健康检查。
2. AI 按固定分析模板读取核心表：Campaign、搜索词、Targeting、频次、路径角色、否词候选。
3. AI 输出分层建议：保留、加预算、降价、否定、暂停观察、补数据。
4. AI 给每条建议附上证据字段：花费、销售额、订单、ACOS、ROAS、NTB、touch_role、avg_path_steps。
5. 人工审核后，才进入广告后台执行。
6. 执行结果回填，下一周期复盘建议是否有效。

关键限制：

- 数据类型错误会直接影响 AI 判断，所以导入后必须先做字段校验。
- AI 不应只看仪表盘截图，必须读取 Base 结构化字段。
- 所有预算、竞价、否词、暂停、启用动作都必须人工确认。
- 若要做 API 自动执行，需要另建审批和日志链路，不能和当前只读分析流程混在一起。

### 新版飞书教程建议结构

1. 保留旧文档第一到四章：AMC 与后台报表的区别、路径分析、归因、新客价值。
2. 删除旧版“22 张表中英文对照”，改为“新版 Base 20 张表分层地图”。
3. 新增“核心字段卡片”：普通广告字段、AMC 独有字段、路径字段、数据质量字段。
4. 新增“从 5 个业务问题开始看表”：Campaign 优先级、搜索词否定、Targeting 助攻、频次疲劳、数据可信度。
5. 新增“表间关联练习”：给新人 3 个固定问题，让他按表关联找到答案。
6. 新增“仪表盘阅读顺序”：先总览，再 Campaign，再搜索词，再 Targeting/频次，最后数据健康。
7. 新增“AI 分析 SOP”：AI 读表、生成建议、人工审核、回填结果。

### 已落地的新飞书 Docx 结构

- 文档标题：`AMC 新版查询结果表新人入门：从仪表盘到广告动作`。
- 飞书链接：<https://my.feishu.cn/docx/F08Cd129aoe25BxnSRWci326nyh>。
- 正文已包含 8 个核心章节：开篇、AMC 与广告后台差异、核心字段、新版 Base 20 张表分层、7 个业务问题、7 张 V2 仪表盘阅读顺序、新人练习题、AI 分析使用边界。
- 已为 7 张 V2 仪表盘预留截图占位与 4 个标注点，后续补图时直接替换占位块。
- 已加入 4 道新人练习题，每题包含操作路径、应看字段和合格答案示例。
- 已保留旧版文档为来源，不覆盖旧版《AMC 新手入门》。

## 关联

- [[AMC清洗后数据质量审查与仪表盘建议]]
- [[AMC查询用例与自动化对接方案]]
- [[亚马逊广告营销优化规划方案与学习路径]]
- [[亚马逊广告活动页操作教程]]

## 来源

- 新版飞书 Docx：AMC 新版查询结果表新人入门：从仪表盘到广告动作，https://my.feishu.cn/docx/F08Cd129aoe25BxnSRWci326nyh
- 旧版飞书文档：AMC 新手入门，https://my.feishu.cn/docx/LS0xdPD0uoSKBexFAeJc1OidnDg
- 新版飞书 Base：清洗后的 AMC 数据，https://my.feishu.cn/base/SkeGbjBLhasz7Ls9VdXcC4lFnge
- 新导入 Sheet：AMC_Targeting_First_Last_Assist，https://my.feishu.cn/sheets/PBY5sRc4RhINMptWcQrcRebGnnc
- 新导入 Sheet：Campaign 路径宽表，https://my.feishu.cn/sheets/A55ps6KEGhIeBRtsJgpcEnDqn1d
