---
title: Claude Code CLI 指令手册
tags:
  - 工具/Claude
  - 参考文档
aliases:
  - claude命令
  - CLI手册
date: 2026-03-08
---

# Claude Code CLI 指令手册

> [!info] 说明
> 基于 `claude --help` 整理的完整命令参考，附带中文注释和实际使用案例。
> 执行 `claude -v` 可查看当前版本。

---

## 基本用法

```bash
claude [选项] [子命令] [提示词]
```

- **不带参数**：启动交互式对话（默认模式）
- **带提示词**：直接开始对话并输入第一条消息
- **`-p` 模式**：非交互式，输出后退出（适合脚本/管道）

---

## 常用场景速查

| 场景 | 命令 |
|------|------|
| 启动交互会话 | `claude` |
| 快速提问并退出 | `claude -p "问题"` |
| 继续上次对话 | `claude -c` |
| 恢复指定会话 | `claude -r` |
| 使用 Opus 模型 | `claude --model opus` |
| 低权限沙箱模式 | `claude --permission-mode plan` |
| 管道处理文本 | `echo "代码" \| claude -p "解释这段代码"` |

---

## 会话控制

### `-c` / `--continue` — 继续上次对话
恢复当前目录最近一次会话，无需记住 Session ID。

```bash
claude -c
claude -c "继续刚才的任务，帮我加上错误处理"
```

### `-r` / `--resume` — 恢复指定会话
通过 Session ID 或交互选择器恢复历史对话。

```bash
claude -r                        # 打开选择器，列出所有历史会话
claude -r abc-123-def            # 直接恢复指定 ID 的会话
claude -r "上周的重构"           # 模糊搜索会话名称
```

### `--fork-session` — 分叉会话
在继续或恢复会话时，创建新的 Session ID 而不覆盖原始会话（保留原始分支）。

```bash
claude -c --fork-session         # 从上次会话分叉出新分支
claude -r abc-123 --fork-session # 从指定会话分叉
```

### `--session-id <uuid>` — 指定会话 ID
用固定 UUID 启动会话，方便脚本化管理。

```bash
claude --session-id "550e8400-e29b-41d4-a716-446655440000"
```

### `--from-pr` — 从 PR 恢复会话
恢复与某个 Pull Request 关联的会话。

```bash
claude --from-pr 42              # 恢复与 PR #42 关联的会话
claude --from-pr https://github.com/user/repo/pull/42
```

---

## 模型与性能

### `--model <model>` — 指定模型
```bash
claude --model opus              # 使用 claude-opus-4-6（最强）
claude --model sonnet            # 使用 claude-sonnet-4-6（默认）
claude --model haiku             # 使用 claude-haiku-4-5（最快）
claude --model claude-sonnet-4-6 # 完整模型名称
```

### `--effort <level>` — 思考深度
控制模型投入的计算资源，影响响应质量和速度。

```bash
claude --effort low              # 快速响应，适合简单问题
claude --effort medium           # 平衡模式（默认）
claude --effort high             # 深度思考，适合复杂任务
```

### `--fallback-model <model>` — 过载时回退
仅在 `--print` 模式下有效，主模型过载时自动切换。

```bash
claude -p "分析代码" --model opus --fallback-model sonnet
```

---

## 输出控制

### `-p` / `--print` — 非交互输出
打印响应后立即退出，适合脚本和管道。

```bash
claude -p "用一句话解释量子纠缠"
cat error.log | claude -p "分析这个错误日志，给出修复建议"
claude -p "生成5个Python变量命名建议" > names.txt
```

### `--output-format <format>` — 输出格式
仅在 `--print` 模式下有效。

```bash
claude -p "列出前5大编程语言" --output-format text        # 纯文本（默认）
claude -p "解析用户数据" --output-format json             # JSON 单次结果
claude -p "写一首诗" --output-format stream-json          # 流式 JSON
```

### `--json-schema <schema>` — 结构化输出
要求模型输出符合指定 JSON Schema 的结果。

```bash
claude -p "提取姓名和年龄" \
  --json-schema '{"type":"object","properties":{"name":{"type":"string"},"age":{"type":"number"}},"required":["name","age"]}'
```

### `--include-partial-messages` — 流式部分消息
在流式 JSON 模式下实时获取每个 chunk。

```bash
claude -p "写一篇长文章" --output-format stream-json --include-partial-messages
```

---

## 权限控制

### `--permission-mode <mode>` — 权限模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `default` | 敏感操作需逐一确认 | 日常使用 |
| `acceptEdits` | 自动接受文件编辑，其他需确认 | 信任的代码项目 |
| `dontAsk` | 不询问，自动执行所有操作 | 熟悉的自动化任务 |
| `bypassPermissions` | 绕过所有权限检查 | 受控沙箱环境 |
| `plan` | 只规划不执行，输出操作计划 | 审查模式 |
| `auto` | 自动判断何时需要确认 | 智能模式 |

```bash
claude --permission-mode plan    # 先看计划，再决定是否执行
claude --permission-mode dontAsk # 全自动，无需确认
```

### `--dangerously-skip-permissions` — 跳过所有权限
⚠️ 危险选项，仅在无网络的沙箱中使用。

```bash
claude --dangerously-skip-permissions
```

### `--allow-dangerously-skip-permissions` — 允许跳过权限
将跳过权限作为可选项提供，而非默认启用。

---

## 工具控制

### `--allowedTools` — 允许工具白名单
只允许指定工具，其余全部禁用。

```bash
claude --allowedTools "Read,Glob"              # 只允许读文件和查找
claude --allowedTools "Bash(git:*)"            # 只允许 git 相关 bash 命令
claude --allowedTools "Edit,Write,Bash(npm:*)" # 编辑文件 + npm 命令
```

### `--disallowedTools` — 禁止工具黑名单
禁用指定工具，其余正常使用。

```bash
claude --disallowedTools "Bash"               # 禁止执行任何 Shell 命令
claude --disallowedTools "Bash(rm:*)"         # 禁止 rm 命令
```

### `--tools` — 替换默认工具集
从内置工具集中指定可用工具（替换而非追加）。

```bash
claude --tools ""                             # 禁用所有工具（纯对话）
claude --tools "default"                      # 启用所有工具（默认）
claude --tools "Read,Grep,Glob"               # 只用文件读取类工具
```

### `--add-dir <目录>` — 追加可访问目录
允许工具访问额外目录（默认只能访问当前工作目录）。

```bash
claude --add-dir /data/logs --add-dir /etc/config
```

---

## 提示词控制

### `--system-prompt <prompt>` — 覆盖系统提示词
完全替换默认系统提示词。

```bash
claude --system-prompt "你是一位专业的中文技术文档作者，只输出中文"
```

### `--append-system-prompt <prompt>` — 追加系统提示词
在默认提示词基础上追加内容。

```bash
claude --append-system-prompt "所有代码示例必须包含注释"
```

---

## 工作区与 Worktree

### `-w` / `--worktree` — 创建 Git Worktree
为当前会话创建独立的 git worktree，实现隔离开发。

```bash
claude -w                        # 自动命名 worktree
claude -w feature-auth           # 指定 worktree 名称
claude -w feature --tmux         # 同时创建 tmux 会话
```

---

## MCP 服务器管理

> [!tip] 什么是 MCP？
> Model Context Protocol，让 Claude 连接外部服务（如 GitHub、Figma、数据库等）。

```bash
claude mcp list                              # 列出已配置的 MCP 服务器
claude mcp get <名称>                        # 查看某个服务器详情
claude mcp remove <名称>                     # 删除某个服务器
claude mcp reset-project-choices             # 重置项目级 MCP 确认记录
```

### `mcp add` — 添加 MCP 服务器

```bash
# 添加 HTTP 类型服务器
claude mcp add --transport http figma https://api.figma.com/mcp

# 添加带 Header 认证的服务器
claude mcp add --transport http github https://api.github.com/mcp \
  --header "Authorization: Bearer ghp_xxxx"

# 添加 stdio 类型服务器（本地进程）
claude mcp add -e GITHUB_TOKEN=ghp_xxx github-local -- npx @modelcontextprotocol/server-github

# 从 Claude Desktop 导入配置（Mac/WSL）
claude mcp add-from-claude-desktop
```

### `--mcp-config` — 临时加载 MCP 配置
本次会话临时使用额外 MCP 配置，不写入全局设置。

```bash
claude --mcp-config ./my-mcp.json
claude --mcp-config '{"mcpServers":{"test":{"command":"node","args":["server.js"]}}}'
```

### `mcp serve` — 将 Claude 作为 MCP 服务器
让其他客户端通过 MCP 协议连接 Claude。

```bash
claude mcp serve
```

---

## 认证管理

```bash
claude auth status                # 查看当前登录状态
claude auth login                 # 登录 Anthropic 账号
claude auth logout                # 退出登录
claude setup-token                # 配置长期认证 Token（需要订阅）
```

---

## 调试与诊断

### `-d` / `--debug` — 调试模式

```bash
claude -d                         # 开启全部调试日志
claude -d "api"                   # 只看 API 相关日志
claude -d "api,hooks"             # 看 API 和 Hooks 日志
claude -d "!file"                 # 排除文件操作日志
claude --debug-file ./debug.log   # 调试日志写入文件
```

### `doctor` — 健康检查

```bash
claude doctor                     # 检查自动更新器状态
```

### `--verbose` — 详细输出

```bash
claude --verbose                  # 覆盖配置中的 verbose 设置
```

---

## 更新与安装

```bash
claude update                     # 检查并安装更新（同 upgrade）
claude upgrade                    # 同上
claude install stable             # 安装稳定版
claude install latest             # 安装最新版
claude install 1.2.3              # 安装指定版本
```

---

## Agents（代理）

```bash
claude agents                     # 列出所有已配置的 Agent
claude agents --setting-sources user,project  # 指定配置来源
```

### `--agent <agent>` — 使用指定 Agent

```bash
claude --agent reviewer           # 使用名为 reviewer 的 Agent
```

### `--agents <json>` — 临时定义 Agent

```bash
claude --agents '{"reviewer":{"description":"代码审查员","prompt":"你是一位严格的代码审查员"}}'
```

---

## 插件管理

```bash
claude plugin                     # 插件管理入口
claude --plugin-dir ./my-plugins  # 临时加载指定目录的插件
```

---

## 其他选项

### `--disable-slash-commands` — 禁用 Skills
禁用所有 `/skill` 命令。

```bash
claude --disable-slash-commands
```

### `--ide` — 自动连接 IDE

```bash
claude --ide                      # 自动连接已开启的 IDE（如 VS Code）
```

### `--chrome` / `--no-chrome` — Chrome 集成

```bash
claude --chrome                   # 启用 Claude in Chrome
claude --no-chrome                # 禁用
```

### `--settings` — 加载额外配置

```bash
claude --settings ./custom.json
claude --settings '{"model":"opus"}'
```

### `--setting-sources` — 指定配置来源

```bash
claude --setting-sources user,project   # 只加载用户级和项目级配置
claude --setting-sources local          # 只加载本地配置
```

### `--file` — 启动时下载文件资源

```bash
claude --file file_abc123:document.txt file_def456:image.png
```

### `--betas` — 启用 Beta 功能
仅 API Key 用户可用。

```bash
claude --betas interleaved-thinking-2025-05-14
```

---

## 实用组合案例

```bash
# 1. 代码审查（只读，不修改文件）
claude --tools "Read,Glob,Grep" -p "审查 src/ 目录下所有 Python 文件的代码质量"

# 2. 自动化脚本（无确认，输出 JSON）
claude -p "分析 package.json 的依赖风险" \
  --permission-mode bypassPermissions \
  --output-format json

# 3. 管道处理
git diff HEAD~1 | claude -p "生成这次提交的 changelog 条目"

# 4. 结构化数据提取
cat resume.txt | claude -p "提取联系信息" \
  --json-schema '{"type":"object","properties":{"email":{"type":"string"},"phone":{"type":"string"}}}'

# 5. 多步骤任务（先看计划）
claude --permission-mode plan "重构 utils.js，提取公共函数"

# 6. 隔离实验
claude -w experiment-branch "尝试用 TypeScript 重写这个模块"

# 7. 临时限制权限（只允许读）
claude --allowedTools "" "解释 main.py 的整体架构"
```

---

## 相关链接

- [[CLAUDE.md]] — 本项目 Claude 配置说明
- [[Claude Code CLI 指令手册]] — 本文档
- 官方文档：https://docs.anthropic.com/claude-code
