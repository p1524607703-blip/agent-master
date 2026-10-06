---
title: TikTok 创意拆解插件 — Phase 1 架构文档
tags:
  - 架构文档
  - Phase1
  - Chrome Extension
  - TikTok
date: 2026-03-29
status: 定稿
project: 鞋类跨境广告
parent: "[[TikTok广告PRD-Phase1-创意拆解插件-2026-03-29]]"
team: PM + UI设计师 + 开发工程师（三方评审）
version: v1.0
---

# TikTok 创意拆解插件 — Phase 1 架构文档

> [!info] 文档说明
> 本文档由产品经理、UI 设计师、前端插件开发工程师三方联合评审产出，作为 Phase 1 开发的唯一技术基准。
> 上层需求见：[[TikTok广告PRD-Phase1-创意拆解插件-2026-03-29]]

---

## 目录

1. [[#一、需求层（PM 产出）]]
2. [[#二、设计层（UI 设计师产出）]]
3. [[#三、技术层（开发工程师产出）]]
4. [[#四、三方确认清单]]

---

## 一、需求层（PM 产出）

### 1.1 用户故事（User Stories）

#### Epic A：单视频分析（模式 A）

| ID | 用户故事 | 优先级 |
|----|---------|--------|
| A-1 | 作为竞品分析员，当我在 TikTok 刷到一条感觉很好的竞品视频时，我希望点击悬浮按钮后 15 秒内拿到结构化拆解卡片，这样我不需要切换到任何其他工具 | P0 |
| A-2 | 作为分析员，我希望在拿到分析结果后，能一键将这条视频加入"批量分析列表"，这样好内容不会遗漏 | P0 |
| A-3 | 作为分析员，我希望历史分析记录在重启浏览器后不丢失，这样几天的积累都有价值 | P1 |
| A-4 | 作为分析员，我希望分析结果卡片展示"最值得借鉴的一句话"，这样我不需要自己总结 | P1 |

#### Epic B：搜索页批量分析（模式 B）

| ID | 用户故事 | 优先级 |
|----|---------|--------|
| B-1 | 作为分析员，当我在 TikTok 搜索关键词后，我希望插件自动检测到搜索页并弹出提示气泡，这样我不需要额外操作 | P0 |
| B-2 | 作为分析员，我希望能选择"按点赞数"或"TikTok推荐顺序"批量抓取前 10/20/30 条，这样我能用最短时间获得最有价值的数据 | P0 |
| B-3 | 作为分析员，我希望在批量分析时看到进度提示（"已分析 8/20，预计还需 4 分钟"），这样我不会因等待焦虑而关闭插件 | P1 |
| B-4 | 作为分析员，我希望批量分析结果自动与模式A的列表合并去重，这样我的竞品数据库是统一的 | P1 |

#### Epic C：导出与共享

| ID | 用户故事 | 优先级 |
|----|---------|--------|
| C-1 | 作为分析员，我希望将积累的数据导出为 CSV 文件，这样我能导入 Excel 做进一步分析 | P0 |
| C-2 | 作为分析员，我希望能推送数据到飞书多维表格，这样团队可以实时查看我的分析成果 | P1 |

---

### 1.2 功能边界（In/Out Scope）

**✅ In Scope（Phase 1 包含）**

- Canvas 截帧（5帧/视频：0.5s、1.5s、3s、中段、结尾前2s）
- Claude Haiku 多模态分析（结构化 JSON 输出）
- 模式 A：单视频分析 + 是否加入列表询问
- 模式 B：搜索页感知 + 批量抓取（点赞数排序 / 推荐顺序 / 播放量慢模式）
- Shadow DOM UI 注入（完全隔离 TikTok 样式）
- IndexedDB 本地持久化（3 个 Store）
- CSV 导出（浏览器 Blob，零依赖）
- 飞书推送（飞书 MCP）
- 分析进度实时显示

**❌ Out Scope（Phase 1 不包含）**

- 自动生成广告文案（Phase 2 负责）
- 图片/视频素材生产（Phase 3 负责）
- TikTok API 对接（非官方 API 合规风险高）
- 多用户/多账号管理
- 云端数据同步（Phase 1 全本地）
- 竞品账号追踪（只分析单次搜索结果）
- 移动端（仅 Chrome 桌面版）

---

### 1.3 验收标准（Given/When/Then）

#### AC-1：模式 A 核心流程

```
Given 用户正在 TikTok 视频页观看视频（视频已开始播放）
When 用户点击悬浮按钮 → 选择"分析当前视频"
Then 插件在 15 秒内展示分析卡片
  AND 卡片包含：钩子类型、情绪弧线、视觉风格、CTA类型、一句话洞察
  AND 卡片底部显示「＋ 加入列表」和「跳过」两个按钮
  AND 3 秒后若无操作，卡片自动收起（不强制）
```

#### AC-2：模式 A → 加入列表

```
Given 用户已完成一次模式 A 分析，分析卡片正在展示
When 用户点击「＋ 加入列表」
Then 视频记录写入 IndexedDB batch_list Store
  AND 悬浮按钮上方的徽章数字 +1
  AND 显示 Toast："已加入列表（共 X 条）"，2 秒后消失
  AND 同一视频重复加入时，Toast 提示"已在列表中"，不重复写入
```

#### AC-3：模式 B 搜索感知

```
Given 用户在 TikTok 搜索任意关键词（URL 变为 /search/...）
When DOM URL 变化被 MutationObserver 检测到
Then 悬浮按钮在 500ms 内变色（绿色脉冲）
  AND 弹出提示气泡，显示排序选项和数量选择
  AND 气泡 8 秒后无操作自动收起
```

#### AC-4：模式 B 批量分析

```
Given 用户在搜索页气泡中选择"点赞数排序 / 20条" → 点击"开始抓取"
When 插件开始执行批量流程
Then 页面自动滚动直到加载 ≥ 40 条结果（2 倍候选池）
  AND 按点赞数降序取前 20 条
  AND 展示视频列表预览，用户可取消勾选
  AND 逐条执行 Canvas 截帧 + Claude 分析
  AND 进度条实时更新："已分析 X/20，预计还需 Y 分钟"
  AND 完成后自动与模式 A 列表合并去重
  AND 整批操作 API 费用 ≤ ¥1.5（30条上限）
```

#### AC-5：导出

```
Given 分析列表中有 ≥ 1 条记录
When 用户点击"导出 CSV"
Then 浏览器立即触发文件下载
  AND 文件名格式：tiktok_analysis_YYYYMMDD.csv
  AND 包含 PRD 定义的全部 15 个字段
  AND 编码 UTF-8 BOM（确保 Excel 中文不乱码）
```

---

### 1.4 数据字典（TypeScript 类型定义）

```typescript
// ============================================================
// 核心数据类型定义（IndexedDB / API 响应 / 消息通信共用）
// ============================================================

/** Claude Haiku 返回的分析结果 */
interface VideoAnalysisResult {
  // 钩子
  hook_type: '痛点激发' | '好奇悬念' | '社交证明' | '前后对比' | '直接产品';
  hook_duration_sec: number;

  // 情绪弧线（3个节点）
  emotion_arc: [string, string, string];

  // 产品聚焦
  product_focus: '舒适性' | '外观颜值' | '性价比' | '功能特性';

  // 视觉风格
  visual_style: {
    color_tone: '暖色' | '冷色' | '中性';
    edit_pace: '快切' | '中速' | '慢节奏';
    subtitle_style: '大字幕' | '小字幕' | '无字幕';
  };

  cta_type: '软引导' | '硬引导' | '无CTA';
  music_vibe: '轻快' | '情绪' | '平静' | '燃' | '无';
  estimated_engagement: '低' | '中' | '高';
  key_insight: string;  // ≤ 30 字中文
}

/** 批量分析列表条目（IndexedDB: batch_list） */
interface BatchListItem {
  id: string;                    // UUID v4
  video_url: string;             // TikTok 视频链接（唯一键）
  title: string;
  author: string;
  thumbnail_url: string;
  like_count: number;            // 点赞数（DOM 读取）
  view_count: number | null;     // 播放量（慢模式才有）
  date_text: string;             // 发布日期（原始文本）
  tiktok_rank: number;           // TikTok 推荐排序位置

  analysis: VideoAnalysisResult | null;
  analysis_status: 'pending' | 'analyzing' | 'done' | 'failed';
  analysis_error?: string;

  source: 'mode_a' | 'mode_b';   // 来源
  added_at: number;              // Unix timestamp ms
  analyzed_at: number | null;
}

/** 导出历史记录（IndexedDB: export_history） */
interface ExportRecord {
  id: string;                    // UUID v4
  export_type: 'csv' | 'feishu';
  item_count: number;
  exported_at: number;
  file_name?: string;            // CSV 文件名
  feishu_table_id?: string;      // 飞书表格 ID
  status: 'success' | 'failed';
  error?: string;
}

/** Service Worker 消息协议 */
type ExtensionMessage =
  | { type: 'ANALYZE_VIDEO'; payload: { frames: FrameData[]; meta: VideoMeta } }
  | { type: 'ANALYZE_VIDEO_RESULT'; payload: VideoAnalysisResult }
  | { type: 'ADD_TO_LIST'; payload: BatchListItem }
  | { type: 'GET_LIST'; payload?: { limit?: number; offset?: number } }
  | { type: 'LIST_DATA'; payload: { items: BatchListItem[]; total: number } }
  | { type: 'EXPORT_CSV'; payload: { ids?: string[] } }
  | { type: 'EXPORT_FEISHU'; payload: { tableId: string; ids?: string[] } }
  | { type: 'BATCH_ANALYZE_START'; payload: { videos: SearchResultItem[]; sortBy: SortType; topN: number } }
  | { type: 'BATCH_PROGRESS'; payload: { done: number; total: number; eta_sec: number } }
  | { type: 'BATCH_COMPLETE'; payload: { added: number; skipped: number } }
  | { type: 'ERROR'; payload: { code: string; message: string } };

interface FrameData {
  timestamp: number;
  base64: string;  // JPEG base64
}

interface VideoMeta {
  url: string;
  title: string;
  author: string;
  duration: number;
}

interface SearchResultItem {
  link: string;
  title: string;
  like_count: number;
  view_count: number | null;
  author: string;
  thumbnail: string;
  date_text: string;
  tiktok_rank: number;
}

type SortType = 'likeCount' | 'tiktokOrder' | 'viewCount';
```

---

### 1.5 状态机（核心流程）

```
                    ┌─────────────────────────────────────────────┐
                    │              插件生命周期                     │
                    └─────────────────┬───────────────────────────┘
                                      │ 安装/启动
                                      ▼
                              ┌───────────────┐
                              │   IDLE 待机    │◄──────────────────┐
                              │  悬浮按钮显示  │                    │
                              └───────┬───────┘                    │
                         ┌───────────┴───────────┐                 │
                         │                       │                 │
              TikTok 视频页               TikTok 搜索页            │
                         │                       │                 │
                         ▼                       ▼                 │
               ┌──────────────┐       ┌──────────────────┐        │
               │ MODE_A_READY │       │  SEARCH_DETECTED  │        │
               │ 等待用户触发  │       │  气泡弹出提示      │        │
               └──────┬───────┘       └────────┬──────────┘        │
                      │ 点击分析                │ 点击开始抓取       │
                      ▼                        ▼                   │
               ┌──────────────┐       ┌──────────────────┐        │
               │  CAPTURING   │       │  SCROLLING_LOAD  │        │
               │  Canvas 截帧  │       │  自动滚动加载数据  │        │
               └──────┬───────┘       └────────┬──────────┘        │
                      │                        │ 加载完成           │
                      │                        ▼                   │
                      │               ┌──────────────────┐        │
                      │               │  PREVIEW_SELECT  │        │
                      │               │  视频列表预览     │        │
                      │               └────────┬──────────┘        │
                      │                        │ 确认开始           │
                      ▼                        ▼                   │
               ┌──────────────────────────────────────┐           │
               │           ANALYZING 分析中            │           │
               │  逐帧调用 Claude Haiku API             │           │
               │  进度：[████░░░░] 8/20，还需 4 分钟   │           │
               └──────────────────┬───────────────────┘           │
                                   │ 完成                          │
                                   ▼                               │
                          ┌─────────────────┐                      │
                          │  RESULT_READY   │                      │
                          │  展示分析卡片   │                      │
                          └────────┬────────┘                      │
                     ┌─────────────┴─────────────┐                 │
                     │ 加入列表                    │ 跳过/关闭       │
                     ▼                            └────────────────►┤
              ┌─────────────┐                                       │
              │ SAVED 已保存 │──────────────────────────────────────┘
              └─────────────┘
```

---

### 1.6 边界情况与异常处理（12 个 Edge Cases）

| # | 场景 | 处理策略 |
|---|------|---------|
| E-01 | 视频尚未加载完成（duration=NaN）| 等待 `loadedmetadata` 事件，超时 5s 显示"视频未就绪" |
| E-02 | Canvas 截帧返回黑帧（全黑/白）| 检测平均亮度 < 10，跳过该帧并补一帧 |
| E-03 | Claude API 返回非 JSON 格式 | 重试一次（不同 prompt 结尾），二次失败标记 `analysis_status: 'failed'` |
| E-04 | Claude API 返回 429（超速率）| 指数退避：1s → 2s → 4s → 8s，超过 4 次放弃 |
| E-05 | 搜索页 DOM 选择器失效（TikTok 改版）| 降级到 `querySelectorAll('a[href*="/video/"]')`，同时上报到错误日志 |
| E-06 | 搜索结果加载不足 N×2 条 | 滚动 15 次后停止，使用已有数量（显示提示：仅抓取到 X 条） |
| E-07 | 同一视频重复分析 | 检查 `batch_list` 中是否已有相同 `video_url`，已有则跳过并 Toast 提示 |
| E-08 | IndexedDB 存储空间不足（>50MB）| 弹出提示"本地存储已满，请导出并清理"，阻止新写入 |
| E-09 | Service Worker 被浏览器休眠 | Content Script 在发送消息时检测 SW 是否存活，死则 ping 唤醒后重发 |
| E-10 | 播放量慢模式：视频页加载超时 | 单个视频页加载超时 15s，跳过该条（view_count 保留 null），继续下一条 |
| E-11 | 飞书推送失败 | 本地保留数据，显示错误原因（token 过期 / 网络问题），提供"重试"按钮 |
| E-12 | 用户在批量分析进行中切换页面 | 弹出确认框："正在分析 8/20，离开会中断。确认离开？" |

---

## 二、设计层（UI 设计师产出）

### 2.1 设计系统

#### 色彩规范

```
主题：深色沉浸（不抢夺 TikTok 视觉焦点）

主色
  --color-primary:        #00D4AA   // TikTok 品牌绿（认知一致性）
  --color-primary-hover:  #00B894
  --color-primary-dim:    rgba(0, 212, 170, 0.15)

背景
  --bg-panel:             #1A1A1A   // 插件面板主背景
  --bg-card:              #242424   // 卡片背景
  --bg-input:             #2E2E2E   // 输入框/选择器背景
  --bg-overlay:           rgba(0, 0, 0, 0.6)  // 遮罩层

文字
  --text-primary:         #FFFFFF
  --text-secondary:       #B0B0B0
  --text-muted:           #666666
  --text-accent:          #00D4AA

语义色
  --color-success:        #00D4AA
  --color-warning:        #FFB800
  --color-error:          #FF4757
  --color-info:           #5E9EFF

边框
  --border-default:       rgba(255, 255, 255, 0.08)
  --border-active:        rgba(0, 212, 170, 0.4)
```

#### 字体规范

```
字体栈：-apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif

层级：
  --text-xl:    16px / font-weight: 600  // 面板标题
  --text-lg:    14px / font-weight: 600  // 卡片标题、按钮文字
  --text-md:    13px / font-weight: 400  // 正文内容
  --text-sm:    12px / font-weight: 400  // 辅助信息、标签
  --text-xs:    11px / font-weight: 400  // 时间戳、版本号

行高：1.5（统一）
字间距：正文 0，标题 0.02em
```

#### 间距系统（8px 网格）

```
--space-1:  4px
--space-2:  8px    ← 基准单位
--space-3:  12px
--space-4:  16px
--space-5:  20px
--space-6:  24px
--space-8:  32px

圆角：
  --radius-sm:   6px   // 标签、小按钮
  --radius-md:   10px  // 卡片
  --radius-lg:   14px  // 面板、弹窗
  --radius-full: 999px // 徽章、药丸形状
```

#### 阴影规范

```
--shadow-panel:  0 8px 32px rgba(0,0,0,0.5), 0 2px 8px rgba(0,0,0,0.3)
--shadow-card:   0 2px 8px rgba(0,0,0,0.3)
--shadow-float:  0 4px 16px rgba(0,212,170,0.2)  // 悬浮按钮高亮状态
```

---

### 2.2 组件规范与线框图

#### 组件 01：悬浮按钮（Floating Action Button）

```
位置：页面右侧，距右边缘 16px，垂直居中偏上（top: 40%）

┌────────────────────────────────────────┐
│                                        │
│                              ╔═══════╗ │
│   TikTok 原生界面             ║ [🔍]  ║ │  ← 待机状态（白色图标）
│                              ║  ●3   ║ │  ← 徽章：列表中3条记录
│                              ╚═══════╝ │
│                                        │
└────────────────────────────────────────┘

尺寸：44×44px（遵循触控目标最小尺寸）
背景：#1A1A1A，透明度 90%
边框：1px solid rgba(255,255,255,0.1)
圆角：12px

状态变体：
  待机     → 白色图标，背景 #1A1A1A
  搜索页   → 绿色脉冲动画，图标变为 #00D4AA
  分析中   → 旋转加载动画（CSS @keyframes spin）
  有新结果 → 绿色闪烁（fade-in-out 1.5s）

徽章（数量 ≥ 1 时显示）：
  位置：按钮右上角，偏移 -6px/-6px
  尺寸：16×16px，最大显示 99+
  颜色：#FF4757（红色，醒目）
```

#### 组件 02：分析结果卡片（Analysis Card）

```
触发：模式 A 分析完成后，从右侧滑入

┌─────────────────────────────────────────┐
│ TikTok 创意拆解                    ✕   │  ← 标题栏（16px，关闭按钮）
├─────────────────────────────────────────┤
│                                         │
│  🎣 钩子                                │
│  ┌──────────────┐  ┌─────────────────┐  │
│  │  痛点激发    │  │   前 3.2 秒     │  │  ← 标签（绿色背景）
│  └──────────────┘  └─────────────────┘  │
│                                         │
│  💭 情绪弧线                            │
│  痛苦 ──────►  认同 ──────►  解脱      │  ← 箭头流程
│                                         │
│  🎨 视觉风格                            │
│  暖色 · 快切 · 大字幕                   │  ← 逗号分隔行
│                                         │
│  📢 CTA 类型                            │
│  软引导（评论问尺码）                    │
│                                         │
│  ─────────────────────────────────────  │
│  💡 核心洞察                            │
│  ┌─────────────────────────────────────┐│
│  │ 前3秒用"站了8小时脚不疼"直击        ││  ← 绿色背景卡片
│  │ 办公族痛点，代入感极强              ││
│  └─────────────────────────────────────┘│
│                                         │
│  ─────────────────────────────────────  │
│  [＋ 加入列表]          [跳过]          │  ← 主/次按钮
│  （3秒后自动收起）                      │  ← 小字提示
└─────────────────────────────────────────┘

尺寸：宽 320px，高度自适应（最大 480px，超出滚动）
位置：右侧悬浮，距右边缘 72px（不遮挡悬浮按钮）
动画：translateX(360px→0) ease-out 280ms
```

#### 组件 03：搜索感知提示气泡（Search Prompt Bubble）

```
触发：检测到 URL 含 /search 后 500ms

┌────────────────────────────────────┐
│ 📊 检测到搜索结果页                 │
│ 是否批量抓取并分析？                │
├────────────────────────────────────┤
│ 排序依据：                          │
│ ● 点赞数（推荐，快速）              │
│ ○ TikTok 推荐顺序                   │
│ ○ 播放量（慢，需进每个视频页）       │
├────────────────────────────────────┤
│ 抓取数量：                          │
│  ┌─────┐  ┌─────┐  ┌─────┐        │
│  │ 10  │  │ 20  │  │ 30  │        │  ← 选中态：绿色描边
│  └─────┘  └─────┘  └─────┘        │
├────────────────────────────────────┤
│  [开始抓取]           [忽略]        │
└────────────────────────────────────┘

位置：悬浮按钮上方，向左展开
尺寸：宽 280px
动画：scaleY(0→1) + opacity(0→1) origin-bottom-right 200ms
自动收起：8 秒无操作（右上角倒计时指示条）
```

#### 组件 04：批量分析进度面板（Batch Progress Panel）

```
┌─────────────────────────────────────────┐
│ 批量分析进行中                    [暂停] │
├─────────────────────────────────────────┤
│                                         │
│  已分析 8 / 20                          │
│  ████████████░░░░░░░░░░░░  40%          │  ← 进度条（绿色填充）
│                                         │
│  预计剩余时间：约 4 分钟                 │
│  API 费用：约 ¥0.24 / ¥0.60            │  ← 已用/预计总费用
│                                         │
│  当前：分析 @sneakerzone_daily 的视频...│  ← 当前处理项
│                                         │
│  ✅ @footwear_trends  痛点激发 · 高     │  ← 已完成缩略
│  ✅ @shoes_for_life   好奇悬念 · 中     │
│  ⏳ @sneakerzone_daily （分析中）        │
│  ○  @footwear_usa     （队列中）        │
└─────────────────────────────────────────┘

位置：右侧固定，替换分析结果卡片区域
宽度：320px
```

#### 组件 05：分析列表面板（List Panel）

```
点击悬浮按钮 → 主面板打开 → Tab 切换到"列表"

┌─────────────────────────────────────────┐
│ [分析]  [列表 ●7]  [设置]              ✕ │  ← Tab 导航
├─────────────────────────────────────────┤
│ 🔍 搜索列表...        排序: [点赞数 ▼]  │
├─────────────────────────────────────────┤
│ □ ┌────────────────────────────────┐    │
│   │ 🖼 [缩略图]  站了8小时脚不疼    │    │
│   │             @shoebrand 45.3K❤  │    │
│   │             痛点激发 · 高       │    │  ← 列表条目
│   └────────────────────────────────┘    │
│ □ ┌────────────────────────────────┐    │
│   │ 🖼 [缩略图]  穿上它直接起飞    │    │
│   │             @kicks_daily 23K❤  │    │
│   │             好奇悬念 · 中       │    │
│   └────────────────────────────────┘    │
│   （更多条目...）                        │
├─────────────────────────────────────────┤
│ [导出 CSV]    [推送飞书]    [清空列表]   │
└─────────────────────────────────────────┘
```

#### 组件 06：设置面板（Settings Panel）

```
┌─────────────────────────────────────────┐
│ 设置                                    │
├─────────────────────────────────────────┤
│ API 配置                                │
│ Claude API Key                          │
│ ┌─────────────────────────────────────┐ │
│ │ sk-ant-••••••••••••••••••         👁 │ │
│ └─────────────────────────────────────┘ │
│ [验证 Key]                   ✅ 已验证  │
│                                         │
│ 飞书配置                                │
│ Webhook URL                             │
│ ┌─────────────────────────────────────┐ │
│ │ https://open.feishu.cn/...          │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 分析设置                                │
│ 截帧数量  ○ 3帧（快）  ● 5帧（精准）   │
│ 分析语言  ● 中文       ○ 英文          │
│                                         │
│ 存储管理                                │
│ 已使用 12.3 MB / 50 MB                 │
│ ████░░░░░░░░░░░░░░░░  25%              │
│ [导出备份]              [清空本地数据] │
└─────────────────────────────────────────┘
```

---

### 2.3 动画规范

| 动画场景 | 属性 | 时长 | 缓动 |
|---------|------|------|------|
| 面板展开 | translateX / opacity | 280ms | ease-out |
| 面板收起 | translateX / opacity | 200ms | ease-in |
| 气泡弹出 | scale(0.8→1) + opacity | 200ms | cubic-bezier(0.34,1.56,0.64,1)（弹性） |
| 进度条填充 | width | 600ms | linear |
| Toast 出现 | translateY + opacity | 160ms | ease-out |
| Toast 消失 | opacity | 120ms | ease-in |
| 悬浮按钮脉冲 | box-shadow | 1500ms | ease-in-out，infinite |
| 加载旋转 | rotate(360deg) | 800ms | linear，infinite |

**原则：所有动画使用 `transform` 和 `opacity`，避免触发重排（layout）。**

---

### 2.4 响应式断点

| 分辨率 | 面板宽度 | 字体 | 备注 |
|--------|---------|------|------|
| < 1366px | 280px | -1px | 笔记本低分辨率适配 |
| 1366-1920px | 320px | 默认 | 主要使用场景 |
| > 1920px | 360px | +1px | 大显示器提升可读性 |

---

### 2.5 Shadow DOM 融合策略

```javascript
// Shadow DOM 接入方案（完全隔离 TikTok CSS 污染）
const host = document.createElement('div');
host.id = 'tiktok-analyzer-root';
document.body.appendChild(host);

const shadow = host.attachShadow({ mode: 'closed' });  // closed 模式防止外部JS访问

// 注入样式（通过 CSSStyleSheet 而非 <link> 标签）
const sheet = new CSSStyleSheet();
sheet.replaceSync(SHADOW_CSS);  // 打包时 inline 进来
shadow.adoptedStyleSheets = [sheet];

// 渲染根
const container = document.createElement('div');
container.id = 'app';
shadow.appendChild(container);
```

**重要约束**：
- 所有 `querySelector` 必须在 `shadow.querySelector` 内执行（不影响主页面 DOM）
- 字体通过 `@font-face` 在 Shadow CSS 内定义（不依赖宿主页面字体）
- `z-index` 统一设为 `2147483647`（最大值，确保在 TikTok 浮层之上）

---

## 三、技术层（开发工程师产出）

### 3.1 完整目录结构

```
tiktok-analyzer/
├── manifest.json
├── package.json
├── vite.config.ts
├── tsconfig.json
│
├── src/
│   ├── background/
│   │   ├── service_worker.ts      # 消息路由 + API调用 + IndexedDB管理
│   │   ├── claude_client.ts       # Claude API 封装（重试、限流、错误处理）
│   │   ├── db.ts                  # IndexedDB 操作层（CRUD）
│   │   └── export.ts              # CSV 生成 + 飞书推送逻辑
│   │
│   ├── content/
│   │   ├── video_page/
│   │   │   ├── index.ts           # 入口：Shadow DOM 挂载、悬浮按钮
│   │   │   ├── capture.ts         # Canvas 截帧核心逻辑
│   │   │   └── ui/
│   │   │       ├── FloatButton.ts   # 悬浮按钮组件
│   │   │       ├── AnalysisCard.ts  # 分析结果卡片
│   │   │       └── BatchProgress.ts # 批量进度面板
│   │   │
│   │   └── search_page/
│   │       ├── index.ts           # 入口：搜索页检测
│   │       ├── detector.ts        # URL 变化监听 + 气泡触发
│   │       ├── scraper.ts         # DOM 抓取 + 排序逻辑
│   │       └── ui/
│   │           └── SearchBubble.ts  # 搜索提示气泡
│   │
│   ├── popup/
│   │   ├── index.html
│   │   ├── App.ts                 # 面板入口
│   │   ├── ListPanel.ts           # 列表面板
│   │   └── SettingsPanel.ts       # 设置面板
│   │
│   ├── styles/
│   │   ├── shadow.css             # Shadow DOM 内样式（完整设计系统）
│   │   └── popup.css              # 面板样式
│   │
│   └── shared/
│       ├── types.ts               # 全量类型定义（见 1.4 节）
│       ├── constants.ts           # 常量：SYSTEM_PROMPT、DB_NAME、Store名
│       ├── utils.ts               # parseCount、blobToBase64、sleep、uuid
│       └── messages.ts            # 消息类型常量
│
├── public/
│   ├── icon-16.png
│   ├── icon-48.png
│   └── icon-128.png
│
└── dist/                          # 构建输出（不提交 git）
```

---

### 3.2 进程通信图（完整消息流）

```
Content Script (video_page)          Service Worker              Content Script (search_page)
         │                                 │                                │
         │  ANALYZE_VIDEO                  │                                │
         │  { frames[], meta }             │                                │
         │────────────────────────────────►│                                │
         │                                 │ fetch Claude API               │
         │                                 │────────────►  Anthropic        │
         │                                 │◄────────────  API Response     │
         │  ANALYZE_VIDEO_RESULT           │                                │
         │◄────────────────────────────────│                                │
         │                                 │                                │
         │  ADD_TO_LIST                    │                                │
         │  { BatchListItem }              │                                │
         │────────────────────────────────►│                                │
         │                                 │  db.put(batch_list, item)      │
         │  LIST_UPDATED { id, total }     │                                │
         │◄────────────────────────────────│                                │
         │                                 │                                │
         │                                 │  BATCH_ANALYZE_START           │
         │                                 │◄───────────────────────────────│
         │                                 │  { videos[], sortBy, topN }    │
         │                                 │                                │
         │                                 │  [循环每条视频]                │
         │  CAPTURE_VIDEO                  │                                │
         │◄────────────────────────────────│                                │
         │  { url, frameCount }            │                                │
         │  CAPTURE_DONE { frames[] }      │                                │
         │────────────────────────────────►│                                │
         │                                 │  fetch Claude API              │
         │                                 │  BATCH_PROGRESS { done, eta }  │
         │                                 │───────────────────────────────►│
         │                                 │  [继续下一条...]               │
         │                                 │                                │
         │                                 │  BATCH_COMPLETE { added, skip }│
         │                                 │───────────────────────────────►│
         │                                 │                                │
Popup Panel                               │
         │  GET_LIST { limit, offset }     │
         │────────────────────────────────►│
         │  LIST_DATA { items[], total }   │
         │◄────────────────────────────────│
         │  EXPORT_CSV { ids? }            │
         │────────────────────────────────►│
         │                                 │  生成 Blob → sendMessage 返回  │
         │  CSV_READY { dataUrl }          │
         │◄────────────────────────────────│
```

---

### 3.3 IndexedDB Schema（完整定义）

```typescript
// src/background/db.ts

const DB_NAME = 'TikTokAnalyzer';
const DB_VERSION = 1;

// ── Store 1：batch_list（分析列表）──────────────────────────
// keyPath: 'id'（UUID v4）
// 索引：
//   - 'by_url'        on video_url     （唯一索引，防重复）
//   - 'by_added_at'   on added_at      （时间排序）
//   - 'by_like_count' on like_count    （点赞数排序）
//   - 'by_status'     on analysis_status （筛选 pending/failed）

// ── Store 2：export_history（导出历史）─────────────────────
// keyPath: 'id'
// 索引：
//   - 'by_exported_at' on exported_at

// ── Store 3：settings（用户设置）───────────────────────────
// keyPath: 'key'（字符串，如 'api_key', 'feishu_webhook'）
// 注意：API Key 加密存储（使用 chrome.storage.local，更安全）

class AnalyzerDB {
  private db: IDBDatabase | null = null;

  async open(): Promise<IDBDatabase> {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);

      req.onupgradeneeded = (e) => {
        const db = (e.target as IDBOpenDBRequest).result;

        // batch_list store
        if (!db.objectStoreNames.contains('batch_list')) {
          const store = db.createObjectStore('batch_list', { keyPath: 'id' });
          store.createIndex('by_url', 'video_url', { unique: true });
          store.createIndex('by_added_at', 'added_at');
          store.createIndex('by_like_count', 'like_count');
          store.createIndex('by_status', 'analysis_status');
        }

        // export_history store
        if (!db.objectStoreNames.contains('export_history')) {
          const store = db.createObjectStore('export_history', { keyPath: 'id' });
          store.createIndex('by_exported_at', 'exported_at');
        }
      };

      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async addToList(item: BatchListItem): Promise<'added' | 'duplicate'> {
    const db = await this.open();
    return new Promise((resolve, reject) => {
      const tx = db.transaction('batch_list', 'readwrite');
      const req = tx.objectStore('batch_list').add(item);
      req.onsuccess = () => resolve('added');
      req.onerror = (e) => {
        if ((e.target as IDBRequest).error?.name === 'ConstraintError') {
          resolve('duplicate');
        } else {
          reject((e.target as IDBRequest).error);
        }
      };
    });
  }

  async getList(options: { sortBy?: string; limit?: number; offset?: number }): Promise<BatchListItem[]> {
    // 实现分页查询逻辑（IDBKeyRange + cursor）
    // ...
  }

  async updateAnalysisResult(id: string, result: VideoAnalysisResult): Promise<void> {
    // ...
  }

  async getStorageSize(): Promise<number> {
    // 使用 navigator.storage.estimate() 获取已用空间
    const estimate = await navigator.storage.estimate();
    return estimate.usage || 0;
  }
}
```

---

### 3.4 核心模块伪代码

#### Service Worker 消息路由

```typescript
// src/background/service_worker.ts
chrome.runtime.onMessage.addListener((msg: ExtensionMessage, sender, sendResponse) => {
  // 必须同步返回 true 表示异步响应
  handleMessage(msg, sender).then(sendResponse).catch(err => {
    sendResponse({ type: 'ERROR', payload: { code: err.code || 'UNKNOWN', message: err.message } });
  });
  return true;
});

async function handleMessage(msg: ExtensionMessage, sender: chrome.runtime.MessageSender) {
  switch (msg.type) {
    case 'ANALYZE_VIDEO':
      return await analyzeFrames(msg.payload.frames, msg.payload.meta);

    case 'ADD_TO_LIST':
      const result = await db.addToList(msg.payload);
      const total = await db.countList();
      return { type: 'LIST_UPDATED', payload: { id: msg.payload.id, total, result } };

    case 'GET_LIST':
      const items = await db.getList(msg.payload || {});
      return { type: 'LIST_DATA', payload: items };

    case 'BATCH_ANALYZE_START':
      // 不 await，异步推进，通过 BATCH_PROGRESS 消息推送进度
      startBatchAnalysis(msg.payload, sender.tab!.id!);
      return { type: 'BATCH_STARTED' };

    case 'EXPORT_CSV':
      const csv = await generateCSV(msg.payload.ids);
      return { type: 'CSV_READY', payload: { csv } };

    case 'EXPORT_FEISHU':
      await pushToFeishu(msg.payload);
      return { type: 'FEISHU_DONE' };

    default:
      throw { code: 'UNKNOWN_MSG_TYPE', message: `Unknown: ${(msg as any).type}` };
  }
}
```

#### Claude API 客户端（含重试）

```typescript
// src/background/claude_client.ts
const MAX_RETRIES = 4;
const BASE_DELAY_MS = 1000;

async function analyzeFrames(
  frames: FrameData[],
  meta: VideoMeta
): Promise<VideoAnalysisResult> {
  const apiKey = await getApiKey();  // 从 chrome.storage.local 读取

  for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
    try {
      const response = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: {
          'x-api-key': apiKey,
          'anthropic-version': '2023-06-01',
          'content-type': 'application/json'
        },
        body: JSON.stringify({
          model: 'claude-haiku-4-5-20251001',
          max_tokens: 600,
          system: ANALYSIS_SYSTEM_PROMPT,
          messages: [{
            role: 'user',
            content: [
              ...frames.map(f => ({
                type: 'image' as const,
                source: { type: 'base64' as const, media_type: 'image/jpeg' as const, data: f.base64 }
              })),
              { type: 'text', text: `视频标题：${meta.title}\n分析以上帧，输出 JSON 创意标签。` }
            ]
          }]
        })
      });

      if (response.status === 429) {
        const delay = BASE_DELAY_MS * Math.pow(2, attempt);
        await sleep(delay);
        continue;
      }

      if (!response.ok) {
        throw { code: `HTTP_${response.status}`, message: await response.text() };
      }

      const data = await response.json();
      const text = data.content[0].text;

      // 提取 JSON（处理模型可能包裹 ``` 的情况）
      const jsonMatch = text.match(/\{[\s\S]*\}/);
      if (!jsonMatch) throw { code: 'PARSE_ERROR', message: 'No JSON in response' };

      return JSON.parse(jsonMatch[0]) as VideoAnalysisResult;

    } catch (err: any) {
      if (attempt === MAX_RETRIES - 1) throw err;
      if (err.code === 'PARSE_ERROR' && attempt === 0) {
        // 第一次解析失败，在 prompt 末尾加强 JSON 约束后重试
        continue;
      }
    }
  }
  throw { code: 'MAX_RETRIES', message: 'Exceeded maximum retry attempts' };
}
```

#### Canvas 截帧（完整实现）

```typescript
// src/content/video_page/capture.ts
export async function captureFrames(
  videoEl: HTMLVideoElement,
  frameCount = 5
): Promise<FrameData[]> {
  const duration = videoEl.duration;
  if (!duration || isNaN(duration)) {
    throw { code: 'VIDEO_NOT_READY', message: '视频时长未知，请等待视频加载完成' };
  }

  // 采样时间点
  const rawTimestamps = [0.5, 1.5, 3.0, duration * 0.5, duration - 2.0];
  const timestamps = rawTimestamps
    .filter(t => t > 0 && t < duration)
    .slice(0, frameCount);

  const frames: FrameData[] = [];

  for (const t of timestamps) {
    await seekTo(videoEl, t);

    const canvas = new OffscreenCanvas(
      Math.min(videoEl.videoWidth, 1280),   // 限制最大宽度，减少 base64 体积
      Math.min(videoEl.videoHeight, 720)
    );
    const ctx = canvas.getContext('2d')!;
    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);

    // 检测黑帧
    const imageData = ctx.getImageData(0, 0, 20, 20);  // 采样左上角20×20
    const avgBrightness = calcAvgBrightness(imageData.data);
    if (avgBrightness < 10) continue;  // 跳过黑帧

    const blob = await canvas.convertToBlob({ type: 'image/jpeg', quality: 0.75 });
    const base64 = await blobToBase64(blob);
    frames.push({ timestamp: t, base64 });
  }

  if (frames.length === 0) {
    throw { code: 'ALL_BLACK_FRAMES', message: '所有帧均为黑帧，视频可能受 DRM 保护' };
  }

  return frames;
}

function seekTo(video: HTMLVideoElement, time: number): Promise<void> {
  return new Promise((resolve, reject) => {
    const timeout = setTimeout(() => reject({ code: 'SEEK_TIMEOUT' }), 5000);
    video.addEventListener('seeked', () => {
      clearTimeout(timeout);
      resolve();
    }, { once: true });
    video.currentTime = time;
  });
}

function calcAvgBrightness(data: Uint8ClampedArray): number {
  let sum = 0;
  for (let i = 0; i < data.length; i += 4) {
    sum += (data[i] * 0.299 + data[i+1] * 0.587 + data[i+2] * 0.114);
  }
  return sum / (data.length / 4);
}
```

---

### 3.5 Manifest.json（完整版）

```json
{
  "manifest_version": 3,
  "name": "TikTok 创意拆解助手",
  "version": "1.0.0",
  "description": "鞋类广告竞品分析：一键拆解 TikTok 视频创意公式，积累结构化创意数据库",

  "icons": {
    "16": "public/icon-16.png",
    "48": "public/icon-48.png",
    "128": "public/icon-128.png"
  },

  "permissions": [
    "activeTab",
    "scripting",
    "storage",
    "tabs"
  ],

  "host_permissions": [
    "https://www.tiktok.com/*",
    "https://api.anthropic.com/*"
  ],

  "content_scripts": [
    {
      "matches": ["https://www.tiktok.com/*"],
      "js": ["content/video_page/index.js"],
      "css": [],
      "run_at": "document_idle",
      "all_frames": false
    },
    {
      "matches": ["https://www.tiktok.com/search/*"],
      "js": ["content/search_page/index.js"],
      "run_at": "document_idle"
    }
  ],

  "background": {
    "service_worker": "background/service_worker.js",
    "type": "module"
  },

  "action": {
    "default_popup": "popup/index.html",
    "default_icon": {
      "16": "public/icon-16.png",
      "48": "public/icon-48.png"
    }
  },

  "content_security_policy": {
    "extension_pages": "script-src 'self'; object-src 'self'"
  },

  "web_accessible_resources": [
    {
      "resources": ["styles/shadow.css", "public/*.png"],
      "matches": ["https://www.tiktok.com/*"]
    }
  ]
}
```

---

### 3.6 Vite 构建配置

```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import { crx } from '@crxjs/vite-plugin';
import manifest from './manifest.json';

export default defineConfig({
  plugins: [
    crx({ manifest })
  ],
  build: {
    rollupOptions: {
      input: {
        popup: 'src/popup/index.html',
      }
    },
    // 内联 shadow.css 到 JS 模块（避免 web_accessible_resources 暴露路径）
    assetsInlineLimit: 65536
  }
});
```

**构建脚本**（`package.json`）：

```json
{
  "scripts": {
    "dev": "vite build --watch",
    "build": "vite build",
    "zip": "npm run build && cd dist && zip -r ../tiktok-analyzer.zip ."
  },
  "dependencies": {},
  "devDependencies": {
    "vite": "^5.0.0",
    "@crxjs/vite-plugin": "^2.0.0",
    "typescript": "^5.0.0"
  }
}
```

---

### 3.7 安全策略

#### API Key 存储

```typescript
// ❌ 错误：硬编码在源码中
const API_KEY = 'sk-ant-xxxx';

// ✅ 正确：存储在 chrome.storage.local（加密分区，不随 profile 同步）
async function getApiKey(): Promise<string> {
  const result = await chrome.storage.local.get('claude_api_key');
  if (!result.claude_api_key) {
    throw { code: 'NO_API_KEY', message: '请先在设置中配置 Claude API Key' };
  }
  return result.claude_api_key;
}

async function saveApiKey(key: string): Promise<void> {
  // 验证格式
  if (!key.startsWith('sk-ant-')) {
    throw { code: 'INVALID_KEY_FORMAT', message: 'API Key 格式错误' };
  }
  await chrome.storage.local.set({ claude_api_key: key });
}
```

#### Content Security Policy

```
extension_pages CSP: "script-src 'self'; object-src 'self'"
- 禁止 eval() 和 inline script
- 禁止加载外部 JS（除 Anthropic API 通过 fetch 调用，不需要 CSP 例外）
- Shadow DOM 中所有 innerHTML 赋值均经过 DOMPurify 清洗（防 XSS）
```

#### Shadow DOM XSS 防护

```typescript
// 视频标题等用户数据严禁直接 innerHTML
// ❌
element.innerHTML = videoTitle;

// ✅
element.textContent = videoTitle;
// 或使用 textContent + createElement 组合构建 DOM
```

#### 权限最小化原则

- `activeTab`：仅当前激活 Tab，不访问后台 Tab
- `scripting`：仅用于 `executeScript` 执行截帧（播放量慢模式）
- `tabs`：仅用于慢模式下开启/关闭视频页 Tab
- 无 `cookies`、无 `webRequest`、无 `history` 权限

---

### 3.8 错误处理策略总览

```
错误来源              处理层级            用户感知
────────────────────────────────────────────────────
Canvas 截帧失败      content/capture.ts   Toast "截帧失败，请确认视频正在播放"
Claude API 429      background/claude    自动重试（用户不感知），超限后 Toast
Claude 返回非JSON   background/claude    自动重试一次，失败标记 analysis_status=failed
IndexedDB 存满      background/db        弹窗阻止操作，提示清理
DOM 选择器失效      content/scraper      降级方案 + 上报错误日志（chrome.storage）
网络断线            background/claude    Toast "网络异常，请检查网络连接"
SW 休眠            content/index.ts     自动 ping 唤醒，无感知
视频 DRM 保护       content/capture.ts   Toast "该视频受版权保护，无法截帧"
```

---

## 四、三方确认清单

> [!success] 开发启动前必须全部勾选

**需求层（PM 确认）**

- [x] 用户故事覆盖全部核心场景（A-1 ～ C-2）
- [x] 功能边界清晰，Phase 1 不包含文案生成和素材制作
- [x] 验收标准可测试（Given/When/Then 格式）
- [x] 12 个边界情况有明确处理策略
- [x] 数据字典已定义全部字段和类型

**设计层（UI 确认）**

- [x] 设计系统完整（色彩/字体/间距/阴影）
- [x] 6 个核心组件有线框图和尺寸规范
- [x] Shadow DOM 隔离策略已确认（closed 模式）
- [x] 动画规范全部使用 transform/opacity（无重排）
- [x] z-index 统一使用最大值（2147483647）

**技术层（Dev 确认）**

- [x] 目录结构已定义，无模糊文件
- [x] 进程通信消息协议完整（所有 type 有 payload 定义）
- [x] IndexedDB 3 个 Store 及索引已定义
- [x] Canvas 截帧已处理黑帧检测、DRM 保护、seeked 超时
- [x] Claude API 客户端实现指数退避（4次，最大延迟8s）
- [x] API Key 使用 chrome.storage.local（不硬编码、不同步到云端）
- [x] Manifest V3 CSP 无 unsafe-eval / unsafe-inline
- [x] 构建工具链已选定（Vite + @crxjs/vite-plugin + TypeScript）

**跨层确认（三方）**

- [x] 消息类型 `ExtensionMessage` 在 `src/shared/types.ts` 统一定义，三层共用
- [x] CSV 导出字段与 PRD 第 3.3 节 15 个字段完全一致
- [x] 批量分析费用上限（30条 ≤ ¥1.5）已在 UI 进度面板实时展示
- [x] 模式 A 和模式 B 数据统一合并去重逻辑已在 `by_url` 唯一索引实现

---

> [!note] 下一步
> 架构文档确认后，进入 **开发阶段**：
> 1. Codex 搭建项目骨架（package.json + tsconfig + vite.config）
> 2. Claude Review 代码结构
> 3. 按模块顺序开发：db.ts → claude_client.ts → capture.ts → content script UI → popup
> 4. 本地 Chrome 加载 `dist/` 目录测试
> 5. 通过全部 AC 验收标准后，打包为 .zip 提交 Chrome Web Store
