# Alexa 商品推荐诊断插件开发者文档

> 对应应用版本：`0.1.0`
>
> 本地事实源：`docs/DEVELOPMENT.md`；固定飞书文档由 `npm run docs:sync:feishu` 覆盖同步。

本文面向维护 `alexa-recommendation-auditor` 的开发者，描述当前代码已经实现的架构、数据边界、运行状态、Hermes 模型链路、评分规则和发布方法。本文不把 Alexa 的回答解释为 Amazon 内部算法，也不把尚未实现的能力写成现状。

## 1. 当前版本基线

| 版本面 | 当前值 | 定义位置 |
| --- | --- | --- |
| 应用版本 | 见文档顶部 | 根目录 `VERSION` 及各 workspace 的 `package.json` |
| Chrome 扩展版本 | 跟随应用版本 | `extension/manifest.json` |
| 健康检查版本 | 跟随应用版本 | `server/src/auth/auth.controller.ts` |
| 数据契约版本 | `1.0.0` | `packages/contracts/src/types.ts` |
| 鞋类题集版本 | `footwear-v4.1.0` | `packages/contracts/src/types.ts` |
| 判断标准版本 | `footwear-judgment-v2` | `packages/contracts/src/types.ts` |
| 评分公式版本 | `2.1.0` | `packages/contracts/src/scoring.ts` |
| Amazon 选择器版本 | `amazon-us-v1.4.0` | `extension/src/amazon/version.ts` |

这些版本承担不同职责，不能只更新扩展的 `manifest.json`。发布流程见“版本与发布”章节。

## 2. 系统目标与边界

系统针对 Amazon.com 鞋类商品执行可回放的 Alexa for Shopping 黑盒测试：

1. 从当前 PDP 的可见 DOM 建立商品证据快照。
2. 根据固定鞋类模板和页面证据生成可审核题集。
3. 允许 Hermes 后端模型在严格约束下改写题目。
4. 由 Chrome 扩展的固定状态机逐题操作 Alexa。
5. 直接读取 Alexa 面板 DOM，保存完整回答、全部可识别商品卡/链接和脱敏截图。
6. 用共享契约中的确定性代码计算分数和原因码。
7. 在独立报告页展示原始证据、审计事件和诊断。

系统明确不做以下事情：

- 不访问 Amazon 隐藏接口、Cookie 或私有网络请求。
- 不绕过 CAPTCHA、登录、限流或其他安全限制。
- 不让模型控制浏览器或直接决定分数。
- 不把 Alexa 自述当作排序机制的事实。
- 不宣称得到了 Amazon 内部召回或排序权重。

## 3. 架构

```text
Amazon PDP / Alexa 可见页面
          │ 可见 DOM、页面交互、脱敏截图
          ▼
Chrome MV3 扩展
  Content Script ─ Background Service Worker ─ Vue/Pinia 侧边栏
          │ localhost REST
          ▼
NestJS 本地服务（127.0.0.1:4318）
  商品快照 │ 题集 │ 运行编排 │ 确定性评分 │ 审计 │ 报告接口
          │ OpenAI-compatible chat completions
          ▼
Hermes Agent API Server（默认 127.0.0.1:8642）
          │ Hermes 内部配置的模型供应商
          ▼
DeepSeek 等模型

SQLite + artifacts/
          │
          ▼
Vue / Element Plus / ECharts 报告页
```

### 3.1 Workspace

| 目录 | 职责 |
| --- | --- |
| `extension/` | Chrome MV3 扩展、Amazon 页面解析、Alexa 执行状态机、侧边栏 |
| `server/` | NestJS API、Hermes 通道、Prisma/SQLite、运行与审计 |
| `report/` | 独立 Vue 报告页 |
| `packages/contracts/` | 前后端共享类型、JSON Schema、评分标准和计算函数 |
| `server/prisma/` | SQLite 数据模型 |
| `server/artifacts/` | 默认截图目录；运行后生成，不应提交凭据或隐私内容 |

### 3.2 关键文件

| 文件 | 作用 |
| --- | --- |
| `extension/src/amazon/adapter.ts` | PDP 数据提取、启发式意图、Alexa 回答和商品卡解析、安全停止检测 |
| `extension/src/content.ts` | 页面消息入口、提问、等待回答稳定 |
| `extension/src/background/index.ts` | 当前标签页、运行循环、截图、服务端提交 |
| `extension/src/studio-bridge.ts` | 图片工作台同源消息桥接与请求 ID 关联 |
| `extension/src/studio/product-context.ts` | 六站点 PDP 选择、策划字段白名单、缓存 TTL 与 ASIN 一致性校验 |
| `extension/src/sidepanel/store.ts` | 侧栏状态、持久化、题集准备和运行控制 |
| `server/src/products/products.service.ts` | 商品快照校验、裁剪、模型意图完善和持久化 |
| `server/src/runs/prompt-builder.ts` | 英文/简体中文双轨鞋类题集、轨道上限与固定/随机顺序展开 |
| `server/src/deepseek/deepseek.service.ts` | Hermes 上层的意图完善、题目改写、诊断和模型审计 |
| `server/src/hermes/hermes-transport.service.ts` | 唯一模型传输层 |
| `server/src/runs/runs.service.ts` | 运行状态机、题集审批、轮次入库、评分、截图和诊断 |
| `packages/contracts/src/scoring.ts` | 唯一权威的机器评分实现 |
| `report/src/App.vue` | 完整报告与证据回放 |

> `DeepSeekService` 是当前代码中的服务类名，但它不会直连 DeepSeek API。所有模型调用都必须经过 `HermesTransportService`。

## 4. 本地开发

### 4.1 前置条件

- Node.js 20 或以上。
- npm workspace 依赖已经安装。
- Chrome，可加载未打包 MV3 扩展。
- 如需模型增强，本机 Hermes Agent API Server 已配置并启动。

### 4.2 安装与启动

```bash
cd "/Users/panjinlong/Documents/agent-master/apps/alexa-recommendation-auditor"
npm install
cp .env.example .env
npm run dev
```

`npm run dev` 同时启动：

- NestJS 服务：`http://127.0.0.1:4318`
- Vite 报告开发服务：`http://127.0.0.1:4319`
- 扩展侧栏和 service worker 的 watch build

服务端 `predev` 会运行 `prisma generate` 和 `prisma db push`。开发环境数据库默认位于 `server/prisma/alexa-auditor.db`。

### 4.3 加载扩展

1. 执行一次 `npm run build`，或保持 `npm run dev` 运行。
2. 打开 `chrome://extensions`。
3. 开启开发者模式。
4. 加载 `extension/dist/`。
5. watch build 产出变化后，在扩展管理页点击“重新加载”；Chrome 不会自动替换正在运行的 service worker。

### 4.4 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `PORT` | `4318` | 本地 NestJS 端口 |
| `LOCAL_AUTH_MODE` | `auto` | `disabled`、`pairing` 或 `auto` |
| `HERMES_API_URL` | `http://127.0.0.1:8642` | Hermes 根地址，不含 `/v1/chat/completions` |
| `HERMES_MODEL` | `hermes-agent` | 发给 Hermes 的模型名 |
| `HERMES_TIMEOUT_MS` | `120000` | 模型调用超时，代码限制为 1–180 秒 |
| `HERMES_API_KEY` | 空 | 可选的本机 Hermes Bearer token，不是供应商密钥 |
| `HERMES_DASHBOARD_URL` | `http://127.0.0.1:9119` | 侧栏“打开 Hermes 日志”的地址 |
| `MIN_TURN_INTERVAL_MS` | `12000` | `.env.example` 中保留；当前扩展执行器实际至少等待 12 秒 |
| `MAX_CORE_TURNS` | `45` | `.env.example` 中保留；当前题量主要由请求校验和预设控制 |
| `ARTIFACT_DIR` | `./artifacts` | 以服务进程工作目录解析的截图根目录 |
| `REPORT_DIST_PATH` | `../report/dist` | 报告生产构建目录 |

当前 `server/src/main.ts` 会从项目根目录的 `.env` 读取配置。不要在本项目的 `.env`、扩展代码或 `chrome.storage` 中保存 DeepSeek 供应商密钥；供应商凭据只应配置在 Hermes 内部。

## 5. 数据流

### 5.1 商品快照

侧栏请求 `GET_ACTIVE_PRODUCT`，background 获取当前活动的 Amazon.com 标签页，并向 content script 发送 `AUDITOR_EXTRACT_PRODUCT`。

`extractProductSnapshot()` 当前读取：

- URL、隐藏 ASIN 输入和变体节点中的请求 ASIN、已解析子 ASIN及别名。
- `#productTitle` 商品标题。
- `#bylineInfo` 品牌。
- 面包屑类目。
- Bullet。
- 商品详情表格。
- A+ 文本。
- 可见评论摘要和 Q&A。
- 当前价格、库存和配送。

结果拆成：

- `stableFacts`：标题、品牌、类目、Bullet、规格、A+、评论摘要、Q&A。
- `volatileFacts`：价格、库存、配送。

评论摘要和 Q&A 可以作为诊断参考，但只有标题、规格、Bullet、A+ 和类目路径中的证据能够使动态条件成为正向主计分条件。服务端会再次限制字段长度、证据来源和 ASIN 格式。

### 5.2 意图画像

扩展先用中英文词典生成本地启发式 `IntentProfile`。快照提交后，服务端通过 Hermes 请求模型完善 18 字段意图画像；模型只能看到裁剪后的稳定证据。

若 Hermes 未配置、不可用、超时、返回非 JSON 或结果不符合 `intentProfileSchema`，服务端保留扩展提供的本地画像。模型输出中的机器标签使用英文 `snake_case`，`latent_task` 使用中文。

### 5.3 问题计划

创建运行时的顺序为：

```text
保存 ProductSnapshot
→ 创建 draft ExperimentRun
→ 按预设生成确定性模板
→ 经 Hermes 尝试受控改写
→ 校验全部改写
→ 独立新会话对照组按 runSeed 稳定打乱
→ 单会话递进组保持固定顺序
→ 每个问题只展开 1 个执行轮次
→ 保存 PromptCase 和 question_plan_generated 审计事件
```

题集预设：

| 预设 | 独立新会话对照 | 单会话递进 | 总题数 |
| --- | ---: | ---: | ---: |
| `smoke` | 3 | 2 | 5 |
| `calibration` | 5 | 4 | 9 |
| `full` | 5 | 6 | 11 |

服务端只接受 `repetitions=1`，并在生成、人工编辑和审批三个阶段强制验证：

- `sessionPolicy=fresh` 的独立新会话题最多 5 个。
- 递进题只能属于一个 `sessionGroup`，最多 6 个。
- 独立组可以按种子随机顺序执行；递进组必须按模板顺序执行。
- 不再自动追加品牌或 ASIN 辅助题，以免身份提示污染盲测。

#### 5.3.1 `footwear-v4.1.0` 双轨模板

| 轨道 | 模板 ID | 条件变化 | 主指数 |
| --- | --- | --- | --- |
| 独立对照 | `footwear.control.category-baseline.v4` | 严格品类的自然全候选基线 | 否 |
| 独立对照 | `footwear.control.primary-function-direct.v4` | 主要功能、公开证据、限制与全链接 | 证据对齐时 |
| 独立对照 | `footwear.control.primary-function-natural.v4` | 自然需求映射并保持严格鞋类 | 证据对齐时 |
| 独立对照 | `footwear.control.comparison.v4` | 分离页面事实、评论和推断的全候选比较 | 证据对齐时 |
| 独立对照 | `footwear.control.negative-category.v4` | 明确冲突鞋类且排除当前品类 | 否 |
| 单会话递进 | `footwear.progressive.01-category.v4` | 建立自然全候选集 | 否 |
| 单会话递进 | `footwear.progressive.02-alexa-score.v4` | 获取 Alexa 自定义维度、权重与逐项推荐指数 | 否 |
| 单会话递进 | `footwear.progressive.03-screening-transparency.v4` | 区分可见筛选信息与未知内部机制 | 否 |
| 单会话递进 | `footwear.progressive.04-entry-hypotheses.v4` | 生成无品牌进入条件与最多3条自然问法 | 否 |
| 单会话递进 | `footwear.progressive.05-scene-narrowing.v4` | 按页面证明场景观察候选增删 | 否 |
| 单会话递进 | `footwear.progressive.06-budget-rescore.v4` | 锁定标准价格带并沿用 P2 标准复评分 | 否 |

独立对照题使用 `sessionPolicy=fresh`，每题从新 Alexa 会话开始；递进题使用 `sessionPolicy=shared_sequence` 和固定组 `footwear_progressive_intent`，只有第一题创建新会话。主推荐指数只接纳独立组中页面证据对齐、`positive_control`、`expectedMatch=eligible` 的完成轮次。递进组只报告候选保留率、我方商品进入/退出和条件承接，不与主分混算。

`footwear-v4.1.0` 还给每道独立题和递进组 P1 加入同语言隔离前缀，要求 Alexa 把当前消息视为全新的独立请求，只依据本条需求回答，不引用或延续先前对话。隔离语句同时进入 `requiredTerms`，Hermes 若删除它会被拒绝并回退到确定性模板。P2—P6 不添加此前缀，因为它们必须显式承接同一递进会话。

#### 5.3.2 当前中英文确定性题面

动态占位符来自当前 PDP 已证明的鞋类事实：`{audience}`、`{product_type}`、`{primary_function}`、`{implicit_primary_need}`、`{scene}` 与 `{material}`。`{current_page_product}` 只在递进诊断组中以“当前页面商品”引用，不暴露品牌或 ASIN；`{budget_ceiling}` 在运行前由当前价格映射到标准价格带并锁定。无合格页面证据时题目仍可用于诊断，但不能升级为正向主计分题。

```text
独立 F1
zh-CN: 我想购买适合{audience}日常穿着的{product_type}。请列出本轮实际建议我了解的全部候选，不要只做Top5。按自然推荐顺序，每个商品只写一行：商品名｜当前价格｜Amazon商品链接。候选池规模或价格无法确认时，请直接写“无法确认”。
en-US: I want {audience} {product_type} for everyday wear. List every candidate you actually recommend in this turn, not just a Top 5. In natural recommendation order, use one line per item: product name | current price | Amazon product link. If the candidate-pool size or price cannot be verified, say "unable to verify".

独立 F2
zh-CN: 我只考虑{audience}{product_type}，需要明确具备{primary_function}。请列出本轮实际符合条件的全部候选，不要只做Top5。每项只写一行：商品名｜支持该功能的公开证据｜主要限制｜当前价格｜Amazon商品链接。无法验证的功能不要推断。
en-US: I am only considering {audience} {product_type} that clearly have {primary_function}. List every candidate that actually qualifies in this turn, not just a Top 5. Use one line per item: product name | public evidence for the feature | main limitation | current price | Amazon product link. Do not infer a feature that cannot be verified.

独立 F3
zh-CN: {implicit_primary_need}。我只考虑{audience}{product_type}，并且需要适合日常较长时间穿着。请列出本轮实际建议的全部候选，不要只做Top5。每项只写一行：商品名｜为什么适合这个实际需求｜主要不确定性｜当前价格｜Amazon商品链接。
en-US: {implicit_primary_need}. I am only considering {audience} {product_type} suitable for extended everyday wear. List every candidate you actually recommend in this turn, not just a Top 5. Use one line per item: product name | why it fits this practical need | main uncertainty | current price | Amazon product link.

独立 F4
zh-CN: 请比较本轮最相关的全部候选，仅限{audience}{product_type}，并说明它们在{primary_function}方面的表现，不要只做Top5。按你认为的自然优先顺序，每项只写一行：商品名｜相对优势｜相对限制｜公开商品证据｜Amazon商品链接。请把页面事实、评论信息和你的推断分开；证据不足时写“未知”。
en-US: Compare every candidate from this turn that is a relevant {audience} {product_type} option on {primary_function}, not just a Top 5. In your natural priority order, use one line per item: product name | relative advantage | relative limitation | public product evidence | Amazon product link. Separate page facts, review information, and your inference; write "unknown" when evidence is insufficient.

独立 F5
zh-CN: 我只考虑{audience}{inverse_product_type}，明确排除任何{product_type}。请列出本轮实际建议的全部候选，每项只写商品名和Amazon商品链接。
en-US: I am only considering {audience} {inverse_product_type} and explicitly exclude all {product_type}. List every candidate you actually recommend in this turn, using only the product name and Amazon product link for each item.

递进 P1
zh-CN: 我想购买适合{audience}日常穿着的{product_type}。先列出你本轮实际建议我了解的全部候选，不要只做Top5。按自然推荐顺序，每项只写一行：商品名｜当前价格｜Amazon商品链接。
en-US: I want {audience} {product_type} for everyday wear. First list every candidate you actually recommend in this turn, not just a Top 5. In natural recommendation order, use one line per item: product name | current price | Amazon product link.

递进 P2
zh-CN: 针对上一轮全部候选，并把{current_page_product}作为一个普通对照项，请先说明你会从哪些维度判断推荐程度，最多6个维度，并让权重合计100。然后按同一套标准给每个候选一个0到100的推荐指数。每个维度直接给0到该维度权重的加权分，总分只能由各维度分数相加，不要再次乘权重。请区分页面事实、评论证据和推断；没有证据的维度标记“未知”，不要编造比例或样本量，也不要因为它是当前页面商品而优先。
en-US: For every candidate from the previous turn, and with {current_page_product} included only as an ordinary comparison item, first state up to six dimensions you use to judge recommendation strength and make their weights total 100. Then give every candidate a 0-to-100 recommendation index using the same standard. For each dimension, assign the already-weighted score from zero to that dimension's weight; the total must be only the sum of those dimension scores, with no second multiplication by weight. Separate page facts, review evidence, and inference; mark unsupported dimensions "unknown", do not invent percentages or sample sizes, and do not prioritize the current-page product because it is on the page.

递进 P3
zh-CN: 这些候选是怎样进入本轮推荐的？请分别说明你实际能够确认的候选数量、使用了哪些可见信息、哪些筛选过程无法确认。不要估算Amazon全站商品总量，也不要把评分、销量、广告或历史行为说成确定的内部排序规则。
en-US: How did these candidates enter this turn's recommendations? Separately state the candidate count you can actually confirm, which visible information you used, and which screening processes you cannot confirm. Do not estimate Amazon's total catalog size or describe ratings, sales, advertising, or history as confirmed internal ranking rules.

递进 P4
zh-CN: 假设用户第一次咨询这个品类，并且不使用品牌词或ASIN。根据{current_page_product}当前可核验的商品事实，哪些真实需求、使用场景、预算条件和属性组合会使它有资格成为合理候选？请生成最多3条自然用户问法，并为每条标出所依据的页面证据。不要声称这些词一定会提高Amazon内部排序；它们只是下一步需要用新会话验证的测试假设。
en-US: Assume a user is asking about this category for the first time without using a brand name or ASIN. Based on verifiable facts for {current_page_product}, which real needs, use cases, budget conditions, and attribute combinations would make it eligible as a reasonable candidate? Generate at most three natural user questions and identify the page evidence behind each one. Do not claim these words will improve Amazon's internal ranking; they are only test hypotheses for later validation in fresh sessions.

递进 P5
zh-CN: 如果需求进一步限定为适合{scene}的{audience}{product_type}，请列出你本轮会推荐的全部候选，不要只做Top5。每项只写一行：商品名｜进入理由｜替换条件｜当前价格｜Amazon商品链接。请标出相对第一轮新增、保留和退出的商品；只陈述可见证据，不推断Amazon内部权重。
en-US: If the need is narrowed to {audience} {product_type} suitable for {scene}, list every candidate you would recommend in this turn, not just a Top 5. Use one line per item: product name | entry reason | replacement condition | current price | Amazon product link. Mark products added, retained, or removed relative to the first turn; state only visible evidence and do not infer Amazon's internal weights.

递进 P6
zh-CN: 在保留{scene}和{primary_function}要求的前提下，把预算进一步限制为{budget_ceiling}。请重新列出本轮全部候选，并沿用P2的同一评分标准复评分。每项只写一行：商品名｜推荐指数｜进入或退出原因｜已知风险｜当前价格｜Amazon商品链接。请特别标出{current_page_product}是新增、保留还是退出；不要因为低价自动优先，也不要把历史偏好或内部排序当作已知事实。
en-US: Keep the {scene} and {primary_function} requirements, but narrow the budget to {budget_ceiling}. Relist every candidate in this turn and rescore them with the exact same standard from P2. Use one line per item: product name | recommendation index | entry or exit reason | known risk | current price | Amazon product link. Explicitly mark whether {current_page_product} is added, retained, or removed; do not automatically prioritize low price or treat historical preferences or internal ranking as known facts.
```

Hermes / DeepSeek 只改写题面，不得改变轨道、会话组、固定顺序、必需词、证据 ID、预期结果或计分角色。开发端必须在 `question_plan_generated` 事件中看到确定性原题、最终题面、改写原因、证据和轨道元数据。

审核页同时显示 5 个 AI 建议问题方向：价格带进入条件、使用场景进入条件、材料与结构进入条件、风险反证、自然用户问法。建议只能替换 P4—P6 中不适用的一题，不能突破 5+6 上限；正式建议必须保存题文、页面证据 ID、适用槽位与替换理由，并标注为“待新会话验证的假设”，不得解释为 Amazon 内部排名规则。

> [!warning]
> 以下折叠内容仅保留已停用的 `footwear-v2.0.0` 历史参考，不得用于新运行、计分或预设解释。

<details>
<summary>展开已停用的 v2 模板记录</summary>

#### 历史 v2 预设包含关系

三档预设不是三套互不相关的题库，而是同一个有序模板列表的前缀：

| 序号 | 模板 ID | 测试目的 | `smoke` | `calibration` | `full` | 主指数资格 |
| ---: | --- | --- | :---: | :---: | :---: | --- |
| 1 | `footwear.category.baseline.v2` | 宽泛品类基线 | ✓ | ✓ | ✓ | 否 |
| 2 | `footwear.primary-function.direct.v2` | 主要功能直接表达 | ✓ | ✓ | ✓ | 页面证据对齐时 |
| 3 | `footwear.category.negative.v2` | 冲突品类负控制 | ✓ | ✓ | ✓ | 否 |
| 4 | `footwear.primary-function.natural.v2` | 主要功能自然语言表达 |  | ✓ | ✓ | 页面证据对齐时 |
| 5 | `footwear.capability.task.v2` | 商品能力任务表达 |  | ✓ | ✓ | 页面证据对齐时 |
| 6 | `footwear.body-need.natural.v2` | 脚型或身体需求 |  | ✓ | ✓ | 页面证据对齐时 |
| 7 | `footwear.event.task.v2` | 使用活动 |  | ✓ | ✓ | 页面证据对齐时 |
| 8 | `footwear.location.task.v2` | 使用地点 |  | ✓ | ✓ | 页面证据对齐时 |
| 9 | `footwear.material-structure.direct.v2` | 材质或结构 |  | ✓ | ✓ | 页面证据对齐时 |
| 10 | `footwear.multi-constraint.v2` | 多条件同时保留 |  | ✓ | ✓ | 功能、能力、材质均对齐时 |
| 11 | `footwear.comparison.v2` | 候选商品比较 |  | ✓ | ✓ | 功能和能力均对齐时 |
| 12 | `footwear.retail.price-delivery.v2` | 当前价格与配送探针 |  | ✓ | ✓ | 否 |
| 13 | `footwear.semantic-task.v2` | 端到端语义任务 |  |  | ✓ | 活动和功能均对齐时 |
| 14 | `footwear.tradeoff.diagnostic.v2` | 条件冲突与取舍诊断 |  |  | ✓ | 否 |
| 15 | `footwear.substitute.diagnostic.v2` | 替代关系诊断 |  |  | ✓ | 否 |

`promptCount` 会从上述列表开头截取模板，因此修改 `buildAllFootwearCases()` 的排列顺序会同时改变三档预设。自定义 `promptCount` 截断时，辅助题数量目前按截断后的计划长度推断：最多 3 个核心模板不追加辅助题，4–12 个追加品牌题，13–15 个追加品牌题和 ASIN 题。盲测模板按 `runSeed` 稳定打乱并展开重复轮次；辅助认知题不参与打乱，始终追加在盲测题之后。

#### 5.3.2 动态占位符

下面列出的文本是 `footwear-v2.0.0` 的确定性基线模板。运行时会先从商品快照和 18 字段意图画像填入动态值，再允许 Hermes 后端模型只改写措辞。

| 占位符 | 来源或含义 |
| --- | --- |
| `{audience}` | `audience_intent`，例如女士、男士、儿童 |
| `{product_type}` | `product_type`，英文会转换为适合题句的复数形式 |
| `{primary_function}` | `function_intent` 中的首个主要功能 |
| `{implicit_function_need}` | 将主要功能转写成不直接复述属性词的自然语言痛点 |
| `{capability_requirement}` | `capability_intent` 转写后的能力要求 |
| `{implicit_fit_need}` | `body_need_intent` 转写后的脚型或穿着痛点 |
| `{event}` | `event_intent` |
| `{location}` | `location_intent` |
| `{material}` | 商品规格中的材质或结构；无值时使用安全回退文案 |
| `{inverse_product_type}` | 根据当前品类生成的明显冲突鞋类 |
| `{substitute}` | `substitute_intent` |
| `{price_ceiling_usd}` | 当前价格向上取整后的美元上限，限制在 `$20–$250` |
| `{brand}`、`{title}`、`{resolved_asin}`、`{asin_family_aliases}` | 仅用于不计分的辅助认知题 |

标题、规格、Bullet、A+ 和类目路径中的页面证据可以使动态正向条件获得主指数资格；评论摘要和 Q&A 只能作为诊断证据。若动态槽位没有合格证据，题目仍会生成，但角色降级为 `diagnostic`，`scoreEligible=false`。

计划中的 `scoreEligible=true` 不是最终得分保证。机器评分还会检查题目已启用、角色仍为 `positive_control`、预期为 `eligible`、证据来源仍合格且本轮状态为 `completed`。

> 当前实现审计点：材质题固定带有“轻量 / lightweight”，但计分资格只验证商品类型与材质；比较题固定带有“耐用性 / durability”，但计分资格只验证主要功能与能力。它们目前应被视为需要人工查看的附加比较条件，不能仅凭 `scoreEligible=true` 就认定页面已经证明轻量或耐用。若要改变这一语义，必须修改模板和证据规则并升级题集版本。

#### 5.3.3 `smoke` 固定模板

1. 宽泛品类基线  
   `templateId`: `footwear.category.baseline.v2`；角色：`baseline`；不计入主指数。

```text
zh-CN: 推荐适合{audience}日常穿着的{product_type}。
en-US: Recommend {audience} {product_type} for everyday wear.
```

2. 主要功能直接表达  
   `templateId`: `footwear.primary-function.direct.v2`；页面明确支持商品类型和主要功能时为正向计分题。

```text
zh-CN: 推荐具有{primary_function}的{audience}{product_type}。
en-US: Recommend {audience} {product_type} with {primary_function}.
```

3. 冲突品类负控制  
   `templateId`: `footwear.category.negative.v2`；角色：`negative_control`；正确行为是我方全部 ASIN 别名不进入 Alexa 完整返回列表。

```text
zh-CN: 推荐{audience}{inverse_product_type}。不要包含{product_type}。
en-US: Recommend {audience} {inverse_product_type}. Do not include {product_type}.
```

`smoke` 用于验证商品快照、题集、Alexa 会话、完整返回列表解析、截图和回传链路。它没有可计分的比较模板，当前不能满足正式 0–100 推荐指数的精确样本门槛；报告应显示诊断结果或样本不足，而不是把冒烟结果当成正式推荐指数。

#### 5.3.4 `calibration` 新增模板

`calibration` 包含全部 `smoke` 模板，并新增以下 9 题。

4. 主要功能自然语言表达  
   `templateId`: `footwear.primary-function.natural.v2`。

```text
zh-CN: {implicit_function_need}。日常长时间穿着时，我应该考虑哪些{audience}{product_type}？
en-US: {implicit_function_need}. Which {audience} {product_type} should I consider for extended everyday wear?
```

5. 商品能力任务表达  
   `templateId`: `footwear.capability.task.v2`。

```text
zh-CN: 哪些{audience}{product_type}在日常使用中能提供{capability_requirement}？请推荐并说明原因。
en-US: Which {audience} {product_type} deliver {capability_requirement} during regular daily use? Recommend suitable options and explain why.
```

6. 脚型或身体需求  
   `templateId`: `footwear.body-need.natural.v2`。

```text
zh-CN: {implicit_fit_need}。为了日常舒适穿着，我应该考虑哪些{audience}{product_type}？
en-US: {implicit_fit_need}. Which {audience} {product_type} should I consider for comfortable everyday wear?
```

7. 使用活动  
   `templateId`: `footwear.event.task.v2`。

```text
zh-CN: 推荐适合{event}的{audience}{product_type}。
en-US: Recommend {audience} {product_type} suitable for {event}.
```

8. 使用地点  
   `templateId`: `footwear.location.task.v2`。

```text
zh-CN: 哪些{audience}{product_type}适合在{location}使用？请推荐实用的选择。
en-US: Which {audience} {product_type} work well around {location}? Recommend practical options.
```

9. 材质或结构  
   `templateId`: `footwear.material-structure.direct.v2`。

```text
zh-CN: 寻找采用{material}材质、轻量的{audience}{product_type}。
en-US: Find lightweight {audience} {product_type} made with {material}.
```

10. 多条件同时保留  
    `templateId`: `footwear.multi-constraint.v2`。

```text
zh-CN: 推荐兼具{primary_function}、{capability_requirement}和{material}结构的{audience}{product_type}。
en-US: Recommend {audience} {product_type} that combine {primary_function}, {capability_requirement}, and {material} construction.
```

11. 候选商品比较  
    `templateId`: `footwear.comparison.v2`。

```text
zh-CN: 比较你认为最相关的{audience}{product_type}在{primary_function}、{capability_requirement}和耐用性方面的表现。请按优劣排序，并引用所依据的公开证据。
en-US: Compare the most relevant {audience} {product_type} for {primary_function}, {capability_requirement}, and durability. Rank the strongest options and cite the public evidence used.
```

12. 当前价格与配送探针  
    `templateId`: `footwear.retail.price-delivery.v2`；角色：`retail_probe`；不计入主指数。

```text
zh-CN: 推荐价格低于 {price_ceiling_usd} 且配送快的{audience}{product_type}。
en-US: Recommend {audience} {product_type} under {price_ceiling_usd} with fast delivery.
```

#### 5.3.5 `full` 新增模板

`full` 包含全部 `calibration` 模板，并新增以下 3 题。

13. 端到端语义任务  
    `templateId`: `footwear.semantic-task.v2`。

```text
zh-CN: 我需要适合{event}的鞋，因为{implicit_function_need}。哪些{product_type}最符合这个需求？
en-US: I need footwear for {event} because {implicit_function_need_lowercase}. Which {product_type} best fit that need?
```

14. 条件冲突与取舍诊断  
    `templateId`: `footwear.tradeoff.diagnostic.v2`；角色：`diagnostic`；不计入主指数。

```text
zh-CN: 哪些{product_type}最能平衡高度柔韧的轻量结构、最大缓震和刚性支撑？请说明哪项要求存在最大的取舍。
en-US: Which {product_type} best balance very flexible lightweight construction, maximum cushioning, and rigid support? Explain which requirement involves the greatest tradeoff.
```

15. 替代关系诊断  
    `templateId`: `footwear.substitute.diagnostic.v2`；角色：`diagnostic`；不计入主指数。

```text
zh-CN: 如果我优先考虑{primary_function}和便于穿脱，什么可以替代{substitute}？请比较你认为合适的鞋类选择。
en-US: What could replace {substitute} if I prioritize {primary_function} and easy on-off wear? Compare the footwear options you consider suitable.
```

#### 5.3.6 辅助认知题

辅助认知题会明确出现受测商品身份，只用于判断 Alexa 是否识别品牌、商品和父子 ASIN，不计入盲测主推荐指数。它们在核心题完成 Hermes 改写后由本地代码追加，始终只执行 1 次，也不会发送给 Hermes 改写。

`calibration` 和 `full` 追加品牌认知题：

```text
zh-CN: 仅依据公开商品页面证据，{brand} {title} 能满足哪些鞋类需求，哪些宣称仍未得到证明？
en-US: Based only on public product-page evidence, what footwear needs does {brand} {title} satisfy, and which claimed needs remain unproven?
```

`full` 再追加 ASIN 家族认知题：

```text
zh-CN: 将亚马逊鞋类商品 {resolved_asin} 与适合其主要使用场景的优质替代品进行比较。将 {asin_family_aliases} 视为同一受测商品家族的别名，并指出页面上没有明确证明的每项要求。
en-US: Compare Amazon footwear product {resolved_asin} with strong alternatives for its main use case. Treat {asin_family_aliases} as aliases of the same tested product family and identify every requirement not explicitly proven on the page.
```

#### 5.3.7 Hermes 改写与运行日志

Hermes/DeepSeek 只允许改写核心盲测模板的 `promptText`，必须保留 `templateId`、`requiredTerms`、测试角色、证据 ID、预期结果和计分资格；辅助品牌/ASIN认知题不经过模型改写。最终运行题目可能与基线措辞不同，但测试语义必须一致。

开发端应在 `question_plan_generated` 事件和 Hermes Session 日志中同时检查：

- 确定性原题 `originalPromptText`。
- 最终题目 `promptText`。
- `generatedBy` 是 `deterministic`、`deepseek_rewrite` 还是 `developer_edit`。
- `rewriteReason`、证据 ID、角色和 `scoreEligible`。
- 是否发生整批回退及其脱敏原因。

人工调整后会生成 `question_plan_updated` 事件；题集批准后锁定，运行中不得静默改变题目。

</details>

### 5.4 一键编排与可选人工审核

侧边栏唯一主操作为“查看推荐指数”。`recommendationIndexAction()` 按当前运行状态决定行为：

- 已完成且有结果：打开报告。
- `ready`、`stopped` 或执行器已中断但仍有 `pending` 问题：复用并继续原运行。
- 没有可执行运行：创建新快照和题集。

新运行仍先保存为 `draft`，但一键编排会自动保存已有问题草稿、调用服务端校验、批准锁定并启动后台执行器。审批请求保存明确的一键编排说明，服务端仍执行全部题集不变量校验；UI 自动化不能绕过独立题/递进题上限、页面证据门槛或乐观锁。

默认折叠的高级区域仍允许开发者在点击主按钮前：

- 修改题目文本。
- 启用或禁用模板。
- 修改测试元数据，但必须通过服务端不变量校验。
- 保存调整原因。

每个模板只对应一个执行轮次。每次更新使用 `questionPlanRevision` 做乐观锁，并产生 `question_plan_updated` 事件；服务端同时重验独立组最多5题、递进组最多6题且只能有一个递进会话组。批准后题集进入 `ready`，所有问题锁定，运行开始后不允许静默改题。自动编排和人工高级模式共享同一服务端审批接口与审计规则。

### 5.5 Alexa 执行

background 一次只执行一个问题，但一次“查看推荐指数”会自动循环完成题集中全部 `pending` 轮次：

1. 启动或恢复服务端运行。
2. 创建隔离执行工作区。执行器只调用 `tabs.create({ url: AMAZON_HOME, active: false })`，在当前 Chrome 窗口创建一个非活动后台测试标签页；不会调用 `windows.create()`，也不会读取、导航或关闭用户的活动标签页。自动执行路径不调用 `tabs.get()`：导航前先注册 `tabs.onUpdated`，同时检查 `tabs.update()` 的返回值来覆盖同 URL 情况。
3. 校验运行绑定的已锁定商品快照。独立新会话题只在后台测试标签页导航到 Amazon 首页，绕过缓存强制刷新并通过 `AUDITOR_PING` 校验当前选择器版本，再根据 `sessionPolicy` 创建新 Alexa 会话；同组递进题继续既有会话。新会话的第一条消息同时携带题面隔离前缀。
4. content script 写入问题，等待可见且已启用的语义提交控件后点击发送。提交控件优先按 `type=submit`、`aria-label`、`data-testid` 和可访问名称定位；不得把未确认生效的模拟回车当作成功发送。
5. 每 500 ms 检查回答；“正在生成”标记存在时绝不完成。新回答必须比提交前文本至少多 20 个字符，并在已观察到生成过程、新完成标记或 8 秒兼容等待之后稳定 3 秒，最长等待 90 秒。
6. 从 Alexa 面板直接提取回答文本与完整可识别商品列表；按 ASIN 或规范化标题去重，并设置 100 条防漂移安全上限。
7. 将轮次提交给服务端。静默后台模式把 `screenshotError` 记录为 `background_mode_screenshot_skipped`，不调用 `captureVisibleTab`。
8. 至少等待 12 秒后自动执行下一题，直到完成、安全停止或执行环境被外部终止。

默认 `fresh` 策略使每道独立题新建会话；`shared_sequence` 只允许同一 `sessionGroup` 继承上下文。欢迎页本身已是空白新会话时，首题直接使用当前输入框；检测到 `Customer question / 客户问题` 或回答生命周期痕迹时，执行器通过 Alexa 面板或“更多选项”创建新对话，并连续验证会话至少 600 ms 保持空白。无法证明干净时以 `context_isolation_failed` 停止。提示词隔离是第二道防线，不能替代 DOM 会话校验；两者都不能清除 Amazon 账户级个性化。

扩展重载、侧边栏关闭或 service worker 重启后，服务端可能仍保留 `running` 状态。侧边栏恢复时会查询后台执行器：

- 执行器仍存在：显示真实运行中状态，不允许重复启动。
- 执行器已经断开但仍有 `pending` 题：再次点击“查看推荐指数”只执行未完成题目。
- 新生成问题集后：清除当前视图中的旧运行结果，并按运行 ID 忽略上一轮迟到的消息；历史运行仍保留在数据库和报告中。

续跑只允许当前 `FOOTWEAR_PROMPT_VERSION`。一键入口发现旧 prompt 版本时强制走 `prepare_run` 新建题集，扩展启动前和服务端 `start()` 还会分别复验版本；因此旧运行不能绕过界面继续发送没有隔离前缀的题目。已完成的历史运行仍可打开其原版本报告。

侧边栏端口只负责显示进度。`port.postMessage()` 失败会被忽略，不得让关闭侧边栏、切换标签页或页面销毁中断后台状态机。运行结束或停止后必须销毁该非活动后台测试标签页。

background 抛出的执行错误统一带有 `[phase]` 前缀和 `executor <build>` 后缀，例如 `[prepare_session:case-id] ... · executor 2026.07.17-no-window-prompt-isolation.1`。侧边栏在恢复和启动前发送 `GET_EXECUTOR_INFO`，要求后台返回相同的 `EXECUTOR_PROTOCOL_VERSION` 与 `EXECUTOR_BUILD`；`EXECUTE_RUN` 同样携带两者，后台会反向拒绝旧侧边栏。若用户看到不含阶段和构建标识的旧 `tabs.get` 错误，说明 Chrome service worker 仍在运行上一次构建，必须在 `chrome://extensions` 对从 `extension/dist` 加载的扩展再次点击“重新加载”。`extension/tests/background-contract.test.ts` 会阻止自动执行器重新引入 `chrome.tabs.get()` 和 `chrome.windows.create()`，`extension/tests/executor-protocol.test.ts` 覆盖新旧前后台错配。

### 5.6 图片工作台商品上下文桥接

扩展在本地 `127.0.0.1`、`localhost` 和项目固定 GitHub Pages 地址注入 `studio-bridge.js`。图片工作台先把用户粘贴的 PDP 链接规范化为无追踪参数的站点、ASIN 与 `/dp/ASIN` 地址，再发送带随机 `requestId`、`productUrl` 和 `asin` 的同源 `window.postMessage`。桥接脚本使用专用 `GET_STUDIO_AMAZON_PRODUCT_CONTEXT` 协议向 service worker 请求商品上下文；请求和响应都必须携带相同、格式有效的 `requestId`。

页面选择与回退遵循以下确定性顺序：

1. `productUrl` 必须属于受支持站点，且路径明确包含 `/dp/ASIN` 或 `/gp/product/ASIN`。首页、搜索页和非 Amazon 地址在进入扩展前即被拒绝。
2. service worker 查询所有受支持的 Amazon 标签页，只保留站点和 URL ASIN 同时与粘贴链接一致的 PDP。同一窗口有多个匹配页时优先请求来源窗口内最近使用的匹配页；不存在精确匹配时明确失败，不猜测其他商品。
3. 支持 `amazon.com`、`amazon.co.jp`、`amazon.de`、`amazon.fr`、`amazon.it` 和 `amazon.es`；读取过程不激活、不导航、不关闭标签页，也不调用 `chrome.windows.create()`。
4. PDP 抽取成功后立即缩减为策划专用快照并写入 15 分钟显式缓存。读取失败时，缓存 ASIN 必须与链接 ASIN 一致；不一致就明确失败，禁止跨商品回退。

策划专用快照只允许标题、品牌、类目、Bullet、稳定规格和 A+ 正文。价格、优惠、配送、库存、卖家、评论、评分、Q&A、Rufus/Alexa 对话、账户标签、易变证据和 URL 跟踪参数在离开扩展前删除。图片工作台再校验 `amazon-product-context/v1`，展示来源、标题、ASIN、品牌和证据计数，用户确认后才覆盖策划表单；同步本身不调用模型、不生图。

手动 Listing 文本、粘贴 JSON 和导入 JSON 文件始终保留。桥接只读取页面可见商品内容，不传递 Cookie、令牌、支付或账号信息。

### 5.7 评分与报告

服务端写入轮次后立即重新计算分数、保存 `TurnJudgment`，并产生 `turn_recorded`、`turn_judged` 和 `score_recalculated` 事件。全部轮次完成后，先生成确定性诊断，再尝试经 Hermes 改写为受约束诊断。

报告接口重新从原始轮次计算分数，不依赖模型保存的分数解释，因此同一数据和同一版本代码应得到相同结果。

## 6. Hermes 模型链路

### 6.1 唯一出口

模型请求只允许调用：

```text
POST {HERMES_API_URL}/v1/chat/completions
```

请求固定包含：

```json
{
  "model": "hermes-agent",
  "temperature": 0,
  "top_p": 0.2,
  "response_format": { "type": "json_object" },
  "stream": false
}
```

Hermes health 使用 `GET {HERMES_API_URL}/health`，最多等待 2 秒。

### 6.2 三类操作

| 操作 | `HermesOperation` | 失败回退 |
| --- | --- | --- |
| 商品意图完善 | `intent_profile_refinement` | 页面本地启发式画像 |
| 问题措辞改写 | `question_rewrite` | 确定性题集 |
| 完成后诊断 | `run_diagnosis` | 确定性原因规则 |

### 6.3 题目改写守卫

Hermes/模型只能改写 `promptText`，不能改变模板的测试语义。服务端会原子校验整批结果：

- JSON Schema、版本和条数必须正确。
- 每个 `templateId` 必须且只能出现一次。
- `requiredTerms` 必须保留。
- 盲测题不得出现我方品牌或 ASIN。
- 不得新增数字约束。
- 不得新增价格、评分、评论、配送、库存、医疗功效、隐藏算法、购买或加购要求。
- 不得新增原题没有的鞋类属性。
- `zh-CN` 必须要求自然简体中文；品牌和 ASIN 保持不变。

任意一题校验失败时，整批回退到对应语言的确定性模板，避免部分改写造成实验口径漂移。

### 6.4 模型审计

内存审计和 NestJS 结构化日志记录：

- 操作类型和 request ID。
- run、snapshot、ASIN、schema、prompt 和 template 上下文。
- 请求模型、响应模型和 Hermes Session ID。
- token 使用量和延迟。
- 成功、回退或未配置状态。
- 经过脱敏和长度限制的回退原因。
- 问题改写前后文本、改写理由和证据 ID。

不会记录供应商密钥。`DeepSeekService` 内存审计有上限，权威运行历史是 SQLite 中的 `RunEvent`。

## 7. 多语言

当前支持：

- `en-US`
- `zh-CN`

语言选择存入 `ExperimentRun.promptLanguage`，并由侧栏保存在 `chrome.storage.local`。两种语言使用相同：

- 模板槽位。
- 页面证据映射。
- 测试角色。
- 预期结果。
- 是否计入主指数。
- 评分公式。

语言只改变确定性题目、动态值和 Hermes 改写输出，不改变双轨会话策略、固定顺序或计分角色。新增动态鞋类词时，应同时维护 `server/src/runs/prompt-builder.ts` 中的中文映射，并增加英文、中文和未知标签回退测试。

中文校验和证据匹配使用 NFKC 与 Unicode 字母/数字规则，不能退回只保留 ASCII 的正则。

## 8. 评分

权威实现位于 `packages/contracts/src/scoring.ts`：

```text
总分 =
35% × 完整返回列表进入率
+ 25% × 标准化排名
+ 15% × 竞品比较胜率
+ 15% × 页面证据承接度
+ 10% × 同一意图直接表达/自然语言表达的一致性
```

只有同时满足以下条件的已完成轮次进入主分：

- `sessionPolicy = fresh`
- `testRole = positive_control`
- `scoreEligible = true`
- `expectedMatch = eligible`
- 绑定有效卖家页面证据
- 轮次状态为 `completed`

单会话递进、基线、负控制和其他诊断题单独汇总，不能混入主分。

关键实现：

- 自有商品首先通过父体、子体和 ASIN 别名识别；仅在 ASIN 不足时使用保守的品牌和标题鉴别词匹配。
- 排名分为 `100 / log2(rank + 1)`，使用完整解析列表中的全部名次。
- 一致性使用同一逻辑槽位中“直接属性表达”和“自然语言需求表达”的完整解析结果集合两两 Jaccard。
- 证据承接只读取归属于我方商品卡的 `evidenceText`，不使用 Alexa 自由文本代替商品卡证据。
- 事实整句命中，或非停用词至少命中 `min(2, token数)` 且覆盖率不少于 50%，才算单项事实通过。
- 绑定的全部事实均通过，题目证据结果才是 `pass`。

精度门槛由 `SCORING_STANDARDS.precisionGate` 控制。当前要求至少 3 个完成的证据对齐独立正向轮次、至少 2 个逻辑问题组，并存在比较观察；若当前计划本身更小，轮次数门槛会下调到计划可完成数量，但冒烟预设通常只输出定性结果。不满足时 `total=null`，等级为 `insufficient`。

`judgmentCriteria` 是开发者人工审阅说明，不会执行或修改代码评分。

## 9. 数据持久化与审计

### 9.1 SQLite

Prisma 模型：

- `ProductSnapshot`
- `ExperimentRun`
- `PromptCase`
- `ConversationTurn`
- `RunEvent`

JSON 字段以字符串保存在 SQLite，出入库统一通过共享类型和 `parseJson`/`stringifyJson`。

### 9.2 截图

静默后台执行默认不截图，因为 `chrome.tabs.captureVisibleTab()` 依赖用户手势产生的瞬时 `activeTab` 授权，并有误截当前前台窗口的风险。轮次会保存 `background_mode_screenshot_skipped`，回答正文、完整商品列表、提取诊断和选择器版本仍是正式审计事实。

如果未来增加显式的“前台审计截图”模式，必须先对已知账户和地址节点加模糊、由用户单独授权，并且服务端仍只接受 PNG/JPEG data URL，单张最大 8 MB。当前版本不自动进入该模式。

文件默认保存到：

```text
server/artifacts/{runId}/{sha256(promptCaseId)前16位}.jpg
```

目录权限为 `0700`，文件权限为 `0600`。报告只通过限定路径的 artifact 接口读取，服务端会防止路径穿越。

### 9.3 审计事件

当前主要事件包括：

- `question_plan_generated`
- `run_created`
- `question_plan_updated`
- `question_plan_approved`
- `run_started`
- `turn_recorded`
- `turn_judged`
- `score_recalculated`
- `model_diagnosis_completed`
- `run_completed`
- `run_stopped`

事件带 `actor`：`system`、`developer`、`deepseek` 或 `extension`。侧栏通过 REST 刷新 `/audit`；服务端同时提供 SSE `/events`，当前扩展执行 UI 没有依赖 SSE 完成核心流程。

## 10. API

服务默认仅监听 `127.0.0.1`。主要接口：

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/api/v1/health` | 服务、认证和 Hermes 健康 |
| `POST` | `/api/v1/pair` | 使用一次性六位码换取本次进程 token |
| `GET` | `/api/v1/scoring-standards` | 无运行数据的只读评分标准 |
| `POST` | `/api/v1/product-snapshots` | 保存商品快照 |
| `GET` | `/api/v1/product-snapshots/:id` | 读取商品快照 |
| `POST` | `/api/v1/runs` | 创建 draft 运行和题集 |
| `GET` | `/api/v1/runs/:id` | 读取运行和题目 |
| `GET` | `/api/v1/runs/:id/audit` | 读取审计历史和评分标准 |
| `PATCH` | `/api/v1/runs/:id/prompts/:promptCaseId` | 修改同模板题目 |
| `POST` | `/api/v1/runs/:id/question-plan/approve` | 审批并锁定 |
| `POST` | `/api/v1/runs/:id/start` | 开始或恢复 |
| `POST` | `/api/v1/runs/:id/turns` | 保存一轮结果 |
| `POST` | `/api/v1/runs/:id/stop` | 停止 |
| `GET` | `/api/v1/runs/:id/events` | SSE 运行事件 |
| `GET` | `/api/v1/reports/:id` | 完整报告 JSON |
| `GET` | `/reports/:id` | 报告页面 |
| `GET` | `/api/v1/artifacts/:runId/:name` | 截图文件 |

商品和运行写接口受 `LocalAuthGuard` 保护。健康、配对、只读评分标准和报告控制器没有该 guard，但仍只能通过本机监听地址访问。若未来改变监听地址，必须重新设计报告鉴权，不能直接暴露当前接口。

## 11. 认证与安全

`LOCAL_AUTH_MODE`：

- `disabled`：不要求 token。
- `pairing`：总是要求一次性六位配对码。
- `auto`：development/test 免配对，其他环境强制配对。

生产模式启动时终端输出一次性六位码；成功配对后该码立即失效，Bearer token 只在当前服务进程有效。

服务端安全措施：

- 只监听 `127.0.0.1`。
- CORS 只允许 Chrome 扩展、本机 `127.0.0.1` 和 localhost。
- JSON 请求上限 12 MB。
- Helmet 开启，CSP 在服务端禁用以便托管报告资源。
- 输入长度、枚举、题集语义和 ASIN 均在服务端再次校验。
- 模型页面证据作为不可信数据处理。
- 错误审计会脱敏 Bearer token 和 `sk-` 形式密钥。

扩展权限只包括 `sidePanel`、`activeTab`、`storage`、`scripting`、`tabs`、`alarms`，以及六个受支持 Amazon 站点、图片工作台和本地服务 host permissions。

安全停止条件：

- CAPTCHA / Robot Check
- 429 或页面限流文本
- 登录失效
- 关键选择器漂移
- 连续三轮失败

当前 `detectSafetyStop()` 会返回 `captcha`、`rate_limited`、`login_required` 或 `selector_drift`；background 和服务端还会识别 `forbidden`、`context_isolation_failed` 和 `response_timeout`。出现这些原因时不得增加规避逻辑。

## 12. 测试与验证

提交前运行：

```bash
npm run typecheck
npm test
npm run build
```

根脚本依次验证 contracts、server、report 和 extension。当前报告 workspace 没有独立单元测试，其 `test` 脚本只输出提示；报告的类型检查和生产构建仍属于必过项。

现有测试覆盖：

- contracts JSON Schema 和评分。
- Hermes transport 成功、超时、HTTP错误和安全错误码。
- 意图完善、受控题目改写、中文保留和回退。
- 双轨题集生成、动态证据、5/6轨道上限、独立组稳定打乱与递进组固定顺序。
- 请求校验、题集版本冲突、审批和运行服务。
- Amazon DOM 解析、商品绑定、题目草稿和会话策略。

自动测试不访问真实 Amazon、Hermes 或 DeepSeek。现场验收必须由用户小规模触发，先使用 `smoke`，确认选择器、会话创建、截图脱敏和停止逻辑后再使用更大预设。

### 12.1 变更对应测试

| 变更 | 最低验证 |
| --- | --- |
| Amazon DOM 选择器 | adapter fixture + 小规模 smoke；必要时升级 `SELECTOR_VERSION` |
| Prompt 模板或中文映射 | prompt-builder 中英测试 + DeepSeek 改写守卫测试 |
| 共享字段或枚举 | contracts schema + 所有 workspace typecheck |
| 评分规则 | 固定样例、原因码、精度门槛；升级公式/判断标准版本 |
| Prisma 模型 | Prisma generate、迁移/数据库升级验证、旧记录兼容 |
| Hermes 协议 | transport mock；不可使用真实凭据进入 CI |
| 侧栏流程 | extension 单测 + Chrome 手工 smoke |

## 13. 版本与发布

项目已提供本地版本一致性、开发日志和飞书文档同步工具，但不会自动提交 Git、创建标签、打包发布或绕过人工验收。

### 13.1 何时升级哪个版本

- UI、服务或一般修复：升级应用/扩展 SemVer。
- `ProductSnapshot`、API JSON 或共享类型不兼容：升级 `SCHEMA_VERSION`。
- 模板槽位、题目语义或必需词变化：升级 `FOOTWEAR_PROMPT_VERSION`。
- 轮次资格、原因码含义或判断规则变化：升级 `JUDGMENT_STANDARDS_VERSION`。
- 权重、排名函数、证据聚合或精度门槛变化：升级评分 `formulaVersion`，通常同时升级判断标准。
- Amazon 页面选择器变化：升级 `SELECTOR_VERSION`。

纯措辞修复是否升级 prompt 版本，应以“是否影响跨运行可比性”为判断标准；影响可比性就必须升级。

### 13.2 发布检查清单

1. 确认改动类别和需要升级的版本面。
2. 同步根 `package.json`、各 workspace `package.json`、`extension/manifest.json` 和 health 响应中的应用版本。
3. 如涉及共享契约，更新版本常量、Schema 和兼容映射。
4. 如涉及 Prisma，生成正式 migration；不要只依赖开发环境的 `db push`。
5. 更新开发者日志/CHANGELOG，记录日期、版本、变更、迁移、验证和已知限制。
6. 运行：

   ```bash
   npm run typecheck
   npm test
   npm run build
   ```

7. 确认 `extension/dist/manifest.json` 版本和源 manifest 一致。
8. 在全新 Chrome 扩展重载后执行一次 `smoke`。
9. 检查 `/api/v1/health`、Hermes 状态、题目审计、截图脱敏和报告复算。
10. 再发布/同步使用文档和飞书文档；文档版本必须注明对应的应用版本。

### 13.3 飞书文档同步

本地 Markdown 是唯一事实源，飞书中的开发文档和使用手册是固定发布目标：

- 开发文档：`docs/DEVELOPMENT.md`
- 使用手册：`docs/USER_GUIDE.md`
- 开发文档自动附录：`CHANGELOG.md`、`docs/DEVELOPMENT_LOG.md`、`docs/RELEASE_PROCESS.md`
- 文档映射：`docs/feishu-docs.json`
- 最近同步状态：`docs/feishu-sync-state.json`

同步前先预览：

```bash
npm run docs:sync:feishu:dry-run
```

正式覆盖两份固定飞书文档并回读验证：

```bash
npm run docs:sync:feishu
```

只检查本地文档是否与最近成功同步的哈希一致：

```bash
npm run docs:check
```

`release:check` 会执行 `docs:check`。任何文档源发生变化后，必须先同步飞书，发布门禁才会重新通过。覆盖同步适用于这两份由项目生成、以本地 Markdown 为事实源的文档；不要直接在飞书正文中维护仅存于云端的批注式内容。

同步脚本通过 lark-cli 官方支持的相对路径 `--content @file` 传递长 Markdown 正文，并在每份文档更新后删除临时载荷文件；不要改回 `spawnSync` 的大段 stdin 输入，否则 lark-cli 提前关闭输入流时会触发 `EPIPE`。只有覆盖更新与回读验证都成功后才允许写入同步状态。

## 14. 故障排查

### 插件显示“本地服务未启动”

```bash
curl http://127.0.0.1:4318/api/v1/health
```

检查 `npm run dev` 是否仍在运行、端口是否被占用、扩展中的服务地址是否为 `http://127.0.0.1:4318`。

### 显示“配对码无效或已经使用”

配对码是一次性的。开发阶段使用 `LOCAL_AUTH_MODE=disabled`，或重启生产服务获取新码。不要重复提交已使用的码。

### Hermes 不可用

```bash
hermes gateway status
hermes gateway run
curl http://127.0.0.1:8642/health
```

同时检查 `.env` 的 `HERMES_API_URL`。模型不可用不应阻塞固定题集；侧栏和 `question_plan_generated` 应显示 fallback 原因。

### Hermes 显示在线但题目仍是固定模板

查看：

- 侧栏“运行日志”中的 `question_plan_generated.modelAudit`。
- NestJS 日志中的 `PROMPT_GENERATION_AUDIT`。
- Hermes Dashboard 中对应 Session。

常见原因是漏掉 required term、盲测泄漏品牌/ASIN、新增未授权属性、返回条数不一致或非 JSON。

### 无法读取商品

确认：

- 浏览器中必须保留与图片工作台粘贴链接同站点、同 ASIN 的 Amazon 商品详情页；不要求切回商品页，也不会自动导航页面。
- 页面是 PDP 且 `#productTitle` 已加载。
- 能从 URL、`#ASIN` 或变体节点得到 10 位 ASIN。
- 扩展已在 `chrome://extensions` 重载。

若提示扩展后台没有响应，说明本地工作台桥接脚本与 Chrome service worker 版本不一致或后台未加载；在 `chrome://extensions` 重新加载 `extension/dist` 后刷新工作台。若提示缓存 ASIN 不一致，说明当前 PDP 抽取失败，而 15 分钟缓存属于另一商品。刷新正确 PDP 并等待标题加载后重试；不要放宽为跨 ASIN 缓存，否则会把另一商品的内容带入策划。

如果 Amazon 改版，先保存脱敏 DOM fixture，再修改 adapter 和选择器版本，不能直接扩大到脆弱的全局文本抓取。

### 无法创建新 Alexa 会话

content script 只接受可见且可用、按钮文本为 `New chat`、`New conversation`、`新对话` 或 `新聊天` 的控件。直接按钮不存在时，可先在同一 Alexa 面板点击 `More options / 更多选项`，再从浮层选择新对话。欢迎页首题若已稳定为空白则不要求额外点击；检测到历史但无法创建并验证空白新会话时，以 `context_isolation_failed` 停止，避免上下文污染。修改时优先使用可访问名称和语义属性，并增加 fixture。

### Alexa 回答超时

当前最长等待 90 秒，并要求新回答至少比旧文本多 20 个字符且稳定 3 秒。“正在生成”标记存在时不会落库；先确认 Alexa 实际完成输出，再检查面板定位和回答解析，不要简单取消稳定条件。

### 问题已填入但没有自动发送

执行器应自动完成整轮测试，用户只需点击一次“查看推荐指数”，不需要手动批准、再次开始或逐题点击 Rufus 发送按钮。content script 会等待最多 7.5 秒寻找已启用的提交控件；找不到时以 `selector_drift` 停止，并在错误中保存控件数量、候选名称、启用状态和 `SELECTOR_VERSION`。不要恢复“无条件模拟 Enter 后视为发送成功”的旧逻辑。

发送控件必须与 Rufus composer 绑定。无可访问名称的 `button[type=submit]` 只允许来自 composer 的精确所属表单；无表单时，只能在 composer 的近邻容器或同一 Shadow Root 中接受具有 `send / submit / 发送 / 提交` 语义的控件。禁止在整个 Amazon 文档中优先选择第一个裸 `type=submit`，否则会误点顶部商品搜索按钮，引发顶层导航并销毁等待回答的消息通道。对应 fixture 必须让 Amazon 搜索表单排在 Rufus 表单之前，并断言仍选择 Rufus 控件。

`chrome.tabs.sendMessage` 失败不能统一解释成“content script 未注入”。只有 `Receiving end does not exist / Could not establish connection` 可以在补注入后重试；`A listener indicated an asynchronous response ... channel closed` 说明监听器已经收到消息但文档在回执前被销毁，此时问题可能已经提交，执行器必须按 at-most-once 原则停止，禁止重发。`message_channel_closed` 或测试目标丢失时，当前窗口的后台测试标签页保留 60 秒供核查，然后自动清理。当前选择器版本为 `amazon-us-v1.4.0`，执行器构建为 `2026.07.17-no-window-prompt-isolation.1`。

### 返回商品列表为空或商品卡解析错误

解析器直接读取 Alexa 面板 DOM，按以下顺序提取：商品链接中的 ASIN、`data-asin`、带“Add to cart”的可见商品卡、当前 PDP 商品在回答中的明确提及。按 ASIN 或规范化标题去重，保存全部识别结果，设置 100 条安全上限以防选择器漂移误抓整页。运行事件中的 `extractionDiagnostics` 会记录回答字符数、DOM 链接数、含 ASIN 数和纯文本商品数。

### 报告页面跳转到 4319

服务端没有找到 `REPORT_DIST_PATH/index.html` 时会跳转到 Vite 开发服务。生产启动前运行 `npm run build`，并确认 `report/dist` 存在。

### 数字分数不显示

检查报告 warnings、有效正向题数、完成问题组和比较题。`insufficient` 是设计结果，不应通过降低门槛或混入基线/探针来强制显示数字。

### 截图缺失

截图只是可选人工审计证据，不参与替代 Alexa DOM 文本和商品链接。静默后台模式下 `background_mode_screenshot_skipped` 是预期结果，不是失败。只有未来显式启用前台截图模式时才检查：

- 页面是否允许 `captureVisibleTab`。
- data URL 是否为 PNG/JPEG。
- 单张是否超过 8 MB。
- `ARTIFACT_DIR` 是否可写。
- 脱敏遮罩是否正确恢复。

## 15. 开发约束

- 前后端字段先改 `packages/contracts`，再改消费端。
- 所有实验含义都放在不可变元数据中，模型只改语言表述。
- 所有可计分的新属性必须能追溯到允许的稳定页面证据。
- 新测试角色必须同时定义评分隔离、报告展示和审计含义。
- 新安全错误码必须同时更新 content、background、server 和文档。
- 不在日志、fixture、截图、扩展存储或 Git 中保存供应商密钥、Amazon Cookie、账户地址或支付信息。
- 不以真实 Amazon/模型网络调用作为 CI 前提。
- 所有报告结论必须区分观察事实、模型推断和未知原因。
