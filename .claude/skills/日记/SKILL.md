---
name: 日记
description: 创建或打开今天的日记，包含任务、笔记和上下文链接的结构化模板。当用户说"日记"、"今天的笔记"、"打开今天"、"早间计划"或要开始新的一天时自动激活。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# 日记

在仓库中创建或更新今天的日记。

## 配置

- 日记文件夹：`Daily/`（不存在则创建）
- 文件名格式：`YYYY-MM-DD.md`（如 `2026-03-08.md`）
- 模板位置：`Templates/Daily Note.md`（若存在则使用）

## 工作流程

1. 获取今天日期：`date +%Y-%m-%d`
2. 检查今天的笔记是否存在：查找 `Daily/YYYY-MM-DD.md`
3. 若已存在 → 打开并汇总当前任务/内容
4. 若不存在 → 从下方模板创建
5. 报告已创建或找到的内容

## Default Template

```markdown
---
date: {{DATE}}
tags:
  - daily
---

# {{DATE}}

## 今日任务

- [ ]

## 笔记

## 回顾

### 昨天完成了什么

### 今天的重点

### 遇到的阻碍

## 链接

- [[{{YESTERDAY}}]] ← 昨天
- 本周：[[{{WEEK}}]]
```

Replace `{{DATE}}` with today's date, `{{YESTERDAY}}` with yesterday's date, `{{WEEK}}` with the Monday of this week (format: `Week of YYYY-MM-DD`).

## Steps to Execute

```bash
# Get dates
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)
WEEK_START=$(date -d "last monday" +%Y-%m-%d 2>/dev/null || date +%Y-%m-%d)
NOTE_PATH="D:/Download/agent-master/Daily/${TODAY}.md"
```

1. Check if `Daily/` folder exists, create if needed
2. Check if `${NOTE_PATH}` exists
3. If not, write the template with dates substituted
4. Report the note path and any existing tasks found
