---
title: TikTok 广告 PRD — Phase 3：素材生产（出图 + 视频合成）
tags:
  - PRD
  - Phase3
  - 出图
  - 视频合成
  - ComfyUI
  - Kling
date: 2026-03-29
status: 草稿
project: 鞋类跨境广告
parent: "[[TikTok广告AI工作流-PRD总览-2026-03-29]]"
version: v1.0
---

# Phase 3：素材生产（出图 + 视频合成）— 详细 PRD

> [!info] 上下文
> 本文档为 [[TikTok广告AI工作流-PRD总览-2026-03-29]] 的 Phase 3 子文档。
> **输入**：Phase 2 输出的 `ImageGenerationBrief` JSON
> **产出**：带溯源标签的成品广告视频素材包，进入 Phase 4 投放队列

---

## 一、产品目标

**一句话定义**：把文案 Brief 自动转化为可投放的广告视频素材，出图和视频合成在同一条流水线内完成，人工只在出图后做一次质检卡点。

**产能目标**：

| 当前 | 目标 |
|------|------|
| 手动 PS，每周 5 条可用素材 | 每天 20-50 条可用素材 |
| 出图到视频需多部门传递 | 同一系统内自动串联 |
| 无质检，问题素材直接投放 | AI 初筛 + 人工抽检，合格率 > 85% |

---

## 二、子阶段划分

```
Phase 2 Brief JSON
       │
       ▼
┌──────────────────┐
│  子阶段 A：出图   │
│  ComfyUI API     │
│  批量生成场景图   │
└────────┬─────────┘
         │
         ▼
┌─────────────────────────────┐
│  【人工卡点】质检            │
│  AI 初筛（Claude Vision）   │
│  人工抽检 10%               │
│  批量勾选 → 点确认           │
└────────┬────────────────────┘
         │ 仅通过质检的图片
         ▼
┌──────────────────┐
│  子阶段 B：视频   │
│  Kling AI 图生视频│
│  Remotion 字幕   │
│  FFmpeg 合并      │
└────────┬─────────┘
         │
         ▼
  成品素材包（带溯源标签）
  → Phase 4 投放队列
```

> [!warning] 人工卡点是必须的，不可跳过
> 出图→视频之间有人工确认节点。图方向错了（场景不对/产品变形），在这里止损。
> 跳过卡点会导致：错误图片进入视频合成 → 浪费 Kling API 费用 → 发现时素材已进投放队列。

---

## 三、子阶段 A — 出图

### 3.1 工具选型与开发策略

> [!tip] 先跑通再自动化（重要原则）
> Phase 3 第一个 Sprint 完全用 ComfyUI Web UI 手动调参，确认 Prompt 模板和 ControlNet 参数后，再开发 Fabric.js 自动化层。
> 避免"边写代码边调参"，导致代码写完参数还没调好。

| Sprint | 工具 | 方式 | 目标 |
|--------|------|------|------|
| Sprint 1（Week 4）| ComfyUI Web UI | 手动操作 | 调通 Prompt 模板、ControlNet 参数、出图质量达标 |
| Sprint 2（Week 5）| ComfyUI API + Fabric.js | 自动化 | 从 Brief JSON 自动触发批量出图 |

### 3.2 出图工作流

```
Brief JSON 中的 image_specs[]
       │ 每个 variant
       ▼
[Step 1] 读取出图参数
  - product_image_path（白底产品图）
  - scene_description（场景 Prompt）
  - negative_prompt
  - comfyui_workflow_id（预设工作流）
  - batch_count（每个变体生成几张）
       │
       ▼
[Step 2] 调用 ComfyUI API（异步）
  POST /prompt → 返回 prompt_id
  WS /ws?client_id=xxx → 监听队列事件
  GET /view?filename=xxx → 下载成品图
       │
       ▼
[Step 3] 图片写入本地/云端存储
  命名规范：{brief_id}_{variant_id}_{序号}.jpg
  例：B-20260329-042_V1_003.jpg
       │
       ▼
[Step 4] 触发 AI 初筛（Claude Vision）
  检测：脚部/手部变形、产品比例失调、明显合成痕迹
       │
       ▼
[Step 5] 展示待质检图片列表（人工卡点）
```

### 3.3 ComfyUI 工作流预设

鞋类广告需要以下预设工作流（Sprint 1 期间在 ComfyUI Web UI 中调试并保存）：

| 工作流 ID | 场景 | 关键节点 |
|----------|------|---------|
| `product_scene_office_v3` | 办公/通勤场景 | SDXL + ControlNet 姿态图 + 背景替换 |
| `product_scene_street_v2` | 街头/城市场景 | FLUX + IP-Adapter 产品保持 + 场景融合 |
| `product_scene_sport_v1` | 运动/户外场景 | SDXL + 动态模糊后处理 |
| `product_whitebg_enhance` | 白底图精修 | 仅产品增强，不换背景 |

### 3.4 UGC 风格 Prompt 规范

> [!danger] 防"太精美"被 TikTok 标记为过度 AI 内容
> TikTok 广告审核对过于完美的 AI 生成图有标记机制。鞋类广告需要生活化、真实感。

**必须加入的正向风格词**（所有工作流通用）：
```
shot on iPhone, casual lifestyle photography, natural lighting,
authentic, slightly imperfect, real person, candid style,
instagram story vibe, UGC content
```

**必须加入的负向词**（所有工作流通用）：
```
cinematic lighting, professional photography, studio shot,
dramatic shadows, perfect symmetry, CGI, rendered, 8k ultra detail,
stock photo, commercial advertisement look
```

**场景特化词（示例）**：

| 场景 | 额外正向词 |
|------|-----------|
| 办公/通勤 | `office background blurred, standing desk, business casual outfit` |
| 街头 | `city street, golden hour, crowd background, walking motion blur` |
| 运动 | `park trail, natural sweat, athletic wear, movement freeze frame` |

### 3.5 ComfyUI API 通信（异步，必须正确处理）

> [!warning] ComfyUI 是异步 API，不是同步请求
> 常见错误：发完 POST /prompt 就等响应，实际上响应只返回 prompt_id，图片还在队列里生成。

```javascript
// comfyui_client.js
class ComfyUIClient {
  async generateImage(workflowId, params) {
    const clientId = crypto.randomUUID();

    // Step 1: 提交任务
    const { prompt_id } = await this.postPrompt(workflowId, params, clientId);

    // Step 2: WebSocket 监听队列状态
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(`ws://${this.host}/ws?client_id=${clientId}`);
      const TIMEOUT = 30 * 60 * 1000; // 30分钟硬超时

      const timer = setTimeout(() => {
        ws.close();
        reject(new Error('ComfyUI 超时：生成时间超过30分钟'));
      }, TIMEOUT);

      ws.onmessage = async (event) => {
        const msg = JSON.parse(event.data);

        if (msg.type === 'executing' && msg.data?.prompt_id === prompt_id) {
          // 更新进度显示
          onProgress?.(msg.data.node);
        }

        if (msg.type === 'executed' && msg.data?.prompt_id === prompt_id) {
          clearTimeout(timer);
          ws.close();
          // Step 3: 下载图片
          const images = await this.fetchImages(msg.data.output);
          resolve(images);
        }

        if (msg.type === 'execution_error') {
          clearTimeout(timer);
          ws.close();
          reject(new Error(msg.data?.exception_message));
        }
      };

      ws.onerror = (err) => {
        clearTimeout(timer);
        reject(err);
      };
    });
  }

  // Fallback：轮询方式（WebSocket 失败时使用）
  async pollUntilDone(prompt_id, intervalMs = 5000) {
    while (true) {
      const history = await fetch(`${this.baseUrl}/history/${prompt_id}`).then(r => r.json());
      if (history[prompt_id]?.status?.completed) {
        return this.fetchImages(history[prompt_id].outputs);
      }
      await sleep(intervalMs);
    }
  }
}
```

### 3.6 出图部署方案

| 方案 | 适用阶段 | 成本 | 并发能力 |
|------|---------|------|---------|
| 本地 ComfyUI（自有 GPU）| Sprint 1 调参 | 电费 | 单任务，15-90秒/张 |
| Replicate API（云端） | Sprint 2+ 生产 | ~$0.05-0.15/张 | 按需扩容 |
| RunComfy / Geeknow | Sprint 2+ 备选 | 月费制 | 稳定队列 |

**推荐路线**：Sprint 1 用本地调参 → Sprint 2 切换 Replicate API（按量付费，无需维护 GPU 服务器）

**每日出图成本估算**（Replicate，50张/天）：
```
50张 × $0.08/张 = $4/天 ≈ ¥29/天 ≈ ¥870/月
```

---

## 四、质检流程

> [!danger] 质检是出图→视频之间的强制卡点
> 没有质检 = AI 生图常见错误（脚趾变形/鞋底失真/产品消失）直接进入视频合成。

### 4.1 AI 初筛（Claude Vision）

```javascript
async function aiQualityCheck(imagePath) {
  const imageBase64 = await readImageAsBase64(imagePath);

  const result = await claudeAPI.messages.create({
    model: 'claude-haiku-4-5-20251001', // 速度优先，成本低
    max_tokens: 200,
    messages: [{
      role: 'user',
      content: [
        { type: 'image', source: { type: 'base64', media_type: 'image/jpeg', data: imageBase64 }},
        { type: 'text', text: `
检查这张鞋类广告图片的质量问题，输出 JSON：
{
  "pass": true/false,
  "issues": ["问题描述1", "问题描述2"],
  "confidence": 0-1
}

检查项目：
1. 人体部位变形（脚趾/手指数量异常、比例失调）
2. 产品变形（鞋子形状异常、鞋底消失、鞋带缺失）
3. 明显合成痕迹（边缘锯齿、光影不一致）
4. 产品主体不清晰或被遮挡

若无明显问题输出 pass: true，有任何一项问题输出 pass: false。
        `}
      ]
    }]
  });

  return JSON.parse(result.content[0].text);
}
```

**AI 初筛成本**：每张图约 1000 token，`claude-haiku` 约 ¥0.007/张，50张/天 ≈ ¥0.35/天，可忽略。

### 4.2 人工质检界面

```
┌────────────────────────────────────────────────────┐
│  🖼️ 出图质检（Brief B-042，共 16 张）               │
│  AI 初筛：通过 12 张 / 问题 4 张                    │
├────────────────────────────────────────────────────┤
│  ✅ 通过（12张）                    ❌ 问题（4张）  │
├────────────────────────────────────────────────────┤
│                                                      │
│  [图1] ☑  [图2] ☑  [图3] ☑  [图4] ☑              │
│  [图5] ☑  [图6] ☑  [图7] ☑  [图8] ☑              │
│                                                      │
│  ── AI 标记问题（默认不勾选）──                     │
│  [图13] ☐ ⚠️ 脚趾变形           [重新生成]         │
│  [图14] ☐ ⚠️ 鞋底比例失调       [重新生成]         │
│  [图15] ☐ ⚠️ 明显合成痕迹       [重新生成]         │
│  [图16] ☐ ⚠️ 产品被遮挡         [重新生成]         │
│                                                      │
├────────────────────────────────────────────────────┤
│  已选 12 张通过图片                                  │
│  [确认，进入视频合成 →]   [全部重新生成]            │
└────────────────────────────────────────────────────┘
```

**人工操作规范**：
- 系统预先勾选 AI 初筛通过的图片
- AI 标记问题的图片默认不勾选，标注问题原因
- 人工可以覆盖 AI 判断（手动勾选 AI 标记问题的图片）
- 点击"重新生成"对单张图片重新调用 ComfyUI，不影响其他图片
- 目标：每批次质检操作 < 5 分钟

### 4.3 质检数据记录

```json
{
  "quality_check_id": "QC-20260329-042",
  "brief_id": "B-20260329-042",
  "total_generated": 16,
  "ai_passed": 12,
  "ai_flagged": 4,
  "human_approved": 12,
  "human_override_approved": 0,
  "rejection_reasons": ["脚趾变形×2", "鞋底比例失调×1", "合成痕迹×1"],
  "checked_at": "2026-03-29T15:00:00Z",
  "checked_by": "design_team"
}
```

---

## 五、子阶段 B — 视频合成

### 5.1 视频合成流水线

```
质检通过的图片（12张）
       │ 按 Brief 中的 video_specs 参数
       ▼
[Step 1] Kling AI — 图生视频
  每张图 → 3-5秒视频片段（slow zoom / subtle motion）
       │
       ▼
[Step 2] ElevenLabs — AI 配音（可选）
  根据 full_copy 文本生成配音音频
  语言：英文（面向海外市场）
       │
       ▼
[Step 3] Remotion — 字幕逐字动效
  hook 文字 → 前3秒大字幕逐字出现
  body + CTA → 后续字幕
  （Remotion 运行在 Node.js 服务端，不是浏览器）
       │
       ▼
[Step 4] FFmpeg — 合并音视频
  视频片段 + 配音 + 字幕 → 成品 MP4
  规格：1080×1920（9:16），≤ 60秒，< 500MB
       │
       ▼
[Step 5] 写入素材库，附溯源标签
```

### 5.2 工具说明

| 工具 | 用途 | API | 成本估算 |
|------|------|-----|---------|
| Kling AI | 图生视频（主力） | ✅ REST API | ~$0.14/视频（5秒） |
| Runway Gen-3 | 图生视频（备选） | ✅ REST API | ~$0.05/秒 |
| ElevenLabs | AI 英文配音 | ✅ REST API | ~$0.30/1000字符 |
| Remotion | 字幕逐字动效 | Node.js 本地服务 | 开源，无 API 费用 |
| FFmpeg | 音视频合并 | 命令行工具 | 免费 |

> [!warning] Remotion 架构说明（开发必读）
> Remotion **不能在浏览器中运行**，它是 Node.js 服务端渲染框架。
> 必须有一个常驻 Node.js 服务（本地或部署在服务器上），接收渲染请求。
>
> 调用方式：
> ```
> 前端/后端 → POST http://localhost:3001/render
>           → Remotion 服务渲染字幕视频
>           → 返回视频文件路径
> ```

### 5.3 Remotion 字幕动效规范

```javascript
// remotion/compositions/TikTokCaption.tsx
import { useCurrentFrame, interpolate, spring } from 'remotion';

export const TikTokCaption: React.FC<{ hook: string; body: string; cta: string }> = ({
  hook, body, cta
}) => {
  const frame = useCurrentFrame();

  // 逐字出现动效：每个字延迟3帧
  const hookChars = hook.split('');

  return (
    <div style={captionContainer}>
      {/* 前3秒：Hook 大字幕逐字出现 */}
      {frame < 90 && hookChars.map((char, i) => (
        <span key={i} style={{
          opacity: interpolate(frame, [i * 3, i * 3 + 6], [0, 1], { extrapolateRight: 'clamp' }),
          transform: `translateY(${interpolate(frame, [i * 3, i * 3 + 6], [10, 0], { extrapolateRight: 'clamp' })}px)`
        }}>
          {char}
        </span>
      ))}

      {/* 3秒后：正文字幕淡入 */}
      {frame >= 90 && (
        <p style={{ opacity: interpolate(frame, [90, 105], [0, 1]) }}>
          {body}
        </p>
      )}
    </div>
  );
};
```

### 5.4 TypeTale 的使用场景（明确定位）

> [!note] TypeTale 在本阶段的正确角色
> TypeTale 是 Windows 桌面客户端，无 REST API，**不纳入自动化流水线**。
> 仅在以下情况使用：

| 场景 | 是否用 TypeTale | 说明 |
|------|---------------|------|
| 自动化视频合成（主流程） | ❌ | 用 Kling + Remotion + FFmpeg |
| AI 合成视频质量不达标 | ✅ | 人工用 TypeTale 精修，替换问题素材 |
| 需要字字动画精品版本 | ✅ | TypeTale 的逐字动画效果优于 Remotion，用于重点素材精修 |
| 风格提示词反推 | ✅ | 用 TypeTale 的"图片反推 Prompt"功能优化 ComfyUI 参数 |

**精修操作流程**（人工介入）：
```
自动合成视频质量不达标
    ↓
导出问题视频的帧 → 导入 TypeTale
    ↓
TypeTale 精修（口型同步/场景重排/字幕动效）
    ↓
导出 MP4 → 替换素材库中对应文件
    ↓
继续进入 Phase 4 投放队列
```

### 5.5 视频合成成本估算

| 数量 | Kling 图生视频 | ElevenLabs 配音 | 合计/天 |
|------|-------------|----------------|---------|
| 20 条/天 | 20 × $0.14 = $2.8 | 20 × $0.10 = $2.0 | ~$4.8（¥35） |
| 50 条/天 | 50 × $0.14 = $7.0 | 50 × $0.10 = $5.0 | ~$12（¥87） |

---

## 六、素材溯源标签

> [!success] 每条素材从生成起就携带完整溯源链
> 投手后续复盘"这10条高效素材的 Brief 来自哪里"时，可以一键追溯到竞品视频。

### 6.1 溯源标签结构

```json
{
  "asset_id": "AST-20260329-042-V1-003",
  "asset_type": "video",
  "file_path": "/assets/videos/AST-20260329-042-V1-003.mp4",
  "brief_id": "B-20260329-042",
  "copy_id": "copy_v12_007",
  "prompt_version": "v1.2",
  "source_video_ids": ["vid_001", "vid_007"],
  "variant_id": "V1",
  "scene": "office_commute",
  "generated_at": "2026-03-29T15:30:00Z",
  "quality_check": {
    "ai_passed": true,
    "human_approved": true,
    "checked_at": "2026-03-29T15:45:00Z"
  },
  "ad_naming": "AD_20260329_B042_V1"
}
```

### 6.2 广告命名规范

TikTok Ads Manager 中的广告命名使用溯源标签，方便投手做 AB 归因：

```
AD_{日期}_{brief_id}_{变体号}
例：AD_20260329_B042_V1
```

---

## 七、系统架构

```
┌─────────────────────────────────────────────────┐
│           素材生产系统（Web App + 服务端）         │
│                                                   │
│  前端（Vue 3）                                    │
│  ├── Brief 队列看板（待出图/出图中/待质检/待合成） │
│  ├── 质检界面（图片网格 + 勾选确认）              │
│  └── 素材库（视频列表 + 溯源信息）                │
│                                                   │
│  后端（Python FastAPI）                           │
│  ├── ComfyUI API 封装（异步 + WebSocket）         │
│  ├── Claude Vision 质检调用                       │
│  ├── Kling AI API 封装                            │
│  ├── Remotion 渲染服务调用                        │
│  └── FFmpeg 合并脚本                              │
│                                                   │
│  Node.js 服务（独立进程）                         │
│  └── Remotion 字幕渲染服务（localhost:3001）       │
└─────────────────────────────────────────────────┘
```

---

## 八、开发里程碑

| 里程碑 | 内容 | 验收标准 |
|--------|------|---------|
| M1（Week 4）| ComfyUI Web UI 调参 | 手动出图效果达标：场景真实、产品清晰、UGC 风格 |
| M2（Week 4）| 3个核心工作流确定 | office / street / sport 三套 Prompt 模板固定 |
| M3（Week 5）| ComfyUI API 自动化 | 传入 Brief JSON 自动触发出图，图片正确保存 |
| M4（Week 5）| Claude Vision 质检 | AI 初筛能检出明显变形，误报率 < 20% |
| M5（Week 5）| 人工质检 UI | 图片网格展示，勾选确认操作流畅 |
| M6（Week 5-6）| Kling AI 图生视频 | 通过质检的图片自动触发视频合成 |
| M7（Week 6）| Remotion 字幕服务 | Node.js 服务部署，字幕逐字动效正常渲染 |
| M8（Week 6）| FFmpeg 合并 + 溯源标签 | 成品 MP4 正确合并，溯源 JSON 完整写入 |
| M9（Week 6+）| 素材库看板 | 素材列表、溯源信息、投放状态可视化 |

---

## 九、已知风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| ComfyUI 本地显存不足 | 中 | 出图失败 | Sprint 1 用本地调参，Sprint 2 切 Replicate API，不依赖本地显存 |
| Kling AI 单日配额限制 | 中 | 视频合成卡队列 | 申请企业配额；备选 Runway Gen-3；超配额时通知设计人工处理 |
| Remotion 服务挂掉 | 低 | 字幕渲染失败 | 字幕渲染失败时用无字幕版本进入投放，字幕通过 TikTok Ads Manager 叠加 |
| AI 质检误报率高 | 中 | 好图被过度拦截 | 人工可覆盖 AI 判断；调整 Claude Vision Prompt 降低误报 |
| UGC 风格不够自然 | 中 | TikTok 审核标记 | 在 Prompt 中持续加强自然感词汇；参考 TypeTale 反推高质量 UGC 视频的 Prompt |
| 视频合成成本超预期 | 低 | 费用增加 | 设置每日最大合成数量上限（默认50条），超出自动暂停并通知 |
