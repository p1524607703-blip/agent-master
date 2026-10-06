---
title: agent-browser 原理与完整命令手册
tags:
  - clawhub
  - agent-browser
  - 浏览器自动化
  - TheSethRose
date: 2026-03-22
status: 完成
source: https://clawhub.ai/TheSethRose/agent-browser
---

# agent-browser 原理与完整命令手册

> 来源：TheSethRose/agent-browser（clawhub 官方版）
> 安装位置：`D:\Download\agent-master\skills\agent-browser\`
> GitHub：https://github.com/TheSethRose/Agent-Browser-CLI

---

## 一、是什么

**agent-browser** 是一个基于 **Rust** 的无头浏览器自动化 CLI，配合 Node.js fallback，让 AI Agent 可以：

> 通过结构化命令导航网页、点击元素、填写表单、截图，完成所有人类可以在浏览器里做的操作。

底层引擎：**Playwright**（Chromium）
作者：TheSethRose / Vercel Labs

---

## 二、核心工作原理

```
AI Agent 发出自然语言指令
       ↓
转化为 agent-browser 命令
       ↓
  1. open <url>         → 打开页面
  2. snapshot -i        → 获取可交互元素列表（带 @ref 编号）
       ↓ 返回：
       textbox "Email" [ref=e1]
       textbox "Password" [ref=e2]
       button "Submit" [ref=e3]
  3. fill @e1 "..."     → 通过 ref 操作元素
  4. click @e3          → 点击
  5. wait --load        → 等待页面响应
  6. snapshot -i        → 重新获取元素（导航后 ref 会刷新）
```

**核心循环：导航 → 快照 → 交互 → 重复**

> [!tip] 关键概念：@ref 元素引用
> snapshot -i 返回的 `@e1` `@e2` 等是**每次页面加载后的临时编号**，导航后必须重新 snapshot 获取新 ref。

---

## 三、安装

```bash
npm install -g agent-browser
agent-browser install          # 安装 Playwright 浏览器
agent-browser install --with-deps  # 含系统依赖（推荐 Linux）
```

---

## 四、完整命令参考

### 4.1 导航

```bash
agent-browser open <url>      # 打开 URL
agent-browser back            # 后退
agent-browser forward         # 前进
agent-browser reload          # 刷新
agent-browser close           # 关闭浏览器
```

### 4.2 页面快照（分析页面结构）

```bash
agent-browser snapshot            # 完整可访问性树
agent-browser snapshot -i         # 仅可交互元素（推荐）
agent-browser snapshot -c         # 紧凑输出
agent-browser snapshot -d 3       # 限制深度为 3
agent-browser snapshot -s "#main" # 限定 CSS 选择器范围
```

### 4.3 元素交互（使用 snapshot 返回的 @ref）

```bash
agent-browser click @e1           # 点击
agent-browser dblclick @e1        # 双击
agent-browser fill @e2 "text"     # 清空并输入（推荐用于表单）
agent-browser type @e2 "text"     # 不清空，追加输入
agent-browser press Enter         # 按键
agent-browser press Control+a     # 组合键
agent-browser hover @e1           # 悬停
agent-browser check @e1           # 勾选复选框
agent-browser uncheck @e1         # 取消勾选
agent-browser select @e1 "value"  # 下拉选择
agent-browser scroll down 500     # 滚动页面
agent-browser scrollintoview @e1  # 滚动到元素可见
agent-browser drag @e1 @e2        # 拖拽
agent-browser upload @e1 file.pdf # 上传文件
```

### 4.4 获取信息

```bash
agent-browser get text @e1        # 获取元素文字
agent-browser get html @e1        # 获取 innerHTML
agent-browser get value @e1       # 获取输入框的值
agent-browser get attr @e1 href   # 获取属性
agent-browser get title           # 获取页面标题
agent-browser get url             # 获取当前 URL
agent-browser get count ".item"   # 统计匹配元素数量
agent-browser get box @e1         # 获取元素边界框
```

### 4.5 状态检查

```bash
agent-browser is visible @e1      # 是否可见
agent-browser is enabled @e1      # 是否可用
agent-browser is checked @e1      # 是否勾选
```

### 4.6 截图 & PDF

```bash
agent-browser screenshot          # 截图输出到 stdout
agent-browser screenshot path.png # 保存到文件
agent-browser screenshot --full   # 整页截图
agent-browser pdf output.pdf      # 保存为 PDF
```

### 4.7 视频录制

```bash
agent-browser record start ./demo.webm    # 开始录制
agent-browser click @e1                   # 执行操作
agent-browser record stop                 # 停止并保存
agent-browser record restart ./take2.webm # 重新录制
```

### 4.8 等待

```bash
agent-browser wait @e1                    # 等待元素出现
agent-browser wait 2000                   # 等待毫秒
agent-browser wait --text "Success"       # 等待文字出现
agent-browser wait --url "/dashboard"     # 等待 URL 匹配
agent-browser wait --load networkidle     # 等待网络空闲
agent-browser wait --fn "window.ready"   # 等待 JS 条件
```

### 4.9 语义定位（替代 @ref）

```bash
agent-browser find role button click --name "Submit"
agent-browser find text "Sign In" click
agent-browser find label "Email" fill "user@test.com"
agent-browser find first ".item" click
agent-browser find nth 2 "a" text
```

### 4.10 浏览器设置

```bash
agent-browser set viewport 1920 1080      # 设置视口
agent-browser set device "iPhone 14"     # 模拟设备
agent-browser set geo 37.7749 -122.4194  # 设置地理位置
agent-browser set offline on             # 离线模式
agent-browser set headers '{"X-Key":"v"}' # HTTP 请求头
agent-browser set credentials user pass  # HTTP 基础认证
agent-browser set media dark             # 暗色模式
```

### 4.11 Cookie & Storage

```bash
agent-browser cookies                    # 获取所有 Cookie
agent-browser cookies set name value    # 设置 Cookie
agent-browser cookies clear             # 清除 Cookie
agent-browser storage local             # 获取所有 localStorage
agent-browser storage local set k v    # 设置值
agent-browser storage local clear      # 清除
```

### 4.12 网络拦截

```bash
agent-browser network route <url>             # 拦截请求
agent-browser network route <url> --abort     # 阻断请求
agent-browser network route <url> --body '{}' # Mock 响应
agent-browser network unroute [url]           # 移除拦截
agent-browser network requests                # 查看请求记录
agent-browser network requests --filter api  # 过滤请求
```

### 4.13 多标签 & 多窗口

```bash
agent-browser tab                 # 列出所有 Tab
agent-browser tab new [url]       # 新建 Tab
agent-browser tab 2               # 切换到 Tab 2
agent-browser tab close           # 关闭当前 Tab
agent-browser window new          # 新建窗口
```

### 4.14 JavaScript 执行

```bash
agent-browser eval "document.title"
```

### 4.15 会话状态持久化

```bash
agent-browser state save auth.json    # 保存登录状态
agent-browser state load auth.json    # 加载登录状态
```

### 4.16 并行会话

```bash
agent-browser --session test1 open site-a.com
agent-browser --session test2 open site-b.com
agent-browser session list
```

---

## 五、完整使用示例

### 示例1：表单提交

```bash
agent-browser open https://example.com/form
agent-browser snapshot -i
# → textbox "Email" [ref=e1], textbox "Password" [ref=e2], button "Submit" [ref=e3]

agent-browser fill @e1 "user@example.com"
agent-browser fill @e2 "password123"
agent-browser click @e3
agent-browser wait --load networkidle
agent-browser snapshot -i  # 检查结果
```

### 示例2：保存并复用登录状态

```bash
# 第一次登录
agent-browser open https://app.example.com/login
agent-browser snapshot -i
agent-browser fill @e1 "username"
agent-browser fill @e2 "password"
agent-browser click @e3
agent-browser wait --url "/dashboard"
agent-browser state save auth.json

# 后续会话直接跳过登录
agent-browser state load auth.json
agent-browser open https://app.example.com/dashboard
```

---

## 六、调试技巧

```bash
agent-browser open example.com --headed   # 显示浏览器窗口（可视化调试）
agent-browser console                     # 查看控制台日志
agent-browser errors                      # 查看页面错误
agent-browser highlight @e1               # 高亮元素
agent-browser trace start                 # 开始录制 trace
agent-browser trace stop trace.zip        # 保存 trace
agent-browser --cdp 9222 snapshot         # 通过 CDP 连接
```

---

## 七、与选品工具的集成想象

> [!example] 竞品监控自动化
> ```bash
> # 自动抓取 Shopee 竞品数据
> agent-browser open "https://shopee.sg/search?keyword=..."
> agent-browser snapshot -i
> agent-browser scroll down 3000
> agent-browser get text .product-list  # 提取商品列表
> agent-browser screenshot shopee-$(date +%Y%m%d).png
> ```
> 无需维护 XPath 选择器，Agent 通过 snapshot 自适应页面结构变化。

---

## 八、常见问题

| 问题 | 解法 |
|------|------|
| 元素找不到 | 重新 `snapshot` 获取最新 ref |
| 页面未加载完 | 在导航后加 `wait --load networkidle` |
| Linux ARM64 找不到命令 | 使用 bin 文件夹的完整路径 |
| 调试困难 | 加 `--headed` 显示浏览器窗口 |

#agentBrowser #浏览器自动化 #TheSethRose #clawhub #Playwright
