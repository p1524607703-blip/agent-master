# RADAR AI — 选品雷达

跨境电商选品工具，基于 Vue 3 + NestJS 全栈架构。

## 项目结构

```
选品工具/
├── frontend/          # Vue 3 前端
│   ├── src/
│   │   ├── pages/     # 5个页面视图
│   │   │   ├── Dashboard/        # 首页仪表盘
│   │   │   ├── TrendDiscovery/   # 趋势发现
│   │   │   ├── AIAnalysis/       # AI深度分析
│   │   │   ├── ProductBoard/     # 选品看板
│   │   │   └── AgentMonitor/     # Agent监控
│   │   ├── components/  # Sidebar / GlassCard / StatCard
│   │   ├── stores/      # Pinia: products / trends / agents
│   │   ├── router/      # Vue Router
│   │   └── assets/styles/variables.css
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── package.json
├── backend/           # NestJS 后端
│   ├── src/modules/   # products / trends / analysis / agents / alerts
│   ├── prisma/schema.prisma
│   └── .env.example
└── UI设计稿/          # HTML 视觉稿 01-05
```

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Vite + Element Plus + ECharts |
| 状态 | Pinia |
| 后端 | NestJS + PostgreSQL + Prisma + Redis + Bull |
| AI | MiniMax M2.5 |
| 部署 | Vercel (前端) + Railway (后端) |

## 快速启动

```bash
# 前端
cd frontend && npm install && npm run dev   # http://localhost:5173

# 后端
cd backend && npm install
cp .env.example .env   # 填写环境变量
npx prisma migrate dev
npm run start:dev      # http://localhost:3000
```
