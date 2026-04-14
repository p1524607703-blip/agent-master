---
title: Claude Code Agent Teams 完整解析
tags:
  - Claude Code
  - Agent Teams
  - 多智能体
  - 实验功能
date: 2026-03-22
status: 完成
source: https://code.claude.com/docs/zh-CN/agent-teams
---

# Claude Code Agent Teams 完整解析

> [!warning] 实验性功能
> Agent Teams 默认**禁用**，需手动启用。存在已知限制（见文末）。
> 要求：Claude Code **v2.1.32+**

---

## 一、是什么

Agent Teams 让你协调**多个 Claude Code 实例**一起工作：
- 一个会话充当 **Team Lead（负责人）**，协调分工、分配任务、综合结果
- 若干 **Teammate（队友）** 各自独立运行，每人有自己的 context window
- 队友之间可以**直接相互通信**（不需要通过负责人中转）

---

## 二、与 Subagents 的区别

| | Subagents | Agent Teams |
|---|---|---|
| **Context** | 自己的 context，结果返回给调用者 | 自己的 context，完全独立 |
| **通信** | 仅向主 Agent 报告结果 | 队友直接相互发消息 |
| **协调** | 主 Agent 管理所有工作 | 共享任务列表，自我协调 |
| **最适合** | 只需要结果的专注任务 | 需要讨论协作的复杂工作 |
| **Token 成本** | 较低 | 较高（每个队友是独立实例） |

> [!tip] 选择原则
> 需要队友**互相交流、质疑彼此发现**时 → Agent Teams
> 只需要结果汇报时 → Subagents

---

## 三、启用方式

**方法一：settings.json**
```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**方法二：环境变量**
```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
```

---

## 四、启动第一个 Agent Team

用自然语言描述任务和团队结构，Claude 自动生成：

```text
I'm designing a CLI tool that helps developers track TODO comments across
their codebase. Create an agent team to explore this from different angles:
one teammate on UX, one on technical architecture, one playing devil's advocate.
```

Claude 会自动：
1. 创建共享任务列表
2. 生成各角色队友
3. 让他们并行探索
4. 综合发现
5. 完成后清理团队

---

## 五、控制团队

### 5.1 显示模式

| 模式 | 说明 | 要求 |
|------|------|------|
| **In-process**（默认） | 所有队友在主终端内，Shift+Down 切换 | 任意终端 |
| **Split panes** | 每个队友独立窗格，同时可见 | tmux 或 iTerm2 |

配置（settings.json）：
```json
{
  "teammateMode": "in-process"
}
```

强制单次会话：
```bash
claude --teammate-mode in-process
```

### 5.2 指定队友和模型

```text
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.
```

### 5.3 要求计划审批（高风险任务）

```text
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.
```

流程：队友进入只读计划模式 → 提交计划 → 负责人审批 → 通过后执行

### 5.4 直接与单个队友对话

- **In-process**：Shift+Down 循环切换，Enter 进入会话，Escape 中断
- **Split pane**：直接点击队友窗格
- Ctrl+T 切换任务列表视图

### 5.5 任务管理

任务状态流：`待处理 → 进行中 → 完成 | 失败`

- 负责人显式分配，或队友自我认领
- 使用**文件锁定**防止多人同时认领同一任务
- 任务依赖关系自动管理（依赖完成后自动解锁）

### 5.6 关闭队友

```text
Ask the researcher teammate to shut down
```

### 5.7 清理团队

```text
Clean up the team
```

> [!warning] 必须由负责人清理，不要让队友运行清理命令

### 5.8 用 Hooks 强制质量门控

| Hook | 触发时机 | 以代码 2 退出的效果 |
|------|---------|-----------------|
| `TeammateIdle` | 队友即将空闲时 | 发送反馈，让队友继续工作 |
| `TaskCompleted` | 任务被标记完成时 | 阻止完成，发送反馈 |

---

## 六、架构原理

```
Team Lead（主 Claude Code 会话）
  ├─ 创建团队、生成队友、协调工作
  ├─ 共享任务列表（Task List）
  │    └─ 队友认领 & 完成任务
  ├─ 邮箱系统（Mailbox）
  │    └─ 代理间异步消息传递
  └─ Teammates（N 个独立 Claude Code 实例）
       ├─ 各自独立的 context window
       ├─ 加载相同的 CLAUDE.md / MCP / Skills
       └─ 可直接互发消息（不经过负责人）
```

**本地存储路径：**
- Team config：`~/.claude/teams/{team-name}/config.json`
- Task list：`~/.claude/tasks/{team-name}/`

**权限规则：** 队友继承负责人的权限设置，生成后可单独修改

---

## 七、Token 成本说明

- 每个队友有独立 context window，Token 用量**随队友数量线性增加**
- 适合：研究、审查、新功能开发（并行价值 > 成本）
- 不适合：日常简单任务（单会话更经济）

---

## 八、典型使用场景

### 场景1：并行代码 Review

```text
Create an agent team to review PR #142. Spawn three reviewers:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
```

### 场景2：竞争假设调试

```text
Users report the app exits after one message instead of staying connected.
Spawn 5 agent teammates to investigate different hypotheses. Have them talk
to each other to try to disprove each other's theories, like a scientific debate.
Update the findings doc with whatever consensus emerges.
```

**关键机制：** 让队友主动反驳彼此的理论，存活下来的才是真正的根因。

---

## 九、最佳实践

| 原则 | 说明 |
|------|------|
| 给队友足够 context | 队友不继承负责人对话历史，生成时在 prompt 中补充 |
| 团队规模 3-5 人 | Token 线性增加，超过收益递减 |
| 每人 5-6 个任务 | 保持生产力，便于负责人重新分配 |
| 避免同文件编辑 | 两个队友编辑同文件会覆盖，任务分解到不同文件 |
| 等待队友完成 | 发现负责人抢先做工作时说："Wait for your teammates to complete" |
| 监控 & 引导 | 不要无人值守运行太久 |

---

## 十、已知限制（实验性）

| 限制 | 说明 |
|------|------|
| In-process 不支持会话恢复 | `/resume` `/rewind` 不恢复 in-process 队友 |
| 任务状态可能滞后 | 队友有时不标记完成，需手动推动 |
| 关闭可能很慢 | 队友完成当前请求后才关闭 |
| 每会话只有一个团队 | 不支持同时管理多个团队 |
| 不支持嵌套团队 | 队友不能生成自己的队友 |
| 负责人固定 | 不能转移团队领导权 |
| 权限在生成时锁定 | 不能在 spawn 时为不同队友设置不同权限 |
| Split panes 兼容性 | 不支持 VS Code 集成终端、Windows Terminal、Ghostty |

---

## 十一、与我们项目的对应关系

> [!example] 选品工具开发场景映射
> - **Team Lead** = Claude（当前会话）
> - **Builder Teammate** = Codex（执行编码任务）
> - **Reviewer Teammate** = Claude 第二实例（Code Review）
> - **任务列表** = 我们当前的开发 TODO
>
> 当前我们**手动模拟**了 Agent Teams 的协作模式，
> 等功能稳定后可以用官方 Agent Teams 自动化这个流程。

---

## 十二、故障排除

| 问题 | 解法 |
|------|------|
| 队友未出现 | Shift+Down 检查；确认任务复杂度；检查 tmux 是否安装 |
| 过多权限提示 | 在 settings.json 预批准常见操作 |
| 队友遇错停止 | Shift+Down 检查输出，给额外指示或重新 spawn |
| 负责人提前关闭 | "Wait for your teammates to complete before proceeding" |
| 孤立 tmux 会话 | `tmux ls` → `tmux kill-session -t <name>` |

#ClaudeCode #AgentTeams #多智能体 #实验功能
