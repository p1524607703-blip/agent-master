---
name: reddit市场调研
description: 针对指定产品关键词，通过 Reddit 公开 API 抓取真实用户讨论，结合 Tavily 预筛选相关子版块，直接分析并生成市场洞察报告，最终写入 Obsidian 笔记。
type: skill
triggers:
  - reddit
  - 市场调研
  - reddit调研
  - 产品调研
  - 竞品reddit
  - reddit相关链接
---

# Reddit 市场调研

## 功能概述

本 Skill 利用 Reddit 公开 JSON API（无需注册/认证），通过真实用户帖子和评论，快速获取某一产品/品类的市场声音。由执行本 Skill 的 Agent 直接在上下文中完成分析，不调用任何外部 AI API。

## 适用场景

- 选品前的需求验证（用户真实在讨论什么？）
- 竞品分析（用户对竞品的抱怨和赞美）
- 定价参考（用户觉得多少钱值？）
- 功能优先级判断（最高频的痛点是什么？）

---

## 完整工作流（6 步）

### 第 1 步：接收产品关键词

用户提供产品名称（中文或英文均可），例如：`睡眠耳塞`、`noise cancelling earplugs`。

如为中文，优先翻译为英文关键词再搜索，同时也用中文补搜以覆盖中文社区。

### 第 2 步：Tavily 预筛选相关子版块和帖子

使用 Tavily 先快速搜索，找出最相关的 Reddit 子版块（subreddit）和热门讨论主题，判断是否值得深入抓取。

Tavily 查询示例：
```
site:reddit.com noise cancelling earplugs sleep
```

记录发现的子版块（如 `r/sleep`、`r/Nootropics`、`r/BuyItForLife`），传给第 3 步。

### 第 3 步：运行 fetch_reddit.py 获取评论数据

调用脚本抓取帖子和评论：

```bash
# 基础用法（自动发现子版块）
python "D:\Download\agent-master\.claude\skills\reddit市场调研\scripts\fetch_reddit.py" \
  --product "noise cancelling earplugs" \
  --limit 20

# 指定子版块
python "D:\Download\agent-master\.claude\skills\reddit市场调研\scripts\fetch_reddit.py" \
  --product "noise cancelling earplugs" \
  --subreddits "sleep,noisemakers,BuyItForLife,SIDS" \
  --limit 20

# 调整时间范围（week/month/year/all）
python "D:\Download\agent-master\.claude\skills\reddit市场调研\scripts\fetch_reddit.py" \
  --product "sleeping earplugs" \
  --subreddits "sleep,noisemakers" \
  --limit 25 \
  --time month
```

> 提示：Windows 下需确保 `PYTHONIOENCODING=utf-8`，或在命令前加 `set PYTHONIOENCODING=utf-8 &&`

脚本将向 stdout 打印一行：
```
RESULT_JSON:{"product":"...","posts":[...],"total_posts":N,"total_comments":M}
```

### 第 4 步：Agent 直接分析（不调用外部 AI API）

Agent 读取 RESULT_JSON 后，**必须先完成数据覆盖清单**，再按分析模板输出报告。

---

**【强制执行】分析前置检查（不可跳过）**

```
在开始分析之前，Agent 必须完成以下自检步骤：

Step A — 列出帖子清单（逐一编号）
  将 RESULT_JSON 中全部 N 条帖子按编号列出：
  帖子#1：{标题} — {url}
  帖子#2：{标题} — {url}
  ...
  帖子#N：{标题} — {url}

Step B — 阅读每条帖子的 content 字段
  对每条帖子，读取完整的 content 字段内容（不得跳过），
  记录该帖涉及的主要话题标签（如：材质/防滑/尺码/卫生/定价/品牌）。

Step C — 覆盖率验证（输出前必须通过）
  ✓ 每个痛点是否来自 ≥2 个不同帖子的来源？
  ✓ RESULT_JSON 中的帖子是否全部被检阅（未引用的需说明原因）？
  ✓ 是否覆盖了评论区内容（content 字段），而非仅读帖子标题？
  ✓ 材质 / 设计 / 价格 / 卫生 四个维度是否均有覆盖？
  → 未通过任一项 → 必须返回重新阅读剩余帖子内容后再输出
  → 全部通过 → 进入分析输出
```

---

**分析输出模板**

```
你是一位经验丰富的跨境电商选品分析师。
以下是从 Reddit 抓取的关于「{产品名}」的真实用户讨论数据（含帖子全文和评论区）。

【必须先完成上方"分析前置检查"再输出以下内容】

每个痛点必须附带：
① Reddit 来源链接（直接用数据中的 url 字段）
② 用户高频讨论话题（该痛点下反复出现的子话题）
③ 用户适用性建议（用户自己给出的解决方案或替代品）
④ 用户提及的竞品/卖家链接（从 shop_links 和 brand_mentions 字段提取）
⑤ 评论区树形结构（3条楼层用户讨论，中文翻译，格式见笔记模板）

输出章节：
1. 用户核心痛点（Top 5，按讨论热度排序）
2. 竞品格局（品牌口碑排名 + 正负面评价）
3. 材质 / 规格偏好（偏好/排斥材质表格，原文支撑）
4. 定价认知（价格带 + 典型评论）
5. 市场机会点（至少3个，材质+设计+场景三维度）
6. 综合评估（讨论热度/市场成熟度/推荐度）
7. 数据覆盖率报告（已引用 X/N 条，未引用帖子编号及原因）

输出末尾追加：
> 当前已分析前 N 条帖子。是否继续生成更多？请告知数量（建议3-6条）。

原始数据：
{RESULT_JSON}
```

---

### 第 5 步：生成市场洞察报告

Agent 根据分析结果，按下方笔记模板整理成结构化报告。

### 第 6 步：写入 Obsidian 笔记

将报告写入 `竞品分析/` 目录，文件名格式：
```
竞品分析/Reddit调研-{产品名}-{YYYY-MM-DD}.md
```

---

## Obsidian 笔记模板

```markdown
---
tags: [市场调研, reddit, 选品]
product: "{产品名}"
date: {YYYY-MM-DD}
source: Reddit
total_posts: {N}
total_comments: {M}
subreddits: [{sub1}, {sub2}]
---

# Reddit 市场调研：{产品名}

> 调研日期：{YYYY-MM-DD}
> 数据来源：Reddit 公开 API（近 1 个月热帖）
> 分析子版块：{subreddits}
> 帖子数：{total_posts} | 有效评论数：{total_comments}

## 一、用户核心痛点

### 痛点 1：{痛点标题}
- **来源**：[{帖子标题}]({URL}) · r/{subreddit}
- **高频讨论话题**：{子话题1}、{子话题2}
- **原文引用**：
  > "{英文原文}" — [来源]({帖子URL})
  > 译：{中文翻译}
- **用户适用性建议**：{用户自己给出的解法}
- **用户提及竞品/卖家**：[{品牌名}]({购物链接}) 或 未提及具体链接

### 痛点 2：{痛点标题}
（同上格式）

## 二、竞品格局

| 品牌 | 用户评价 | 被提及次数 | 典型评论 |
|------|---------|-----------|---------|
| {品牌1} | 正面/负面 | {N}次 | "{引用}" |

## 三、材质 / 规格偏好

> [!info] 用户材质偏好
> - **偏好**：{材质1}（原因：{...}）
> - **排斥**：{材质2}（原因：{...}）
> - **设计偏好**：{半脚趾/分趾/普通款/...}

## 四、定价认知

- 可接受区间：**${低} ~ ${高}**
- "贵但值"："{引用}" — [来源]({URL})
- "便宜踩坑"："{引用}" — [来源]({URL})

## 五、市场机会点

> [!tip] 差异化方向
> 1. **{机会1}**：{材质+设计+场景描述}
> 2. **{机会2}**：{...}
> 3. **{机会3}**：{...}

## 六、综合评估

| 维度 | 评分 | 备注 |
|------|------|------|
| Reddit 讨论热度 | 高/中/低 | {依据} |
| 市场成熟度 | 红海/蓝海/细分机会 | {...} |
| 选品推荐度 | ⭐⭐⭐⭐ | {建议} |

## 七、数据来源索引

| # | 帖子标题 | 子版块 | 链接 |
|---|---------|--------|------|
| 1 | {标题} | r/{sub} | [链接]({URL}) |
```

---

## RESULT_JSON 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `product` | string | 搜索的产品名 |
| `posts` | array | 帖子列表 |
| `posts[].id` | string | Reddit 帖子 ID |
| `posts[].title` | string | 帖子标题 |
| `posts[].subreddit` | string | 所属子版块 |
| `posts[].score` | int | 帖子得分（赞数） |
| `posts[].url` | string | 帖子完整 URL |
| `posts[].selftext` | string | 帖子正文（可能为空） |
| `posts[].comments` | array | 高质量评论列表（score > 5） |
| `posts[].comments[].score` | int | 评论得分 |
| `posts[].comments[].body` | string | 评论正文 |
| `posts[].comments[].author` | string | 评论作者 |
| `total_posts` | int | 实际抓取帖子数 |
| `total_comments` | int | 实际抓取评论总数 |

---

## 已知限制

1. **无需认证，但有限速**：Reddit 对未认证请求每分钟约 60 次，脚本已内置 500ms 间隔和限速重试。
2. **仅公开内容**：私密子版块（private subreddit）无法访问。
3. **历史数据有限**：`t=month` 只能获取近 1 个月内容；如需更长周期改为 `--time year`，但数据量会更大。
4. **中文内容较少**：Reddit 以英文为主，中文产品调研建议配合其他平台（小红书、知乎）补充。
5. **评论质量过滤**：脚本只保留 score > 5 的评论，可能漏掉最新但尚未获得投票的有价值内容。
6. **IP 封禁风险**：过于频繁运行（同一 IP 每小时多次）可能触发 429，建议单次调研间隔 5 分钟以上。
