# Amazon Ads Console

Amazon 多店铺广告数据控制台第一版骨架。技术栈：Vue 3 + TypeScript + ECharts + FastAPI + PostgreSQL。

## 当前页面

- `/dashboard` 概览看板
- `/cpo-jobs` CPO 处理中心（核心 SOP 工作台）
- `/issues` 待确认异常
- `/products` 产品明细
- `/ad-types` 广告类型
- `/rules` 产品归属规则 / 广告类型映射
- `/reports` 报告管理

## SOP 领域原则

产品归属回答“算给谁”，广告类型回答“算在哪一类”，两者独立判断后再聚合。第一版只搭领域边界、枚举、异常码、任务状态和 mock API，不把完整 CPO SOP 硬编码成单个大函数。

分析层预留三个粒度：`product_daily_summary`、`product_daily_ad_type_l1`、`product_daily_ad_type_l2`。

## 启动 PostgreSQL

```bash
cp .env.example .env
docker compose up -d postgres
```

## 启动 FastAPI

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

健康检查：`GET http://localhost:8000/api/health`。当前页面 API 使用 mock/fallback 数据，所以 PostgreSQL 未启动时也可展示骨架。

## 启动 Vue

```bash
cd frontend
npm install
npm run dev
```

默认访问 `http://localhost:5173`。前端 API 地址可通过 `VITE_API_BASE` 修改。

## 架构方向

```text
Vue 3 / ECharts
      ↓ REST API
FastAPI services
      ↓
PostgreSQL
      ↓
事实层 → 业务映射层 → 分析消费层
```

后续优先继续开发：报告上传/字段识别 → CPO Job 状态机 → Issue 确认写回规则表 → 行级标准化 → 分配/分类 → 守恒校验 → 发布分析表。
