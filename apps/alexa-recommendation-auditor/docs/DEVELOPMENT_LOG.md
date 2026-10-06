# Alexa 商品推荐诊断开发日志

本文件记录开发过程中的可审计变更。它与 `CHANGELOG.md` 的职责不同：

- `DEVELOPMENT_LOG.md`：记录每次开发变更、影响范围、验证结果和后续事项。
- `CHANGELOG.md`：只记录面向版本发布的用户可感知变化。
- `VERSION`：当前应用版本的唯一事实源。

日志只追加，不回写历史。新增记录应使用 `npm run devlog:add`，以确保格式稳定并便于后续同步。

---

## 2026-07-16 · infrastructure · v0.1.0

- **摘要**：建立本地版本号、开发日志和发布检查体系。
- **影响范围**：根工作区、四个子包、Chrome Manifest、服务健康检查、发布工具。
- **验证**：`npm run release:check` 通过；87 项测试、全工作区类型检查、服务/报告页/扩展生产构建及构建后版本复核均通过；版本更新与开发日志工具 dry-run 通过。
- **后续事项**：每次功能或修复完成后先追加开发日志；准备发布时再更新 `CHANGELOG.md` 和应用版本。

## 2026-07-16 · docs · v0.1.0

- **摘要**：拆分开发文档与使用手册，创建两份固定飞书发布目标并建立版本化覆盖同步门禁
- **影响文件**：docs/DEVELOPMENT.md,docs/USER_GUIDE.md,docs/feishu-docs.json,docs/feishu-sync-state.json,docs/DOCUMENTATION_SYNC.md,scripts/sync-feishu-docs.mjs,AGENTS.md,README.md,CHANGELOG.md
- **验证**：飞书开发文档 revision 11、使用手册 revision 9 回读通过；npm run release:check 通过；87 项测试、类型检查与生产构建通过；16 个版本位置一致
- **后续事项**：后续代码或操作流程变更先更新本地事实源，再运行 npm run docs:sync:feishu

## 2026-07-16 · docs · v0.1.0

- **摘要**：补充三档运行预设的真实题目模板与计分边界
- **影响文件**：docs/DEVELOPMENT.md,CHANGELOG.md,docs/DEVELOPMENT_LOG.md
- **验证**：footwear-v2.0.0 模板与 prompt-builder 代码、contracts 和测试交叉核对；prompt-builder 10 项测试通过；version:check 通过，16 个版本位置一致
- **后续事项**：若修正材质题的轻量证据或比较题的耐用性证据门槛，需升级题集版本并同步更新本文

## 2026-07-16 · fix · v0.1.0

- **摘要**：修复扩展重载后运行状态残留，支持从pending轮次恢复，并完成Alexa完整DOM结果与截图诊断链路
- **影响文件**：extension/src/background/index.ts,extension/src/sidepanel/store.ts,extension/src/sidepanel/App.vue,extension/src/amazon/adapter.ts,packages/contracts/src/scoring.ts,server/src/runs/runs.service.ts,report/src/App.vue,docs/DEVELOPMENT.md,docs/USER_GUIDE.md
- **验证**：扩展13项测试、全工作区90项测试、类型检查与生产构建通过；中断运行日志保留且安全停止
- **后续事项**：在Chrome重新加载extension/dist后重新执行3题冒烟测试，核对extractionDiagnostics和截图错误码

## 2026-07-16 · feature · v0.1.0

- **摘要**：将鞋类问题集重构为独立新会话对照组与单会话递进组：三档预设分别为3+2、5+4、5+6；每题执行一次，服务端强制5/6上限，并新增递进候选轨迹报告。
- **影响文件**：prompt-builder、runs service、contracts/scoring、Chrome侧边栏、报告页、测试、README、开发文档、使用手册与CHANGELOG
- **验证**：typecheck、contracts 17项测试、server 63项测试、extension 14项测试和四个workspace生产构建全部通过
- **后续事项**：重新加载Chrome未打包扩展后，由用户小规模启动冒烟现场测试；真实Amazon测试不由发布门禁自动触发。

## 2026-07-17 · feature · v0.1.0

- **摘要**：问题集升级为鞋类双轨 v4：冒烟固定为 F1/F2/F5 与 P1/P2，新增客观评分算术、完整候选与链接约束，并在侧栏提供 5 个 AI 建议问题方向；Hermes 改写若删除关键约束会自动回退确定性模板。
- **影响文件**：packages/contracts/src/types.ts；server/src/runs/prompt-builder.ts；server/prisma/schema.prisma；extension/src/sidepanel/App.vue；README.md；CHANGELOG.md；docs/DEVELOPMENT.md；docs/USER_GUIDE.md；相关测试与 v4 审核文档
- **验证**：类型检查通过；contracts 17、server 63、extension 14，共 94 项测试通过；生产构建通过；16 个版本位置一致。
- **后续事项**：完成 Chrome 中 v4 五题冒烟实测并记录 Hermes、Alexa 与解析数据。

## 2026-07-17 · fix · v0.1.0

- **摘要**：修复 Alexa 题目只填入未发送的问题，并明确一键启动后自动递进；同时补充 Amazon 页面硬刷新与内容脚本版本握手。
- **影响文件**：extension/src/amazon/adapter.ts,extension/src/content.ts,extension/src/amazon/version.ts,extension/tests/amazon-adapter.test.ts,README.md,docs/DEVELOPMENT.md,docs/USER_GUIDE.md,CHANGELOG.md
- **验证**：extension tests 20/20, typecheck, build
- **后续事项**：重载扩展后由用户触发一次新的冒烟测试，观察五轮自动发送与递进。

## 2026-07-17 · feature · v0.1.0

- **摘要**：新增不抢焦点的专用后台 Alexa 执行工作区、断开侧边栏后持续自动递进，以及 amazon-image-studio 商品上下文 JSON 桥接
- **影响文件**：extension/src/background/index.ts, extension/src/run/workspace.ts, extension/src/studio-bridge.ts, extension/src/sidepanel, extension/manifest.json, docs, CHANGELOG.md
- **验证**：扩展 typecheck、22 项扩展测试和扩展 build 已通过；图片工作台单元测试与 build 已通过
- **后续事项**：重新加载已解压扩展后执行真实 Alexa smoke 验收，并验证图片工作台页面同步

## 2026-07-17 · fix · v0.1.0

- **摘要**：修复后台工作区标签页ID缺失导致 chrome.tabs.get No matching signature，并打开本地新版图片工作台
- **影响文件**：extension/src/run/workspace.ts,extension/src/background/index.ts,extension/tests/workspace.test.ts,CHANGELOG.md,docs/DEVELOPMENT.md,docs/USER_GUIDE.md
- **验证**：extension 25 tests passed; npm run release:check passed; Feishu development revision 87 and user guide revision 49 readback verified; local image studio opened at 127.0.0.1:5173
- **后续事项**：在 Chrome 重新加载 extension/dist 后创建新的冒烟运行，验证真实 Rufus 自动发送

## 2026-07-17 · feature · v0.1.0

- **摘要**：将 Alexa 推荐诊断收敛为一键查看推荐指数，自动生成、校验、审批锁定、续跑和打开报告，并修复后台窗口缺失标签页ID时第一题前反复 executor_error
- **影响文件**：extension/src/sidepanel/App.vue,extension/src/sidepanel/store.ts,extension/src/sidepanel/quick-action.ts,extension/src/run/workspace.ts,extension/src/background/index.ts,extension/tests/quick-action.test.ts,extension/tests/workspace.test.ts,README.md,CHANGELOG.md,docs/DEVELOPMENT.md,docs/USER_GUIDE.md
- **验证**：全工作区类型检查通过；contracts 17、server 63、extension 29，共109项测试通过；扩展与报告生产构建通过
- **后续事项**：在 Chrome 重新加载 extension/dist 后，由用户点击一次查看推荐指数完成真实 Alexa 冒烟验收

## 2026-07-17 · fix · v0.1.0

- **摘要**：彻底移除自动执行器的 chrome.tabs.get 调用，并新增侧边栏与 Service Worker 的协议/构建版本握手，阻止新旧执行器混跑
- **影响文件**：extension/src/background/index.ts,extension/src/run/executor-protocol.ts,extension/src/sidepanel/store.ts,extension/src/sidepanel/App.vue,extension/tests/background-contract.test.ts,extension/tests/executor-protocol.test.ts,CHANGELOG.md,docs/DEVELOPMENT.md,docs/USER_GUIDE.md
- **验证**：扩展 typecheck 通过；33 项扩展测试通过；生产构建通过；src 与 dist 均为 0 处 tabs.get
- **后续事项**：在 Chrome 关闭侧边栏后重新加载 extension/dist，再由用户点击查看推荐指数完成真实 Alexa 冒烟验收

## 2026-07-17 · fix · v0.1.0

- **摘要**：修复飞书文档同步长 Markdown 通过 stdin 触发 EPIPE，改用 lark-cli 官方支持的相对 @file 载荷并自动清理
- **影响文件**：scripts/sync-feishu-docs.mjs,docs/DEVELOPMENT.md,docs/DOCUMENTATION_SYNC.md,docs/DEVELOPMENT_LOG.md
- **验证**：本地同步已越过 EPIPE 并到达 lark-cli 认证阶段；沙箱内 Keychain 不可访问，外部发布等待用户明确授权
- **后续事项**：用户明确授权飞书外部发布后重跑 docs:sync:feishu 并执行 release:check

## 2026-07-17 · fix · v0.1.0

- **摘要**：修复 Rufus 发送控件误命中 Amazon 顶部搜索按钮导致页面导航、消息通道关闭和测试窗口闪退；异步通道不明时禁止重复发送并短暂保留诊断窗口
- **影响文件**：extension/src/amazon/adapter.ts,extension/src/background/index.ts,extension/src/run/message-delivery.ts,extension/src/amazon/version.ts,extension/src/run/executor-protocol.ts,extension/tests,CHANGELOG.md,docs/DEVELOPMENT.md,docs/USER_GUIDE.md
- **验证**：扩展 40 项测试通过；扩展类型检查通过；extension/dist 生产构建完成并核验 selector amazon-us-v1.3.0 与 executor 2026.07.17-rufus-submit-scope.1
- **后续事项**：在 Chrome 重新加载 extension/dist 后，由用户点击一次查看推荐指数完成真实 Rufus 冒烟验证

## 2026-07-17 · fix · v0.1.0

- **摘要**：将传输错误后的 60 秒诊断窗口清理改为 Chrome alarms 持久调度，避免 Service Worker 休眠留下孤儿窗口
- **影响文件**：extension/manifest.json,extension/src/background/index.ts,extension/src/run/diagnostic-workspace.ts,extension/tests/diagnostic-workspace.test.ts,extension/tests/background-contract.test.ts
- **验证**：扩展类型检查通过；43 项扩展测试通过；extension/dist 生产构建通过
- **后续事项**：重新加载 extension/dist 后进行真实 Rufus 冒烟验证

## 2026-07-17 · fix · v0.1.0

- **摘要**：将 Alexa 测试隔离改为当前 Chrome 窗口内单一非活动标签页，并为独立题和递进首题加入不继承历史的提示词前缀，同时保留新对话 DOM 校验与安全停止
- **影响文件**：extension/src/run/workspace.ts,extension/src/run/executor-protocol.ts,extension/src/background/index.ts,extension/src/sidepanel/store.ts,extension/tests/workspace.test.ts,extension/tests/background-contract.test.ts,server/src/runs/prompt-builder.ts,server/src/runs/prompt-builder.test.ts,server/src/deepseek/deepseek.service.test.ts,packages/contracts/src/types.ts,server/prisma/schema.prisma,CHANGELOG.md,docs/DEVELOPMENT.md,docs/USER_GUIDE.md
- **验证**：全工作区 typecheck 通过；contracts 17、server 65、extension 52，共 134 项测试通过；全生产构建通过；extension/dist 无 tabs.get、windows.create、windows.remove 或 chrome.windows；构建包含 selector amazon-us-v1.4.0、executor 2026.07.17-no-window-prompt-isolation.1 与 footwear-v4.1.0 隔离提示
- **后续事项**：在 chrome://extensions 重新加载 extension/dist，创建新的冒烟运行；不要继续使用可能已串联上下文或提交状态不明的旧运行

## 2026-07-17 · fix · v0.1.0

- **摘要**：阻止旧版问题集继续执行，并完成同一窗口新对话与提示词上下文隔离的最终构建修复
- **影响文件**：packages/contracts/package.json, extension/src/sidepanel/quick-action.ts, extension/src/sidepanel/store.ts, server/src/runs/runs.service.ts
- **验证**：类型检查、136 个测试与生产构建通过；构建产物不含 chrome.windows、windows.create/remove 或 tabs.get
- **后续事项**：在 Chrome 扩展管理页重新加载 extension/dist 后，由用户触发一次新的冒烟运行验证 Amazon 实际页面

## 2026-07-22 · feature · v0.1.0

- **摘要**：接通 Amazon 商品详情页到图片工作台的安全策划上下文桥接
- **影响文件**：extension/src/studio/product-context.ts, extension/src/studio-bridge.ts, extension/src/background/index.ts, extension/src/content.ts, extension/tests, extension/manifest.json, README.md, CHANGELOG.md, docs/DEVELOPMENT.md, docs/USER_GUIDE.md
- **验证**：扩展 66 项测试、typecheck 与 production build 通过；图片工作台 262 项测试与 production build 通过
- **后续事项**：在 Chrome 重新加载 extension/dist，并用真实商品页对同步预览做一次小规模人工验收

## 2026-07-22 · fix · v0.1.0

- **摘要**：图片工作台商品同步改为按粘贴链接的站点与ASIN精确匹配已打开PDP，并补充空后台响应诊断
- **影响文件**：extension/src/studio/product-context.ts, extension/src/background/index.ts, extension/src/studio-bridge.ts, extension/tests, docs, amazon-image-studio同步入口与测试
- **验证**：图片工作台263项测试和生产构建通过；扩展68项测试、全项目typecheck和扩展生产构建通过
- **后续事项**：在chrome://extensions重新加载extension/dist后进行真实PDP联调；飞书文档同步需外部授权
