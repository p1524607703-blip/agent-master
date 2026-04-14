---
name: bilibili总结
description: 输入 B 站链接或 BV 号，自动扫码登录、获取官方 AI 字幕、由 Claude 生成结构化总结，输出 Obsidian 笔记。无需下载视频，无需 API Key，可被其他 Agent 复用。
type: skill
triggers:
  - b站
  - bilibili
  - BV号
  - b站视频
  - 总结b站
  - b站链接
  - bilibili链接
  - 帮我看这个视频
---

# bilibili总结 Skill

## 概述

| 步骤 | 执行方 | 说明 |
|------|--------|------|
| 提取 BV 号 | Claude | 从用户输入或链接中解析 |
| 检查登录状态 | Claude | 读取 `.env` 中的 Cookie |
| 扫码登录 | login.py + 用户 | 首次或 Cookie 失效时触发 |
| 获取字幕 | bilibili_subtitle.py | 调用 Bilibili 官方 AI 字幕 API |
| 生成总结 | Claude | 读取字幕直接总结，无需 API Key |
| 写入笔记 | Claude | 输出标准 Obsidian Markdown |

---

## 完整工作流

### 第一步：提取 BV 号

支持格式：
- 纯 BV 号：`BV1NyPKzHELr`
- 完整链接：`https://www.bilibili.com/video/BV1NyPKzHELr/`

### 第二步：检查 Cookie

检查 `.env` 是否存在 `BILIBILI_SESSDATA`：
- **存在** → 跳到第四步直接获取字幕
- **不存在或失效** → 执行第三步登录

### 第三步：扫码登录（首次或 Cookie 失效）

**运行登录脚本：**

```bash
PYTHONIOENCODING=utf-8 python "D:\Download\agent-master\bilibili总结\scripts\login.py"
```

脚本输出格式：
```
QR_CODE_PATH:D:\Download\agent-master\bilibili_login_qr.png
POLLING:1/90 state=SCAN
SCANNED:已扫码，等待手机确认...
POLLING:2/90 state=SCAN
...
LOGIN_SUCCESS:用户名
```

**Claude 处理流程：**

1. 读到 `QR_CODE_PATH:<路径>` → 立即用 `Read` 工具读取该图片，**在上下文窗口展示二维码**
2. 告知用户："请用手机 Bilibili APP 扫描上方二维码，扫完后在手机上点击确认登录"
3. 继续读取脚本输出，监听信号：
   - `SCANNED:` → 提示用户"已检测到扫码，请在手机上点击确认"
   - `LOGIN_SUCCESS:<用户名>` → 登录完成，继续下一步
   - `LOGIN_FAILED:<原因>` → 告知用户，重新运行 login.py

> **实现说明：** login.py 是阻塞式脚本，内置轮询循环（最多等 3 分钟）。
> 建议用 `run_in_background=True` 运行，然后持续读输出文件直到出现 `LOGIN_SUCCESS`。

### 第四步：获取字幕

```bash
PYTHONIOENCODING=utf-8 python "D:\Download\agent-master\bilibili总结\scripts\bilibili_subtitle.py" <BV号> --output "D:\Download\agent-master\Daily"
```

脚本输出 `RESULT_JSON:<json>` 时表示成功。

**RESULT_JSON 字段：**
```json
{
  "bvid": "BV1NyPKzHELr",
  "title": "视频标题",
  "owner": "UP主名称",
  "duration": "6:50",
  "upload_date": "2026-03-04",
  "url": "https://www.bilibili.com/video/BV1NyPKzHELr/",
  "subtitle_lang": "中文",
  "transcript": "完整字幕纯文本...",
  "chunks": ["D:\\...\\BV1NyPKzHELr_chunk_0.txt"],
  "output_dir": "D:\\Download\\agent-master\\Daily"
}
```

### 第五步：Claude 生成总结

从 `RESULT_JSON.transcript` 读取字幕，按模板生成总结（见下方）。

### 第六步：写入 Obsidian 笔记

文件名：`{output_dir}/{YYYY-MM-DD}-{safe_title}.md`，写入内容见下方笔记模板。

---

## 总结提示词模板（其他 Agent 可直接复用）

```
视频标题：{title}
UP主：{owner}
时长：{duration}
字幕内容：
{transcript}

请用中文生成结构化总结，输出以下格式：

### 核心主题
（1-2句话概括视频主旨）

### 关键要点
- （3-8条要点，每条不超过50字）

### 重要数据 / 引用
（如有具体数字、案例、引用，否则省略此节）

### 适合人群
（1句话）

### 行动建议
（如有实操价值，否则省略）
```

---

## Obsidian 笔记模板

```markdown
---
title: "{title}"
source: "{url}"
channel: "{owner}"
platform: Bilibili
bvid: {bvid}
upload_date: {upload_date}
duration: "{duration}"
subtitle_lang: {subtitle_lang}
tags: [视频总结, bilibili]
created: {today}
---

# {title}

> [!info] 视频信息
> | | |
> |---|---|
> | **来源** | [Bilibili]({url}) |
> | **UP主** | {owner} |
> | **时长** | {duration} |
> | **发布** | {upload_date} |
> | **字幕** | {subtitle_lang} |

## 内容总结

{summary}

## 原始字幕

> [!note]- 展开完整字幕（{char_count} 字符）
> {transcript_quoted}
```

---

## 脚本说明

### login.py — 扫码登录

```bash
python login.py
```

| 输出 | 含义 | Claude 动作 |
|------|------|------------|
| `QR_CODE_PATH:<路径>` | 二维码已生成 | Read 图片 → 展示给用户 |
| `POLLING:<n>/90 state=SCAN` | 等待扫码中 | 继续等待 |
| `SCANNED:` | 已扫码未确认 | 提示用户点手机确认 |
| `LOGIN_SUCCESS:<用户名>` | 登录完成 | 继续获取字幕 |
| `LOGIN_FAILED:<原因>` | 失败 | 告知用户，重新运行 |

### bilibili_subtitle.py — 字幕获取

```bash
python bilibili_subtitle.py <BV号> [--output <目录>]
```

只做字幕获取，输出 RESULT_JSON，不调用任何 AI API。

---

## 环境依赖

```bash
pip install bilibili-api-python aiohttp
```

Cookie 保存到 `.env`：`BILIBILI_SESSDATA` / `BILIBILI_bili_jct` / `BILIBILI_buvid3` / `BILIBILI_buvid4` / `BILIBILI_DedeUserID`

---

## Agent 复用指南

```
1. 检查 .env 是否有 BILIBILI_SESSDATA
2. 没有 → 运行 login.py，解析输出 QR_CODE_PATH，Read 图片展示，等待 LOGIN_SUCCESS
3. 运行 bilibili_subtitle.py <BV号>，解析 RESULT_JSON
4. 取 result["transcript"] 套用总结提示词模板，由 Claude 生成总结
5. 用笔记模板写入 Obsidian
```

---

## 已知限制

| 问题 | 原因 | 解决 |
|------|------|------|
| 无字幕 | 视频未开启 AI 字幕 | 改用"视频转录总结" Skill（Whisper） |
| Cookie 失效 | 长时间未使用 | 重新运行 login.py |
| 字幕质量差 | 口音/方言/专业术语 | 字幕来自 B 站官方 AI，无法改善 |
| 课程/番剧 | SS/EP 号格式不同 | 当前不支持 |
