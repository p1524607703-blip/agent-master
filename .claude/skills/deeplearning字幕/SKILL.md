---
name: deeplearning字幕
description: 输入 deeplearning.ai 课程链接，自动提取英文字幕，由 Claude 生成结构化学习笔记（核心概念、代码要点、知识总结），输出为 Obsidian 笔记。当用户说"总结这个课程"、"deeplearning笔记"、"dl.ai"、"分析deeplearning视频"，或粘贴 learn.deeplearning.ai 链接时自动激活。
allowed-tools: Bash, Read, Write
---

# DeepLearning.AI 字幕提取与学习笔记

从课程页面直接提取 WebVTT 字幕，**无需下载视频**，Claude 分析后生成结构化 Obsidian 笔记。

---

## 依赖声明

### ✅ 本地已就绪

| 软件 | 说明 |
|------|------|
| Python 3.14 | `D:\Program Files\Python\python.exe` |
| 标准库（urllib / re / json） | 无需额外安装 |

### 首次使用：导出浏览器 cookies

deeplearning.ai 课程需要登录态。先在 Chrome 安装插件导出 cookies：

1. 安装 Chrome 插件：[Get cookies.txt LOCALLY](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. 登录 learn.deeplearning.ai
3. 点插件图标 → Export → 保存为 `D:\Download\agent-master\dl_cookies.txt`

---

## Claude 执行步骤

### 第一步：运行字幕提取脚本

```bash
"D:/Program Files/Python/python.exe" \
  "D:\Download\agent-master\.claude\skills\deeplearning字幕\scripts\fetch_transcript.py" \
  "<课程URL>" \
  --cookies "D:\Download\agent-master\dl_cookies.txt"
```

脚本输出格式：
```
LESSON_TITLE:Introduction to Structured Output Generation
COURSE_NAME:Getting Structured LLM Output
VTT_URL:https://dyckms5inbsqq.cloudfront.net/...
TRANSCRIPT_TEXT:Welcome to this course on structured output...
```

### 第二步：Claude 分析字幕内容

拿到 `TRANSCRIPT_TEXT` 后，按以下结构生成笔记：

**分析维度：**
- 核心概念（3-5个，每个一句话解释）
- 技术要点（代码示例、API 用法、重要参数）
- 关键结论（这节课解决了什么问题，有什么局限）
- 行动建议（学完后应该做什么、下一步去哪）

### 第三步：写入 Obsidian 笔记

输出路径：`D:\Download\agent-master\Daily\DL-{课程名}-{章节名}-{日期}.md`

---

## 输出笔记格式

```markdown
---
title: "{章节标题}"
course: "{课程名称}"
source: "{原始URL}"
platform: DeepLearning.AI
date: YYYY-MM-DD
tags: [学习笔记, deeplearning, AI]
---

# {章节标题}

> [!info] 课程信息
> **课程**：{课程名称}
> **平台**：DeepLearning.AI
> **链接**：{URL}

## 核心概念

- **{概念1}**：{一句话解释}
- **{概念2}**：{一句话解释}

## 技术要点

{代码示例或 API 用法}

## 关键结论

{这节课的核心收获，2-3条}

## 行动建议

{学完后应该尝试什么}

## 原始字幕（可折叠）

> [!note]- 展开查看完整字幕
> {完整转录文本}
```

---

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `未找到 __NEXT_DATA__` | cookies 未提供或已过期 | 重新导出 cookies |
| `未找到字幕文件` | 该课程暂无字幕 | 使用 `视频转录总结` skill 用 Whisper 转录 |
| 字幕乱码 | 编码问题 | Windows 下运行加 `set PYTHONIOENCODING=utf-8` |
| 内容截断 | 课程字幕特别长 | Claude 分段处理，每段约 4000 字 |
