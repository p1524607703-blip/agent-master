---
name: 摄像头监控
description: 接入小米C700摄像头，截图/人员检测/场景分析/入侵告警。当用户说"摄像头截图"、"看看摄像头"、"有没有人"、"场景分析"、"入侵检测"、"监控告警"时自动激活。
allowed-tools: Bash, Read, Write, Edit
---

# 摄像头监控 Skill

通过 **go2rtc**（本地运行）直接拉取小米C700实时画面，结合 MiniMax 视觉模型实现智能分析。

---

## 依赖声明

### ✅ 本地已就绪（无需安装）

| 软件 | 版本 | 路径 | 说明 |
|------|------|------|------|
| **go2rtc.exe** | v1.9.13 | `D:\Download\agent-master\OpenClaw+IoT\go2rtc.exe` | 摄像头流桥接，**必须保持运行** |
| **Python** | 3.14.2 | `D:\Program Files\Python\python.exe` | 运行环境 |
| `requests` | 2.32.5 | 已安装 | HTTP 请求 |
| `httpx` | 0.28.1 | 已安装 | 备用 HTTP 客户端 |

### ❌ 需要下载安装（首次使用前执行）

> 目前无需额外安装，所有依赖已就绪。

---

## 环境变量

| 变量 | 必填 | 说明 | 来源 |
|------|------|------|------|
| `MINIMAX_API_KEY` | ✅ 人员检测/场景分析 | MiniMax API 密钥 | `.env` 已配置 |
| `FEISHU_WEBHOOK_URL` | 仅告警功能 | 飞书机器人 Webhook | `.env` 可选配置 |
| `GO2RTC_URL` | 否 | go2rtc 地址（默认 localhost:1984） | 可选 |
| `STREAM_NAME` | 否 | 流名称（默认 xiaomi_cam） | 可选 |

---

## go2rtc 启动

**每次使用前确认 go2rtc 在运行：**

```bash
# 检查是否运行
curl -s http://localhost:1984/api/streams

# 如果未运行，双击启动
D:\Download\agent-master\OpenClaw+IoT\启动go2rtc.bat

# 或命令行启动
"D:\Download\agent-master\OpenClaw+IoT\go2rtc.exe" -config "D:\Download\agent-master\OpenClaw+IoT\configs\go2rtc.yaml"
```

---

## 使用方式

技能文件位于：`D:\Download\agent-master\.claude\skills\摄像头监控\`

```python
SKILLS_DIR = r"D:\Download\agent-master\.claude\skills\摄像头监控"
import sys; sys.path.insert(0, SKILLS_DIR)
```

### 1. 截图

```python
from camera_snapshot import take_snapshot

result = take_snapshot()
# → {"success": True, "image_base64": "...", "timestamp": "...", "size_bytes": 474250}
```

### 2. 人员检测

```python
from person_detection import detect_person

result = detect_person()
# → {"has_person": True, "count": 2, "description": "两人在客厅沙发区域"}
```

### 3. 场景分析

```python
from scene_analysis import analyze_scene

result = analyze_scene()
# → {"scene": "客厅", "objects": ["沙发","电视"], "anomaly": False, "summary": "..."}
```

### 4. 入侵告警

```python
from intrusion_alert import check_and_alert, start_monitoring

# 单次检测
result = check_and_alert()

# 持续监控（每30秒，5分钟静默期）
start_monitoring(interval=30, cooldown=300)
```

---

## Claude 执行步骤

当用户触发此 Skill 时：

1. **检查 go2rtc** — `curl -s http://localhost:1984/api/streams`，若无响应提示用户启动
2. **加载 .env** — 读取 `MINIMAX_API_KEY`（`D:\Download\agent-master\.env`）
3. **执行对应函数** — 运行相应 Python 脚本
4. **展示结果** — 截图显示 base64 预览，检测结果用中文汇报

---

## 故障排查

| 现象 | 原因 | 解决 |
|------|------|------|
| `Connection refused :1984` | go2rtc 未运行 | 双击 `启动go2rtc.bat` |
| `streams: 401 Unauthorized` | passToken 过期 | 重新扫码登录米家，更新 `configs/go2rtc.yaml` 中的 passToken |
| 截图全黑 / 0字节 | 摄像头离线或流未建立 | 确认C700在线，等待go2rtc重连（约5秒） |
| `MINIMAX_API_KEY 未设置` | .env 未加载 | 确认从 `.env` 加载环境变量 |
