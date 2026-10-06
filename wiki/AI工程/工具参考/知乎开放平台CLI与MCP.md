---
tags: [AI工程, 知乎, CLI, MCP, Skill]
date: 2026-08-17
status: 现行
---

# 知乎开放平台 CLI 与 MCP

> [!summary] 摘要
> 本机已安装知乎官方 `zhihu` Skill 与 `zhihu-cli` 0.3.0，CLI 已使用用户单独提供的 Access Secret 完成在线验证。另有一个使用独立钥匙串凭证的本地 MCP 桥接器，仅提供知乎站内搜索。两者可共存，但不应为同一次查询重复调用。

## 核心知识

### 当前配置

- Skill：`~/.codex/skills/zhihu`，版本 0.3.0；下一次 Codex 对话起可自动发现。
- CLI：`~/Library/Application Support/zhihu-cli/current/zhihu-cli`，版本 0.3.0。
- CLI 鉴权：用户单独提供的新凭证保存在 macOS 钥匙串，已通过在线验证和一条最小本人内容读取验收；知识库不保存 Access Secret 或其片段。
- MCP：Codex 中启用的服务名为 `zhihu_search`，本地包装器是 `~/.local/bin/zhihu-search-mcp`。
- MCP 实际形态：本地 `mcp-remote` 通过 stdio 桥接知乎官方 SSE 地址 `https://developer.zhihu.com/api/mcp/zhihu_search/v1/sse`；它不是完全离线的本地搜索服务。

### CLI Skill 与现有 MCP 的区别

| 维度 | `zhihu` Skill + CLI | `zhihu_search` MCP |
|---|---|---|
| Agent 接入方式 | Skill 告诉 Agent 何时、如何调用本地 CLI | Codex 直接加载一个结构化 MCP 工具 |
| 当前能力 | 知乎搜索、全网搜索、热榜、知乎直答、本人创作/关注/收藏 | 仅知乎站内搜索 |
| 本地组件 | Skill 文档、安装脚本和 `zhihu-cli` 二进制 | Shell 包装器和 `mcp-remote` 桥接器 |
| 远端调用 | CLI 调用知乎开放平台 HTTP API | 桥接知乎官方 MCP SSE 服务 |
| 输出 | JSON、SSE 或文本，适合脚本化与完整能力调用 | MCP Tool Result，适合模型直接调用 |
| 凭证 | CLI 自己管理的 macOS 钥匙串项 | 包装器从旧钥匙串项 `codex.zhihu.mcp` 读取 |

> [!note] 使用建议
> 日常知乎任务优先使用新 Skill/CLI，因为覆盖能力更完整；仅需要站内搜索且希望直接使用 MCP 工具时，可继续使用现有 MCP。CLI 与 MCP 当前使用各自的钥匙串凭证，但同一知乎账号下的 Access Secret 仍共享账号额度池；重复查询会重复消耗对应能力额度。

### 安装与验收记录

- 官方 Skill ZIP SHA-256：`2af2647c468a366050a39dd78b8d844eccaeb679d91a56cd134573c0b383e4df`。
- Skill 与 CLI 均为 0.3.0，状态检查显示没有可用更新。
- `auth status --verify` 成功，`me contents --type all --limit 1` 成功。
- 2026-08-17：CLI 凭证已按用户要求替换为新 Access Secret，并再次通过在线验证和最小业务验收；旧 MCP 凭证未修改。
- 旧 MCP 保持启用，未删除或修改。

## 关联

- [[工具参考/Skills工作原理]]
- [[工具参考/OpenCode-AI编码代理]]

## 来源

- [知乎官方 zhihu-cli Skill](https://developer-cdn.zhihu.com/zhihu-cli/releases/stable/skill/zhihu-cli-skill.zip)
- `~/.codex/skills/zhihu/SKILL.md`
- `~/.codex/skills/zhihu/references/cli.md`
- `~/.codex/skills/zhihu/references/mcp.md`
- `~/.codex/config.toml`（仅核对 MCP 注册信息，未记录凭证）
