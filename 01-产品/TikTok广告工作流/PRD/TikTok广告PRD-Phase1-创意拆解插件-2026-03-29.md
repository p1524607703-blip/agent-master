---
title: TikTok 广告 PRD — Phase 1：创意拆解浏览器插件
tags:
  - PRD
  - Phase1
  - 浏览器插件
  - Chrome Extension
  - TikTok
date: 2026-03-29
status: 草稿
project: 鞋类跨境广告
parent: "[[TikTok广告AI工作流-PRD总览-2026-03-29]]"
version: v2.0（模式B重构：用户自行搜索→插件感知页面）
---

# Phase 1：创意拆解浏览器插件 — 详细 PRD

> [!info] 上下文
> 本文档为 [[TikTok广告AI工作流-PRD总览-2026-03-29]] 的 Phase 1 子文档。
> 阅读总 PRD 后再阅读本文档。

---

## 一、产品目标

**一句话定义**：竞品分析员在 TikTok.com 上，无需切换工具，随手完成竞品视频结构化拆解，并积累为可批量导出的创意数据库。

**解决的核心痛点**：
- 看了很多竞品视频，停留在感性判断（"这个视频好"）
- 没有提炼成可复用的结构化公式（"前3秒用了什么钩子、情绪点是什么"）
- 分析结果散落在文档/截图里，无法团队共享和批量导出

---

## 二、用户与使用场景

**主要用户**：竞品分析员（非技术背景，每天刷 TikTok 做竞品研究）

**使用场景**：
| 场景 | 触发方式 | 期望结果 |
|------|---------|---------|
| 刷到一条感觉很好的竞品视频 | 点击悬浮按钮 → 分析当前视频 | 拿到结构化拆解卡片，可选择加入收藏列表 |
| 想系统研究某个品类 | 用户自行在 TikTok 搜索关键词 → 悬浮窗感知搜索页 → 一键批量抓取 | 批量拆解当前搜索结果，导出表格 |
| 日常积累 | 模式A随手分析 → 加入列表 | 随时间积累成高质量竞品数据库 |

---

## 三、核心功能：双模式架构

```
插件悬浮按钮（左侧边栏，不遮挡原生按钮）
         │
    点击展开面板
         │
    ┌────┴────┐
    │         │
  模式 A    模式 B
 当前视频   关键词搜索
  分析       批量分析
    │         │
    └────┬────┘
         │
    统一分析列表
    （可合并、排序、导出）
```

### 3.1 模式 A — 当前视频分析（被动模式）

**触发**：用户正在观看某条视频时，点击悬浮按钮 → 选择"分析当前视频"

**流程**：

```
用户暂停/播放视频
    ↓
点击悬浮按钮 → 选择"分析当前视频"
    ↓
Canvas 截帧（自动抓取前3秒帧 + 中段帧 + 结尾帧，共5帧）
    ↓
调用 Claude Haiku API（图片输入 + 系统Prompt）
    ↓
返回结构化分析卡片（约10-15秒）
    ↓
展示分析结果
    ↓
【新增】弹出询问："是否加入批量分析列表？"
    ├── 加入列表 → 写入本地列表，显示"已加入（共X条）"
    └── 不加入 → 仅本地缓存，可在历史记录中查看
```

**"是否加入批量分析列表"的交互设计**：

> [!tip] 设计原则
> 询问要轻量，不打断用户刷视频的节奏。

- 分析结果卡片底部固定显示两个按钮：`＋ 加入列表` 和 `跳过`
- 默认3秒后自动关闭（不强制用户操作）
- 加入列表后，悬浮按钮上方出现徽章数字（如 `●7`），提示列表已有7条
- 用户可随时在面板中查看已收藏的列表

---

### 3.2 模式 B — 搜索结果页感知批量分析（主动模式）

> [!success] v2 重构说明
> 原方案（插件内输入关键词 → 自动跳转搜索页）已废弃。
> 新方案：**用户自行搜索，插件感知当前页面**，行为等同于广告拦截器/翻译插件，检测风险最低。

**触发**：用户在 TikTok 正常搜索关键词（如"sport shoes"）→ 页面跳转至搜索结果页 → 悬浮按钮自动变色并弹出提示气泡

> [!tip] 给分析员的操作建议（写入插件提示文案）
> 💡 建议先点击「**视频**」标签页再触发抓取，结果更纯净（无用户账号混入）

**触发判断逻辑**：

```javascript
// content_scripts/tiktok_search.js
// 监听 URL 变化（TikTok 是 SPA，页面不刷新）
const observer = new MutationObserver(() => {
  if (location.href.includes('/search')) {
    showSearchPromptBubble();  // 悬浮按钮变色 + 弹出提示气泡
  } else {
    hideSearchPromptBubble();
  }
});
observer.observe(document.body, { childList: true, subtree: true });
```

**完整流程**：

```
用户在 TikTok 搜索"sport shoes"（正常操作）
    ↓
URL 变为 tiktok.com/search/...
    ↓
插件检测到搜索页 → 悬浮按钮高亮 + 弹出提示气泡：

  ┌────────────────────────────────┐
  │ 📊 检测到搜索结果页             │
  │ 是否批量抓取并分析？            │
  │                                 │
  │ 排序依据：                      │
  │ ● 点赞数排序（推荐，速度快）    │
  │ ○ TikTok 推荐顺序（最快）      │
  │ ○ 播放量排序（慢，需进每个视频）│
  │                                 │
  │ 抓取数量：[10]  [20]  [30]      │
  │                                 │
  │      [开始抓取]    [忽略]       │
  └────────────────────────────────┘
    ↓ 用户点击"开始抓取"
[Step 1] 自动滚动当前页面加载更多结果（目标：N条×2的候选池）
    ↓
[Step 2] Content Script 读取当前页 DOM，提取所有视频卡片
  提取字段：视频链接、标题、点赞数、作者、封面图、日期
    ↓
[Step 3] 按所选排序依据处理：
  ● 点赞数排序 → 直接从 DOM 读取，客户端排序，取前 N 条（快速）
  ● 推荐顺序  → 不排序，直接取前 N 条（最快）
  ● 播放量排序 → 逐条进入视频页读取播放量，排序后取前 N 条（慢）
    ↓
[Step 4] 展示视频列表预览，用户可手动勾选/取消
    ↓
[Step 5] 逐条分析（Canvas截帧 + Claude Haiku）
  进度提示："已分析 8/20，预计还需 4 分钟"
    ↓
[Step 6] 完成 → 自动合并模式A列表（去重）→ 可导出
```

**排序方式说明（诚实标注）**：

| 排序方式 | 数据来源 | 速度 | 说明 |
|---------|---------|------|------|
| 点赞数排序 | 搜索结果页 DOM 直接读取 | 快 | **推荐**。页面上可见的心形数字（如438.2K），相关性高 |
| TikTok 推荐顺序 | 不做二次排序 | 最快 | TikTok 算法本身是质量过滤，排前面的已是综合最优 |
| 播放量排序 | 逐条进入视频页读取 | 慢 | 精准但耗时，20条额外需3-4分钟，作为高级选项 |

> [!warning] 已明确不支持"收藏数排序"
> 搜索结果页 DOM 中无收藏数字段，技术上不可读取，已从选项中移除。

**批量分析时间与成本**：

| 数量 | 点赞数排序耗时 | 播放量排序耗时 | API 费用（3帧） |
|------|-------------|-------------|--------------|
| 10 条 | 2-4 分钟 | 4-6 分钟 | ~¥0.3 |
| 20 条 | 5-8 分钟 | 8-12 分钟 | ~¥0.6 |
| 30 条 | 8-12 分钟 | 13-18 分钟 | ~¥0.9 |

---

### 3.3 统一分析列表与导出

**列表来源**：
- 模式A分析后手动加入的视频
- 模式B批量分析的所有视频
- 两者自动合并，去重（相同视频链接不重复）

**列表管理**：
- 支持手动删除单条
- 支持批量选中导出
- 支持按字段排序（播放量、钩子类型、情绪弧线等）
- 本地持久化（IndexedDB），重新打开浏览器不丢失

**导出格式**：

| 格式 | 实现方式 | 适用场景 |
|------|---------|---------|
| CSV | 浏览器 Blob 下载，零依赖 | 本地分析、导入 Excel |
| 飞书多维表格 | 飞书 MCP 推送 | 团队协作、实时共享 |

**导出字段**：

| 字段名     | 示例                                |
| ------- | --------------------------------- |
| 视频链接    | https://tiktok.com/@xxx/video/xxx |
| 标题      | "站了8小时脚不疼？"                       |
| 作者      | @shoebrand_official               |
| 播放量     | 1,200,000                         |
| 点赞数     | 45,000                            |
| 钩子类型    | 痛点激发                              |
| 钩子时长（秒） | 3.2                               |
| 情绪弧线    | 痛苦 → 认同 → 解脱                      |
| 产品展示方式  | 穿着对比                              |
| 视觉风格    | 暖色/快切/大字幕                         |
| BGM 氛围  | 轻快                                |
| CTA 类型  | 软引导（评论问尺码）                        |
| 综合评分    | 高                                 |
| 分析来源    | 模式A手动 / 模式B搜索                     |
| 分析时间    | 2026-03-29 10:30                  |

---

## 四、技术架构

### 4.1 Chrome Extension 文件结构

```
extension/
├── manifest.json           # MV3 配置
├── background/
│   └── service_worker.js   # 后台任务：API调用、Tab管理
├── content_scripts/
│   ├── tiktok_video.js     # 注入视频页：Canvas截帧、Shadow DOM UI
│   └── tiktok_search.js    # 注入搜索页：DOM抓取视频列表
├── offscreen/
│   └── offscreen.html      # Offscreen Document（备用）
├── popup/
│   └── panel.html          # 插件面板 UI
├── styles/
│   └── shadow.css          # Shadow DOM 样式（隔离）
└── lib/
    └── claude_client.js    # Claude Haiku API 封装
```

### 4.2 Manifest V3 关键配置

```json
{
  "manifest_version": 3,
  "name": "TikTok 创意拆解助手",
  "permissions": [
    "activeTab",
    "scripting",
    "storage",
    "tabs"
  ],
  "host_permissions": [
    "https://www.tiktok.com/*"
  ],
  "content_scripts": [
    {
      "matches": ["https://www.tiktok.com/*"],
      "js": ["content_scripts/tiktok_video.js"],
      "run_at": "document_idle"
    },
    {
      "matches": ["https://www.tiktok.com/search/*"],
      "js": ["content_scripts/tiktok_search.js"],
      "run_at": "document_idle"
    }
  ],
  "background": {
    "service_worker": "background/service_worker.js"
  },
  "content_security_policy": {
    "extension_pages": "script-src 'self' 'wasm-unsafe-eval'"
  }
}
```

### 4.3 Canvas 截帧实现（核心）

```javascript
// content_scripts/tiktok_video.js
async function captureFrames(videoEl, frameCount = 5) {
  const frames = [];
  const duration = videoEl.duration;
  // 采样点：0.5s（开头钩子）、1.5s、3s（黄金前三秒）、中段、结尾前2s
  const timestamps = [0.5, 1.5, 3.0, duration * 0.5, duration - 2.0]
    .filter(t => t > 0 && t < duration)
    .slice(0, frameCount);

  for (const t of timestamps) {
    await seekTo(videoEl, t);
    const canvas = new OffscreenCanvas(videoEl.videoWidth, videoEl.videoHeight);
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoEl, 0, 0);
    const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.75 });
    const base64 = await blobToBase64(blob);
    frames.push({ timestamp: t, base64 });
  }
  return frames;
}

function seekTo(video, time) {
  return new Promise(resolve => {
    video.currentTime = time;
    video.addEventListener('seeked', resolve, { once: true });
  });
}
```

### 4.4 Claude Haiku API 调用（分析帧）

```javascript
// background/service_worker.js
async function analyzeFrames(frames, videoMeta) {
  const imageContent = frames.map(f => ({
    type: 'image',
    source: { type: 'base64', media_type: 'image/jpeg', data: f.base64 }
  }));

  const response = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': CLAUDE_API_KEY,   // 团队共享Key，不暴露给用户
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json'
    },
    body: JSON.stringify({
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 600,
      system: ANALYSIS_SYSTEM_PROMPT,  // 见 4.5 节
      messages: [{
        role: 'user',
        content: [
          ...imageContent,
          {
            type: 'text',
            text: `视频标题：${videoMeta.title}\n分析以上 ${frames.length} 帧，输出 JSON 格式的创意标签。`
          }
        ]
      }]
    })
  });

  const data = await response.json();
  return JSON.parse(data.content[0].text);
}
```

### 4.5 Claude 分析 Prompt（系统提示词）

```
你是专业的 TikTok 广告创意分析师，专注鞋类/服饰跨境广告。
分析给定视频帧，输出严格的 JSON 格式，不要任何额外文字。

输出 JSON 结构：
{
  "hook_type": "痛点激发|好奇悬念|社交证明|前后对比|直接产品",
  "hook_duration_sec": <前几秒是钩子，数字>,
  "emotion_arc": ["起始情绪", "...", "结尾情绪"],
  "product_focus": "舒适性|外观颜值|性价比|功能特性",
  "visual_style": {
    "color_tone": "暖色|冷色|中性",
    "edit_pace": "快切|中速|慢节奏",
    "subtitle_style": "大字幕|小字幕|无字幕"
  },
  "cta_type": "软引导|硬引导|无CTA",
  "music_vibe": "轻快|情绪|平静|燃|无",
  "estimated_engagement": "低|中|高",
  "key_insight": "<一句话总结这条视频最值得借鉴的点，中文，不超过30字>"
}
```

### 4.6 TikTok 搜索页 DOM 抓取（v2 重构）

> [!warning] 搜索结果页可读字段说明
> 页面上的心形数字（如 ❤ 438.2K）是**点赞数**，不是播放量。
> 播放量在搜索结果页 DOM 中不存在，需进入视频页才能获取。
> 代码中已移除对 `viewCount` 的依赖，改用 `likeCount` 作为主排序字段。

```javascript
// content_scripts/tiktok_search.js

// ① 监听 URL 变化，感知用户进入搜索页
function initSearchPageDetection() {
  let lastUrl = location.href;
  const observer = new MutationObserver(() => {
    if (location.href !== lastUrl) {
      lastUrl = location.href;
      if (location.href.includes('/search')) {
        // 延迟500ms等待页面内容渲染
        setTimeout(showSearchPromptBubble, 500);
      } else {
        hideSearchPromptBubble();
      }
    }
  });
  observer.observe(document.body, { childList: true, subtree: true });
}

// ② 从当前搜索结果页提取视频列表
async function extractSearchResults(targetCount = 20) {
  // 等待视频卡片出现
  await waitForSelector('[data-e2e="search_video-item"]', 10000);

  // 自动滚动加载，目标：候选池 = targetCount × 2
  await autoScrollUntil(() => {
    return document.querySelectorAll('[data-e2e="search_video-item"]').length >= targetCount * 2;
  }, { maxScrolls: 15, interval: 800 });

  const items = document.querySelectorAll('[data-e2e="search_video-item"]');
  const results = [];

  for (const item of items) {
    try {
      const link = item.querySelector('a[href*="/video/"]')?.href;
      const title = item.querySelector('[data-e2e="search-card-desc"]')?.innerText?.trim();
      // 点赞数：页面上可见的心形数字，DOM 可读 ✅
      const likeCountRaw = item.querySelector('[data-e2e="like-count"]')?.innerText
                        || item.querySelector('strong[data-e2e]')?.innerText;
      const author = item.querySelector('[data-e2e="search-card-user-unique-id"]')?.innerText;
      const thumbnail = item.querySelector('img[src*="tiktokcdn"]')?.src;
      const dateText = item.querySelector('[data-e2e="search-card-video-date"]')?.innerText;

      if (link && title) {
        results.push({
          link,
          title,
          likeCount: parseCount(likeCountRaw),  // 点赞数（页面可读）
          viewCount: null,                        // 播放量（需进视频页，默认null）
          author: author || '',
          thumbnail: thumbnail || '',
          dateText: dateText || '',
          tiktokRank: results.length             // 保留 TikTok 原始推荐顺序
        });
      }
    } catch (e) { continue; }
  }

  return results; // 返回原始列表，排序在调用层处理
}

// ③ 排序策略
function sortResults(results, sortBy, topN) {
  let sorted;
  switch (sortBy) {
    case 'likeCount':
      // 点赞数降序，DOM 直接可读，无需额外请求 ✅
      sorted = [...results].sort((a, b) => b.likeCount - a.likeCount);
      break;
    case 'tiktokOrder':
      // 保持 TikTok 算法推荐顺序 ✅
      sorted = [...results].sort((a, b) => a.tiktokRank - b.tiktokRank);
      break;
    case 'viewCount':
      // 需要逐条进入视频页读取播放量（慢模式，在 background 中处理）
      sorted = results; // 先返回原始列表，播放量异步补全后再排序
      break;
  }
  return sorted.slice(0, topN);
}

// ④ 播放量补全（慢模式专用，逐条进视频页）
async function fetchViewCounts(videos) {
  for (const video of videos) {
    const tab = await chrome.tabs.create({ url: video.link, active: false });
    await waitForTabLoad(tab.id);
    const [viewCountRaw] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => document.querySelector('[data-e2e="video-views"]')?.innerText
    });
    video.viewCount = parseCount(viewCountRaw?.result);
    await chrome.tabs.remove(tab.id);
    await sleep(1500 + Math.random() * 1000); // 随机延迟，避免频控
  }
  return videos.sort((a, b) => (b.viewCount || 0) - (a.viewCount || 0));
}

// ⑤ 数字解析："1.2M" → 1200000, "45.3K" → 45300
function parseCount(str = '') {
  if (!str) return 0;
  const clean = str.replace(/,/g, '').trim();
  const num = parseFloat(clean);
  if (isNaN(num)) return 0;
  if (clean.includes('M')) return Math.round(num * 1_000_000);
  if (clean.includes('K')) return Math.round(num * 1_000);
  return Math.round(num);
}
```

### 4.7 IndexedDB Schema

```javascript
// 数据库名：tiktok_creative_db，版本：1
const DB_SCHEMA = {
  // 存储1：已分析视频
  analyzed_videos: {
    keyPath: 'video_id',         // md5(url)
    indexes: ['analyzed_at', 'source', 'hook_type', 'estimated_engagement']
  },
  // 存储2：批量列表（跨会话持久化）
  batch_list: {
    keyPath: 'video_id',
    indexes: ['added_at', 'source']  // source: 'mode_a' | 'mode_b'
  },
  // 存储3：导出历史
  export_history: {
    keyPath: 'export_id',
    indexes: ['exported_at']
  }
};

// analyzed_videos 单条记录结构
const VIDEO_RECORD = {
  video_id: '',          // md5(url)
  source_url: '',
  title: '',
  author: '',
  view_count: 0,
  like_count: 0,
  thumbnail: '',
  analyzed_at: '',       // ISO 8601
  source: 'mode_a|mode_b',
  frames_captured: 0,
  creative: { /* Claude 输出的结构化标签 */ },
  raw_claude_response: '' // 调试用
};
```

---

## 五、UI 设计

### 5.1 悬浮按钮

- **位置**：视频左侧边缘，垂直居中，不遮挡右侧原生按钮（点赞/评论/分享）
- **样式**：圆形半透明按钮，插件图标，有列表数量徽章（`●7` 表示已收藏7条）
- **交互**：点击展开侧边面板（不跳转新页面）

### 5.2 侧边面板布局

```
┌─────────────────────────────┐
│  🎯 TikTok 创意拆解助手      │
│                    [×关闭]  │
├─────────────────────────────┤
│  ┌──────────┐ ┌──────────┐  │
│  │ 分析当前 │ │ 搜索批量 │  │
│  │  视频    │ │  分析    │  │
│  └──────────┘ └──────────┘  │
├─────────────────────────────┤
│  [模式A结果卡片 / 模式B进度] │
├─────────────────────────────┤
│  📋 收藏列表（7条）          │
│  ┌─────────────────────┐    │
│  │ ● 视频标题1   播放量 │    │
│  │ ● 视频标题2   播放量 │    │
│  │ ● 视频标题3   播放量 │    │
│  └─────────────────────┘    │
│  [导出 CSV] [推送飞书]       │
└─────────────────────────────┘
```

### 5.3 模式A分析结果卡片

```
┌─────────────────────────────┐
│ ✅ 分析完成                  │
├─────────────────────────────┤
│ 钩子类型    痛点激发         │
│ 情绪弧线   😣痛苦→😌解脱    │
│ 产品焦点    舒适性           │
│ 视觉风格    暖色/快切/大字幕 │
│ BGM 氛围    轻快             │
│ CTA 类型    软引导           │
│ 综合评分    ⭐⭐⭐ 高         │
├─────────────────────────────┤
│ 💡 这条视频最值得借鉴的点：  │
│ "久站痛点切入，情绪共鸣强，  │
│  字幕突出核心卖点"           │
├─────────────────────────────┤
│  [＋ 加入列表]    [跳过]     │  ← 3秒后自动收起
└─────────────────────────────┘
```

### 5.4 模式B — 搜索页感知气泡 + 进度展示

**① 感知气泡（用户搜索完后自动弹出）**

```
悬浮按钮右侧弹出气泡：

  ┌────────────────────────────────┐
  │ 📊 检测到搜索结果页             │
  │ 是否批量抓取并分析？            │
  │                                 │
  │ 排序依据：                      │
  │ ● 点赞数排序（推荐，速度快）    │
  │ ○ TikTok 推荐顺序（最快）      │
  │ ○ 播放量排序（慢，需进每个视频）│
  │                                 │
  │ 抓取数量：[10]  [20]  [30]      │
  │                                 │
  │ 💡 建议先切到「视频」标签页     │
  │      [开始抓取]    [忽略]       │
  └────────────────────────────────┘
```

**② 视频列表预览（抓取元数据后展示）**

```
┌─────────────────────────────────┐
│ 已找到 54 条结果，按点赞数排序   │
│ 展示前 20 条：                   │
│                                  │
│ ☑ ❤438.2K  阿迪达斯PRIME X EVO  │
│ ☑ ❤112.4K  EDM男女通用运动鞋…   │
│ ☑ ❤ 20.2K  Bila kasut secantik… │
│ ☑ ❤    157  霍卡马赫7 -          │
│    ...                           │
│                                  │
│   [全选]  [取消全选]             │
│   [确认，开始 AI 分析]           │
└─────────────────────────────────┘
```

> [!note] 列表展示说明
> 点赞数旁边显示的是 ❤（点赞），不标注"播放量"，避免误导用户。
> 若用户选择"播放量排序"，此处显示"正在进入每个视频读取播放量..."进度条。

**③ 批量分析进度**

```
┌─────────────────────────────┐
│ 🔄 批量分析中...             │
│                              │
│ ████████████░░░░  14/20      │
│ 预计还需 3 分钟               │
│                              │
│ 最新：✅ EDM男女通用运动鞋    │
│ 排队：⏳ Bila kasut secantik  │
│                              │
│            [暂停]            │
└─────────────────────────────┘
```

---

## 六、降级方案（必须实现）

| 情况 | 降级处理 | 用户提示 |
|------|---------|---------|
| Canvas 截帧失败（私密视频/特殊格式） | 弹出手动截图模式：用户框选屏幕区域提交 | "自动抓帧失败，请手动截图" |
| Claude API 超时（>20秒） | 自动重试3次，失败后提示 | "分析服务繁忙，已加入重试队列" |
| Claude API 失败（余额/网络） | 提示具体错误，保留视频信息供后续补分析 | "API 暂时不可用，视频已保存，稍后重试" |
| TikTok 搜索页 DOM 变更 | 提示"搜索功能暂时不可用"，保留手动模式 | "搜索功能需要更新，请联系管理员" |
| 视频已分析过 | IndexedDB 命中缓存，秒开显示历史结果 | "（已缓存）点击查看历史分析" |

---

## 七、数据流总览

```
TikTok.com 页面
    │
    ├── [模式A] video.currentTime + OffscreenCanvas
    │       │ 5帧 JPEG base64
    │       ▼
    │   Background Service Worker
    │       │ Claude Haiku API
    │       │ 结构化标签 JSON
    │       ▼
    │   分析结果卡片（Shadow DOM）
    │       │ 用户选择"加入列表"
    │       ▼
    │   IndexedDB: batch_list
    │
    └── [模式B] 用户自行搜索 → 插件感知 URL 变化
            │ tiktok_search.js 读取当前页 DOM
            │ 提取视频卡片（链接/标题/点赞数/作者）
            │ 客户端按点赞数排序（或保持推荐顺序）
            ▼
        for each video（逐条，有进度显示）:
            当前 Tab 导航至视频页 → Canvas 截帧 → Claude API
            ▼
        IndexedDB: batch_list（合并去重）
            │
            ▼
        导出面板
        ├── CSV 下载（Blob）
        └── 飞书多维表格推送（飞书 MCP）

        IndexedDB: analyzed_videos
        （长期存档，用于 Phase 2 创意数据库）
```

---

## 八、Phase 1 与 Phase 2 的接口

Phase 1 的 `analyzed_videos` 存储即是 Phase 2 文案系统的输入数据库。

Phase 2 从 IndexedDB 或同步到云端数据库中读取，格式见 [[TikTok广告AI工作流-PRD总览-2026-03-29]] 第七节 7.1 接口定义。

**同步策略（两个选项，需决策）**：
| 方案 | 说明 | 推荐 |
|------|------|------|
| 本地优先 | 插件写本地 IndexedDB，Phase 2 系统从本地读 | MVP 阶段，零服务器依赖 |
| 云端同步 | 插件 POST 到后端 API，Phase 2 从云端数据库读 | 团队多人共享时启用 |

---

## 九、开发里程碑

| 里程碑 | 内容 | 验收标准 |
|--------|------|---------|
| M1（Week 1）| 插件骨架 + Canvas 截帧 | 能在 TikTok 视频页截到5帧，控制台输出 base64 |
| M2（Week 1-2）| Claude API 集成 | 截帧发送给 Claude，返回结构化 JSON |
| M3（Week 2）| Shadow DOM UI + 分析卡片 | 侧边栏展示中文分析结果卡片 |
| M4（Week 2-3）| 模式A完整流程 + "加入列表"功能 | 完整走通：分析→卡片→询问→写入列表 |
| M5（Week 3）| 模式B搜索页感知 | 用户搜索后插件自动弹出气泡，点赞数排序后能展示 Top 20 视频列表 |
| M6（Week 3）| 模式B批量分析 + 进度显示 | 批量分析20条，显示进度，完成后合并列表 |
| M7（Week 3）| 导出功能 | CSV 一键下载，字段完整 |
| M8（Week 3+）| 降级方案 + 错误处理 | 所有降级场景有友好提示 |
| M9（可选）| 飞书多维表格推送 | 一键推送分析列表到飞书 |

---

## 十、已知风险与应对

| 风险 | 概率 | 影响 | 应对方案 |
|------|------|------|---------|
| TikTok 搜索页 DOM 选择器失效 | 中（TikTok 频繁改版） | 模式B列表抓取失败 | 选择器单独配置文件维护，失效时提示用户；模式A完全不受影响 |
| 点赞数字段 DOM 路径变更 | 中 | 排序退化为推荐顺序 | 多备份选择器（data-e2e / aria-label / strong标签），任一命中即可 |
| Canvas 截帧分辨率受 CSS 影响 | 低 | 帧质量下降 | 使用 `videoWidth/videoHeight` 原始分辨率而非 CSS 渲染尺寸 |
| 播放量慢模式逐条进视频被识别 | 低（真实用户浏览器） | 触发验证码 | 每条间隔1.5-2.5秒随机延迟；遇验证码弹出提示让用户手动通过后继续 |
| Claude API 成本超预期 | 低 | 费用增加 | 每日分析量软上限（默认100条），超出提示管理员；推荐使用 Batch API 享50%折扣 |
| SPA URL 监听遗漏跳转 | 低 | 模式B不自动弹出 | MutationObserver + history.pushState 双重监听 |
