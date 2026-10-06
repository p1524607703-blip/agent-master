---
tags: [SOP与工作流, 亚马逊广告, AMC, 受众包, 产品方案]
date: 2026-06-05
status: 现行
---

# AMC受众细分与Hermes网页方案

> [!summary] 摘要
> 本页基于知乎文章《【史诗级更新】—亚马逊AMC功能&策略详解》中 ai.xmars.com 相关截图和作者对 AMC 广告的理解，提炼适合迁移到 AMC Hermes Dashboard 的网页功能方案。核心结论是：Hermes 不应只展示 AMC 报表，而要把“路径洞察、受众包创建、SP/SB/SD 激活、对照实验、复盘复用”做成一个运营闭环。

## 核心知识

### 文章截图里的 Xmars 产品信号

| 截图/画面 | 画面信息 | 对 Hermes 的启发 |
|---|---|---|
| AMC 报告模板库 | Xmars 将复杂 AMC 查询包装为可点选的报告模板，例如触点、路径、受众、关键词、地域等分析入口。 | Hermes 首页应提供“模板库/场景库”，让运营先选问题，而不是先写 SQL。 |
| 转化路径分析 | 用 DSP、SP、SD 及组合路径展示路径人数、销售额、购买人数、转化率、Total ROAS。作者用“SP 单独转化率 55.32% vs DSP 后接 SP 62.83%”说明上层触点助攻价值。 | `广告触点路径分析` 需要从图形路径升级为可排序路径表，突出“助攻提升、单触点基线、组合路径差异”。 |
| 已浏览但未下单人群 | 通过 AMC 创建“浏览过某 ASIN 但未购买”的人群，排除已购用户。 | `ASIN受众机会` 需要内置购买排除逻辑、ASIN 粒度和回溯窗口，而不是只列受众包名称。 |
| SD Custom audiences | 创建后的 AMC 自定义人群会出现在 SD 广告人群选择里。 | Hermes 的受众卡片应显示可激活渠道：SD、DSP、SP/SB bid boosting。 |
| SP 人群溢价 | SP 广告位置溢价区域出现自定义人群溢价选项。 | 新增“SP/SB Audience Bid Boosting 建议”模块，输出基础 bid、人群溢价、对照组配置。 |
| 核心词需求切分 | 同一个大词下有不同细分需求，例如 Bluetooth headphone 包含 TWS、运动耳机等不同意图。 | 搜索词页应把“关键词”与“人群意图”交叉，形成关键词 x 受众的投放矩阵。 |
| 通用人群模板 | Xmars 提供常用模板，也允许 DIY。 | Hermes 应做模板注册表：PDP 浏览未购买、PDP >= 2 未购买、SB 点击 + PDP、视频完播未购买、加购未转化等。 |
| 加购未转化 | 将加购行为和未购买排除结合，作为高意向再营销人群。 | 作为高优先级模板，但必须先验证加购字段可用性和人群规模。 |

### 作者对 AMC 广告的核心理解

- AMC 的价值不是“给卖家更多后台字段”，而是把亚马逊沉淀的用户行为数据转成运营可理解、可行动的洞察。
- CPC 变贵的根因是竞争变激烈，尤其大词里混杂了很多不同需求，粗放投放会被非对标产品抬高流量成本。
- 解决路径不是单纯压低 CPC，而是用 AMC 人群把流量池切细：在大词、大 ASIN 或大广告类型里找到更匹配的人。
- DSP、SB、SD 等上层触点不能只看直接 ROAS，应通过转化路径判断它们是否提升了后续 SP 或购买转化。
- AMC 自定义人群比普通 SD 浏览人群更细，因为可以排除已购买用户，也可以按自有 ASIN、行为频次、回溯周期做组合。
- SP/SB 接入人群溢价后，可以尝试“低基础 bid + 高人群溢价”：只对更像目标用户的人提高竞争力。
- 所有人群都必须配对照组。没有对照组时，不能判断受众包是否带来增量，容易把自然转化或品牌老客误认为广告效果。
- 受众规模是硬约束：大流量词适合切小人群，小流量词适合更宽的人群；太小的人群跑不出统计意义。
- 不能用竞品 ASIN 的用户行为直接建人群，数据边界应限制在广告主自身可用信号内。

### 可以直接迁移到 Hermes 网页的模块

1. **AMC 场景模板库**
   - 入口位置：`工作台概览` 顶部或独立“模板库”页。
   - 卡片字段：模板名、解决问题、数据源、必填参数、输出指标、可激活渠道、风险提示。
   - 首批模板：转化路径分析、PDP 浏览未购买、PDP >= 2 未购买、SB 点击 + PDP 未购买、视频 50/75/100% 观看未购买、加购未转化、已购买排除、频次疲劳排除。

2. **路径分析对比表**
   - 入口位置：`广告触点路径分析`。
   - 增加字段：路径人数、购买人数、CVR、销售额、ROAS、平均触点、相对单触点提升、建议动作。
   - 关键交互：点击某条路径后，自动生成可测试受众候选，例如“DSP 曝光后 SP 点击未购买”。

3. **受众创建向导**
   - 入口位置：`ASIN受众机会` 的“生成受众包”按钮。
   - 步骤：选择模板 -> 填 ASIN/活动/时间窗 -> 选择购买排除 -> Measurement 估算规模 -> 生成 Audience SQL -> 人工确认后创建。
   - 状态：`READY_FOR_AUDIENCE`、`TOO_SMALL`、`TOO_BROAD`、`NEED_MORE_ASINS`、`NEED_FIELD_VALIDATION`、`NOT_RECOMMENDED`。

4. **SP/SB 人群溢价建议**
   - 入口位置：`ASIN受众机会` 和 `搜索词优化` 交叉。
   - 推荐字段：目标关键词/ASIN、基础 bid、建议人群溢价、预估可触达人数、对照组、预算上限、观察周期。
   - 运营表达：不要只说“创建人群”，要输出“在哪个 campaign/ad group 上测试、出价怎么设、多久复盘”。

5. **关键词 x 受众矩阵**
   - 入口位置：`搜索词优化`。
   - 行：高流量核心词或 ASIN 定向。
   - 列：高意向人群、浏览未购、加购未购、视频观看、老客排除、疲劳排除。
   - 单元格：推荐动作，包括扩量、降 bid、加人群溢价、排除或暂不测试。

6. **实验与复盘台**
   - 入口位置：`工作台概览` 或新建“实验中心”。
   - 组件：实验假设、测试组、对照组、起止日期、样本规模、主指标、停止条件、结论、是否沉淀为模板。
   - 主指标：CVR、CPA/ACOS、ROAS、增量销售额、受众重叠率、样本置信度。

### 与现有 Hermes 页面对应关系

| 现有页面 | 当前状态 | 建议改造 |
|---|---|---|
| `工作台概览` | 已有路径矩阵、广告诊断、搜索词行动队列和 Hermes 洞察。 | 增加“本周可测试受众包”和“正在运行的 AMC 实验”两块，让首页从看板变成决策队列。 |
| `广告触点路径分析` | 已有路径图、路径解读和路径明细。 | 增加 Xmars 风格路径表，支持按 CVR/ROAS/销售额排序，并把路径一键转成受众假设。 |
| `ASIN受众机会` | 已有 TOP ASIN、受众机会列表和创建按钮。 | 补上模板库、购买排除、Measurement 可行性估算、渠道激活建议和对照组。 |
| `搜索词优化` | 适合承接关键词/ASIN 决策。 | 加入“核心词需求切分”和“关键词 x 受众矩阵”，支持低 bid + 高人群溢价方案。 |
| `SQL Workshop` | 适合写和调 AMC SQL。 | 连接模板参数、字段字典、Measurement SQL、Audience SQL，避免运营手写 SQL。 |

### 第一版落地优先级

| 优先级 | 功能 | 原因 | MVP 判断 |
|---|---|---|---|
| P0 | 受众模板库 + Measurement 可行性状态 | 已有 docs 中的候选包和状态体系，可最快形成产品感。 | 能看到模板、填参数、输出规模和状态。 |
| P0 | 已购排除与受众规模卡片 | 是文章中最明确区别于普通 SD 浏览人群的价值。 | 每个受众候选显示 buyers、non_buyers、建议窗口。 |
| P1 | 路径表升级 | 能解释 DSP/SB/SD 助攻，不再只看直接 ROAS。 | 能比较单触点和组合路径，并生成行动建议。 |
| P1 | SP/SB bid boosting 建议 | 这是 2024-10-15 官方更新和文章最大兴奋点。 | 输出基础 bid、人群溢价、对照组配置。 |
| P2 | 实验中心 | 避免所有建议停留在“预计表现不错”。 | 能记录测试组/对照组/结论，沉淀模板。 |
| P2 | 关键词 x 受众矩阵 | 能把“核心词需求切分”做成运营工具。 | 搜索词页出现可测试矩阵和动作标签。 |

### 风险与边界

> [!warning] 不要自动执行广告动作
> Hermes 可以生成受众、出价和实验建议，但创建 audience、改 bid、改预算、改 campaign 状态都应人工确认。当前阶段优先做分析和建议，不做自动投放执行。

- 必须区分 Measurement 与 Audience：Measurement 先输出聚合规模和可行性，Audience SQL 才输出 `user_id` 用于创建受众。
- 受众包不能只追求高意向；如果池子太小，应先扩 ASIN 池、延长窗口或放宽条件。
- 不要把疲劳/排除类人群当高价再营销包，它们更适合作为降 bid、排除或素材刷新信号。
- 官方强调 AMC 输出需匿名和汇总，产品 UI 不应展示原始用户级数据。
- 文章中的转化率案例来自单个卖家数据，适合作为思路，不应直接当作所有类目的基准。

### 建议的下一步交付

1. 在 `amc-hermes-dashboard` 新增产品文档：`docs/audience-segmentation-product-plan.md`。
2. 让 OpenCode/DeepSeek 改前端：先做 `ASIN受众机会` 的模板库和可行性状态，不直接接 API。
3. Codex 复核：检查页面是否符合“运营决策系统”定位，重点看字段口径、风险提示和对照组是否完整。
4. 再把 `amc-hermes-skills` 中受众模板注册表接入前端，形成模板 -> SQL -> 估算 -> 建议动作的闭环。

## 关联

- [[AMC查询用例与自动化对接方案]]
- [[AMC清洗后数据质量审查与仪表盘建议]]
- [[AMC新版查询结果表新人入门规划]]
- [[亚马逊广告营销优化规划方案与学习路径]]

## 来源

- 飞书同步文档：AMC受众细分与Hermes网页方案，https://my.feishu.cn/docx/UvSwdTwenokqV0xjGCtcPpLMnBc
- 知乎文章：【史诗级更新】—亚马逊AMC功能&策略详解，https://zhuanlan.zhihu.com/p/11226805150
- Amazon Ads 官方页面：Amazon Marketing Cloud，https://advertising.amazon.com/solutions/products/amazon-marketing-cloud
- Amazon Ads 官方公告：Audience bid boosting，https://advertising.amazon.com/resources/whats-new/unboxed-audience-bid-boosting
- 本地项目：`/Users/panjinlong/Documents/amc-hermes-dashboard`
- 本地项目文档：`/Users/panjinlong/Documents/amc-hermes-dashboard/docs/amc-measurement-audience-feasibility-master-table.md`
- 本地项目页面：`/Users/panjinlong/Documents/amc-hermes-dashboard/apps/web/src/views/AsinAudiencePage.vue`
- 本地项目页面：`/Users/panjinlong/Documents/amc-hermes-dashboard/apps/web/src/views/HaloPathPage.vue`
