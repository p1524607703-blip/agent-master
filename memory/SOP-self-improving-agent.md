# SOP: 安装 self-improving-agent Skill

## 适用场景
给 OpenClaw Agent 安装自改进技能，包含 hooks 自动提醒

## 步骤

### 1. 安装 Skill
```bash
clawdhub install self-improving-agent
# 或手动
git clone https://github.com/peterskoett/self-improving-agent.git ~/.openclaw/skills/self-improving-agent
```

### 2. 创建学习文件
```bash
mkdir -p ~/.openclaw/workspace/.learnings

# 创建三个文件（模板从 skill 的 assets/ 目录复制，或手动创建）
# - LEARNINGS.md
# - ERRORS.md
# - FEATURE_REQUESTS.md
```

### 3. 配置 Hook（自动提醒）
```bash
# 复制 hook 到 managed 目录
mkdir -p ~/.openclaw/hooks
cp -r ~/.openclaw/skills/self-improving-agent/hooks/openclaw ~/.openclaw/hooks/self-improvement

# 启用 hook
openclaw hooks enable self-improvement

# 重启 gateway 让 hooks 生效
openclaw gateway restart
```

### 4. 验证
```bash
openclaw hooks list
# 应该看到: ✓ ready  🧠 self-improvement
```

## 学习文件格式

### LEARNINGS.md
```markdown
## [LRN-YYYYMMDD-XXX] category

**Logged**: ISO-8601 timestamp
**Priority**: low | medium | high | critical
**Status**: pending
**Area**: frontend | backend | infra | tests | docs | config

### Summary
One-line description

### Details
Full context

### Suggested Action
Specific fix or improvement

### Metadata
- Source: conversation | error | user_feedback
- Related Files: path/to/file.ext
- Tags: tag1, tag2
- See Also: LRN-20250110-001
```

### ERRORS.md
```markdown
## [ERR-YYYYMMDD-XXX] skill_or_command_name

**Logged**: ISO-8601 timestamp
**Priority**: high
**Status**: pending

### Summary
Brief description

### Error
```
Actual error message
```

### Context
What was attempted

### Suggested Fix
How to resolve
```

### FEATURE_REQUESTS.md
```markdown
## [FEAT-YYYYMMDD-XXX] capability_name

**Logged**: ISO-8601 timestamp
**Priority**: medium
**Status**: pending

### Requested Capability
What user wanted

### User Context
Why they needed it
```

## 注意事项
- Hook 监听 `agent:bootstrap` 事件，每次 agent 启动时提醒
- 学习文件放在 `~/.openclaw/workspace/.learnings/`
- 重要学习可推广到 SOUL.md / AGENTS.md / TOOLS.md
