---
title: OpenClaw × 摄像头接入 · 项目进度
tags:
  - OpenClaw
  - IoT
  - 项目进度
  - 小米
  - go2rtc
date: 2026-03-25
updated: 2026-03-26
status: Phase 2 完成 ✅（go2rtc 原生 Windows 运行，摄像头流已通）
---

# OpenClaw × 摄像头接入 · 项目逻辑链 + 进度跟进

相关：[[OpenClaw接入小米摄像头方案]] | [[go2rtc已知问题清单]] | [[IoT设备市场调研Skill开发计划]]
参考：[[环境检查报告]] | [[HA-API参考]] | [[C700配置参考]]

---

## 项目逻辑链

```
① 硬件准备
   小米C700（chuangmi.camera.81ac1）
   + 本机 Windows 11（friday）WSL2 Ubuntu 24.04 ✅
        ↓
② 流媒体桥接层
   go2rtc v1.9.13（Windows 原生 .exe）✅ 运行中
   小米摄像头 →[xiaomi:// cs2+udp]→ RTSP 标准流
        ↓
③ 设备管理层
   Home Assistant（Docker in WSL2，8123端口）⬅ 待部署
   提供 REST API：GET /api/camera_proxy/{entity_id}
        ↓
④ 智能感知层（Skills 已就绪 ✅）
   camera_snapshot.py → 截图（base64）
   person_detection.py → 人员检测（claude-opus-4-6）
   scene_analysis.py → 场景分析
   intrusion_alert.py → 告警推送（飞书）
        ↓
⑤ 输出动作层
   飞书推送 / Obsidian 写入 / 米家联动
```

---

## 阶段进度

### Phase 0 · 方案研究（✅ 已完成）

- [x] 确认方案选型（方案A：HA + go2rtc）
- [x] 确认 C700 型号兼容性（go2rtc #1982 已列入支持，协议 cs2+udp）
- [x] 整理 go2rtc 已知问题 → [[go2rtc已知问题清单]]
- [x] 可行性分析完成 → [[OpenClaw接入小米摄像头方案]]

---

### Phase 1 · 环境准备（✅ 已完成）

- [x] **WSL2 环境确认**：Ubuntu 24.04.1 LTS，16核 / 7.7GB内存 / 942GB磁盘 ✅
- [x] **Docker Desktop 已安装**（含中文化 app.asar）✅
- [x] **go2rtc 配置文件已就绪** → `configs/go2rtc.yaml`（含实际账号/DID/passToken）
- [x] **go2rtc.exe Windows 原生二进制** → `OpenClaw+IoT/go2rtc.exe`（v1.9.13）

---

### Phase 2 · go2rtc 部署（✅ 已完成 — 流已通）

> [!success] 摄像头流已成功连通！
> 2026-03-26 首帧截图成功（474KB JPEG），go2rtc Windows 原生运行

**关键突破记录：**
- 认证方式：go2rtc YAML 需填 `passToken`（非 `serviceToken`）—— 来自 mijiaAPI `auth.json`
- 部署方式：必须用 Windows 原生 `.exe`（Docker/WSL2 均因 UDP NAT 导致 CS2 punch 失败）
- passToken 位于：`~/.config/mijia-api/auth.json` → `passToken` 字段（V1: 开头）

**当前运行方式：**
```powershell
# 启动 go2rtc（需保持运行）
Start-Process "D:\Download\agent-master\OpenClaw+IoT\go2rtc.exe" `
  -ArgumentList "-config D:\Download\agent-master\OpenClaw+IoT\configs\go2rtc.yaml"
```

- [x] go2rtc 配置完成（账号 2167879033，C700 DID: 1190512086，IP: 192.168.2.2）
- [x] passToken 注入 go2rtc.yaml ✅（米家 QR 扫码登录获取）
- [x] **流媒体验证通过**：首帧截图 474KB，延迟 ~4s ✅
- [x] API 可用：`http://localhost:1984/api/frame.jpeg?src=xiaomi_cam`
- [x] RTSP 可用：`rtsp://localhost:8554/xiaomi_cam`
- [ ] 部署 HA（可选，Skills 可直连 go2rtc）
- [ ] HA 实体配置 + 长期令牌（Phase 3 联调需要）

---

### Phase 3 · OpenClaw Skills 接入（✅ 代码已就绪，待环境联调）

- [x] `camera_snapshot.py` — HA REST API 截图，返回 base64 + 时间戳
- [x] `person_detection.py` — 截图 → claude-opus-4-6 多模态 → {has_person, count, description}
- [x] `scene_analysis.py` — 通用场景分析 → {scene, objects, anomaly, summary}
- [x] `intrusion_alert.py` — 定时检测 + 飞书 Webhook 推送，含 cooldown 静默期
- [x] `skill_manifest.json` — 所有 Skill 的输入输出格式定义
- [x] `skills/README.md` — 完整使用说明
- [ ] 联调测试（依赖 Phase 2 完成）
  ```bash
  # 设置环境变量后测试：
  export HA_URL=http://localhost:8123
  export HA_TOKEN=<从HA复制>
  export ANTHROPIC_API_KEY=<key>
  python skills/camera_snapshot.py
  python skills/person_detection.py
  ```

---

### Phase 4 · 进阶联动（⏳ 规划中）

- [ ] 入侵告警自动化（Cron 定时任务，每分钟检测）
- [ ] 家庭日记 Skill（每小时截图 → 总结 → 写 Obsidian Daily Note）
- [ ] 访客识别（人脸库构建）
- [ ] PTZ 云台控制（等待 go2rtc #2162 ONVIF 功能完善）
- [ ] 双向对讲（等待 #2175 音频噪声 bug 修复）

---

## 交付物清单

| 文件 | 类型 | 状态 | 说明 |
|------|------|------|------|
| `configs/go2rtc.yaml` | 配置 | ✅ 就绪 | C700 xiaomi:// cs2+udp，含占位符 |
| `configs/docker-compose.yml` | 配置 | ✅ 就绪 | go2rtc v1.9.13 + HA，network_mode: host |
| `configs/部署说明.md` | 文档 | ✅ 就绪 | 6步部署指南，含米账号验证说明 |
| `skills/camera_snapshot.py` | 代码 | ✅ 就绪 | HA截图，完整错误处理 |
| `skills/person_detection.py` | 代码 | ✅ 就绪 | 多模态人员检测 |
| `skills/scene_analysis.py` | 代码 | ✅ 就绪 | 通用场景分析 |
| `skills/intrusion_alert.py` | 代码 | ✅ 就绪 | 定时检测+飞书推送 |
| `skills/skill_manifest.json` | 元数据 | ✅ 就绪 | Skill 接口定义 |
| `skills/README.md` | 文档 | ✅ 就绪 | 使用说明+环境变量 |
| `环境检查报告.md` | 报告 | ✅ 就绪 | WSL2正常，Docker待安装 |
| `HA-API参考.md` | 文档 | ✅ 就绪 | HA REST API 接口速查 |
| `C700配置参考.md` | 文档 | ✅ 就绪 | C700配置+兼容表+故障排查 |

---

## 风险与注意事项

> [!warning] 当前主要风险
> 1. **Docker 未安装**：Phase 1 阻塞项，需人工执行安装命令
> 2. **go2rtc v1.9.14 CS2 timeout（#2048）**：已锁定 v1.9.13 规避
> 3. **米账号验证码**：首次授权需人工在浏览器/手机完成，go2rtc 无法处理滑块
> 4. **双向音频噪声（#2175）**：暂不启用双向对讲功能

> [!tip] WSL2 网络
> go2rtc 和 HA 均在 WSL2 Docker 内，端口自动映射到 Windows localhost。
> OpenClaw 运行在 Windows 本机，直接访问 `localhost:1984` / `localhost:8123`。

---

## 下一步行动（优先级排序）

1. **马上可做**：安装 Docker（5分钟）
   ```bash
   curl -fsSL https://get.docker.com | sh && sudo usermod -aG docker $USER
   ```
2. **填写配置**：在 `configs/go2rtc.yaml` 填入真实的米账号和C700设备DID
3. **启动服务**：`docker compose up -d`
4. **联调测试**：验证截图 → 人员检测完整链路

---

*创建：2026-03-25 | 最后更新：2026-03-25（agent-team openclaw-camera 汇总）*
*团队成员：team-lead / devops-engineer / researcher / skill-developer*
