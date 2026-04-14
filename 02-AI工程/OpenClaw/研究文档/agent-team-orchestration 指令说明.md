---
title: agent-team-orchestration 指令说明
tags:
  - clawhub
  - agent-team
  - 多智能体
  - 编排
date: 2026-03-22
status: 完成
---

# agent-team-orchestration 指令说明

> 来源：clawhub 安装 `agent-team-orchestration`（评分 3.772，最高）
> 安装位置：`D:\Download\agent-master\skills\agent-team-orchestration\`

---

## 一、这个 skill 是干什么的

**多 Agent 团队编排的生产级操作手册**，用于：

1. 设置 2+ 个专职 Agent 组成的团队
2. 定义任务路由和生命周期（收件箱 → 规格 → 构建 → 审查 → 完成）
3. 创建 Agent 间的交接协议
4. 建立审查和质量关卡
5. 管理 Agent 间的异步通信和产物共享

---

## 二、最小团队模型（2 个 Agent）

```
Orchestrator（你/Claude）
  └─ 路由任务、追踪状态、报告结果

Builder（执行者，如 Codex）
  └─ 执行工作、产出代码/文档/配置

（可选）Reviewer（审查者）
  └─ 检查质量、把关交付
```

**核心循环：**
```
Builder 产出 → Reviewer 检查 → Orchestrator 发布 或 打回重做
```

---

## 三、四种 Agent 角色

| 角色 | 职责 | 推荐模型 |
|------|------|---------|
| **Orchestrator（协调者）** | 路由工作、追踪状态、做优先级判断 | 高推理模型（Claude Opus / Sonnet） |
| **Builder（执行者）** | 产出产物——代码、文档、配置 | 成本效益型（Codex / Haiku） |
| **Reviewer（审查者）** | 验证质量、发现漏洞 | 高推理模型（捕捉 Builder 遗漏的问题） |
| **Ops（运维者）** | 定时任务、状态巡检、任务分发 | 最便宜的可靠模型 |

> [!tip] 与我们团队工作流的对应关系
> - Orchestrator = **Claude**（决策层）
> - Builder = **Codex**（代码执行）
> - Reviewer = **Claude**（Code Review）
> - Ops = 自动化脚本 / n8n 工作流

---

## 四、任务生命周期

```
Inbox → Assigned → In Progress → Review → Done | Failed
```

**规则：**
- Orchestrator 拥有状态转换权——不要依赖 Agent 自己更新状态
- 每次状态转换都要留注释（谁做了什么、为什么）
- `Failed` 是合法的终态——记录原因，继续前进

---

## 五、标准交接模板（Handoff）

好的交接必须包含：

```markdown
1. 做了什么  — 变更/输出摘要
2. 产物在哪  — 精确文件路径
3. 如何验证  — 测试命令或验收标准
4. 已知问题  — 未完成或有风险的部分
5. 下一步    — 接收方的明确动作
```

❌ 差的交接：*"做完了，看文件。"*
✅ 好的交接：*"Auth 模块已构建在 `/shared/auth/`，运行 `npm test auth` 验证，已知问题：限流未实现，下一步：Reviewer 检查错误处理边界情况。"*

---

## 六、常见踩坑

| 坑 | 原因 | 解法 |
|----|------|------|
| 找不到产物 | 没指定输出路径 | Spawn 时明确指定精确路径 |
| 质量下滑 | 跳过 Review 步骤 | 每个产物必须有人 Review |
| Agent 沉默 | 没要求进度注释 | 要求：开始/阻塞/交接/完成时必须注释 |
| 能力不匹配 | 分配了 Agent 不具备的能力 | 分配前先确认 Agent 工具权限 |
| Orchestrator 下场干活 | 失去对团队的整体视野 | Orchestrator 只路由和追踪，不执行 |

---

## 七、不适用场景

- **单 Agent 任务** — 直接用 AGENTS.md，加编排只会带来额外开销
- **一次性委托** — 直接用 `sessions_spawn`，不需要这套流程
- **简单问题路由** — 转发问题给专家是"发消息"，不是"工作流"

---

## 八、参考文件（skill 内）

| 文件 | 用途 |
|------|------|
| `references/team-setup.md` | 定义 Agent、角色、模型、工作区 |
| `references/task-lifecycle.md` | 任务状态、转换、注释设计 |
| `references/communication.md` | 异步/同步通信、产物路径配置 |
| `references/patterns.md` | 规格→构建→测试、并行研究、升级等模式 |

---

## 九、与我们项目的应用

> [!example] 选品工具开发场景
> ```
> Claude（Orchestrator）
>   收到需求："新增价格趋势图表"
>   ↓ 拆解任务 → 写 spec → 交给 Codex
> Codex（Builder）
>   实现 Vue 组件 + NestJS API
>   ↓ 交接报告 → 精确说明文件路径 + 测试方法
> Claude（Reviewer）
>   Review 代码 → 检查安全/性能/风格
>   ↓ 通过 → 合并 | 不通过 → 打回重做（注明原因）
> ```

#agentTeam #多智能体 #编排 #clawhub #工作流
