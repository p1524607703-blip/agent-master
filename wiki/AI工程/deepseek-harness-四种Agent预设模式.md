---
tags: [AI工程, 工具参考, DeepSeek-Harness]
date: 2026-08-13
status: 现行
---

# deepseek-harness-四种Agent预设模式

> [!summary] 摘要
> DeepSeek Harness 内置四种 Agent 预设（preset），决定会话所运行的插件组装（工具、提示词与能力）：标准模式（standard）、PTC 模式（code）、极简模式（minimal）、创造模式（cordis）。本文记录四种模式的定义、适用场景，以及 2026-08-13 起与用户的约定：当前会话只用标准模式，后续任务由 AI 判断是否切换到其他三种模式并提前提醒用户。

## 核心知识

### 四种内置预设

| 模式 | 预设 id | 官方描述 | 适用场景 |
|------|---------|----------|----------|
| 标准模式 | `standard` | 功能完整的编码 Agent，支持文件编辑、Shell、文件与网页检索、Skills、计划、目标、子代理和工作流 | 日常任务：文件读写、Shell、检索、知识沉淀、数据查询等（当前会话使用中） |
| PTC 模式 | `code` | 具备标准模式的全部能力，并通过 Code Mode SDK 呈现工具，让模型用一个 TypeScript 程序组合多步操作 | 需要用一个 TS 程序编排多步操作的复杂任务（批量处理、多步骤管线） |
| 极简模式 | `minimal` | 仅提供持久 bash 与 str_replace_editor 的双工具编码 Agent | 纯终端轻量任务：长期驻留的 bash 会话、快速文件改动 |
| 创造模式 | `cordis` | 用于创建自定义 Agent preset：具备标准模式的全部能力，并提供运行时检查、插件实验和 preset 创作指导 | 创建/修改自定义 Agent 预设、插件实验、preset 调试 |

### 模式切换约定（2026-08-13 起）

- **当前会话**：只用标准模式（standard），不切换。
- **后续工作**：AI 在每项任务开始时判断当前任务是否更适合其他三种模式；若判断应切换，**先向用户说明理由并提醒**，得到确认后再切换。
- **切换判断依据**：任务是否天然属于「TS 程序编排」（PTC）、「纯 bash/文件双工具即可」（极简）、「创建或修改 Agent preset」（创造）。

### 技术细节

- 预设即一个会话的 Agent 所运行的插件组装——它的工具、提示词与能力；目录名即预设 id，目录内 `cordis.yml` 为组装文件、`preset.yml` 为展示元数据（name/description/order）。
- 内置预设位于 `apps/cli/config/agent-presets/{standard,code,minimal,cordis}/`；用户自建预设放在 `~/.agent-presets/`。
- 仓库：https://github.com/deepseek-ai/deepseek-harness（本地 checkout：`deepseek-harness/`）。

## 关联

- [[工具参考/DeepSeek-AI分析]]
- [[大模型评测/]]

## 来源

- deepseek-harness 仓库 `apps/cli/config/agent-presets/*/preset.yml`（本地 checkout）
- deepseek-harness `apps/web/tests/snapshots/agent-preset-authoring/section.expected.md`
- 用户 2026-08-13 会话指示（当前对话只用标准模式，后续由 AI 判断并提醒）
