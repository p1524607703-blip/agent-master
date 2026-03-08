---
name: GitHub同步
description: 将 Obsidian 知识库推送到 GitHub 或从 GitHub 拉取更新，同时同步 Claude 记忆文件。当用户说"同步"、"推送"、"上传"、"拉取"、"pull"、"push"、"更新仓库"时自动激活。
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
---

# GitHub 同步

将知识库与 GitHub 远程仓库双向同步，并自动处理 Claude 记忆文件。

## 配置

- 仓库路径：`D:/Download/agent-master`
- 远程仓库：`https://github.com/p1524607703-blip/agent-master.git`
- 主分支：`main`
- 系统记忆路径：`C:\Users\15246\.claude\projects\D--Download-agent-master\memory\MEMORY.md`
- 仓库内记忆路径：`D:/Download/agent-master/.claude/memory/MEMORY.md`

## 操作一：推送（上传到 GitHub）

当用户说"推送"、"上传"、"同步到 GitHub"、"push"时执行：

### 步骤

1. **同步记忆文件**：将系统路径的 MEMORY.md 内容复制到仓库内，确保记忆最新
2. **暂存所有变更**：`git add .`
3. **检查是否有变更**：`git status --porcelain`，若无变更则告知用户"无新内容需要提交"
4. **提交**：使用用户提供的提交信息（若未提供则自动生成）
5. **推送**：`git push origin main`
6. **反馈**：报告推送了哪些文件

### 执行命令

```bash
VAULT="D:/Download/agent-master"
SYS_MEMORY="C:/Users/15246/.claude/projects/D--Download-agent-master/memory/MEMORY.md"
REPO_MEMORY="${VAULT}/.claude/memory/MEMORY.md"

# 步骤1：同步记忆文件
cp "$SYS_MEMORY" "$REPO_MEMORY"

# 步骤2-3：暂存并检查
cd "$VAULT"
git add .
CHANGES=$(git status --porcelain)

# 步骤4：提交（MSG 由用户提供或自动生成）
MSG="同步更新 $(date '+%Y-%m-%d %H:%M')"
git commit -m "$MSG"

# 步骤5：推送
git push origin main
```

> **Token 说明**：如果推送失败提示认证错误，需要在 remote URL 中嵌入 token：
> `git remote set-url origin https://<TOKEN>@github.com/p1524607703-blip/agent-master.git`
> Classic token 以 `ghp_` 开头，在 https://github.com/settings/tokens 生成，勾选 `repo` 权限。

---

## 操作二：拉取（从 GitHub 下载更新）

当用户说"拉取"、"pull"、"从 GitHub 更新"、"同步到本地"时执行：

### 步骤

1. **拉取远程变更**：`git pull origin main`
2. **同步记忆文件**：将仓库内的 MEMORY.md 复制到系统路径，使 Claude 记忆生效
3. **反馈**：报告拉取了哪些更新

### 执行命令

```bash
VAULT="D:/Download/agent-master"
SYS_MEMORY_DIR="C:/Users/15246/.claude/projects/D--Download-agent-master/memory"
REPO_MEMORY="${VAULT}/.claude/memory/MEMORY.md"

# 步骤1：拉取
cd "$VAULT"
git pull origin main

# 步骤2：同步记忆到系统路径
mkdir -p "$SYS_MEMORY_DIR"
cp "$REPO_MEMORY" "${SYS_MEMORY_DIR}/MEMORY.md"
```

---

## 操作三：初次配置（新设备克隆后）

当用户在新设备上克隆仓库后首次使用时执行：

```bash
# 克隆仓库
git clone https://github.com/p1524607703-blip/agent-master.git D:/Download/agent-master

# 同步记忆文件到系统路径（将 <用户名> 替换为实际用户名）
SYS_MEMORY_DIR="C:/Users/<用户名>/.claude/projects/D--Download-agent-master/memory"
mkdir -p "$SYS_MEMORY_DIR"
cp "D:/Download/agent-master/.claude/memory/MEMORY.md" "${SYS_MEMORY_DIR}/MEMORY.md"
```

路径编码规则：仓库绝对路径中 `\`、`:` 均替换为 `-`，如 `D:\Download\agent-master` → `D--Download-agent-master`

---

## 注意事项

- `.gitignore` 已排除 `.obsidian/workspace.json`（设备特有，不同步）
- 记忆文件双向同步：推送时「系统→仓库」，拉取时「仓库→系统」
- 每次推送前自动同步记忆，确保记忆不丢失
