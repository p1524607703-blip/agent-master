---
name: 收集
description: 快速将想法、笔记、任务或 URL 收集到仓库收件箱，供后续整理。当用户说"收集"、"保存这个"、"加入收件箱"、"记住这个"、"记下来"，或想快速保存内容而不决定放哪里时自动激活。
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Bash
---

# 快速收集

快速将任何内容收集到仓库收件箱，供后续处理。

## 收件箱位置

`Inbox/` 文件夹 — 不存在则创建。

## 收集内容

用户会通过 `$ARGUMENTS` 提供内容，可能是：
- A raw idea or thought
- A task or to-do item
- A URL to read later
- A quote or reference
- A question to answer later

## Workflow

1. Get current timestamp: `date "+%Y-%m-%d %H:%M"`
2. Detect content type:
   - Starts with `http` → treat as URL clipping
   - Starts with `- [ ]` or action words → treat as task
   - Otherwise → treat as note/idea
3. Append to `Inbox/Inbox.md` (create if missing) OR create individual note
4. Confirm what was captured

## Inbox Note Format

Append to `Inbox/Inbox.md`:

```markdown
---
type: inbox
---

# 收件箱

<!-- 按时间倒序追加，最新在最上方 -->
```

Each captured item:

```markdown
## {{TIMESTAMP}}

{{CONTENT}}

---
```

## Individual Note (for URLs)

If content is a URL, create `Inbox/{{TIMESTAMP}} Clip.md`:

```markdown
---
source: {{URL}}
date: {{DATE}}
tags:
  - inbox
  - clipping
status: unread
---

# {{URL}}

> 待整理
```

## After Capture

- Confirm: "已捕获到收件箱：[content preview]"
- Remind user they can `/daily` to process inbox items during daily review
