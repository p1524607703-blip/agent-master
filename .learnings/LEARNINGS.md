# LEARNINGS.md

自改进学习记录

---

## [LRN-20260821-002] correction

**Logged**: 2026-08-21T00:00:00-04:00
**Priority**: high
**Status**: resolved
**Area**: docs

### Summary
Amazon Ads API 当前申请表中，直接广告主也必须填写以 `https://` 开头的公司网站。

### Details
先前依据公开入口对直接广告主与 Partner Network 的差异，错误地把网站要求描述为可能仅适用于 Partner Network。用户提供的当前注册页截图明确显示，“公司网站”是直接广告主表单中的必填字段，并要求 HTTPS 地址。

### Suggested Action
以后回答 Amazon Ads API 申请条件时，应区分“Partner Network 对网站内容的正式政策要求”和“直接广告主表单同样存在的网站必填字段”。没有网站时，应建议创建真实、公开、可审核的公司介绍页，不得填写虚假网址、登录后才能访问的页面或无关仓库地址。

### Metadata
- Source: user_feedback
- Related Files: `/Users/panjinlong/Documents/agent-master/.learnings/LEARNINGS.md`
- Tags: amazon-ads-api, direct-advertiser, application, website
- Pattern-Key: verify.current_application_form_requirements

---

## [LRN-20260821-001] correction

**Logged**: 2026-08-21T02:55:00-04:00
**Priority**: critical
**Status**: resolved
**Area**: infra

### Summary
GitHub 只能备份和分发 Codex 插件文件，不能把一个个人 ChatGPT 账号中注册的开发者模式应用连接、应用所有权或 Tunnel 可见范围复制给另一个个人账号。

### Details
测试机使用个人版 ChatGPT/Codex，没有 Business 工作区。此前安装说明错误地要求“公司 OpenAI 工作区”，并把仓库中的固定 `.app.json` 技术 ID 当作可跨个人账号继承的授权，导致测试机无法完成验收。OpenAI 的本地插件流程要求先在目标 ChatGPT 账号的开发者模式中注册 MCP 连接，再将该账号生成的技术 ID 写入个人插件；Secure MCP Tunnel 还必须关联目标个人账号对应的 Platform 个人组织和 ChatGPT 个人空间。静态仓库备份本身不满足这两项条件。

### Suggested Action
个人账号分发可以使用安装引导插件，但“安装器无账号绑定”不代表它能绕过 Secure MCP Tunnel 的云端授权。必须先验证目标账号在“新插件 → 隧道”中确实能发现目标 Tunnel，再由 Codex 为当前个人账号注册连接并生成本地 `.app.json`。不得把 Business/公司工作区当作前提，也不得声称固定应用技术 ID或插件安装包可跨账号复制 Tunnel 使用权。发布前必须在第二个个人账号上做端到端验收；若要求任意个人账号无需管理员预关联即可使用，则改用带 OAuth 2.1、人员白名单和分级权限的稳定公共 HTTPS MCP，而不是 Secure MCP Tunnel。

### Metadata
- Source: user_feedback
- Related Files: `/Users/panjinlong/Documents/amazon-ads-codex-marketplace`, `/Users/panjinlong/Documents/amazon-ads-admin-codex-marketplace`
- Tags: codex, plugin, personal-account, app-id, secure-mcp-tunnel, distribution
- Pattern-Key: avoid.cross_account_app_id_assumption

---

## [LRN-20260820-001] correction

**Logged**: 2026-08-20T03:30:00-04:00
**Priority**: critical
**Status**: resolved
**Area**: infra

### Summary
不能为了制作运营只读版而切换用户正在使用的 25 工具网页端插件或现有 Tunnel；测试版必须复制为独立连接。

### Details
短暂把现有 `amazon-ads-local` Tunnel 的 MCP 启动入口切到只读服务，虽然之后恢复了 25 工具运行时，但 ChatGPT 网页端应用缓存了 10 工具目录，导致用户现有会话无法看到原有写入和管理员能力。插件包引用现有应用 ID 也会把运营安装包错误地指向高权限连接。

### Suggested Action
以后涉及生产插件能力变体时，先创建独立 MCP 入口、Tunnel、注册应用和插件 ID，再做测试。不得复用生产 Tunnel，不得让低权限分发包引用生产应用。发布前同时验证生产应用工具数不变和测试应用最小权限。

### Metadata
- Source: user_feedback
- Related Files: `/Users/panjinlong/Documents/amazon-ads-data/src/amazon_ads_data/mcp_readonly_server.py`, `/Users/panjinlong/Documents/amazon-ads-codex-marketplace`
- Tags: mcp, tunnel, plugin, permissions, isolation, production-safety
- Pattern-Key: isolate.production_mcp_variants

---

## [LRN-20260817-001] best_practice

**Logged**: 2026-08-17T22:31:00-04:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
依赖个人 Mac 的网页端 ChatGPT MCP 不能只提供手动启动脚本；必须同时固化登录自启动、
崩溃恢复、受保护目录隔离、VPN 启动顺序和中国云服务直连规则。

### Details
单纯证明 MCP 能连接 RDS 不能代表重启后可用。可靠验收必须包含：模拟登录重新加载、
主动终止进程后自动拉起、隧道 health/ready、连续数据库读连接、管理员连接，以及
VPN 节点切换下的国内 RDS 直连。对于 macOS LaunchAgent，代码与入口不能依赖
Documents 目录，传给第三方 stdio 启动器的命令路径也应避免空格。

### Suggested Action
以后部署本地 MCP 时，把“登录重载 + 进程崩溃 + VPN 重启 + 连续数据库调用”作为固定
验收矩阵；若要求电脑关机时仍可用，应直接部署云端常驻 MCP，而不是继续加固本地隧道。

### Metadata
- Source: error
- Related Files: `/Users/panjinlong/Documents/amazon-ads-data/README.md`
- Tags: mcp, launchagent, cute-cloud, rds, reliability
- Pattern-Key: harden.macos_launchagent_mcp

---

## [LRN-20260605-001] correction

**Logged**: 2026-06-05T04:35:00Z
**Priority**: high
**Status**: pending
**Area**: config

### Summary
该用户的协作代码任务完成后，应默认提交并推送到 GitHub，而不是只保留本地改动。

### Details
用户明确指出，不推送会阻断与同事的协同。后续在已配置远程仓库的项目中，完成实现和验证后应把 commit、push 作为默认收尾；如果远程分支已分叉，应创建独立 `codex/` 分支，避免覆盖同事提交，并清楚返回分支、提交号和 PR 链接。

### Suggested Action
每次代码任务结束前检查 `git status`、执行相关验证、提交、推送，并报告远程状态。仅在用户明确要求不推送、仓库无远程、认证失败或工作区包含无法判断归属的改动时暂停。

### Metadata
- Source: user_feedback
- Related Files: `/Users/panjinlong/Documents/amc-hermes-dashboard`
- Tags: github, collaboration, push, workflow

---
