---
title: bilibili总结 Skill 开发复盘
tags: [复盘, skill开发, bilibili, python]
created: 2026-03-25
type: 项目复盘
---

# bilibili总结 Skill 开发复盘

## 项目概述

从零开发一套 B 站视频字幕获取 + Claude 总结 + Obsidian 笔记输出的完整 Skill，经历了方案调研、技术选型、多次调试，最终形成可被其他 Agent 复用的标准化工具。

---

## 一、遇到的错误与解决方案

### 1. bilibili_api QrCodeLogin API 变更

> [!bug] 错误
> `AttributeError: 'QrCodeLogin' object has no attribute 'get_qrcode'`

**原因：** clawhub 参考的旧版 API 已废弃，新版方法名变更。

**解决：** 用 `inspect` 动态查看库的实际方法列表，重新映射：
```
旧 API → 新 API
get_qrcode()      → generate_qrcode()
get_qrcode_url()  → get_qrcode_picture().to_file()
SCANNED 枚举      → SCAN 枚举
```

---

### 2. Picture 对象无 pil_img 属性

> [!bug] 错误
> `AttributeError: 'Picture' object has no attribute 'pil_img'`

**原因：** bilibili_api 的 Picture 类没有暴露 PIL 对象，只提供 `to_file()` 方法。

**解决：** 改用 `pic.to_file(str(qr_path))` 直接保存。

---

### 3. aiohttp 未安装

> [!bug] 错误
> `ModuleNotFoundError: No module named 'aiohttp'`

**原因：** bilibili_api 下载字幕 JSON 用了 aiohttp，但未列为依赖。

**解决：** `pip install aiohttp`，并加入 SKILL.md 的依赖说明。

---

### 4. Bilibili 412 反爬封禁

> [!bug] 错误
> yt-dlp 下载 B 站音频时 HTTP 412，加 User-Agent 无效

**原因：** B 站强制要求登录态 Cookie，无 Cookie 的请求直接被拦截。

**解决：** 放弃 yt-dlp 方案，改用 `bilibili_api` 库直接调用官方 AI 字幕 API，完全绕过音频下载需求。

---

### 5. Chrome Cookie 无法用 Python 读取

> [!bug] 问题
> browser_cookie3 / rookiepy 在现代 Chrome 上全部返回空或报错

**原因：** Chrome 127（2024年7月）引入 **App-Bound Encryption**，将加密密钥绑定到 Chrome 二进制本身，外部 Python 进程无法解密。

**解决：** 改用两种替代方案：
- **CDP 方案**：Chrome 启动加 `--remote-debugging-port=9222`，通过 WebSocket 拿明文 Cookie
- **yt-dlp 方案**：关闭 Chrome 后用 yt-dlp 内置解密逻辑读取
- **当前采用**：bilibili_api 扫码登录，完全绕过 Cookie 导出问题

---

### 6. QR 码轮询进程管理问题

> [!bug] 问题
> 每次运行脚本都生成新二维码，用户扫旧码后轮询新对象，状态永远是 SCAN

**原因：** `QrCodeLogin` 对象与 QR 码是一对一绑定的，重启脚本会产生新的 `qrcode_key`，旧扫码状态无法被新对象感知。

**解决：** 将生成二维码和轮询放在同一个进程（`login.py`），脚本启动后持续运行直到 `LOGIN_SUCCESS` 或 `TIMEOUT`，不中途重启。

---

### 7. Windows GBK 编码崩溃

> [!bug] 错误
> `UnicodeEncodeError: 'gbk' codec can't encode character`（Telugu 字符）

**原因：** Windows 终端默认 GBK 编码，无法打印 Telugu、韩文等字符。

**解决：** 所有脚本运行加 `PYTHONIOENCODING=utf-8` 前缀。

---

### 8. Whisper 找不到 ffmpeg

> [!bug] 错误
> `FileNotFoundError: ffmpeg not found`

**原因：** ffmpeg 通过 winget 安装后路径不在 bash 的 `$PATH` 里。

**解决：** 在脚本中 `setup_ffmpeg()` 手动将已知路径注入 `os.environ["PATH"]`：
```python
FFMPEG_DIRS = [r"C:\Program Files\ShadowBot\shadowbot-5.32.44", ...]
```

---

### 9. clawhub CDN 403 无法获取原始文件

> [!bug] 问题
> clawhub.ai 社区 skill 文件通过 CDN 分发，未授权访问返回 403

**原因：** clawhub 是 SPA + Convex 后端，skill 文件需要身份验证才能下载，`chub get` 在 Windows 上还有路径分隔符 bug（`lastIndexOf('/')` 返回 -1）。

**解决：** 根据 clawhub 页面嵌入的元数据（SHA256、文件列表）推断功能，用 `bilibili_api` 完全重新实现，质量更高。

---

## 二、潜在隐藏漏洞

> [!warning] 安全风险

### 1. Cookie 明文存储
`.env` 文件以明文存储 `BILIBILI_SESSDATA` 等敏感 Cookie。若仓库被 push 到 GitHub（`.gitignore` 未正确配置），会造成账号泄露。

**当前状态：** `.gitignore` 已包含 `.env`，但需持续注意。

### 2. BV 号路径穿越
`bili_temp/<BV号>/` 目录由用户输入构成，若传入 `../../../Windows/System32` 这样的恶意输入，理论上可以向任意路径写文件。

**当前风险等级：** 低（仅本地工具，无网络暴露），但应加输入校验：
```python
if not re.match(r'^BV[a-zA-Z0-9]+$', bvid):
    raise ValueError("非法 BV 号")
```

### 3. 字幕 URL 未校验
`target["subtitle_url"]` 直接拼接为 HTTP 请求，若 Bilibili API 返回恶意重定向 URL，存在 SSRF 风险（极低概率，仅理论风险）。

---

## 三、已知 Bug / 可能出现的问题

> [!note] 待修复

| Bug | 触发条件 | 严重程度 |
|-----|---------|---------|
| Cookie 失效无提示 | 距上次登录超过 30 天 | 中 |
| 无字幕视频静默退出 | UP 主未开启 AI 字幕 | 低（已有提示，但不够显眼） |
| 长字幕分块边界截断句子 | 字幕 >3000 字符时分块 | 低（总结时感知不明显） |
| login.py 超时后不清理 QR 图片 | 等待超 3 分钟 | 极低 |
| 多 P 视频只取第一个 cid | 合集/多 P 视频 | 中（只处理第一个分P） |
| 视频标题含特殊字符导致文件名异常 | 标题含 `/\:*?"<>|` | 低（已有 `re.sub` 过滤） |

---

## 四、未来改进方向

### 短期（可直接实现）

- [ ] **多 P 视频支持**：遍历所有 cid，合并或分别生成笔记
- [ ] **B 站课程支持**：适配 SS/EP 号（cheese_downloader 逻辑）
- [ ] **BV 号输入校验**：防止路径穿越
- [ ] **Cookie 有效期检测**：登录前先验证，失效自动触发重新登录
- [ ] **login.py 超时后清理 QR 图片**

### 中期

- [ ] **批量处理**：接受多个 BV 号，批量生成笔记
- [ ] **增量更新**：检测笔记已存在时跳过，或更新总结
- [ ] **与飞书集成**：字幕/总结自动同步到飞书多维表格
- [ ] **YouTube 字幕对接**：YouTube 有官方字幕 API（`yt-dlp --write-sub`），同样无需 Whisper

### 长期

- [ ] **无字幕视频降级方案**：检测到无字幕自动切换 Whisper 转录，整合到同一 Skill
- [ ] **向量化存储**：将字幕 chunks 存入本地向量数据库，支持语义检索
- [ ] **定时巡检**：订阅 UP 主，有新视频自动触发总结并推送到飞书

---

## 五、最终产出物

```
.claude/skills/bilibili总结/     ← Claude 读取版本
D:\Download\agent-master\
├── bilibili总结/                ← 用户可见副本
│   ├── SKILL.md                 ← 完整工作流 + 提示词模板 + Agent 复用指南
│   └── scripts/
│       ├── login.py             ← 扫码登录 + 内置轮询（输出 QR_CODE_PATH）
│       └── bilibili_subtitle.py ← 字幕获取 + RESULT_JSON 输出
├── .env                         ← BILIBILI_SESSDATA 等 Cookie（不提交 git）
└── Daily/
    └── 2026-03-25-openclaw龙虾跨境电商实战.md  ← 首次测试输出的笔记
```

**技术栈：** Python 3.14 · bilibili-api-python · aiohttp · Claude Code

**核心设计原则：**
- 脚本只负责数据获取，AI 总结由 Claude 直接完成（无需 API Key）
- 登录状态持久化到 `.env`，一次登录长期有效
- 所有输出格式化为结构化信号（`QR_CODE_PATH:` / `RESULT_JSON:`），便于 Agent 解析复用
