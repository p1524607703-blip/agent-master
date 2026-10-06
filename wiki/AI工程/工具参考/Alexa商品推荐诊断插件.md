---
tags: [AI工程, 亚马逊, Alexa, Chrome扩展, 黑盒测试]
date: 2026-07-15
status: 现行
---

# Alexa商品推荐诊断插件

> [!summary] 摘要
> Alexa 商品推荐诊断插件是一套面向鞋类的本地优先 Chrome MV3 黑盒测试工具。它从 Amazon 商品详情页建立带证据来源的商品基准，以固定可比模板、页面动态槽位和经 Hermes Agent 调用 DeepSeek 的受控改写生成题集；开发者审核锁定后，固定状态机才会逐轮执行 Alexa for Shopping 问答。推荐指数只度量可观察的 Top 5 进入、排名、比较、证据承接与稳定性，不能代表 Amazon 内部真实权重。

## 核心知识

- 工程目录：`apps/alexa-recommendation-auditor/`。
- 三层架构：Chrome 扩展负责页面读取、对话、Top 5 解析与隐私遮盖截图；NestJS 本地服务负责实验编排、Hermes 调用审计、SQLite 与评分；已安装的 Hermes Agent 负责 DeepSeek 凭据、模型传输、会话和模型日志；Vue 报告页负责证据回放和渠道建议。
- 适配对象是通用鞋类而非单一 ASIN：人字拖、凉鞋、乐福鞋、套脚鞋、赤足鞋、跑鞋、步行鞋、运动鞋、靴子和木底鞋等由页面事实动态识别。
- DeepSeek 仅用于把页面证据映射为18字段意图体系、在服务端约束下优化问题表述和辅助诊断；所有调用必须经本机 Hermes Agent 的 OpenAI 兼容接口，插件不保留直连 DeepSeek 的旁路。浏览器操作与最终评分均由确定性代码完成。改写不得新增品牌、ASIN、医疗功效、价格履约、购买动作或页面未证明的鞋类属性。
- 固定题集覆盖品类基线、受众、功能、能力、脚型需求、任务、场景、地点、材质、多条件、比较、零售探针、负控制、替代关系和条件冲突；动态槽位只引用当前商品的有效页面证据。
- 提问语言支持英语（Amazon US）与简体中文。两种语言共用相同测试槽位、证据映射、角色、预期结果和计分规则；语言选择会同时作用于15个固定题、页面动态槽位、品牌/ASIN辅助认知题、Hermes受控改写和运行日志。中文证据匹配使用Unicode规范化，避免中文页面事实因字符过滤失去评分资格。
- 三档预设为：冒烟3模板×1次；校准12模板×2次并附1个辅助认知题；完整15模板×3次并附2个辅助认知题。
- 问题生成后停在草稿态。运行日志展示完整题文、固定模板原文、DeepSeek改写原因、证据ID、测试假设、角色与预期结果；开发者可改写或停用问题，未保存草稿不能审批，审批后问题集锁定。
- Hermes 调用审计保存操作类型、请求关联ID、`X-Hermes-Session-Id`、请求/响应模型、耗时、标准 token 用量、验证结果和确定性回退原因；完整模型会话与错误可在 `http://127.0.0.1:9119` 的 Hermes Dashboard 或 Hermes CLI 中复核。
- Hermes 改写必须保持运行选定的语言和全部 `requiredTerms`；若中文必需词被删除、加入购物车动作、零售/医疗条件或其他越界属性，整批题集会原子回退到简体中文固定模板。
- 本机开发配置使用 Hermes Agent v0.11.0（检查时为最新版本），API 仅绑定 `127.0.0.1:8642`。`api_server` 平台禁用全部工具集，使不可信商品页面文本只能作为模型数据，不能触发终端、文件、浏览器、联网或代理工具。
- 每个独立问题创建新 Alexa 会话；明确属于同一连续诊断组的题只在组内继承上下文，第一问仍新建会话。会话隔离不能清除 Amazon 账户级个性化，因此报告必须保留测试账户标签。
- 用户批准题集并点击一次“开始测试”后，执行器自动逐题提交并按至少 12 秒间隔继续；无需人工点击每题发送。独立题返回 Amazon 首页时会绕过缓存刷新并校验 content script 版本，Rufus 提交优先按 `type=submit` 和可访问名称定位，失败时保存选择器诊断并安全停止。
- 商品证据分为稳定页面证据和易变零售信号；只有标题、规格、Bullet、A+和类目路径可让动态条件进入主评分。评论摘要与Q&A可作为诊断参考，但不能单独升级为商品事实。
- 推荐指数公式为：35% Top 5进入率、25%标准化排名、15%竞品比较胜率、15%页面证据承接度、10%重复稳定性。
- 只有页面证据对齐的 `positive_control` 完成轮次进入主指数；基线、负控制、零售探针、辅助认知和诊断题分别报告。人工 `judgmentCriteria` 仅是审阅清单，机器评分严格使用版本化角色、证据、Top 5、排名、比较和重复规则。
- 样本、重复组、比较题或可归属证据不足时不输出伪精确分数，只显示样本不足；满足门槛后才显示强、中、弱、置信区间和原因码。
- 开发者侧边栏和报告页公开主分资格、角色隔离、约束/证据结果、证据词法匹配、独立探针、精度门槛与原因码词典；`GET /api/v1/scoring-standards` 是不含运行数据的公开只读口径端点，生产配对模式也可复核。
- 证据承接只判断可归属到我方商品卡的 `evidenceText`，不拿 Alexa 自述替代商品卡证据；规范化后需命中事实短语，或至少命中 `min(2, token数)` 且达到50%非停用词覆盖，绑定事实全部通过才记证据通过。
- 报告包含意图槽位表现、高频候选竞品、Alexa自述与商品卡片行为不一致、逐轮回答/截图及 Listing、SP、SBV、STV、SD 动作建议。
- CAPTCHA、403/429、登录失效、选择器漂移或连续解析失败会触发硬停止；系统不调用隐藏接口、不读取 Cookie、不绕过验证码，也不执行加购或购买。
- 本地服务仅监听 `127.0.0.1`；开发模式可免配对，生产模式使用一次性配对码。DeepSeek 密钥只由 Hermes 的本机配置或凭据存储持有，不得进入插件代码、扩展存储或插件项目 `.env`；插件运行时忽略遗留的 `DEEPSEEK_*` 变量。
- Hermes 不可用、超时、拒绝请求、上游余额不足或返回无效 JSON 时，模型增强必须显式降级为固定题集、确定性商品画像或规则诊断，并记录原因，禁止静默直连其他模型。
- 开始运行前必须重新读取当前标签页并与已保存父体、当前子体和ASIN别名核对；不一致时拒绝执行，防止把商品A的问题跑到商品B页面。
- 扩展同时提供图片工作台专用桥接：从六个受支持 Amazon 站点按用户粘贴链接的站点和 ASIN 精确选择已打开 PDP，输出去除价格、履约、评论、Rufus 对话和账户信息的策划快照。15 分钟缓存必须与链接 ASIN 一致，桥接不会激活、导航或新建页面，也不会自动调用图片策划模型；旧后台空响应会明确提示重新加载扩展。
- 文档治理采用“本地 Markdown 事实源 + 固定飞书发布目标”：开发实现维护在 `docs/DEVELOPMENT.md`，运营使用维护在 `docs/USER_GUIDE.md`，分别同步到[飞书开发文档](https://my.feishu.cn/docx/WSVfdI5iooArKvxhbpDcRJL9nhb)和[飞书使用手册](https://my.feishu.cn/docx/Z8hNd4efYo0nuOx3FC0cQ8E7nvf)。后续更新覆盖这两份固定文档，不重复创建。
- `VERSION` 是应用版本唯一事实源，版本检查同时覆盖根工作区、四个子包、Chrome Manifest、构建产物、共享 `APP_VERSION` 和两份本地文档。`CHANGELOG.md` 记录发布级变化，`docs/DEVELOPMENT_LOG.md` 追加每次开发变更。
- `npm run docs:sync:feishu` 会逐份覆盖飞书正文并回读验证标题、章节和正文规模；成功后将文档修订号与本地 SHA-256 写入不含凭据的同步状态。`npm run release:check` 会拒绝版本不一致、文档未同步、类型检查失败、测试失败或构建失败的交付。

## 与LinkFox-Alexa技能的关系

- LinkFox 当前市场中的对应技能是 `linkfox-amazon-alexa-search` 1.0.4；旧 slug `linkfox-amazon-alexa-for-shopping` 已无法解析，但仍残留在技能的 Feedback API 示例中，可视为上游命名迁移不完整。
- LinkFox 技能通过云端 `POST /amazon/alexaSearch` 发起单条自然语言购物问答，返回 Alexa 回答、推荐商品分组、ASIN、商品链接、追问建议和截图；它适合临时推荐、对话式选品和单次验证。
- LinkFox 每次调用只支持一个 prompt，跨调用不保留会话。所谓“追问”由 Agent 总结上一轮回答后重新组成新 prompt，本质上是新会话，不是 Alexa 原生连续上下文。
- 本地插件直接驱动已登录 Amazon 页面，面向鞋类批量黑盒实验：生成并人工审批固定题集、重复执行、解析 Top 5、保存本地证据、计算确定性推荐指数并生成诊断报告。
- 两者可以互补但不能互相替代：LinkFox 技能适合快速对话和获取候选 ASIN；本地插件适合可重复、可审计的商品推荐可见性测试。
- LinkFox 技能需要 `LINKFOX_AGENT_API_KEY` 或 `LINKFOXAGENT_API_KEY` 和账户积分；当前计费规则为每个对话轮次 12.6 积分，实际调用前必须提示并由用户确认。

> [!warning]
> Alexa 的“为什么推荐”只能作为自述证据，必须与商品实际进入率、排名、页面证据和重复稳定性进行交叉验证。黑盒结果不能直接写成 COSMO 或 Alexa 的内部算法权重。

> [!warning] 当前模型可用性
> 2026-07-16 的本机验收已证明 Hermes API、会话 ID 和日志链路正常，但当时配置的 DeepSeek 账户返回 `402 Insufficient Balance`。`/health` 只代表 Hermes 服务可达，不代表上游模型有可用余额；真实测试前应在 Hermes 本机配置中更换未暴露且有余额的凭据，不能把密钥粘贴到聊天或插件界面。

## 关联

- [[亚马逊搜索词意图簇字段与无绩效指标分类规则]]
- [[亚马逊鞋类listing优化分析指南2026]]
- [[工具参考/DeepSeek-AI分析|DeepSeek-AI分析]]
- [[工具参考/Amazon图片工作台项目分析]]

## 来源

- `apps/alexa-recommendation-auditor/README.md`
- `apps/alexa-recommendation-auditor/packages/contracts/src/scoring.ts`
- `apps/alexa-recommendation-auditor/extension/src/amazon/adapter.ts`
- `apps/alexa-recommendation-auditor/extension/src/studio/product-context.ts`
- `apps/alexa-recommendation-auditor/server/src/runs/prompt-builder.ts`
- `apps/alexa-recommendation-auditor/server/src/runs/runs.service.ts`
- `apps/alexa-recommendation-auditor/server/src/hermes/hermes-transport.service.ts`
- `apps/alexa-recommendation-auditor/docs/DEVELOPMENT.md`
- `apps/alexa-recommendation-auditor/docs/USER_GUIDE.md`
- `apps/alexa-recommendation-auditor/docs/DOCUMENTATION_SYNC.md`
- `apps/alexa-recommendation-auditor/docs/RELEASE_PROCESS.md`
- `/Users/panjinlong/Documents/amc-hermes-dashboard/docs/ai-model-gateway-and-run-log.md`
- `/Users/panjinlong/.codex/skills/linkfox-amazon-alexa-search/SKILL.md`
- `/Users/panjinlong/.codex/skills/linkfox-amazon-alexa-search/references/api.md`
