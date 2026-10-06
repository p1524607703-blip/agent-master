# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## 仓库类型

这是一个采用 **Karpathy 三层架构** 的 Obsidian 知识库。知识管理规则见 **AGENTS.md**。

```
workspace/
├── raw/                # 原始素材层 — 只读
│   ├── 市场调研/
│   ├── 竞品数据/1688/
│   ├── 提示词实验/
│   └── 参考文档/
├── wiki/               # 结构化知识层 — AI 维护
│   ├── 跨境电商/
│   ├── AI工程/
│   ├── SOP与工作流/
│   ├── 个人成长/
│   └── attachments/
├── logs/               # INDEX.md + LOG.md
├── AGENTS.md           # 知识管理规则宪法
├── CLAUDE.md           # 本文件 — 技术环境指南
├── 00-收集箱/          # GTD inbox
├── Daily/              # 日记
├── _归档/              # 归档
├── aily-faas-field/    # 飞书字段捷径项目
├── .claude/skills/     # Skills (24 个 slash command)
├── .claude/memory/     # Agent memory
└── .learnings/         # 自改进系统
```

### 知识管理规则

所有知识库操作规则（Ingest / Query / Lint 流程、页面格式规范、wikilinks 要求等）见 **AGENTS.md**。CLAUDE.md 仅描述技术环境。

### Memory System (`.claude/memory/`)

`memory/MEMORY.md` 是索引，条目不超过 150 字符。Memory 文件使用 YAML frontmatter (`name`, `description`, `type`)。不存储代码模式、git 历史或临时任务状态。

### Self-Improvement System (`.learnings/`)

`ERRORS.md`、`LEARNINGS.md`、`FEATURE_REQUESTS.md`。由 `self-improving-agent` skill 使用。重大任务前应回顾。

## 代码项目（已移至 vault 外）

以下项目已移至 vault 同级目录：
- **选品工具 (RADAR AI)**：`../选品工具/` — Vue 3 + NestJS 全栈项目
- **企业网站**：`../企业网站/` — 芯威霆 + xwt-admin
- **竞品采集工具**：`../竞品采集工具/` — Amazon/Shopee/1688/Temu 爬虫

## 选品工具 Tech Stack (参考)

| Layer | Tech |
|-------|------|
| Frontend | Vue 3 + TypeScript + Vite + Element Plus + ECharts + Tailwind CSS |
| State | Pinia |
| Backend | NestJS 10 + Prisma 5 + Bull 4 (optional, requires Redis) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| E2E | Playwright |

## n8n Automation (`n8n-automation/`)

Amazon A+ 内容抓取和数据回填的工作流 JSON。通过 `n8n部署` skill 部署。

## 飞书字段捷径 (`aily-faas-field/`)

4 个 DeepSeek 驱动的飞书多维表格自定义字段，用于 Amazon A+ 优化。基于 `@lark-opdev/block-basekit-cli`。

```bash
npm run dev    # 本地测试
npm run build  # 构建
npm run pack   # 打包为 output/output.zip
```

4 个字段捷径：①A 核心卖点+Bullet重写、①B A+共用模块方案、② 做图风格生成、③ 做图提示词+素材清单。均使用 `deepseek-v4-pro`。

## Obsidian Syntax

- `[[wikilinks]]`、`![[embeds]]`、`==highlights==`、`%%comments%%`
- `> [!note]`、`> [!warning]-` callouts
- YAML frontmatter (tags, aliases, date, status)
- UTF-8, LF, 中文文件名有效
- 附件按文件名解析（已配置 `attachmentFolderPath: wiki/attachments`）

## Skills (Slash Commands)

Skills 在 `.claude/skills/` 中。名称为 `/skill-name`。

| Skill | 用途 |
|-------|------|
| `ob笔记格式` | Obsidian 笔记创建/编辑 |
| `ob数据库` | `.base` 文件操作 |
| `ob命令行` | Obsidian CLI 控制 |
| `白板` | `.canvas` 可视化 |
| `网页抓取` | `defuddle` 网页截取 |
| `日记` / `周记` | 日记/周回顾 |
| `收集` | 快速收集到收件箱 |
| `GitHub同步` | Git push/pull + memory 同步 |
| `飞书MCP` | 飞书消息/文档/日历 |
| `n8n部署` | n8n 工作流部署 |
| `视频转录总结` | 视频/音频 → 转录 → Obsidian |
| `bilibili字幕` / `bilibili总结` | B 站字幕提取 |
| `deeplearning字幕` | deeplearning.ai 课程字幕 |
| `reddit市场调研` | Reddit 调研 (Tavily) |
| `市场调研` | 品类系统调研 |
| `摄像头监控` | 小米 C700 监控 |
| `agent-browser` | 无头浏览器 |
| `浏览器截图` | 浏览器截图 |
| `tavily` | Tavily Web Search |
| `self-improving-agent` | 错误/学习捕获 |
| `sonoscli` | Sonos 控制 |
| `glm抢购` | GLM Coding Pro 抢购 |

## Installed CLI Tools

- `lark-cli` v1.0.19 — 飞书 API CLI
- `chub` — Context Hub
- `defuddle` — URL → Markdown
- `codex` — OpenAI Codex CLI
- `linkfoxskill` v0.1.13 — LinkFox 电商 Skills 搜索与安装 CLI

## AI Services

| Service | Model | Key |
|---------|-------|-----|
| DeepSeek | deepseek-v4-pro | `DEEPSEEK_API_KEY` |
| MiniMax | M2.5 | `.env` |

## Key Config

- `.env` — API keys — **never commit**
- `.claude/settings.local.json` — `bypassPermissions: true`
- `.obsidian/app.json` — `attachmentFolderPath: wiki/attachments`
