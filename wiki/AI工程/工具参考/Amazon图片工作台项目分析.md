---
tags: [AI工程, Amazon, A+页面, AIGC, 开源项目]
date: 2026-07-15
status: 现行
---

# Amazon 图片工作台项目分析

> [!summary] 摘要
> `amazon-image-studio` 是一个面向 Amazon Listing 与 A+ Content 的纯前端 AI 图片策划、生成和编辑工作台。当前本地版本已通过版本化 JSON 合约和 Chrome 扩展桥接接入 Amazon 商品页：稳定商品事实先预览、确认后填入策划表单，不自动调用模型或生图。它适合作为现有飞书 A+ 流程的人工出图端，但不是批量任务管理、审核或 Seller Central 发布系统。

## 核心知识

### 项目定位

- 基于 `CookSleep/gpt_image_playground` 修改，专门增加 Amazon Listing 图和 A+ 图的策划模板、尺寸、合规约束与多站点文案。
- 它不内置模型或免费额度；用户需要配置自己的文本策划 API 和图片生成 API。
- 适合单个产品或少量 SKU 的交互式制图，定位更接近“设计师工作台”，而不是“电商业务后台”。

### 主要工作流

1. 选择 Listing 图或 A+ 图及目标站点。
2. 粘贴标题、Bullet、产品说明和品牌信息，上传产品实拍、包装或结构参考图。
3. 调用文本或多模态模型，生成逐张图片策划、英文生图提示词、负面提示词与当地化图上文案。
4. 逐张选择 `MAIN`、`PT01-PT11` 或 A+ 模块槽位，修改 Prompt 后调用生图 API。
5. 在浏览器中保留历史、遮罩编辑、参考图、风格预设和批量下载结果。

### 功能边界

| 能力 | 当前实现 |
|---|---|
| Listing 策划 | 默认 7 张，可调整为 7-12 张，包含 MAIN |
| A+ 策划 | 普通 A+、标准 A+、高级 A+、手机 A+；每类 1-12 个模块 |
| 站点 | 美国、日本、德国、法国、意大利、西班牙 |
| 图片 API | OpenAI Images / Responses、OpenAI 兼容接口、OpenRouter Chat 生图、fal.ai、自定义 HTTP 图片接口 |
| 策划 API | Chat Completions 或 Responses API；DeepSeek 官方地址会强制只发文本 |
| 商品页同步 | 粘贴六个 Amazon 站点的 PDP 链接，按站点和 ASIN 精确读取已打开的对应页面，也支持粘贴/导入 `amazon-product-context/v1` JSON |
| 本地数据 | API 配置与 UI 状态进入 `localStorage`；任务、图片、缩略图与策划会话进入 IndexedDB |
| 部署 | GitHub Pages、Cloudflare Pages/Workers、Vercel、Docker/Nginx |
| 未实现 | 不批量抓取 ASIN、不管理 ASIN/SKU 数据库、不自动审批、不发布 Seller Central、不自动裁切或压缩到 2 MB |

### 技术架构

- React 19 + TypeScript + Vite 6 + Zustand + Tailwind CSS 3。
- 纯前端 SPA/PWA，没有项目自带的业务后端或数据库服务。
- 浏览器直接向用户配置的 API URL 发送 `Authorization: Bearer <key>`。如果目标接口不支持 CORS，需要 Docker/Nginx 同源代理或其他反代。
- 内置精炼版 Amazon 图片知识规则，通过 JSON Schema 或 JSON-only Prompt 约束策划结果。

### 项目健康度（2026-07-15）

- GitHub 公开仓库，MIT License，主要语言为 TypeScript。
- 仓库创建于 2026-05-23，最新提交为 2026-07-14，尚处于快速迭代期。
- 查看时约 115 stars、62 forks、0 open issues；贡献列表只有 1 个账号，未发布 GitHub Release 或版本 tag。
- 本地临时检出验证：19 个测试文件、252 项测试全部通过；TypeScript 和 Vite 生产构建成功。
- 构建产物主 JavaScript 包约 871 KB（gzip 约 256 KB），Vite 报出超过 500 KB 的代码分割告警。

### 优点

- Amazon 图片任务槽位、A+ 尺寸、主图禁区、多站点文案等领域逻辑已经产品化，比通用生图界面更贴近运营。
- 支持产品参考图、风格参考、遮罩编辑、历史和批量下载，基本的试图闭环完整。
- 文本策划和生图可分开配置，可以用便宜文本模型策划、用更强图像模型生图。
- 有比较充足的单元测试，当前主分支可构建。

### 局限与风险

> [!warning] API Key 与线上版本
> API Key 会明文保存在浏览器本地状态中。当前源码没有显示把 Key 发给项目作者，但使用 GitHub Pages 线上版等于持续信任站点以后部署的每次代码更新。建议自建本地版，并使用独立、限额、可随时撤销的 API Key。

- 设置页支持生成包含 API Key 的导入 URL。即使界面有提示，也不应在聊天、邮件、工单或截图中传播这种 URL。
- Amazon 合规是 Prompt 与界面检查清单，不是硬性的视觉或文字合规审核；生成图仍需人工核对真实商品、Logo、文案、数量、配件和声明。
- A+ 模块是项目自定义编排，不等于 Seller Central 全部官方模板；手机 A+ `600x450` 是应用内参考，不是独立的官方发布类型。
- 缺少多用户、权限、云端存储、任务队列、成本核算、版本审批、ASIN/SKU 关联和 Seller Central 上传能力。
- 项目由单一账号维护且无正式 Release，如果作为团队生产工具，应固定已验证的 commit，不要直接跟随 `main`。

### 与现有 A+ 工作流的关系

- 现有 [[亚马逊A+优化-飞书多维表格工作流方案]] 负责 ASIN/SKU、竞品、状态和审核；本项目可作为“待生成 → 设计师试图 → 下载结果”的专用工作台。
- [[飞书字段捷径-DeepSeek-AI分析方案]] 的结构化产品信息、核心卖点、A+ 方案和变体提示词，可作为工作台的输入。
- 如要正式接入，最小改造是增加“从飞书记录导入 JSON”与“生成结果导出 JSON/ZIP manifest”；不建议第一阶段就把飞书、审核和 Seller Central 能力全部塞进这个前端。

### 与 Amazon 页面采集和 Alexa 诊断器的本地集成（2026-07-19）

- 手动与自动双模式均已保留：可以继续粘贴 Listing、填写商品信息和上传参考图，也可以从商品页同步、粘贴 JSON 或导入 JSON 文件。
- Chrome 扩展支持美国、日本、德国、法国、意大利和西班牙站。工作台要求先粘贴商品链接，以链接中的站点和 ASIN 精确匹配已打开的对应 PDP，不再依据活动页或最近访问顺序猜测；全程不激活、导航或新建标签页/窗口。
- 扩展在数据离开浏览器隔离区前缩减为策划专用快照，只保留标题、品牌、类目、Bullet、稳定规格和 A+ 正文；价格、促销、库存、配送、卖家、评论、评分、Q&A、Rufus/Alexa 对话、账户标签和跟踪参数均删除。
- 15 分钟缓存只允许相同 ASIN 回退。有候选 PDP 但抽取失败时，缓存 ASIN 与候选 URL 不一致就明确失败，防止把商品 A 的内容导入商品 B。
- 工作台校验 `amazon-product-context/v1` 后先显示来源、ASIN、标题、品牌和证据计数，用户确认才写入 Planner；同步本身不调用 AI、不生图、不产生模型费用。
- 每次确认导入都从默认模板重建策划 Draft，并清除旧提示词、旧策划结果和当前策划会话。切换 ASIN 时还会清除旧商品参考图与风格；同一 ASIN 刷新只保留用户明确上传的参考图。
- 导入的 Listing 正文按“不可信数据”放入结构化边界，策划模型被明确要求忽略正文中的命令式内容，降低商品文案提示注入和跨商品上下文污染。
- 第二阶段再考虑本地 API、飞书记录、批量 ASIN 队列和结果 manifest，不把这些能力耦合进第一版浏览器桥接。

### 建议结论

> [!tip] 适合小范围验证，不建议直接当团队主系统
> 选 1 个真实 ASIN、1-2 个变体，用本地部署和限额 Key 跑完 Listing 7 图或 5-6 个 A+ 模块，记录首轮可用率、平均重生次数、单图 API 成本、产品一致性错误和人工后期时间。数据达标后，再决定是否做飞书导入/回写集成。

## 关联

- [[亚马逊A+优化-飞书多维表格工作流方案]]
- [[飞书字段捷径-DeepSeek-AI分析方案]]
- [[亚马逊A+页面制作SOP]]
- [[亚马逊A+页面模板与规范]]
- [[工具参考/Alexa商品推荐诊断插件]]
- [[亚马逊商品标题与Item-Highlights新规-2026]]

## 来源

- [Ali-Aria/amazon-image-studio](https://github.com/Ali-Aria/amazon-image-studio)
- [README](https://github.com/Ali-Aria/amazon-image-studio/blob/main/README.md)
- [package.json](https://github.com/Ali-Aria/amazon-image-studio/blob/main/package.json)
- [Amazon 策划 API 实现](https://github.com/Ali-Aria/amazon-image-studio/blob/main/src/lib/listingPlannerApi.ts)
- [应用状态与 API 配置持久化](https://github.com/Ali-Aria/amazon-image-studio/blob/main/src/store.ts)
- [本地存储实现](https://github.com/Ali-Aria/amazon-image-studio/blob/main/src/lib/db.ts)
- [MIT License](https://github.com/Ali-Aria/amazon-image-studio/blob/main/LICENSE)
- [提交历史](https://github.com/Ali-Aria/amazon-image-studio/commits/main/)
- 2026-07-15 本地临时检出的 `npm test` 与 `npm run build` 验证结果
