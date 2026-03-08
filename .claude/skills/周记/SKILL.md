---
name: 周记
description: 创建或打开本周的周回顾笔记，汇总日记并跟踪项目和目标进展。当用户说"周回顾"、"周记"、"本周回顾"、"周总结"或想做周计划时自动激活。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# 周记

创建或打开本周的周回顾笔记。

## 位置

`Weekly/Week of YYYY-MM-DD.md` — 日期为本周周一。

## 工作流程

1. 获取本周周一：`date -d "last monday" +%Y-%m-%d`（按平台调整）
2. 检查 `Weekly/Week of YYYY-MM-DD.md` 是否存在
3. 若已存在 → 读取并汇总当前内容
4. 若不存在 → 从下方模板创建
5. 扫描 `Daily/` 中本周日记，预填已完成任务

## Template

```markdown
---
date: {{WEEK_START}}
tags:
  - weekly
---

# Week of {{WEEK_START}}

## 本周重点

-

## 每日概览

- **周一** [[Daily/{{MON}}]] —
- **周二** [[Daily/{{TUE}}]] —
- **周三** [[Daily/{{WED}}]] —
- **周四** [[Daily/{{THU}}]] —
- **周五** [[Daily/{{FRI}}]] —

## 本周完成

-

## 下周计划

-

## 反思

### 进展顺利的

### 需要改进的

### 学到的

## 链接

← [[Weekly/Week of {{PREV_WEEK}}]] | [[Weekly/Week of {{NEXT_WEEK}}]] →
```

## Pre-Population Step

After creating the template, scan `Daily/YYYY-MM-DD.md` files for this week and:
- Extract completed tasks (`- [x]`) and list under "本周完成"
- Copy key notes or highlights to "每日概览"

## Date Calculation

```bash
# Monday of current week (bash)
MONDAY=$(date -d "last monday" +%Y-%m-%d 2>/dev/null || date -v-Monday +%Y-%m-%d)
# Days of week
TUE=$(date -d "$MONDAY + 1 day" +%Y-%m-%d)
WED=$(date -d "$MONDAY + 2 days" +%Y-%m-%d)
THU=$(date -d "$MONDAY + 3 days" +%Y-%m-%d)
FRI=$(date -d "$MONDAY + 4 days" +%Y-%m-%d)
PREV=$(date -d "$MONDAY - 7 days" +%Y-%m-%d)
NEXT=$(date -d "$MONDAY + 7 days" +%Y-%m-%d)
```
