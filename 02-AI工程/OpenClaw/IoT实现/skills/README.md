# OpenClaw IoT Skills

通过 Home Assistant REST API 接入摄像头，结合多模态大模型实现智能视觉分析。

## 架构

```
摄像头 → go2rtc → Home Assistant → OpenClaw Skills → 多模态大模型
```

## 环境变量

| 变量 | 说明 | 示例 |
|------|------|------|
| `HA_URL` | Home Assistant 地址 | `http://192.168.1.100:8123` |
| `HA_TOKEN` | HA 长期访问令牌 | `eyJhbG...` |
| `ANTHROPIC_API_KEY` | Anthropic API 密钥（person_detection / scene_analysis 使用） | `sk-ant-...` |
| `FEISHU_WEBHOOK_URL` | 飞书机器人 Webhook（intrusion_alert 使用） | `https://open.feishu.cn/...` |

## Skills 列表

### 1. camera_snapshot

**状态：** 已完成

获取摄像头截图，返回 base64 编码图像。

```python
from camera_snapshot import take_snapshot, take_snapshots

# 单个摄像头
result = take_snapshot("camera.xiaomi_c700")
# → {"success": True, "image_base64": "...", "timestamp": "...", "entity_id": "..."}

# 多个摄像头（单个失败不影响其他）
results = take_snapshots(["camera.xiaomi_c700", "camera.door"])
```

**CLI 调试：**
```bash
export HA_URL=http://192.168.1.100:8123
export HA_TOKEN=your_token_here
python camera_snapshot.py camera.xiaomi_c700
```

**错误处理：**
- `AuthenticationError` — 令牌无效或未设置
- `CameraUnavailableError` — 摄像头离线或 entity_id 不存在
- `TimeoutError` — 请求超时
- `SnapshotError` — 其他 HTTP 错误

### 2. person_detection

**状态：** 已完成

调用 camera_snapshot 获取图像 → 多模态 prompt（Claude claude-opus-4-6） → 返回人物检测结果。

```python
from person_detection import detect_person
result = detect_person("camera.xiaomi_c700")
# → {"has_person": True, "count": 2, "description": "两人在客厅沙发附近"}
```

### 3. scene_analysis

**状态：** 已完成

通用场景分析，识别场景类型、物体列表、是否存在异常。

```python
from scene_analysis import analyze_scene
result = analyze_scene("camera.xiaomi_c700")
# → {"scene": "客厅", "objects": ["沙发", "电视", "茶几"], "anomaly": False, "summary": "..."}
```

### 4. intrusion_alert

**状态：** 已完成

定时运行 person_detection，检测到人时通过飞书 Webhook 推送告警。支持告警静默期避免重复推送。

```python
from intrusion_alert import start_monitoring, check_and_alert

# 持续监控（每 30 秒检测，5 分钟静默期）
start_monitoring("camera.xiaomi_c700", interval=30, cooldown=300)

# 单次检测 + 告警
result = check_and_alert("camera.xiaomi_c700")
```

**CLI：**
```bash
# 持续监控
python intrusion_alert.py camera.xiaomi_c700 30

# 单次检测
python intrusion_alert.py camera.xiaomi_c700 --once
```

## 依赖安装

```bash
pip install requests anthropic
```
