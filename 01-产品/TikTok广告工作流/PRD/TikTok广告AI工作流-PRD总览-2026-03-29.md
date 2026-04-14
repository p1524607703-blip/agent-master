---
title: TikTok 广告 AI 全链路工作流 — 总 PRD v2
tags:
  - PRD
  - TikTok
  - 广告
  - AI工作流
  - 浏览器插件
  - 自动化
date: 2026-03-29
status: 审核修订版
project: 鞋类跨境广告
aliases:
  - TikTok广告PRD
version: v2.0（三方评审后修订）
---

# TikTok 广告 AI 全链路工作流 — 总 PRD v2

> [!info] 修订说明
> 本版本经产品经理、开发工程师、模拟用户（竞品分析员+广告投手）三方联合评审后修订。
> v1 → v2 主要变更：①修复3个项目级致命问题 ②合并出图+视频为"素材生产"阶段 ③明确 TypeTale 定位 ④补充完整接口 Schema ⑤每阶段新增人工卡点

---

## 一、背景与目标

### 1.1 核心痛点

| 痛点     | 当前状态               | 期望状态                     |
| ------ | ------------------ | ------------------------ |
| 创意同质化  | 竞品分析停留在感性判断，无结构化输出 | 每条视频自动拆解为可复用的创意公式        |
| 文案依赖经验 | 人工写文案，慢且不稳定        | 基于创意数据库批量生成高转化文案         |
| 出图效率低  | 手动 PS，每周最多5条       | 批量生成，每天20-50条可用素材        |
| 素材链路割裂 | 文案/图/视频各自为战        | 统一 Brief → 文案 → 素材生产的流水线 |
| 投放靠人盯  | 人工看数据调预算           | Report Agent 异常自动告警，投手决策 |

### 1.2 目标

1. **自动化率**：全链路人工介入率 < 30%（v1 中 <20% 过于激进，已修正）
2. **素材产能**：从每周5条提升到每天20-50条可用素材
3. **创意质量**：唯一创意公式占比 > 60%（可通过数据库去重率度量）
4. **投放响应**：Report Agent 异常告警响应延迟 < 1小时（推送到手机）

### 1.3 团队与 RACI

| 阶段 | 负责人（Owner） | 人工介入点 |
|------|---------------|-----------|
| Phase 1 创意拆解 | 竞品分析员 | 审核插件输出标签，修正明显错误 |
| Phase 2 文案撰写 | 文案策划 | 从20条候选中选3-5条，评分回流 |
| Phase 3 素材生产 | 设计 + 运营 | **出图后人工抽检图片**，确认后触发视频合成 |
| Phase 4 投放监控 | 广告投手 | 接收飞书告警，决策是否调整预算 |

---

## 二、工作流总览

### 2.1 阶段划分（v2 修订）

> [!warning] v2 两处关键结构变更
> 1. **文案必须在出图之前**（v1 顺序有误，已修正）
> 2. **出图 + 视频合成合并为"Phase 3 素材生产"**（用户建议，评审通过）

```
[Phase 1]          [Phase 2]         [Phase 3]           [Phase 4]
创意智能化    →    文案撰写    →    素材生产          →   投放监控
浏览器插件         Claude API         出图 + 视频合成        Marketing API
竞品视频拆解       结构化Brief        ComfyUI + Kling        Report Agent
    ↓ 人工校验         ↓ 人工筛选         ↓ 人工抽检图片          ↓ 飞书告警
创意数据库 ──────→ 文案候选库          素材库                  日报Obsidian
```

### 2.2 各阶段定义

| 阶段 | 输入 | 核心产出 | 人工卡点 |
|------|------|---------|---------|
| Phase 1：创意拆解插件 | 用户浏览的 TikTok 视频 | 结构化标签 JSON | 分析员校验标签 |
| Phase 2：文案撰写 | 创意数据库标签 | 文案 Brief × 20条 | 文案策划选3-5条并评分 |
| Phase 3：素材生产 | 文案 Brief | 成品视频素材包 | **出图后人工抽检，批准后进视频合成** |
| Phase 4：投放监控 | 素材包 + 广告数据 | 自动调预算 + 日报 | 投手收飞书告警后决策 |

---

## 三、Phase 1 — 创意拆解浏览器插件

### 3.1 产品定位

> 竞品分析员在**正常浏览 TikTok.com** 时，一键触发对当前视频的 AI 结构化拆解，输出标准化创意标签，写入创意数据库。

**目标页面**：TikTok.com 用户端（非 For Business 后台）
**触发方式**：视频暂停后侧边栏自动弹出分析选项，或分析员手动点击插件图标

### 3.2 技术方案（已修正）

> [!danger] v1 技术方案有两处致命错误，已修正
> - ❌ v1：FFmpeg.wasm + Web Worker（MV3 中 SharedArrayBuffer 不可用）
> - ❌ v1：直接处理 HLS 流抽帧（TikTok HLS 加密，FFmpeg.wasm 无法解密）

**✅ 正确方案：Canvas 截帧**

```
用户播放视频
    ↓
[content script] 监听 <video> 播放状态
    ↓
video.pause() → canvas.drawImage(video) → canvas.toDataURL('image/jpeg', 0.8)
    ↓
截取 3-5 帧（前3秒 + 中段 + 结尾）
    ↓
[background service worker] 调用 Claude Haiku API（图片输入）
    ↓
返回结构化标签 JSON，写入 IndexedDB
```

**架构要点：**
- FFmpeg.wasm **不引入**（MV3 的 SharedArrayBuffer 需要 offscreen document，复杂度过高，MVP 阶段不需要）
- Canvas 截帧完全规避 HLS 加密问题（利用浏览器原生解密播放能力）
- Manifest V3 + offscreen document 用于隔离 DOM 操作

### 3.3 降级方案（必须实现）

> [!warning] 降级方案是 MVP 必须项，不是可选项
> 竞品分析员遇到第一次自动分析失败就会放弃工具，必须有兜底。

| 情况 | 降级处理 |
|------|---------|
| 视频无法截帧（私密/特殊格式） | 弹出"手动截图模式"：用户框选屏幕区域提交 |
| Claude API 超时/失败 | 提示"分析排队中"，后台重试3次，仍失败则提示手动录入 |
| 视频已分析过 | IndexedDB 命中缓存，秒开显示历史结果 |

### 3.4 UI 设计原则

- Shadow DOM 隔离，不受 TikTok 原生 CSS 影响
- **不遮挡 TikTok 点赞/评论/分享按钮**（悬浮按钮位于左侧或顶部）
- 结果展示为**中文可视化卡片**，不暴露原始 JSON
- 历史记录支持一键复制到剪贴板或推送飞书

### 3.5 冷启动策略（v1 缺失，v2 新增）

> [!tip] 冷启动问题
> Phase 2 文案生成依赖创意数据库，但系统刚上线时数据为0。

**解决方案：**
1. **种子数据**：上线前由竞品分析员手动录入30-50条高质量竞品视频标签，作为初始数据库
2. **冷启动 Threshold**：数据库 < 50 条时，Phase 2 自动切换为"行业通用公式模板"兜底，不调用数据库检索
3. **目标**：运营第一周积累 ≥ 100 条有效标签，解除冷启动限制

### 3.6 成本估算

| 分析模式 | 帧数 | 成本/条 | 月成本（100条/天） |
|---------|------|--------|-----------------|
| 快速模式 | 3帧 | ~¥0.03 | ~¥90 |
| 标准模式 | 5帧 | ~¥0.05 | ~¥150 |
| 精细模式 | 10帧 | ~¥0.11 | ~¥330 |

**优化**：使用 Claude Batch API（异步，24h内返回）享受 50% 折扣，标准模式降至 ~¥75/月

---

## 四、Phase 2 — 文案撰写系统

### 4.1 产品定位

基于 Phase 1 创意数据库，批量生成高转化文案候选，文案策划介入筛选，选中文案回流数据库形成正向飞轮。

### 4.2 工作流

```
Phase 1 创意数据库
    ↓ 检索高频有效创意公式（≥50条后启用）
Claude API 生成文案 × 20条
    ↓
【人工卡点】文案策划打分筛选（采用/淘汰/修改）
    ↓
选定3-5条文案 → 生成 ImageGenerationBrief
    ↓
采用的文案自动写回创意数据库（正向飞轮）
```

### 4.3 文案评审机制（v1 缺失，v2 新增）

> [!warning] 这是整个链路质量的核心闸门，v1 完全缺失此设计

**最小可用评审 UI**：
- 列表展示20条候选文案
- 每条右侧3个操作：✅ 采用 / ❌ 淘汰 / ✏️ 修改后采用
- 采用率自动统计（监控 Claude Prompt 版本质量）
- Prompt 模板版本化存储，支持 A/B 对比

### 4.4 Prompt 版本管理

- Prompt 模板存储在数据库，支持版本号
- 每次 Prompt 更新后自动对比前后20条输出的人工评分均值
- 避免"改了 Prompt 结果变差也不知道"的黑盒问题

---

## 五、Phase 3 — 素材生产（出图 + 视频合成合并）

> [!success] v2 结构调整
> 原 Phase 3（出图）+ Phase 4（视频合成）合并为"Phase 3 素材生产"。
> 逻辑：出图和视频合成是同一条生产线，分开管理反而增加数据传递复杂度。

### 5.1 子阶段

```
文案 Brief（Phase 2 输出）
    ↓
[子阶段 A] 出图：ComfyUI API 批量生成场景化产品图
    ↓
【人工抽检卡点】设计/运营抽检图片质量（批量勾选确认）
    ↓
[子阶段 B] 视频合成：Kling AI / ComfyUI Wan 图生视频
    ↓
字幕动效：TypeTale（人工精修）或 Remotion（自动化）
    ↓
FFmpeg 合并音视频 → 成品素材包
```

### 5.2 出图工具选型（v2 修订）

| 工具 | 用途 | 部署方式 | 推荐阶段 |
|------|------|---------|---------|
| ComfyUI Web UI | 手动调参验证 Prompt 效果 | 本地 | Sprint 1 过渡 |
| ComfyUI API + Fabric.js 画布 | 自动化批量出图 | 本地/Replicate云 | Sprint 2+ |
| ControlNet（姿态图） | 固定模特姿势换鞋款 | ComfyUI 工作流 | Sprint 2+ |

> [!tip] 先跑通再自动化
> Phase 3 第一个 Sprint 完全用 ComfyUI Web UI 手动跑通，确认 Prompt 模板和 ControlNet 参数后，再开发 Fabric.js 自动化层。避免边写代码边调参。

**ComfyUI API 通信注意事项（开发必读）**：
- ComfyUI 是**异步 API**（WebSocket 监听队列），不是同步 HTTP
- 超时处理：每5秒轮询 `/history/{prompt_id}`，30分钟硬超时
- 任务状态持久化到 IndexedDB，防止刷新页面丢失进度

### 5.3 TypeTale 定位（明确）

> [!important] TypeTale 在本工作流中的正确定位
> TypeTale 是 **Windows 桌面客户端，无 REST API**，无法被服务端流水线自动调用。

| 场景 | TypeTale 是否适用 |
|------|-----------------|
| 自动化批量出图（主流程） | ❌ 不适用（无 API，无法编排） |
| 自动化视频合成（主流程） | ❌ 不适用（同上） |
| **人工精修视频（兜底）** | ✅ 适用——AI 自动合成质量不达标时，人工用 TypeTale 精修 |
| **字字动画字幕效果** | ✅ 适用——TypeTale 逐字动画效果优于手写，用于精修版本 |
| **风格提示词反推** | ✅ 可参考——TypeTale 的"图片反推 Prompt"功能可用于优化 ComfyUI 参数 |

**出图 UGC 风格提示词（防"太精美"被 TikTok 标记）**：
```
正向：shot on iPhone, casual lifestyle photography, natural lighting, real person wearing shoes, authentic, slightly imperfect
负向：cinematic, dramatic lighting, professional photography, CGI, rendered
```

### 5.4 视频合成

| 工具 | 用途 | API 可用 |
|------|------|---------|
| Kling AI | 图生视频（主力） | ✅ |
| ComfyUI Wan2.2 | 本地图生视频 | ✅ |
| ElevenLabs | AI 配音 | ✅ |
| Remotion | 字幕逐字动效（服务端渲染） | ✅（需 Node.js 服务） |
| TypeTale | 人工精修字幕动效 | ❌ 桌面客户端 |
| FFmpeg | 音视频合并 | ✅ |

> [!warning] Remotion 架构说明
> Remotion 是 **Node.js 服务端渲染框架**，不能在浏览器或 Chrome Extension 内运行。
> 架构：浏览器触发 → POST 到本地 Remotion 服务 → 返回视频文件。
> Phase 4 必须有一个常驻 Node.js 服务，不能纯客户端完成。

### 5.5 质检流程（v1 缺失，v2 新增）

> [!danger] 没有质检直接投放是灾难
> AI 出图常见问题：脚趾变形、鞋底比例失调、鞋带数量不对。

**质检方案（出图后、视频合成前）**：
1. **AI 自动审核**：调用 Claude Vision 检测明显变形（脚部比例、产品完整性）
2. **人工抽检**：每批次素材人工抽检10%，批量勾选通过后才触发视频合成
3. **拒绝反馈**：被拒绝的图片记录拒绝原因，回流到 ComfyUI 调参参考

### 5.6 素材版本追溯（v1 缺失，v2 新增）

每条素材从生成起携带溯源标签：
- `source_video_ids`：来源竞品视频 ID
- `brief_id`：对应文案 Brief 版本号
- `generated_at`：生成时间

广告命名规范：`AD_{日期}_{brief_id}_{变体号}`，例如 `AD_20260329_B042_V3`

---

## 六、Phase 4 — 投放与监控

### 6.1 投放方式

> [!success] 官方 Marketing API，零封号风险
> 完全使用 TikTok for Business 官方 Marketing API，不使用任何爬虫或绕过机制。

**申请注意（开发与申请必须并行）**：
- 需要 TikTok for Business 广告账户（非个人账号）
- Creative Management 权限需单独申请，审核 2-3 个工作日
- **Sprint 1 第一天提交 API 申请**，不要等到 Phase 4 再申请
- 开发期间使用 Sandbox 环境：`https://sandbox-ads.tiktok.com/open_api/`

### 6.2 OpenClaw 多智能体架构

```
Scheduler Agent（每日9点触发）
    ├── Creative Agent：从 Phase 1 数据库提取今日洞察
    ├── Production Agent：触发 Phase 3 素材生产
    └── Placement Agent：通过 TikTok API 上传素材、创建广告

Report Agent（每小时拉数据）
    ├── 异常检测 → 飞书即时推送（投手手机）
    └── 每日18点 → 生成日报写入 Obsidian（存档用）
```

### 6.3 自动调预算逻辑（v2 修订）

> [!warning] v1 的单一 CTR 条件风险极高
> 鞋类 TikTok 广告平均 CTR 在 0.8%-1.5%，CTR 飙高可能是标题党（高点击低转化）。

**v1（错误）**：
```python
if ad.ctr > 2.0 and ad.roas > 3.0:  # CTR 高 → 加预算
```

**v2（正确，三条件同时满足）**：
```python
# 加预算条件：CTR超基准 + CVR达标 + 样本量充足
if (ad.ctr > industry_benchmark * 1.5
    and ad.cvr > cvr_baseline
    and ad.spend > 50):  # 花费>$50保证样本量
    tiktok_api.update_budget(ad.id, min(ad.budget * 1.3, daily_budget_cap))

# 熔断机制：单次调整不超过预算的20%
MAX_SINGLE_ADJUSTMENT = 0.20
```

**飞书推送通道（投手手机优先）**：
- 异常告警（ROAS跌破阈值、烧钱过快）：即时推送 @投手
- 日报：消息卡片摘要推送到投手群
- Obsidian 日报：详细数据存档，非主要触达方式

---

## 七、数据接口规范

### 7.1 Phase 1 → Phase 2（视频分析结果）

```json
{
  "video_id": "md5(url) 或 TikTok aweme_id",
  "source_url": "https://...",
  "analyzed_at": "2026-03-29T10:00:00Z",
  "frames_captured": 5,
  "creative": {
    "hook_type": "problem_agitation | curiosity_gap | social_proof | before_after | direct_product",
    "hook_duration_sec": 3.2,
    "emotion_arc": ["pain", "desire", "trust"],
    "product_focus": "sole_comfort | appearance | price",
    "cta_type": "soft_cta | hard_cta | link_in_bio",
    "music_vibe": "upbeat | emotional | calm | hype | none",
    "scene_structure": [
      { "timestamp_sec": 0.5, "scene_type": "hook", "text_overlay": "站了8小时脚不疼？" }
    ],
    "estimated_engagement": "low | medium | high"
  }
}
```

### 7.2 Phase 2 → Phase 3（文案 Brief 到出图指令）

```json
{
  "brief_id": "B042",
  "source_video_ids": ["vid_001", "vid_002"],
  "copy": {
    "headline": "站8小时脚不疼",
    "hook_line": "走了一天路，同事都在换鞋，我还没感觉",
    "body_copy": "记忆棉中底，脚不疼才能工作到下班",
    "cta_text": "评论问尺码",
    "emotion_target": "recognition → relief"
  },
  "image_specs": [
    {
      "variant_id": "V1",
      "scene_description": "woman wearing white sneakers walking in office corridor, shot on iPhone, casual lifestyle, natural lighting",
      "negative_prompt": "cinematic, dramatic lighting, CGI",
      "product_image_path": "/assets/shoe_001_white.png",
      "aspect_ratio": "9:16",
      "comfyui_workflow_id": "product_scene_v3",
      "batch_count": 4
    }
  ],
  "status": "pending | generating | review | approved | rejected",
  "created_at": "2026-03-29T10:30:00Z"
}
```

---

## 八、成功指标（修订版）

| 指标 | 基线（来源） | 目标值 | 度量方式 |
|------|-----------|--------|---------|
| 竞品视频拆解速度 | 30min/条（团队估算，待验证） | < 2min/条 | 插件操作日志 |
| 文案生成速度 | 1-2h/批（团队估算） | < 10min/批 | API 响应时间 |
| 日均可用素材数 | 5条/周（运营记录） | 20-50条/天 | 素材库新增数量 |
| 创意唯一性 | 未度量 | 唯一公式占比 > 60% | 数据库去重率 |
| 投放异常响应时间 | 人工次日（估算） | 飞书告警 < 1小时 | 告警到投手确认时间 |
| 素材合格率 | 未度量 | 质检通过率 > 85% | AI审核 + 人工抽检记录 |

---

## 九、技术栈总览

```
┌─────────────────────────────────────────────────────┐
│              Chrome Extension MV3（TypeScript）      │
│  Canvas 截帧  |  Shadow DOM UI  |  IndexedDB 缓存     │
└──────────────────────┬──────────────────────────────┘
                       │ Claude Haiku API（图片分析）
┌──────────────────────▼──────────────────────────────┐
│                   文案生成层                          │
│          Claude API + Prompt 版本管理                 │
│          创意数据库（本地 SQLite / 云端 Supabase）     │
└──────────────────────┬──────────────────────────────┘
                       │ ImageGenerationBrief JSON
┌──────────────────────▼──────────────────────────────┐
│               素材生产层                              │
│  Fabric.js 画布  |  ComfyUI API（异步 WebSocket）     │
│  Kling AI API   |  Node.js Remotion 服务             │
│  FFmpeg 合并    |  TypeTale（人工精修，可选）          │
└──────────────────────┬──────────────────────────────┘
                       │ 素材包（含溯源标签）
┌──────────────────────▼──────────────────────────────┐
│             投放与监控层（官方）                       │
│  TikTok Marketing API v1.3                          │
│  OpenClaw Multi-Agent（Scheduler/Production/Report）│
│  飞书机器人推送（主）→ Obsidian 日报（存档）           │
└─────────────────────────────────────────────────────┘
```

---

## 十、开发里程碑

| Sprint | 时间 | 目标 | 关键事项 |
|--------|------|------|---------|
| Sprint 0 | Week 0 | 种子数据录入 + API 申请 | 手工录入30-50条竞品标签；提交 TikTok Marketing API 申请 |
| Sprint 1 | Week 1-3 | Phase 1 插件 MVP | Canvas截帧方案；降级入口；Shadow DOM UI；IndexedDB Schema |
| Sprint 2 | Week 2-3 | Phase 2 文案系统 | Claude API + 评审UI + 冷启动逻辑（可与Sprint1并行） |
| Sprint 3 | Week 4-5 | Phase 3 出图 | ComfyUI Web UI 调参验证 → Fabric.js 自动化画布 |
| Sprint 4 | Week 5-6 | Phase 3 视频合成 | Kling API + Remotion Node.js 服务 + FFmpeg |
| Sprint 5 | Week 7+ | Phase 4 投放监控 | TikTok API + OpenClaw Agent + 飞书推送 |

---

## 十一、已排除方案（及原因）

| 方案 | 排除原因 |
|------|---------|
| 反爬绕过 + 住宅代理 + 自动养号 | 违反 TikTok ToS，封号风险高，合规性差 |
| FFmpeg.wasm 直接处理 HLS 流 | TikTok HLS 加密，无法在浏览器内解密，改用 Canvas 截帧 |
| TypeTale 作为主力出图/视频工具 | Windows 桌面客户端，无 REST API，无法被自动化编排 |
| 从0开发 Lovart 完整产品 | 2-3个月以上工期，超出范围；Fabric.js 轻量画布2周可达到同等核心功能 |
| 自动投放全自动无人工 | 自动调预算单条件触发风险高，改为三条件+飞书确认 |

---

## 十二、子文档索引

- [ ] [[TikTok广告PRD-Phase1-创意拆解插件]] — Chrome Extension + Canvas截帧 + Claude API
- [ ] [[TikTok广告PRD-Phase2-文案撰写系统]] — 冷启动策略 + 评审UI + Prompt版本管理
- [ ] [[TikTok广告PRD-Phase3-素材生产]] — ComfyUI出图 + 质检流程 + Kling视频合成
- [ ] [[TikTok广告PRD-Phase4-投放监控]] — Marketing API + OpenClaw + 飞书推送
