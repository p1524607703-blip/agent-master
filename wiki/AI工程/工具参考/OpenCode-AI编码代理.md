---
tags: [AI工程, 编码代理, 工具参考]
date: 2026-06-01
status: 现行
---

# OpenCode-AI编码代理

> [!summary] 摘要
> OpenCode 是一个开源 AI 编码代理，主要用于在终端、IDE、桌面应用或浏览器 Web 页面中辅助理解代码、修改代码、运行命令和管理多会话。它更像 Claude Code、Codex CLI、Gemini CLI 这一类“项目内编码助手”，而不是单纯的网页聊天机器人。

## 核心知识

- OpenCode 的定位是开源 AI coding agent，可以连接 Claude、GPT、Gemini、本地模型等不同模型提供方。
- 默认使用方式是终端 TUI：在项目目录运行 `opencode`，进入交互式界面后直接提需求、引用文件、执行命令。
- 它支持项目初始化：`/init` 会分析项目并生成或更新 `AGENTS.md`，帮助代理理解项目结构和约定。
- 它有可视化页面：运行 `opencode web` 会启动本地 Web 服务，并在浏览器打开 OpenCode 页面。
- Web 页面可用于查看和管理会话、启动新会话、查看服务器状态；也可以用 `opencode attach http://localhost:4096` 让终端 TUI 连接同一个 Web 服务。
- 它还提供 IDE 扩展，支持 VS Code、Cursor、Windsurf、VSCodium 等编辑器中的快捷启动和上下文引用。
- 适合场景：代码库问答、功能实现、局部重构、生成计划、多模型对比、需要开源和多供应商模型支持的编码工作流。

## 快速使用

```bash
# 安装
curl -fsSL https://opencode.ai/install | bash

# 在当前项目启动终端界面
opencode

# 启动浏览器可视化页面
opencode web

# 指定 Web 端口
opencode web --port 4096
```

## 关联

- [[工具参考/Claude Code CLI 指令手册]]
- [[大模型评测]]

## 来源

- https://opencode.ai/
- https://opencode.ai/docs/
- https://opencode.ai/docs/web/
- https://opencode.ai/docs/ide/
