---
title: go2rtc 小米摄像头已知问题清单
tags:
  - go2rtc
  - 小米
  - 问题追踪
  - IoT
date: 2026-03-25
source: https://github.com/AlexxIT/go2rtc/issues
---

# go2rtc × 小米摄像头 已知问题清单

> 数据采集自 [go2rtc GitHub Issues](https://github.com/AlexxIT/go2rtc/issues)，采集时间：2026-03-25
> 格式：标题 / 严重性 / 解决方案

---

## 🔴 严重（阻塞性问题）

### #2048 · CS2 协议 i/o timeout（v1.9.14 回归）
- **严重性**：🔴 严重
- **问题**：v1.9.14 版本的小米摄像头（cs2+udp 协议）出现 `i/o timeout`，v1.9.13 正常
- **影响机型**：CS2 系列（含部分 chuangmi 型号）
- **解决方案**：⚠️ 暂无官方 patch；临时方案：**降级至 v1.9.13**
- **Issue**：[#2048](https://github.com/AlexxIT/go2rtc/issues/2048)（Open）

---

### #2139 · chuangmi.camera.ipc017 EOF 错误
- **严重性**：🔴 严重
- **问题**：v1.9.14 版本连接 ipc017 型号持续返回 `EOF` 错误，无法建立流
- **解决方案**：❌ 官方标记 Not Planned（不支持此型号）
- **Issue**：[#2139](https://github.com/AlexxIT/go2rtc/issues/2139)（Closed/Not Planned）

---

## 🟠 中等（功能受限）

### #2175 · 双向音频输出噪声
- **严重性**：🟠 中等
- **问题**：小米摄像头双向对讲时，摄像头侧输出极大噪声（音频损坏）
- **解决方案**：⚠️ 暂无修复；可暂时关闭双向音频功能
- **Issue**：[#2175](https://github.com/AlexxIT/go2rtc/issues/2175)（Open，2026-03-24）

---

### #2158 / #2157 · 米账号登录设备列表为空
- **严重性**：🟠 中等
- **问题**：用米账号登录后，设备选择下拉框为空，无法选择摄像头
- **解决方案**：✅ **已修复**（v1.9.14，2026-03-16）；升级到最新版即可
- **Issue**：[#2158](https://github.com/AlexxIT/go2rtc/issues/2158)（Closed/Completed）

---

### #1985 · 米账号登录触发验证码无法通过
- **严重性**：🟠 中等
- **问题**：首次登录米账号时触发滑块验证码，go2rtc 无法处理
- **解决方案**：✅ **已修复**（v1.9.14）；先在浏览器手动登录米家完成验证，再用 go2rtc
- **Issue**：[#1985](https://github.com/AlexxIT/go2rtc/issues/1985)（Closed/Completed）

---

### #2113 · 小米 4K 摄像头无法连接
- **严重性**：🟠 中等
- **问题**：Xiaomi Smart Camera 4 4K 型号连接失败
- **解决方案**：✅ **已修复**（2026-02-25）
- **Issue**：[#2113](https://github.com/AlexxIT/go2rtc/issues/2113)（Closed/Completed）

---

## 🟡 低（功能请求 / 兼容性）

### #2171 · 旧款型号 chuangmi.camera.v3 不支持
- **严重性**：🟡 低（旧机型）
- **问题**：用户请求支持老款摄像头 v3
- **解决方案**：⏳ 待评估，暂无时间表
- **Issue**：[#2171](https://github.com/AlexxIT/go2rtc/issues/2171)（Open）

---

### #2162 · PTZ 云台控制未通过 ONVIF 暴露
- **严重性**：🟡 低（增强需求）
- **问题**：xiaomi:// 协议接入后，云台旋转功能无法通过 ONVIF 协议透传给第三方平台
- **解决方案**：⏳ 功能增强请求，待开发
- **Issue**：[#2162](https://github.com/AlexxIT/go2rtc/issues/2162)（Open）

---

### #2134 · Frigate 0.17 + go2rtc 1.9.14 文档缺失
- **严重性**：🟡 低（文档）
- **问题**：Frigate 与 go2rtc 联动时 xiaomi:// 协议配置文档不完整
- **解决方案**：⏳ AlexxIT 已认领，文档更新中
- **Issue**：[#2134](https://github.com/AlexxIT/go2rtc/issues/2134)（Open，已 Assign）

---

### #2170 · 连接小米摄像头失败（通用问题）
- **严重性**：🟡 低（配置问题）
- **问题**：用户反映无法建立连接，原因未明
- **解决方案**：⏳ 排查中，需提供日志
- **Issue**：[#2170](https://github.com/AlexxIT/go2rtc/issues/2170)（Open）

---

## ✅ 与小米 C700（chuangmi.camera.81ac1）相关

> **结论：C700 已在官方 Known Xiaomi Cameras 列表（#1982）中确认支持**

| 项目 | 内容 |
|------|------|
| 型号 | `chuangmi.camera.81ac1` |
| 协议 | `cs2+udp` |
| 视频编码 | H365 |
| 音频编码 | OPUS |
| 已知问题 | v1.9.14 可能受 CS2 i/o timeout 影响（见 #2048） |
| 推荐版本 | v1.9.13（稳定）或等待 #2048 修复后的版本 |

**go2rtc.yaml 配置示例（C700）：**
```yaml
streams:
  c700:
    - xiaomi://用户名:密码@<摄像头IP>?did=<设备ID>&model=chuangmi.camera.81ac1
```

---

## 系统环境：WSL2 + Docker 部署 go2rtc

> **结论：完全可行，WSL2 是推荐的 Windows 部署方式**

| 问题 | 状态 | 说明 |
|------|------|------|
| Docker 能否在 WSL2 内运行 | ✅ 完全支持 | Docker Desktop for Windows 默认以 WSL2 为后端 |
| WSL2 内 Docker 端口是否对 Windows 可访问 | ✅ 自动转发 | WSL2 端口自动映射到 Windows localhost |
| 性能影响 | 可忽略 | WSL2 使用 Hyper-V 虚拟化，网络延迟 < 1ms |
| go2rtc 已知 WSL 问题 | ✅ 无 | GitHub Issues 中无 WSL 相关 bug 报告 |

---

*更新时间：2026-03-25 | 关联：[[OpenClaw接入小米摄像头方案]] | [[OpenClaw摄像头接入项目进度]]*
