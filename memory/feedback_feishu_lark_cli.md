---
name: 飞书操作使用 lark-cli
description: 用户要求所有飞书操作一律使用 lark-cli 工具，不用飞书MCP skill
type: feedback
---

飞书相关操作（多维表格、文档、消息、日历等）一律使用 lark-cli 命令行工具（位于 ~/.local/bin/lark-cli），不要调用飞书MCP skill。

**Why:** 用户明确指定，lark-cli 是统一入口。

**How to apply:** 任何涉及飞书的操作，先用 lark-cli --help 查看子命令，再执行，不要走 Skill 工具。
