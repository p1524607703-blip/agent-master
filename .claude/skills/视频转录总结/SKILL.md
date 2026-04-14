---
name: 视频转录总结
description: 将 YouTube / Bilibili / 本地音视频转录为文字，用 Claude 生成结构化总结，输出为 Obsidian 笔记
type: skill
triggers:
  - 转录视频
  - 总结视频
  - 视频笔记
  - 下载音频
  - 视频转文字
  - 视频 URL + 分析/总结/笔记
---

# 视频转录总结

将 YouTube / Bilibili / 本地音视频一键转录 + 总结，输出结构化 Obsidian 笔记。

## Claude 操作流程

当用户提供视频链接或本地文件，按以下步骤执行：

### 第一步：确认参数

向用户确认（或直接推断）：
- `URL` 或本地路径
- `--lang`：语言（中文→`zh`，英文→`en`，自动→`auto`）
- `--model`：模型大小（默认 `base`，中文建议 `small`）
- `--cookies`：B站必须提供 cookies.txt

### 第二步：执行转录

```bash
python "D:\Download\agent-master\.claude\skills\视频转录总结\scripts\transcribe.py" \
  "<URL>" \
  --model small \
  --lang zh \
  --output "D:\Download\agent-master\Daily"
```

B站额外加 `--cookies "D:\Download\agent-master\cookies.txt"`

### 第三步：输出笔记路径

告知用户生成的笔记路径，并展示总结内容预览。

---

## 脚本参数速查

| 参数 | 默认 | 说明 |
|------|------|------|
| `url` | 必填 | 视频 URL 或本地音频路径 |
| `--model` | `base` | `tiny`/`base`/`small`/`medium`/`large` |
| `--lang` | `auto` | `zh`/`en`/`ja`/`ko`/`auto` |
| `--output` | `Daily/` | Obsidian 笔记输出目录 |
| `--cookies` | 无 | cookies.txt 路径（B站必须） |
| `--keep-audio` | 否 | 保留下载的音频文件 |

## 模型选择建议

| 场景 | 模型 | CPU 速度参考 |
|------|------|-------------|
| 英文清晰语音 | `base` | ~10倍实时 |
| 中文普通话 | `small` | ~5倍实时 |
| 口音/多语言 | `medium` | ~2倍实时 |
| 专业/学术 | `large` | ~1倍实时 |

## B站获取 cookies.txt

B站需要登录态，两种方法：

**方法一：浏览器插件（推荐）**
1. 安装 Chrome 插件 [Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. 登录 bilibili.com
3. 点插件图标 → Export → 保存为 `cookies.txt`
4. 放到 `D:\Download\agent-master\cookies.txt`

**方法二：自动提取（需关闭 Chrome）**
```bash
python "D:\Download\agent-master\.claude\skills\视频转录总结\scripts\export_cookies.py" bilibili.com
```
> 该脚本直接读取 Chrome/Edge 的 cookie 数据库（见 `scripts/export_cookies.py`）

## 输出笔记格式

```markdown
---
title: "视频标题"
source: "原始链接"
channel: "频道/UP主"
platform: YouTube/BiliBili
upload_date: YYYY-MM-DD
duration: "MM:SS"
transcript_lang: zh/en/te
tags: [视频总结, youtube/bilibili]
created: YYYY-MM-DD
---

# 视频标题

> [!info] 视频信息

## 内容总结
（Claude 生成：核心主题 + 关键要点 + 行动建议）

## 原始转录
（可折叠）
```

## 环境依赖

```bash
pip install yt-dlp openai-whisper anthropic
```

- ffmpeg：已在 `C:\Program Files\ShadowBot\shadowbot-5.32.44\ffmpeg.exe`
- ANTHROPIC_API_KEY：在 `.env` 中配置
- TAVILY_API_KEY：可选，用于补充视频描述元数据

## 已知限制

| 问题 | 原因 | 解决 |
|------|------|------|
| B站 412 | 需要登录态 | 提供 cookies.txt |
| 转录质量差 | 语言识别错误 | 指定 `--lang` |
| CPU 慢 | 无 GPU | 用 `tiny`/`base`，或换 `large` 靠精度换时间 |
| YouTube 有些视频无法下载 | 版权保护 | 提供账号 cookies |
