---
title: OpenClaw 接入小米摄像头方案
tags:
  - OpenClaw
  - IoT
  - 小米
  - go2rtc
date: 2026-03-23
updated: 2026-03-25
status: 可行性分析完成
---

# OpenClaw + 小米摄像头接入方案

相关：[[IoT设备市场调研Skill开发计划]]

> [!tip] 核心思路
> **不要**直接对接米家 API（限制多、不成熟）。
> **曲线救国**：go2rtc 作为桥梁，将小米摄像头转成标准 RTSP 流，再接入 OpenClaw。

---

## 可行性分析（2026-03-25）

### 方案 A：Home Assistant + go2rtc ✅ 推荐

| 维度 | 结论 |
|------|------|
| **技术可行性** | ✅ 高——go2rtc 内置 `xiaomi` 协议模块，原生支持米家摄像头，含双向音频 |
| **接入复杂度** | 中——需部署 go2rtc + HA 两个服务，但均有 Docker 镜像 |
| **OpenClaw 集成** | ✅ HA 提供标准 REST API：`GET /api/camera_proxy/{entity_id}` 直接返回截图 |
| **许可证** | ✅ Apache 2.0 / MIT，可商用 |
| **社区成熟度** | ✅ HA 2023+ 已将 go2rtc 内置为 WebRTC 后端，文档完善 |
| **主要风险** | 小米摄像头型号兼容性需逐款测试；米家账号授权偶有失效 |

**数据流：**
```
小米摄像头
  ↓ xiaomi 协议（米家账号授权）
go2rtc（Docker，1984端口）
  ↓ RTSP rtsp://localhost:1984/<摄像头名>
Home Assistant（Docker，8123端口）
  ↓ REST API /api/camera_proxy/camera.<名称>
OpenClaw Skill（HTTP GET → base64图像）
  ↓
多模态大模型（视觉分析）→ 执行动作
```

---

### 方案 B：xiaomi-miloco + go2rtc ⚠️ 有条件可用

| 维度 | 结论 |
|------|------|
| **技术可行性** | ✅ 可行——miloco 直连米家摄像头，go2rtc 独立提供 RTSP 流 |
| **项目状态** | 活跃（2025-11 开源，v0.1.2，2.5k stars，173 forks） |
| **核心能力** | miloco 本身是小米官方 LLM+IoT 框架，自然语言控制设备；视频理解在端侧运行，保护隐私 |
| **⚠️ 许可证限制** | **非商业用途专用**：未经小米书面授权，不得用于开发应用程序或网络服务 |
| **与 OpenClaw 的关系** | miloco 定位是"完整的 LLM 控制框架"，与 OpenClaw 职能重叠；不适合作为纯数据源使用 |
| **go2rtc 的角色** | go2rtc 可**独立**于 miloco 使用，直接接小米摄像头，无需 miloco |

> [!warning] 许可证风险
> **xiaomi-miloco 不可用于商业产品**（含 OpenClaw 如果对外销售/SaaS化）。
> 如果 OpenClaw 是商业项目，方案 B 的 miloco 部分需要规避，仅保留 go2rtc 部分即可。
> go2rtc 本身是 MIT 许可，可商用。

---

### 两方案对比总结

| 对比项 | 方案 A（HA + go2rtc） | 方案 B（miloco + go2rtc） |
|--------|----------------------|--------------------------|
| 适用场景 | OpenClaw 作为 IoT 智能层 | 小米官方 LLM 框架扩展 |
| 商用许可 | ✅ 无限制 | ⚠️ miloco 非商用 |
| 部署复杂度 | 中（两个 Docker 容器） | 中（miloco 环境 + go2rtc） |
| API 标准化 | ✅ HA REST API 成熟 | ❌ miloco API 文档不完整 |
| 扩展性 | ✅ 支持数百种品牌设备 | ❌ 绑定小米生态 |
| **推荐指数** | ⭐⭐⭐⭐⭐ | ⭐⭐（受限场景） |

**结论：选方案 A。** go2rtc 自带小米协议，HA 提供成熟 REST API，OpenClaw 可直接对接，无许可证风险，且未来可扩展接入其他品牌摄像头。

---

## 方案架构（最终）

```
小米摄像头
    ↓ （米家账号授权，xiaomi 协议）
  go2rtc          ← 核心桥梁，Docker 部署
    ↓ （RTSP 标准流）
    ├── 方案A（推荐）：Home Assistant → OpenClaw Skill → 多模态大模型
    └── 方案B（备用）：OpenClaw Skill 直接拉 RTSP（适合轻量场景）
```

---

## 实现步骤

### 第一步：部署 go2rtc

```bash
docker run -d \
  --name go2rtc \
  -p 1984:1984 \
  -v ./go2rtc.yaml:/config/go2rtc.yaml \
  alexxit/go2rtc
```

`go2rtc.yaml` 配置（小米摄像头）：

```yaml
streams:
  living_room:
    - xiaomi://user:pass@<摄像头IP>?did=<设备ID>&model=<型号>
```

> go2rtc 内置 `xiaomi` 模块，支持米家生态所有摄像头，含双向音频。

### 第二步：获取 RTSP 流地址

go2rtc 启动后，为每个摄像头生成标准 RTSP 地址：

```
rtsp://localhost:1984/living_room
```

Web 预览界面：`http://localhost:1984/`

### 第三步：部署 Home Assistant（方案 A）

```bash
docker run -d \
  --name homeassistant \
  -p 8123:8123 \
  -v ./ha_config:/config \
  ghcr.io/home-assistant/home-assistant:stable
```

在 HA `configuration.yaml` 中添加摄像头：

```yaml
camera:
  - platform: generic
    name: "客厅摄像头"
    still_image_url: "http://go2rtc_host:1984/api/frame.jpeg?src=living_room"
    stream_source: "rtsp://go2rtc_host:1984/living_room"
```

### 第四步：OpenClaw Skill 调用 HA API

```python
import requests, base64

HA_URL = "http://homeassistant:8123"
HA_TOKEN = "<长期访问令牌>"

def get_camera_snapshot(entity_id="camera.客厅摄像头"):
    """获取摄像头截图，返回 base64 编码图像"""
    resp = requests.get(
        f"{HA_URL}/api/camera_proxy/{entity_id}",
        headers={"Authorization": f"Bearer {HA_TOKEN}"},
        timeout=10
    )
    resp.raise_for_status()
    return base64.b64encode(resp.content).decode()

# 调用多模态模型分析
image_b64 = get_camera_snapshot()
# → 传入 Claude / GPT-4V 等多模态模型
```

---

## 进阶玩法

| 场景 | 实现方式 | 触发条件 |
|------|---------|---------|
| 入侵告警 | go2rtc 检测到人物 → OpenClaw → 飞书/微信推送照片 | 画面出现人物 |
| 家庭日记 | 定时调用摄像头截图 → 多模态模型分析 → 写入 Obsidian | 每5分钟 |
| 复杂联动 | 摄像头识别场景 → OpenClaw 控制小米音箱/灯具 | 自定义规则 |

---

## IoT 在此方案中的作用

| 层级 | 组件 | 作用 |
|------|------|------|
| **感知层** | 小米摄像头 | 采集物理世界视觉信息 |
| **网关层** | go2rtc | 打破生态壁垒，标准化数据格式（原生支持 xiaomi 协议） |
| **平台层** | Home Assistant（可选） | 设备管理与 REST API 中转 |
| **智能层** | OpenClaw + 大模型 | 理解画面、决策、执行动作 |

---

## 待办

- [ ] Docker 环境确认（friday WSL2 已有 Docker？）
- [ ] 获取小米摄像头型号，查 go2rtc issues 确认兼容性
- [ ] 测试 `xiaomi://` 协议连接（需要米家账号 + 设备 did）
- [ ] 编写 OpenClaw Skill 调用 HA REST API
- [ ] 与 [[IoT设备市场调研Skill开发计划]] 中的 Skill 联动
- [ ] 评估是否需要 HA，或直接 go2rtc → OpenClaw（轻量方案）
