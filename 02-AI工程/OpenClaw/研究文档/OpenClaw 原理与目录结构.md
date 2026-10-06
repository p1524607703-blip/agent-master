---
title: OpenClaw 原理与目录结构
tags:
  - OpenClaw
  - AI网关
  - 工具研究
date: 2026-03-22
status: 完成
---

# OpenClaw 原理与目录结构

## 一、是什么

**OpenClaw** 是一个**个人 AI 助手网关**（MIT 开源），核心定位是：

> 把 LLM 的能力接入你已经在用的**所有消息渠道**，在本地设备上运行，始终在线。

口号：`EXFOLIATE! EXFOLIATE!`（蜕变！蜕变！）

---

## 二、核心架构原理

```
你的设备（本地运行）
  └─ Gateway（Node.js 进程，默认端口 18789）
       ├─ 消息渠道层（Channel Adapters）
       │    ├─ WhatsApp / Telegram / Slack / Discord
       │    ├─ iMessage / Signal / LINE / 飞书 / Teams
       │    └─ WebChat / IRC / Nostr / Zalo 等 20+ 渠道
       ├─ 模型路由层（Model Router）
       │    ├─ 对接 30+ 模型提供商（OpenAI / Claude / MiniMax / Gemini…）
       │    ├─ OpenAI 兼容接口对外暴露
       │    └─ 支持 failover / Auth profile rotation
       ├─ Skills 系统（技能扩展）
       │    └─ 类似 Claude Code Skills，通过 clawhub 安装
       ├─ Agent 引擎
       │    └─ 读取 workspace 中的 SOUL.md / USER.md / AGENTS.md
       └─ 本地存储（SQLite + 文件系统）
```

**工作流程：**
1. 用户在任意渠道（如微信/Telegram）发消息
2. Gateway 接收 → 路由到指定 LLM
3. LLM 处理 → 返回结果 → 推送回原渠道
4. Agent 可调用 Skills 执行本地/远程操作

---

## 三、本机安装信息

| 项目 | 值 |
|------|-----|
| npm 包路径 | `C:\Users\15246\AppData\Local\nvm\v22.22.1\node_modules\openclaw\` |
| 数据目录 | `C:\Users\15246\.openclaw\` |
| 网关端口 | `18789` |
| 当前版本 | `2026.3.13` |
| Windows 计划任务 | `OpenClaw Gateway`（开机自启） |
| 已配置模型 | MiniMax M2.7 / M2.5 / M2.5-Highspeed |

---

## 四、`~/.openclaw/` 目录详解

```
C:\Users\15246\.openclaw\
│
├── openclaw.json          # 主配置文件
│   ├── meta               # 版本元信息、最后触碰时间
│   ├── wizard             # 向导运行记录
│   ├── auth.profiles      # 各模型提供商的 Auth 凭证
│   └── models             # 模型列表及路由配置
│
├── openclaw.json.bak.*    # 配置自动备份（最近5份）
│
├── gateway.cmd            # Windows 网关启动脚本
│   └─ node openclaw/dist/index.js gateway --port 18789
│
├── restart-gateway.ps1    # 重启网关的 PowerShell 脚本
│
├── update-check.json      # 自动更新检查记录
│
├── workspace/             # Agent 工作区（人格/记忆/指令）
│   └── main/
│       ├── SOUL.md        # Agent 的"灵魂"——价值观与行为准则
│       ├── USER.md        # 用户画像——Agent 如何理解你
│       ├── AGENTS.md      # Agent 团队协作指令
│       ├── IDENTITY.md    # Agent 身份设定
│       ├── TOOLS.md       # 可用工具清单
│       ├── HEARTBEAT.md   # 定期自检/保活记录
│       ├── BOOTSTRAP.md   # 首次启动引导（运行后可删除）
│       └── main.sqlite    # 对话历史数据库（SQLite）
│
├── agents/                # Agent 实例配置
│
├── canvas/                # Canvas 渲染数据（实时可视化面板）
│
├── completions/           # LLM 补全缓存
│
├── credentials/           # 渠道 OAuth / API Token 存储
│
├── cron/                  # 定时任务配置
│
├── devices/               # 已连接的消息渠道设备注册表
│
├── identity/              # Agent 身份证明文件
│
├── logs/                  # 网关运行日志
│
├── media/                 # 媒体文件缓存（图片/语音/视频）
│
└── memory/                # Agent 长期记忆文件
```

---

## 五、与本项目的关系

OpenClaw 原本计划作为选品工具的 AI 分析引擎接入点（见 [[reference_openclaw]]），但当前**本地安装的 OpenClaw** 是配置到 MiniMax 模型的**个人助手实例**，与火山云服务器上的远程实例是两个独立部署。

---

## 六、官方资源

- 官网：https://openclaw.ai
- 文档：https://docs.openclaw.ai
- GitHub：https://github.com/openclaw/openclaw
- Discord：https://discord.gg/clawd

#OpenClaw #AI网关 #工具研究 #个人助手
