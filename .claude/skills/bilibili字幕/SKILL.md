---
name: B站字幕提取
description: 直接调用 Bilibili AI 字幕 API，无需下载视频，生成结构化 Obsidian 总结笔记
type: skill
triggers:
  - b站字幕
  - bilibili字幕
  - B站总结
  - B站视频笔记
  - BV号
  - bilibili视频总结
---

# B站字幕提取

直接调用 Bilibili 官方 AI 字幕 API，无需下载视频/音频，质量远优于 Whisper 转录。
支持 QR 码扫码登录，Cookie 自动保存到 `.env`，一次登录长期有效。

## Claude 操作流程

当用户提供 BV 号或 B 站链接时：

### 第一步：提取 BV 号

从 URL 或用户输入中提取 BV 号（`BV` 开头的字符串）。

### 第二步：运行脚本获取字幕

```bash
PYTHONIOENCODING=utf-8 python "D:\Download\agent-master\.claude\skills\bilibili字幕\scripts\bilibili_subtitle.py" <BV号> --no-summary
```

`--no-summary` 跳过脚本内的 API 调用，由 Claude 直接总结（更快、更准、无需配置 key）。

**首次运行**：自动生成二维码图片到 `D:\Download\agent-master\bilibili_login_qr.png`，提示用户扫码。

**已登录**：直接获取字幕，无需用户操作。

### 第三步：Claude 直接生成总结

读取 `RESULT_JSON` 中的 chunk 文件，直接生成结构化总结并写入笔记的 `## 内容总结` 部分：

```
### 核心主题
### 关键要点
### 重要数据 / 引用（如有）
### 适合人群
### 行动建议（如有）
```

### 第四步：告知笔记路径

---

## 脚本参数

| 参数 | 默认 | 说明 |
|------|------|------|
| `bvid` | 必填 | BV 号（如 `BV1NyPKzHELr`）或完整 URL |
| `--output` | `Daily/` | Obsidian 笔记输出目录 |
| `--no-summary` | 否 | 跳过 Claude AI 总结 |

## 首次登录流程

1. 脚本在 `D:\Download\agent-master\bilibili_login_qr.png` 生成二维码
2. 用手机 Bilibili APP 扫码
3. 手机确认登录
4. Cookie 自动保存到 `.env`（字段：`BILIBILI_SESSDATA` 等）
5. 之后运行无需重复登录

## 输出笔记格式

```markdown
---
title: "视频标题"
source: "https://www.bilibili.com/video/BVxxx/"
channel: "UP主"
platform: Bilibili
bvid: BVxxx
upload_date: YYYY-MM-DD
duration: "MM:SS"
subtitle_lang: AI字幕-中文
tags: [视频总结, bilibili]
created: YYYY-MM-DD
---

# 视频标题

> [!info] 视频信息

## 内容总结
（Claude 生成：核心主题 + 关键要点 + 行动建议）

## 原始字幕
（可折叠）
```

## 环境依赖

```bash
pip install bilibili-api-python aiohttp qrcode pillow anthropic
```

- `ANTHROPIC_API_KEY`：在 `.env` 中配置（总结功能需要）
- `BILIBILI_SESSDATA` 等：首次扫码后自动写入 `.env`

## 与视频转录总结的区别

| 对比项 | B站字幕提取 | 视频转录总结 |
|--------|------------|-------------|
| 原理 | 官方 AI 字幕 API | Whisper 音频转录 |
| 质量 | 高（官方字幕） | 中（依赖模型大小） |
| 速度 | 快（无需下载） | 慢（下载 + 转录） |
| 适用 | B 站视频 | YouTube/本地/任意平台 |
| 要求 | 视频需开启 AI 字幕 | 需要 ffmpeg |
