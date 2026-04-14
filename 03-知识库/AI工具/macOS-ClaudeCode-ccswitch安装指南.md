---
title: macOS 系统 Claude Code 与 ccswitch 安装配置指南
tags:
  - Claude Code
  - macOS
  - 开发工具
  - 版本管理
date: 2026-04-14
---

# macOS 系统 Claude Code 与 ccswitch 安装配置指南

本指南详细介绍在 macOS 系统上安装 Claude Code 和 ccswitch（版本管理工具）的完整步骤。

---

## 一、Claude Code 安装

### 官方安装方式（推荐）

#### 方式一：使用安装脚本（最简单）

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

这个脚本会自动：
- 检测你的系统架构（Apple Silicon / Intel）
- 下载最新版本的 Claude Code
- 安装到正确的位置
- 配置环境变量

#### 方式二：使用 Homebrew

如果你已安装 Homebrew，也可以使用：

```bash
# 暂未官方支持，但可以使用安装脚本
curl -fsSL https://claude.ai/install.sh | bash
```

### 验证安装

安装完成后，打开新的终端窗口，运行：

```bash
claude --version
```

如果显示版本号，说明安装成功。

### 首次启动

在任意项目目录中启动 Claude Code：

```bash
cd your-project
claude
```

首次使用时会提示你登录，按照提示完成认证即可。

---

## 二、ccswitch 安装与使用（Claude Code 版本管理工具）

### 什么是 ccswitch

ccswitch 是 Claude Code 的版本管理工具，类似于 Node.js 的 nvm 或 Python 的 pyenv，可以让你：
- 安装多个版本的 Claude Code
- 在不同版本之间快速切换
- 管理不同版本的配置

### 安装 ccswitch

#### 方式一：从 GitHub 安装

```bash
# 克隆 ccswitch 仓库
git clone https://github.com/<username>/ccswitch.git ~/.ccswitch

# 添加到 shell 配置文件（zsh 或 bash）
echo 'export PATH="$HOME/.ccswitch/bin:$PATH"' >> ~/.zshrc
echo 'eval "$(ccswitch init -)"' >> ~/.zshrc

# 重新加载配置
source ~/.zshrc
```

#### 方式二：使用安装脚本（如果有）

```bash
# 如果 ccswitch 提供安装脚本
curl -fsSL https://github.com/<username>/ccswitch/raw/main/install.sh | bash
```

### ccswitch 常用命令

```bash
# 查看可用版本
ccswitch list-remote

# 安装特定版本
ccswitch install 1.0.0

# 安装最新版本
ccswitch install latest

# 切换版本
ccswitch use 1.0.0

# 查看已安装版本
ccswitch list

# 卸载版本
ccswitch uninstall 1.0.0

# 查看当前版本
ccswitch current

# 设置默认版本
ccswitch default 1.0.0
```

---

## 三、安装后的配置

### 配置 Claude Code

Claude Code 的配置文件位于：

```bash
# 全局配置
~/.claude/config.json

# 项目特定配置（在项目根目录）
./CLAUDE.md
```

### 环境变量配置

在 `~/.zshrc` 或 `~/.bash_profile` 中添加：

```bash
# Claude Code 配置
export CLAUDE_HOME="$HOME/.claude"
export PATH="$CLAUDE_HOME/bin:$PATH"

# 如果使用 ccswitch
export CCSWITCH_HOME="$HOME/.ccswitch"
export PATH="$CCSWITCH_HOME/bin:$PATH"
```

### 验证完整配置

```bash
# 检查 Claude Code
which claude
claude --version

# 检查 ccswitch（如果已安装）
which ccswitch
ccswitch --version
```

---

## 四、常见问题与解决方案

### 问题一：安装后 `claude` 命令找不到

**解决方案：**

1. 检查是否安装到正确位置：
```bash
ls -la ~/.claude/bin/
```

2. 重新加载 shell 配置：
```bash
source ~/.zshrc
# 或者
source ~/.bash_profile
```

3. 手动添加到 PATH：
```bash
echo 'export PATH="$HOME/.claude/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

### 问题二：权限错误

**解决方案：**

```bash
# 修复权限
chmod +x ~/.claude/bin/claude

# 如果是 ccswitch
chmod +x ~/.ccswitch/bin/ccswitch
```

### 问题三：Apple Silicon (M1/M2/M3) 兼容性

**解决方案：**

安装脚本会自动检测架构，如果遇到问题：

```bash
# 检查架构
uname -m

# 强制使用 Rosetta（如果需要）
arch -x86_64 /bin/bash
curl -fsSL https://claude.ai/install.sh | bash
```

### 问题四：ccswitch 切换版本后不生效

**解决方案：**

1. 确保已执行 `ccswitch init`：
```bash
echo 'eval "$(ccswitch init -)"' >> ~/.zshrc
source ~/.zshrc
```

2. 重新打开终端窗口，或：
```bash
exec zsh
```

---

## 五、卸载与更新

### 更新 Claude Code

Claude Code 会自动在后台更新，也可以手动更新：

```bash
# 重新运行安装脚本
curl -fsSL https://claude.ai/install.sh | bash
```

### 卸载 Claude Code

```bash
# 删除安装目录
rm -rf ~/.claude

# 从 shell 配置中移除相关配置
# 编辑 ~/.zshrc 或 ~/.bash_profile，删除 Claude Code 相关行
```

### 卸载 ccswitch

```bash
# 删除 ccswitch 目录
rm -rf ~/.ccswitch

# 从 shell 配置中移除相关配置
# 编辑 ~/.zshrc 或 ~/.bash_profile，删除 ccswitch 相关行
```

---

## 六、快速开始使用 Claude Code

### 创建测试项目

```bash
# 创建新项目
mkdir my-test-project
cd my-test-project

# 初始化 git（可选但推荐）
git init

# 启动 Claude Code
claude
```

### 常用命令示例

```bash
# 直接执行任务
claude "创建一个 README.md 文件"

# 交互式模式
claude

# 使用特定技能
claude "/skill-name"
```

---

## 七、参考链接

- [Claude Code 官方文档](https://code.claude.com/docs/zh-CN/)
- [Claude Code 快速入门](https://code.claude.com/docs/zh-CN/quickstart)
- [Claude Code GitHub（如果有）](https://github.com/anthropics/claude-code)
- [ccswitch GitHub（请替换为实际地址）](https://github.com/<username>/ccswitch)

---

> [!tip] 提示
> 如果 ccswitch 还没有公开可用，你可以：
> 1. 关注 Claude Code 官方仓库获取更新
> 2. 使用 Git 标签和分支手动管理不同版本
> 3. 创建多个 `~/.claude` 目录并通过 PATH 切换

**相关链接**：[[Claude Code CLI 指令手册]] | [[AI工具]]
