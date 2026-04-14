# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Type

This is primarily an **Obsidian vault** (knowledge base). The working directory `D:\Download\agent-master` is the vault root. It also contains `选品工具/`, a full-stack software project (Vue 3 + NestJS).

## Vault Structure

```
agent-master/
├── 00-收集箱/          # Inbox for quick-captured items
├── 01-产品/            # Product research (TikTok ads, 竞品分析, market research)
├── 02-AI工程/          # AI engineering (bilibili总结, n8n workflows, OpenClaw)
├── 03-知识库/          # Knowledge base (AI tools, 跨境电商)
├── 04-SOP与任务/       # SOPs, task tracking, main tasks
├── 05-个人/            # Personal (resume, interview prep, Amazon learning)
├── Daily/              # Daily notes
├── _归档/              # Archive
├── memory/             # Agent memory files (persist across conversations)
├── .learnings/         # Self-improvement: ERRORS.md, LEARNINGS.md, FEATURE_REQUESTS.md
├── .claude/skills/     # Claude Code skills (26 slash commands)
└── 选品工具/           # RADAR AI — full-stack software project
```

No community Obsidian plugins are installed. No `.cursor/` or `.github/copilot-instructions.md` rules exist.

## RADAR AI (选品工具) — Architecture

Cross-border e-commerce product selection tool. Full PRD, IA, DB design, API design docs are in `选品工具/` root.

### Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | Vue 3 + TypeScript + Vite + Element Plus + ECharts + Tailwind CSS |
| State | Pinia |
| Backend | NestJS 10 + Prisma 5 + Bull 4 (job queues) |
| Database | SQLite (dev) / PostgreSQL (prod) |
| AI | MiniMax M2.5 |
| E2E | Playwright (`选品工具/e2e/`, baseURL `http://localhost:5174`) |
| Deploy | Frontend → Vercel, Backend → Railway |

### Dev Commands

```bash
# 前端 (http://localhost:5173)
cd 选品工具/frontend && npm install && npm run dev
npm run build          # vue-tsc && vite build
npm run preview        # preview production build

# 后端 (http://localhost:3000)
cd 选品工具/backend && npm install
cp .env.example .env   # fill in env vars (see .env.example for required keys)
npx prisma migrate dev # initialize database
npm run start:dev      # watch mode
npm run build          # production build
npm run start:prod     # production start
npm run lint           # ESLint
npm run test           # Jest unit tests
npm run seed           # seed sample data
npx prisma db push     # sync schema without migration

# E2E tests (run from 选品工具/ root)
npx playwright test    # runs against localhost:5174
```

### Frontend Architecture (`选品工具/frontend/src/`)

- **Pages** (5 views): Dashboard, TrendDiscovery, AIAnalysis, ProductBoard, AgentMonitor
- **Components**: GlassCard, StatCard, Sidebar (glass-morphism design system, teal palette)
- **Stores** (Pinia): `products`, `trends`, `agents`
- **Router**: Vue Router 4 with 5 routes
- **Proxy**: Vite proxies `/api` → `http://localhost:3000`
- **Design**: Tailwind with custom teal color palette, CSS variables in `assets/styles/variables.css`

### Backend Architecture (`选品工具/backend/src/`)

NestJS modular structure with conditional Bull queue (requires Redis):

| Module | Purpose |
|--------|---------|
| `products/` | CRUD for product records |
| `trends/` | Trend data ingestion and queries |
| `analysis/` | AI analysis via MiniMax M2.5 |
| `agents/` | Agent task orchestration and monitoring |
| `alerts/` | Alert generation and notification |
| `scrapers/` | Data scraping adapters |
| `modules/scheduler/` | Cron-based scheduled tasks (scan + report) |
| `prisma/` | Prisma ORM service module |

### Prisma Models (4 tables)

- **Product**: id, name, category, priceMin/Max, score (0-100), status (watching/recommended/dropped)
- **TrendData**: productId → Product, platform (tiktok/reddit/google/facebook), metric (views/mentions/search_volume/ad_count), value, deltaPercent
- **Alert**: productId → Product, type (price_drop/surge/competitor/stock), severity (info/warning/critical), isRead
- **AgentTask**: name, type (scan/ai_analysis/alert_check/report), status (pending/running/completed/failed), progress, result

All models cascade-delete children. Status fields are string enums (not Prisma enums) for SQLite compatibility.

### Design Documents (in `选品工具/`)

PRD, feasibility analysis, IA + user flows, technical architecture, DB design (22KB), API design (18KB), and development progress tracker are all in the `选品工具/` directory as Markdown files.

## Obsidian Notes — Syntax & Conventions

- **OFM (Obsidian Flavored Markdown)**: `[[wikilinks]]`, `![[embeds]]`, `==highlights==`, `%%comments%%`, `[[Note#^block-id]]`
- **Callouts**: `> [!note]`, `> [!warning]-` (collapsible)
- **Frontmatter** (YAML between `---`): tags, aliases, date, status
- **Encoding**: UTF-8, LF line endings. Chinese filenames are valid.
- Attachments (images, PDFs) can be placed anywhere; Obsidian resolves by filename.

## Skills (Slash Commands)

Skills live in `.claude/skills/`. Invoke with `/skill-name` or let Claude auto-activate based on context.

| Skill | Trigger |
|-------|---------|
| `ob笔记格式` | Creating/editing Obsidian notes, wikilinks, callouts |
| `ob数据库` | Working with `.base` files (database/table views) |
| `白板` | Creating `.canvas` files (visual boards) |
| `ob命令行` | Controlling Obsidian via CLI (app must be running) |
| `网页抓取` | Clipping web pages via `defuddle` |
| `日记` / `周记` | Daily notes, weekly reviews |
| `收集` | Quick-saving ideas/tasks/URLs to inbox |
| `GitHub同步` | Push/pull repo + sync memory files |
| `飞书MCP` | Feishu/Lark messages, docs, calendar |
| `n8n部署` | Upload n8n workflows, test via webhook |
| `视频转录总结` | Video/audio → transcription → Obsidian notes |
| `bilibili字幕` / `bilibili总结` | Bilibili subtitle extraction / full summarization |
| `deeplearning字幕` | deeplearning.ai course subtitle extraction |
| `reddit市场调研` | Reddit product research via Tavily + API |
| `市场调研` | Systematic product category research |
| `摄像头监控` | Xiaomi C700 camera: screenshots, detection (requires go2rtc.exe) |
| `agent-browser` | Headless browser automation (Rust CLI) |
| `gemini-designer` | Delegate UI/web design to Gemini via ZenMux |
| `codex` | Delegate coding tasks to Codex CLI |
| `tavily` | Production Tavily web search integration |
| `self-improving-agent` | Capture errors/learnings for continuous improvement |
| `ui-ux-pro-max` | Professional UI/UX design |
| `sonoscli` | Control Sonos speakers |

## Installed CLI Tools

- `chub` — Context Hub: `chub search <term>` / `chub get <id>`
- `defuddle` — Extract clean Markdown from URLs: `defuddle parse <url> --md`
- `codex` — OpenAI Codex CLI (installed at root `package.json`)

## Key Config Files

- `.env` — API keys (MiniMax, ZenMux, OpenClaw, Reddit, Tavily, Bilibili, etc.) — in `.gitignore`
- `.claude/settings.local.json` — Claude Code permissions and hooks
- `选品工具/backend/.env.example` — Backend environment template
- `选品工具/backend/railway.json` + `Procfile` — Railway deployment config
- `选品工具/frontend/vercel.json` — Vercel deployment config
