---
title: Home Assistant REST API 参考
tags:
  - HomeAssistant
  - API
  - IoT
  - OpenClaw
date: 2026-03-25
source: https://developers.home-assistant.io/docs/api/rest/
---

# Home Assistant REST API 参考

> 本文整理 OpenClaw 接入所需的 HA REST API 接口，重点覆盖摄像头截图、流媒体、状态查询和认证。
> 关联：[[OpenClaw接入小米摄像头方案]] | [[C700配置参考]]

---

## 1. 认证方式

### Long-Lived Access Token（推荐）

| 项目 | 说明 |
|------|------|
| **创建位置** | HA Web UI → 左下角用户头像 → 个人资料 → 长期访问令牌 → 创建令牌 |
| **有效期** | 永久（不会过期，除非手动撤销） |
| **使用方式** | HTTP 请求头：`Authorization: Bearer <TOKEN>` |
| **安全建议** | 每个集成单独创建令牌，便于按需撤销；不要将令牌提交到 git |

**请求示例：**
```bash
curl -s -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8123/api/
# 返回：{"message": "API running."}
```

### 其他认证方式

| 方式 | 说明 |
|------|------|
| Refresh Token | 90 天不使用会过期，适合交互式登录场景 |
| 多因素认证（MFA） | 可在用户配置中启用，增加安全层 |

---

## 2. 摄像头相关接口

### 2.1 摄像头截图（核心接口）

```
GET /api/camera_proxy/{entity_id}
```

| 项目 | 说明 |
|------|------|
| **用途** | 获取摄像头当前画面截图（JPEG 二进制数据） |
| **entity_id** | 摄像头实体 ID，例如 `camera.living_room` |
| **可选参数** | `?time=<timestamp>` — 获取指定时间戳的截图 |
| **返回类型** | `image/jpeg`（二进制图像数据） |
| **认证** | 必须，Bearer Token |

**请求示例：**
```bash
curl -s -o snapshot.jpg \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8123/api/camera_proxy/camera.living_room
```

**Python 示例（OpenClaw Skill 用）：**
```python
import requests, base64

def get_camera_snapshot(entity_id: str, ha_url: str, token: str) -> str:
    """获取摄像头截图，返回 base64 编码"""
    resp = requests.get(
        f"{ha_url}/api/camera_proxy/{entity_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10
    )
    resp.raise_for_status()
    return base64.b64encode(resp.content).decode()
```

### 2.2 摄像头服务调用

通过 `POST /api/services/camera/<action>` 调用摄像头服务：

| 服务 | 说明 | 请求体示例 |
|------|------|-----------|
| `camera.snapshot` | 截图保存到文件 | `{"entity_id": "camera.xxx", "filename": "/config/snapshot.jpg"}` |
| `camera.record` | 录制视频片段 | `{"entity_id": "camera.xxx", "filename": "/config/clip.mp4", "duration": 10}` |
| `camera.turn_on` | 开启摄像头 | `{"entity_id": "camera.xxx"}` |
| `camera.turn_off` | 关闭摄像头 | `{"entity_id": "camera.xxx"}` |
| `camera.play_stream` | 推流到媒体播放器 | `{"entity_id": "camera.xxx", "media_player": "media_player.xxx"}` |
| `camera.enable_motion_detection` | 启用移动检测 | `{"entity_id": "camera.xxx"}` |
| `camera.disable_motion_detection` | 关闭移动检测 | `{"entity_id": "camera.xxx"}` |

> [!warning] snapshot 服务需要白名单
> 使用 `camera.snapshot` 保存文件时，目标路径必须在 `configuration.yaml` 的 `allowlist_external_dirs` 中声明：
> ```yaml
> homeassistant:
>   allowlist_external_dirs:
>     - /config/snapshots
> ```

**服务调用示例：**
```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "camera.living_room", "filename": "/config/snap.jpg"}' \
  http://localhost:8123/api/services/camera/snapshot
```

---

## 3. 状态查询接口

### 3.1 查询所有实体状态

```
GET /api/states
```

返回所有实体的当前状态数组。可用于发现摄像头实体 ID。

### 3.2 查询指定实体状态

```
GET /api/states/{entity_id}
```

| 项目 | 说明 |
|------|------|
| **返回字段** | `entity_id`, `state`, `attributes`, `last_changed`, `last_updated` |
| **摄像头状态值** | `idle`（空闲）/ `streaming`（推流中）/ `recording`（录制中） |

**返回示例：**
```json
{
  "entity_id": "camera.living_room",
  "state": "idle",
  "attributes": {
    "access_token": "...",
    "friendly_name": "客厅摄像头",
    "frontend_stream_type": "hls",
    "entity_picture": "/api/camera_proxy/camera.living_room?token=..."
  },
  "last_changed": "2026-03-25T10:30:00+08:00",
  "last_updated": "2026-03-25T10:30:00+08:00"
}
```

---

## 4. 其他常用接口

### 4.1 API 健康检查

```
GET /api/
```
返回：`{"message": "API running."}`

### 4.2 获取配置信息

```
GET /api/config
```
返回 HA 实例配置（组件列表、位置、时区、版本等）。

### 4.3 获取已加载组件

```
GET /api/components
```
返回已加载组件名称数组，可用于确认 `camera` 和 `generic` 集成是否已加载。

### 4.4 获取可用服务

```
GET /api/services
```
返回按 domain 分组的所有可用服务，可用于确认摄像头服务是否可用。

### 4.5 状态历史记录

```
GET /api/history/period/{timestamp}?filter_entity_id={entity_id}
```

| 参数 | 说明 |
|------|------|
| `timestamp` | ISO 格式起始时间（可选，默认过去 1 天） |
| `filter_entity_id` | 按实体 ID 过滤（必填） |
| `end_time` | ISO 格式结束时间 |
| `minimal_response` | 仅返回最小数据集 |

### 4.6 触发事件

```
POST /api/events/{event_type}
```
可用于触发自定义事件，OpenClaw 可用此接口通知 HA 执行自动化。

### 4.7 调用任意服务

```
POST /api/services/{domain}/{service}
```
通用服务调用接口，请求体为 `service_data` JSON。

### 4.8 配置检查

```
POST /api/config/core/check_config
```
验证 `configuration.yaml` 是否有效，返回 `{"result": "valid"}` 或错误信息。

---

## 5. Generic Camera 配置语法

在 HA 中通过 UI 或 `configuration.yaml` 添加摄像头：

### UI 方式（推荐）

设置 → 设备与服务 → 添加集成 → 搜索 "Generic Camera" → 填写参数

### YAML 方式

```yaml
# configuration.yaml
camera:
  - platform: generic
    name: "客厅摄像头"
    still_image_url: "http://go2rtc:1984/api/frame.jpeg?src=living_room"
    stream_source: "rtsp://go2rtc:1984/living_room"
    verify_ssl: false
```

### 完整配置参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `still_image_url` | string | 至少填一个 | — | 静态截图 URL（支持模板） |
| `stream_source` | string | 至少填一个 | — | 实时流 URL，如 `rtsp://...` |
| `name` | string | 否 | Generic Camera | 摄像头名称 |
| `username` | string | 否 | — | 认证用户名（同时用于截图和流） |
| `password` | string | 否 | — | 认证密码 |
| `authentication` | string | 否 | basic | `basic` 或 `digest` |
| `verify_ssl` | bool | 否 | true | 是否验证 SSL 证书 |
| `frame_rate` | float | 否 | — | 流帧率限制 |
| `rtsp_transport_protocol` | string | 否 | — | `tcp` / `udp` / `udp_multicast` / `http` |
| `limit_refetch_to_url_change` | bool | 否 | false | 仅在 URL 变化时重新获取 |
| `use_wallclock_as_timestamps` | bool | 否 | false | 用系统时钟重写时间戳（高级） |

### go2rtc + HA 推荐配置

```yaml
# configuration.yaml — 接入 go2rtc 转发的小米摄像头
camera:
  - platform: generic
    name: "客厅摄像头"
    still_image_url: "http://go2rtc:1984/api/frame.jpeg?src=c700"
    stream_source: "rtsp://go2rtc:1984/c700"
    verify_ssl: false
```

---

## 6. HTTP 状态码

| 状态码 | 含义 |
|--------|------|
| 200 | 成功 |
| 201 | 新实体创建成功 |
| 400 | 请求格式错误 |
| 401 | 未认证（Token 无效或缺失） |
| 404 | 实体或端点不存在 |
| 405 | HTTP 方法不允许 |

---

## 7. OpenClaw 集成要点

> [!note] OpenClaw Skill 只需关注 3 个接口

| 接口 | 用途 | 优先级 |
|------|------|--------|
| `GET /api/camera_proxy/{entity_id}` | 获取截图送入多模态模型 | 核心 |
| `GET /api/states/{entity_id}` | 检查摄像头状态 | 辅助 |
| `POST /api/services/camera/snapshot` | 保存截图到 HA 本地文件系统 | 可选 |

**最简集成流程：**
1. 在 HA 用户配置中创建 Long-Lived Access Token
2. 用 `GET /api/states` 找到摄像头 entity_id
3. 用 `GET /api/camera_proxy/{entity_id}` 获取截图
4. Base64 编码后传入多模态大模型分析

---

*更新时间：2026-03-25 | 关联：[[OpenClaw接入小米摄像头方案]] | [[C700配置参考]]*
