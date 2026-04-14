# 项目记忆 — Obsidian 知识库

## 仓库信息

- 类型：Obsidian 知识库（非代码项目）
- 路径：`D:\Download\agent-master`
- 唯一笔记：`欢迎.md`（默认引导文件）

## 用户偏好

- **所有 Skills 必须用中文编写**：SKILL.md 的 `name:`、`description:`、正文标题、说明文字均使用中文；代码块/命令保持原样
- **所有权限已全部开放**：`bypassPermissions: true` + `allow: ["*"]`（settings.local.json），执行任何工具无需确认
- 用户使用中文交流

## Skills 目录（`.claude/skills/`）

| 目录名 | name 字段 | 触发方式 |
|--------|-----------|---------|
| `ob笔记格式/` | `ob笔记格式` | 创建/编辑 Obsidian 笔记 |
| `ob数据库/` | `ob数据库` | 创建 `.base` 文件 |
| `白板/` | `白板` | 创建 `.canvas` 文件 |
| `ob命令行/` | `ob命令行` | CLI 控制 Obsidian |
| `网页抓取/` | `网页抓取` | 抓取网页保存到仓库 |
| `日记/` | `日记` | 创建今日日记 |
| `周记/` | `周记` | 创建本周回顾 |
| `收集/` | `收集` | 快速收集想法/任务/URL |
| `GitHub同步/` | `GitHub同步` | 推送/拉取仓库，同步记忆文件 |
| `飞书MCP/` | `飞书MCP` | 配置飞书 MCP Server，接入飞书消息/文档/日历 |
| `n8n部署/` | `n8n部署` | 上传工作流 JSON → 触发 webhook → 查执行结果 |

## n8n 实例

- API 密钥和端点见 `reference_n8n_api.md`
- 工作流 ID：`tXodaJYhhHa6GaVV`（Shopee 竞品监控）

## GitHub 仓库

- 地址：`https://github.com/p1524607703-blip/agent-master.git`
- 推送需要 Classic token（`ghp_` 开头），在 https://github.com/settings/tokens 生成，勾选 `repo` 权限
- remote URL 格式：`https://<ghp_token>@github.com/p1524607703-blip/agent-master.git`

## 已安装 CLI 工具

- `chub`：获取最新 API 文档
- `defuddle`：从网页提取干净 Markdown

## 选品工具服务信息

- OpenClaw 远程实例见 `reference_openclaw.md`（火山云，上海，SSH root@118.196.68.214）
- OpenClaw 本地实例（jarvis/friday）见 `reference_openclaw_local.md`
- MiniMax M2.5 最佳实践见 `reference_minimax_best_practices.md`
- 所有密钥存储在 `.env`（不提交 git）

## 团队协作工作流

见 `feedback_team_workflow.md`

- 决策层：Claude + Codex **必须共同讨论**，不允许单独决定，由 Claude 输出最终结果到 Obsidian
- UI 层：Claude（效果不佳时替换 Gemini）
- 代码：Codex 编写，Claude Review
- **调试工作流（强制）：发现问题 → 告诉 Codex 哪里错了、怎么改 → 让 Codex 执行**（Claude 不直接批量写代码文件）

## 选品工具项目（主项目）

- 整体进度见 `project_radar_ai_status.md`
- UI 设计规范见 `project_ui_design_system.md`（浅色 Teal 主题，2026-03-17 确定）
- 当前阶段：UI 视觉稿（01 已完成，02-05 待改稿）
- 下一阶段：UI 全部确认后 → Codex 搭建 Vue 3 + NestJS 项目骨架
