---
title: Win11 卸载 OpenClaw 完整指南
tags:
  - OpenClaw
  - 卸载
  - Windows
date: 2026-03-22
status: 待执行
---

# Win11 卸载 OpenClaw 完整指南

> [!warning] 注意
> 执行前确认已备份需要保留的配置（如 `~/.openclaw/openclaw.json` 中的 API Key）。

---

## 卸载步骤（按顺序执行）

### 步骤 1：停止并删除 Windows 计划任务

OpenClaw 注册了开机自启任务 `OpenClaw Gateway`。

```powershell
# 停止任务
Stop-ScheduledTask -TaskName "OpenClaw Gateway"

# 删除任务
Unregister-ScheduledTask -TaskName "OpenClaw Gateway" -Confirm:$false
```

验证：
```powershell
Get-ScheduledTask | Where-Object {$_.TaskName -like "*openclaw*"}
# 应返回空
```

---

### 步骤 2：停止正在运行的 OpenClaw 进程

```powershell
# 查找并终止进程
Get-Process | Where-Object {$_.CommandLine -like "*openclaw*"} | Stop-Process -Force

# 或者通过端口找到进程
netstat -ano | findstr :18789
# 找到 PID 后：
taskkill /PID <PID号> /F
```

---

### 步骤 3：卸载 npm 全局包

```bash
npm uninstall -g openclaw
```

验证：
```bash
npm list -g --depth=0 | grep openclaw
# 应返回空
```

包位置：`C:\Users\15246\AppData\Local\nvm\v22.22.1\node_modules\openclaw\`

---

### 步骤 4：删除数据目录

> [!danger] 不可逆操作
> 此目录包含对话历史、凭证、记忆文件。请先确认是否需要备份。

```powershell
# 先查看大小
(Get-ChildItem -Path "$env:USERPROFILE\.openclaw" -Recurse |
  Measure-Object -Property Length -Sum).Sum / 1MB

# 确认后删除
Remove-Item -Path "$env:USERPROFILE\.openclaw" -Recurse -Force
```

目录：`C:\Users\15246\.openclaw\`

---

### 步骤 5：删除仓库内的 .openclaw 目录

```powershell
Remove-Item -Path "D:\Download\agent-master\.openclaw" -Recurse -Force
```

内容：`workspace-state.json`（仅一个文件，onboarding 记录）

---

### 步骤 6：清理环境变量（如有）

```powershell
# 检查是否有 openclaw 相关环境变量
[System.Environment]::GetEnvironmentVariables("User") |
  Where-Object {$_.Key -like "*openclaw*" -or $_.Value -like "*openclaw*"}
```

---

### 步骤 7：验证清理完成

```powershell
# 检查进程
Get-Process | Where-Object {$_.Name -like "*openclaw*"}

# 检查计划任务
Get-ScheduledTask | Where-Object {$_.TaskName -like "*openclaw*"}

# 检查 npm 包
npm list -g --depth=0

# 检查目录
Test-Path "$env:USERPROFILE\.openclaw"  # 应返回 False
```

---

## 清理文件清单

| 位置 | 类型 | 大小估计 |
|------|------|---------|
| `C:\Users\15246\AppData\Local\nvm\v22.22.1\node_modules\openclaw\` | npm 包 | ~几十 MB |
| `C:\Users\15246\.openclaw\` | 数据/配置 | 视使用时长 |
| `D:\Download\agent-master\.openclaw\` | 仓库内数据 | 极小 |
| Windows 计划任务 `OpenClaw Gateway` | 注册表 | — |

---

> [!note] 如需重新安装
> `npm install -g openclaw@latest && openclaw onboard --install-daemon`

#OpenClaw #卸载 #Windows #清理
