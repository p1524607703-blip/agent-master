---
title: 选品工具 - API 接口设计
tags:
  - 项目/选品工具
  - API设计
date: 2026-03-16
status: 已完成
aliases:
  - 选品工具API文档
---

# 选品工具 — API 接口设计

> [!info] 决策说明
> 本文档由 Claude + Codex 联合讨论，整合双方方案后输出。
> 关联文档：[[选品工具-数据库设计]] | [[选品工具-技术架构方案]] | [[选品工具开发进度]]

---

## 一、全局规范

### 1.1 Base URL

```
开发环境：http://localhost:3000/api/v1
生产环境：https://api.yourproduct.com/api/v1
```

### 1.2 API 版本策略

- URL 路径版本：`/api/v1/`，保留 2 个大版本，6 个月过渡期
- 废弃通知响应头：`Deprecation: true` + `Sunset: 日期`
- 升级提示：`Link: <v2/path>; rel="successor-version"`

### 1.3 统一响应格式

```json
// ✅ 成功
{
  "success": true,
  "data": { ... }
}

// ✅ 成功（分页）
{
  "success": true,
  "data": [ ... ],
  "meta": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "hasMore": true
  }
}

// ❌ 失败
{
  "success": false,
  "error": {
    "code": "AUTH_001",
    "message": "Token 已过期，请重新登录",
    "details": { }
  }
}
```

### 1.4 错误码规范

| 错误码 | HTTP状态码 | 说明 |
|--------|-----------|------|
| AUTH_001 | 401 | Token 已过期 |
| AUTH_002 | 401 | 用户名或密码错误 |
| AUTH_003 | 403 | 邮箱未验证 |
| AUTH_004 | 401 | Refresh Token 无效/已吊销 |
| PERM_001 | 403 | 权限不足 |
| RATE_001 | 429 | 请求频率超限 |
| VALID_001 | 400 | 参数校验失败 |
| NOT_FOUND | 404 | 资源不存在 |
| CONFLICT | 409 | 资源冲突（如邮箱已注册） |
| SERVER_ERR | 500 | 服务器内部错误 |
| TASK_001 | 202 | 任务已进入队列（异步处理） |

### 1.5 鉴权说明

| 标识 | 说明 |
|------|------|
| 🔓 公开 | 无需 Token |
| 🔐 需登录 | 需要有效 Access Token（`Authorization: Bearer <token>`） |
| 👥 租户 | 需要登录 + 属于当前租户 |
| 👑 管理员 | 需要 admin 角色 |

**Access Token 有效期：15 分钟**
**Refresh Token 有效期：7 天**

### 1.6 限流规范（响应头）

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1705312800
```

| 计划 | 通用接口 | AI 分析接口 | 数据采集接口 |
|------|---------|-----------|------------|
| Free | 100 req/h | 10 次/天 | 50 req/h |
| Pro | 1000 req/h | 100 次/天 | 500 req/h |
| Enterprise | 不限 | 不限 | 不限 |

### 1.7 幂等性

触发异步任务的 POST 接口支持幂等键，防止重复提交：

```
Idempotency-Key: <uuid>
```

---

## 二、认证模块（Auth）

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| POST | `/auth/register` | 🔓 | 注册（自动创建个人租户） |
| POST | `/auth/login` | 🔓 | 登录 |
| POST | `/auth/refresh` | 🔓 | 刷新 Access Token |
| POST | `/auth/logout` | 🔐 | 退出（吊销 Refresh Token） |
| POST | `/auth/password/change` | 🔐 | 修改密码 |
| POST | `/auth/password/reset/send` | 🔓 | 发送重置验证码 |
| POST | `/auth/password/reset/verify` | 🔓 | 验证并重置密码 |
| POST | `/auth/email/verify` | 🔓 | 邮箱验证 |

### 关键接口示例

**POST `/auth/login`**
```json
// 请求
{ "email": "user@example.com", "password": "Passw0rd!" }

// 响应 200
{
  "success": true,
  "data": {
    "accessToken": "eyJ...",
    "refreshToken": "eyJ...",
    "expiresIn": 900,
    "user": { "id": "uuid", "email": "user@example.com", "nickname": "张三" }
  }
}
```

**POST `/auth/refresh`**
```json
// 请求
{ "refreshToken": "eyJ..." }

// 响应 200
{ "success": true, "data": { "accessToken": "eyJ...", "expiresIn": 900 } }
```

---

## 三、用户与团队管理（User & Team）

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| GET | `/users/me` | 🔐 | 获取当前用户信息 |
| PATCH | `/users/me` | 🔐 | 更新个人信息 |
| GET | `/users/me/preferences` | 🔐 | 获取用户偏好（UI 模式/时区/语言） |
| PATCH | `/users/me/preferences` | 🔐 | 更新用户偏好 |
| GET | `/teams` | 🔐 | 获取我加入的团队列表 |
| POST | `/teams` | 🔐 | 创建团队 |
| POST | `/teams/:tenantId/switch` | 🔐 | 切换到指定团队 |
| GET | `/teams/:tenantId` | 👥 | 团队详情 |
| PATCH | `/teams/:tenantId` | 👑 | 更新团队信息 |
| POST | `/teams/:tenantId/members/invite` | 👑 | 邀请成员（发送邮件） |
| GET | `/teams/:tenantId/members` | 👥 | 成员列表 |
| PATCH | `/teams/:tenantId/members/:userId` | 👑 | 更新成员角色 |
| DELETE | `/teams/:tenantId/members/:userId` | 👑 | 移除成员 |
| POST | `/invitations/:invitationId/accept` | 🔐 | 接受邀请 |

**用户偏好示例（`GET /users/me/preferences`）**
```json
{
  "success": true,
  "data": {
    "uiMode": "beginner",       // beginner | professional
    "language": "zh-CN",
    "timezone": "Asia/Shanghai",
    "defaultMarket": "US"
  }
}
```

---

## 四、趋势数据查询（Trends）

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| GET | `/trends/reddit` | 👥 | Reddit 热帖（含中文摘要） |
| GET | `/trends/google` | 👥 | Google Trends 时序数据 |
| GET | `/trends/facebook-ads` | 👥 | Facebook 广告库 |
| GET | `/trends/tiktok` | 👥 | TikTok 热门内容 |
| POST | `/trends/aggregate` | 👥 | 多平台数据聚合查询 |

### 通用查询参数（所有趋势接口）

| 参数 | 类型 | 说明 |
|------|------|------|
| `keyword` | string | 关键词搜索 |
| `country` | string | 国家代码（US/GB/AU） |
| `page` | number | 页码，默认 1 |
| `limit` | number | 每页数量，默认 20，最大 100 |
| `sortBy` | string | 排序字段 |
| `order` | string | `asc` / `desc` |

### Reddit 特有参数

| 参数 | 说明 |
|------|------|
| `subreddit` | 指定版块（如 `dropship,ecommerce`） |
| `sort` | `hot` / `new` / `top` / `rising` |
| `timeRange` | `hour/day/week/month/year/all` |

### Reddit 响应（含 AI 翻译摘要）

```json
{
  "success": true,
  "data": [
    {
      "id": "t3_abc123",
      "subreddit": "r/dropship",
      "title": "Best trending products for 2026?",
      "summary_zh": "讨论2026年最值得关注的跨境选品，无线耳机和智能家居产品被频繁提及",
      "score": 1542,
      "commentCount": 287,
      "url": "https://reddit.com/...",
      "createdAt": "2026-03-15T08:00:00Z",
      "dataUpdatedAt": "2026-03-16T06:00:00Z"
    }
  ],
  "meta": { "page": 1, "limit": 20, "total": 1543, "hasMore": true }
}
```

### 多平台聚合（`POST /trends/aggregate`）

```json
// 请求
{
  "keywords": ["wireless earbuds", "smart watch"],
  "sources": ["reddit", "google", "tiktok"],
  "timeRange": "30d",
  "country": "US"
}

// 响应
{
  "success": true,
  "data": {
    "summary": {
      "totalMentions": 15420,
      "trendDirection": "rising",
      "velocity": 12.5
    },
    "bySource": {
      "reddit":  { "mentions": 8500,  "posts": 234 },
      "google":  { "interest": 78,    "change": "+15%" },
      "tiktok":  { "views": "2.5M",   "engagement": "8.5%" }
    },
    "topProducts": [
      { "name": "AirPods Pro 2", "score": 92, "mentions": 3200 }
    ]
  }
}
```

---

## 五、选品分析（Analysis）

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| POST | `/analysis/quick` | 👥 | 新手快速分析（一句话结论） |
| POST | `/analysis/trigger` | 👥 | 触发专业深度分析（异步） |
| GET | `/analysis/result/:taskId` | 👥 | 查询分析结果（轮询或 WebSocket） |
| GET | `/analysis/history` | 👥 | 分析历史记录 |

### 新手快速分析（`POST /analysis/quick`）

```json
// 请求
{ "productName": "无线蓝牙耳机" }

// 响应 200（同步，10秒内返回）
{
  "success": true,
  "data": {
    "score": 82,
    "verdict": "推荐",
    "oneLiner": "市场需求强劲，竞争中等，利润空间约35%，适合中端定价切入",
    "pros": ["Google Trends热度上升中", "Reddit讨论活跃", "利润空间达标"],
    "cons": ["头部品牌占据大部分市场份额", "需差异化定位"],
    "nextSteps": ["深入竞品分析", "查看Facebook在投广告", "联系供应商报价"]
  }
}
```

### 触发深度分析（`POST /analysis/trigger`）

```json
// 请求
{
  "mode": "professional",
  "product": {
    "name": "Wireless Earbuds",
    "category": "electronics",
    "keywords": ["bluetooth", "noise cancelling"],
    "targetMarket": ["US", "UK"],
    "priceRange": { "min": 20, "max": 150, "currency": "USD" }
  },
  "dataSources": ["reddit", "google", "tiktok", "facebook"]
}

// 响应 202
{
  "success": true,
  "data": {
    "taskId": "analysis_abc123",
    "status": "queued",
    "estimatedSeconds": 60,
    "wsChannel": "/ws/v1/analysis/analysis_abc123"
  }
}
```

### 查询分析结果（`GET /analysis/result/:taskId`）

```json
{
  "success": true,
  "data": {
    "taskId": "analysis_abc123",
    "status": "completed",   // queued | processing | completed | failed
    "progress": 100,
    "result": {
      "marketDemand":  { "score": 85, "summary": "市场需求强劲" },
      "competition":   { "score": 65, "summary": "竞争中等，建议差异化" },
      "profitMargin":  { "score": 78, "estimated": "35-45%" },
      "seasonality":   { "score": 72, "peakSeasons": ["Nov-Dec"] },
      "riskAssessment":{ "score": 70, "risks": [...] },
      "recommendation":{ "action": "buy", "confidence": 85, "notes": [...] }
    }
  }
}
```

---

## 六、选品看板（Boards）

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| GET | `/boards` | 👥 | 看板列表（含产品数量） |
| POST | `/boards` | 👥 | 创建看板 |
| PATCH | `/boards/:boardId` | 👥 | 更新看板信息 |
| DELETE | `/boards/:boardId` | 👑 | 删除看板 |
| POST | `/boards/:boardId/products` | 👥 | 添加产品到看板 |
| GET | `/boards/:boardId/products` | 👥 | 看板产品列表 |
| PATCH | `/boards/:boardId/products/:productId` | 👥 | 更新备注/排序 |
| PATCH | `/boards/:boardId/products/:productId/stage` | 👥 | 漏斗阶段流转 |
| DELETE | `/boards/:boardId/products/:productId` | 👥 | 从看板移除 |
| POST | `/boards/:boardId/products/batch` | 👥 | 批量操作（移动/删除/标签） |
| GET | `/boards/export` | 👥 | 导出看板数据（CSV/Excel） |

### 漏斗阶段流转（`PATCH /boards/:boardId/products/:productId/stage`）

```json
// 请求
{ "stage": "tracking", "reason": "数据不错，持续关注" }

// 响应 200
{
  "success": true,
  "data": {
    "productId": "prod_xyz",
    "fromStage": "saved",
    "toStage": "tracking",
    "changedAt": "2026-03-16T10:00:00Z"
  }
}
```

---

## 七、Agent 监控任务（Agent Tasks）

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| POST | `/agent/tasks` | 👥 | 创建监控任务 |
| GET | `/agent/tasks` | 👥 | 任务列表 |
| GET | `/agent/tasks/:taskId` | 👥 | 任务详情 |
| PATCH | `/agent/tasks/:taskId` | 👥 | 更新任务配置 |
| POST | `/agent/tasks/:taskId/toggle` | 👥 | 启用/暂停 |
| POST | `/agent/tasks/:taskId/run` | 👥 | 立即手动执行 |
| DELETE | `/agent/tasks/:taskId` | 👑 | 删除任务 |
| GET | `/agent/tasks/:taskId/runs` | 👥 | 执行历史列表 |
| GET | `/agent/tasks/:taskId/runs/:runId/logs` | 👥 | 执行日志详情 |

### 创建监控任务（`POST /agent/tasks`）

```json
{
  "name": "无线耳机每日监控",
  "taskType": "reddit_monitor",
  "sourceConfig": {
    "subreddits": ["dropship", "ecommerce"],
    "keywords": ["wireless earbuds", "bluetooth headphones"]
  },
  "scheduleCron": "0 9 * * *",       // 每天早上9点
  "scheduleType": "cron",
  "enableAiAnalysis": true,
  "notifyConfig": {
    "channelIds": ["channel_uuid_1"],
    "onlyWhenNewFound": true          // 只在发现新内容时推送
  }
}
```

---

## 八、推送通知（Notifications）

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| GET | `/notifications/channels` | 🔐 | 获取渠道配置列表 |
| POST | `/notifications/channels` | 🔐 | 新增渠道（微信/飞书/邮件） |
| PATCH | `/notifications/channels/:channelId` | 🔐 | 更新渠道配置 |
| DELETE | `/notifications/channels/:channelId` | 🔐 | 删除渠道 |
| POST | `/notifications/channels/:channelId/verify` | 🔐 | 发送测试通知验证渠道 |
| GET | `/notifications` | 🔐 | 通知记录列表 |
| POST | `/notifications/:id/read` | 🔐 | 标记已读 |
| POST | `/notifications/read-all` | 🔐 | 全部标记已读 |
| DELETE | `/notifications/:id` | 🔐 | 删除通知 |
| GET | `/notifications/settings` | 🔐 | 通知偏好设置 |
| PATCH | `/notifications/settings` | 🔐 | 更新通知偏好 |

### 渠道配置示例

```json
// POST /notifications/channels
{
  "channelType": "feishu",
  "config": {
    "webhookUrl": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
  },
  "preferences": {
    "notifyNewProduct": true,
    "notifyTrendAlert": true,
    "notifyTaskFailed": true,
    "notifyDailyReport": true,
    "quietHours": { "enabled": true, "start": "22:00", "end": "08:00", "timezone": "Asia/Shanghai" }
  }
}
```

---

## 九、OpenClaw 专用 Agent API

> [!warning] 设计原则
> 这套 API 专为 OpenClaw AI Agent 设计，结构化数据输出，版本锁定，不随前端变更而改变。
> Agent 通过此 API 而非网页 DOM 获取数据，确保稳定性。

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| GET | `/agent/v1/trends` | 🔐+API Key | 获取趋势数据（结构化） |
| GET | `/agent/v1/products` | 🔐+API Key | 获取选品列表 |
| POST | `/agent/v1/analyze` | 🔐+API Key | 提交分析任务 |
| GET | `/agent/v1/results/:taskId` | 🔐+API Key | 获取分析结果 |
| GET | `/agent/v1/boards` | 🔐+API Key | 获取看板数据 |
| POST | `/agent/v1/boards/:boardId/products` | 🔐+API Key | Agent 自动加入看板 |

### 鉴权方式（Agent API 专用）

```
Authorization: Bearer <user_token>
X-Agent-Key: <agent_api_key>    // 在设置页生成的专用密钥
```

### 趋势数据（`GET /agent/v1/trends`）

```json
// 响应（结构化，适合 Agent 解析）
{
  "success": true,
  "data": {
    "generatedAt": "2026-03-16T09:00:00Z",
    "period": "last_24h",
    "topTrending": [
      {
        "keyword": "wireless earbuds",
        "platforms": ["reddit", "tiktok"],
        "heatScore": 87,
        "direction": "rising",
        "changePercent": 15,
        "summary": "多个科技版块热议，TikTok短视频带动流量"
      }
    ]
  }
}
```

---

## 十、WebSocket 规范

> [!note] 实时通信场景
> 用于：AI 分析进度推送、任务执行状态、实时通知

**连接地址：**
```
ws://api.yourproduct.com/ws/v1?token=<access_token>
```

**事件类型：**

```json
// 分析进度
{ "type": "analysis.progress", "taskId": "abc", "progress": 45, "stage": "正在分析竞争格局" }

// 分析完成
{ "type": "analysis.completed", "taskId": "abc", "resultUrl": "/analysis/result/abc" }

// 任务执行通知
{ "type": "agent.task.completed", "taskId": "abc", "newItemsCount": 23 }

// 系统通知
{ "type": "notification.new", "notificationId": "n_abc", "title": "今日选品日报已生成" }
```

---

## 十一、其他工具接口

| Method | Path | 鉴权 | 描述 |
|--------|------|------|------|
| GET | `/health` | 🔓 | 健康检查（K8s/负载均衡探针） |
| GET | `/export/boards/:boardId` | 👥 | 导出看板（`?format=csv\|xlsx`） |
| POST | `/import/products` | 👥 | 批量导入产品（CSV 上传） |
| GET | `/search` | 👥 | 全局搜索（产品/看板/分析记录） |

---

## 十二、接口总览速查表

| 模块 | 接口数 | 特殊说明 |
|------|-------|---------|
| 认证 Auth | 8 | 含邮箱验证、密码重置 |
| 用户与团队 | 14 | 含用户偏好（UI模式/时区） |
| 趋势数据 | 5 | Reddit 含 AI 中文摘要 |
| 选品分析 | 4 | 快速（同步）+ 深度（异步） |
| 选品看板 | 10 | 三段漏斗 + 批量操作 + 导出 |
| Agent 任务 | 9 | 含执行日志和历史 |
| 推送通知 | 11 | 含渠道验证 + 免打扰时段 |
| OpenClaw API | 6 | 专用稳定接口，版本独立 |
| WebSocket | — | 分析进度 + 实时通知 |
| 工具接口 | 4 | 健康检查 + 导入导出 + 全局搜索 |
| **合计** | **71** | |

---

## 十三、风险清单

### 🔴 高风险
| 风险 | 应对措施 |
|------|---------|
| AI 分析接口无限流，成本失控 | 按租户计划设置每日配额，超额返回 429 |
| Agent API 被恶意爬取 | 独立 API Key + IP 白名单 + 严格限频 |
| 异步任务结果丢失 | 结果持久化到 DB，WebSocket 断线重连后可轮询补偿 |

### 🟡 中风险
| 风险 | 应对措施 |
|------|---------|
| 幂等键未实现，重复提交分析任务 | 服务端校验 `Idempotency-Key`，相同请求返回原任务 |
| 文件上传无大小限制 | `POST /import/products` 限制 5MB，格式校验 |
| WebSocket 连接数过多 | 单用户最多 3 个连接，超限关闭旧连接 |

---

## 十四、Claude vs Codex 分歧说明

> [!note] 关键决策理由
> - **`/users/me/preferences`**（Claude 补充）：UI 模式（新手/专业）必须持久化到服务端，跨设备同步
> - **`/health` 健康检查**（Claude 补充）：K8s 部署和负载均衡探针必备
> - **WebSocket 规范**（Codex 发现遗漏，Claude 补充完整定义）：分析进度实时推送
> - **幂等键 Idempotency-Key**（Claude 补充）：防止网络重试导致重复提交分析任务
> - **`/agent/v1/` 专用前缀**（双方共识）：OpenClaw 专用接口版本独立，前端重构不影响 Agent
> - **导出/导入接口**（Codex 发现遗漏，Claude 补充）：B 端团队必需功能
> - **渠道验证接口**（Claude 补充）：推送渠道配置完需发测试通知确认可用
