---
title: OpenClaw 官方文档精读
tags:
  - OpenClaw
  - AI助手
  - 工具研究
date: 2026-03-22
status: 完成
source: https://docs.openclaw.ai/
---

# OpenClaw 官方文档精读

---

## 一、产品定位

**OpenClaw** 是一个**自托管的个人 AI 助手网关**（MIT 开源）：

> 把 AI 编码代理的能力接入你已经在用的所有聊天应用——WhatsApp、Telegram、Discord、iMessage 等——运行在你自己的设备上，始终在线。

核心优势：
- **数据完全本地** — 不经过第三方服务
- **多渠道统一** — 一个网关接所有消息平台
- **多模型路由** — 自由切换 30+ 模型提供商
- **Skills 扩展** — 通过 clawhub 安装功能插件

---

## 二、系统架构原理

```
你的设备
  └─ Gateway 进程（Node.js，默认端口 18789）
       │
       ├─ 渠道层（Channel Adapters）
       │    接收来自各平台的消息 → 统一格式
       │    ├─ WhatsApp / Telegram / Discord / iMessage
       │    ├─ Slack / Signal / LINE / 飞书 / Teams
       │    ├─ Matrix / IRC / Nostr / Mattermost
       │    └─ WebChat（内置 Web 界面）
       │
       ├─ Agent 引擎
       │    ├─ 读取 workspace 人格文件（SOUL/USER/AGENTS.md）
       │    ├─ 调用 Memory 系统（长期记忆 + 日记）
       │    └─ 执行 Skills（通过 clawhub 安装的扩展）
       │
       ├─ 模型路由层
       │    ├─ 主模型 → fallback 链 → Provider failover
       │    └─ OpenAI 兼容接口对外暴露
       │
       └─ 控制面板（Dashboard）
            http://127.0.0.1:18789/
```

**工作流程：**
```
用户在任意渠道发消息
  → Gateway 接收（按发件人隔离会话）
  → 加载 Agent 人格 + 记忆
  → 路由到指定模型
  → 模型处理 + Skills 调用
  → 结果推送回原渠道
```

---

## 三、安装方式

### 推荐方式

```bash
# macOS / Linux
curl -fsSL https://openclaw.ai/install.sh | bash

# Windows PowerShell
iwr -useb https://openclaw.ai/install.ps1 | iex

# npm（当前本机使用的方式）
npm install -g openclaw@latest
```

### 其他方式
- Docker：`docker pull openclaw/openclaw`
- Nix：`nix-openclaw` flake
- 从源码构建：`pnpm install && pnpm build`

**系统要求：** Node.js 24（推荐）或 22.16+ LTS

---

## 四、Onboarding Wizard（配置向导）

运行 `openclaw onboard --install-daemon` 会经历 7 个阶段：

| 阶段 | 内容 |
|------|------|
| **1. Model/Auth** | 选择模型提供商（OpenAI 兼容 / Anthropic 兼容 / 自定义），设置 API Key |
| **2. Workspace** | Agent 文件存放位置，默认 `~/.openclaw/workspace` |
| **3. Gateway** | 端口、绑定地址、认证模式、Tailscale 暴露选项 |
| **4. Channels** | 启用消息平台（WhatsApp / Telegram / Discord / iMessage 等） |
| **5. Daemon** | 安装系统服务（macOS: LaunchAgent，Linux/WSL2: systemd） |
| **6. Health Check** | 验证 Gateway 启动正常 |
| **7. Skills** | 安装推荐扩展 |

**两种模式：**
- **QuickStart**：智能默认值（本地网关 18789，自动 Token 认证，"coding" 工具配置）
- **Advanced**：完全控制所有选项

**常用命令：**
```bash
openclaw onboard          # 首次配置
openclaw configure        # 重新配置
openclaw gateway status   # 检查网关状态
openclaw dashboard        # 打开控制面板
openclaw agents add <名称> # 创建新 Agent（独立工作区）
```

---

## 五、模型系统

### 5.1 模型优先级

```
主模型 → Fallback 链（顺序执行） → Provider Auth Failover
```

### 5.2 支持的提供商

| 提供商 | 认证方式 |
|--------|---------|
| **Anthropic** | API Key 或 `claude setup-token` |
| **OpenAI** | API Key 或 OAuth（包括 Codex 订阅） |
| **OpenRouter** | API Key，支持免费模型扫描 |
| **自定义提供商** | 在 `models.json` 中配置 `models.providers` |
| **MiniMax（本机配置）** | `https://api.minimaxi.com/anthropic` |
| **小米** | API Key |

### 5.3 配置字段

```json
{
  "agents": {
    "defaults": {
      "model": {
        "primary": "anthropic/claude-sonnet-4-6",
        "fallbacks": ["openai/gpt-4o", "openrouter/mistral"]
      },
      "models": ["allowed-model-1", "allowed-model-2"]
    }
  }
}
```

### 5.4 运行时切换

- `/model` 命令 → 不重启切换模型
- 模型白名单：设置 `agents.defaults.models` 后只允许列表内的模型

---

## 六、Memory 系统

### 6.1 原理

> 记忆 = **Markdown 文件**。模型只记住写到磁盘的内容，不依赖上下文缓存。

### 6.2 两层存储结构

```
~/.openclaw/workspace/
  ├─ MEMORY.md              # 长期记忆（精华提炼）
  │    └─ 仅私人会话加载，不暴露给群组
  └─ memory/
       └─ YYYY-MM-DD.md    # 每日日记（追加模式）
            └─ 每次会话加载今天 + 昨天的日记
```

### 6.3 记忆工具

- `memory_search`：语义检索（向量 + BM25 混合匹配）
- `memory_get`：精确文件读取

### 6.4 自动记忆保存

当会话 Token 估算超过阈值时，系统自动触发 **memory flush**，在 context 压缩前保存重要信息。

---

## 七、Workspace（工作区）人格文件

```
~/.openclaw/workspace/main/
  ├─ SOUL.md       # Agent 的价值观、行为准则（核心人格）
  ├─ USER.md       # 用户画像（Agent 如何理解你）
  ├─ AGENTS.md     # Agent 团队协作指令（你现在读的就是这个体系）
  ├─ IDENTITY.md   # Agent 身份设定
  ├─ TOOLS.md      # 可用工具清单
  ├─ HEARTBEAT.md  # 定期自检/保活记录
  ├─ BOOTSTRAP.md  # 首次启动引导（运行后删除）
  └─ main.sqlite   # 对话历史数据库
```

**加载顺序（每次会话）：**
1. `SOUL.md` — 我是谁
2. `USER.md` — 我在帮谁
3. `memory/今天.md` + `memory/昨天.md` — 近期发生了什么
4. `MEMORY.md` — 长期记忆（仅主会话）

---

## 八、Skills 系统

Skills 是 OpenClaw 的**功能扩展插件**，通过 clawhub 安装：

```bash
npx clawhub@latest install <skill-id>
```

- 安装位置：项目内 `skills/` 目录
- 每个 skill 包含 `SKILL.md`（描述）和 `_meta.json`（元数据）
- Agent 读取 SKILL.md 来了解如何使用该工具
- 已安装：`agent-team-orchestration`、`sonoscli`

---

## 九、支持的消息渠道（20+）

| 类别 | 渠道 |
|------|------|
| 即时通讯 | WhatsApp · Telegram · Signal · LINE · Zalo |
| 团队协作 | Slack · Discord · Microsoft Teams · Mattermost · Feishu（飞书）|
| Apple 生态 | iMessage · BlueBubbles |
| 开放协议 | Matrix · IRC · Nostr |
| 专有平台 | Synology Chat · Tlon · Twitch |
| 内置 | WebChat（http://127.0.0.1:18789/） |

---

## 十、本机安装信息（2026-03-22）

| 项目 | 值 |
|------|-----|
| 版本 | `2026.3.13` |
| 端口 | `18789` |
| npm 路径 | `C:\Users\15246\AppData\Local\nvm\v22.22.1\node_modules\openclaw\` |
| 数据目录 | `C:\Users\15246\.openclaw\` |
| Windows 计划任务 | `OpenClaw Gateway`（已配置开机自启） |
| 已配置模型 | MiniMax M2.7 / M2.5 / M2.5-Highspeed |
| 已配置渠道 | 小米（xiaomi） |

> [!note] 卸载方式
> 见 [[Win11 卸载 OpenClaw 完整指南]]

---

## 十一、官方资源

- 官网：https://openclaw.ai
- 文档首页：https://docs.openclaw.ai
- GitHub：https://github.com/openclaw/openclaw
- Discord：https://discord.gg/clawd
- DeepWiki：https://deepwiki.com/openclaw/openclaw

#OpenClaw #AI网关 #个人助手 #官方文档 #工具研究
