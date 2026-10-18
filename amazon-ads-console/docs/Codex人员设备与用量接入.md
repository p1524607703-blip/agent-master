# Codex 人员、设备与用量

管理层及超级管理员访问 `/codex-devices`。页面从 `amazon_ads.codex_ops.personnel_roster` 读取分发成员；不修改任何 CPO 业务权限。运营及 AI 角色无权读取完整名单。

## 设备在线

在页面选择成员，添加真实设备。保存本次窗口展示的 JSON 至该设备的私有配置文件，macOS/Linux 权限设为 600。此处生成的是 48 字节随机心跳密钥，不是六位登录密码，也不是模型代理凭据；服务器只存 SHA256 哈希。

安装 Python 3 后，以系统服务或登录启动项运行：

```bash
python3 codex_heartbeat_agent.py --config /absolute/private/device.json
```

组件每 30 秒访问 `POST /api/codex/heartbeat`，服务端根据凭据解析设备，无需信任客户端自报人员ID。超过 120 秒无心跳显示灰点。绿点表示设备心跳在线，不证明 Codex 正在生成回答。没有收到过心跳的登记设备显示“未接入”。页面刷新失败时绿点立即失效，界面空闲超过45秒未刷新也停止显示绿点。

## 主代理回传用量（需在公司 M4 接入）

服务器私有环境配置 `CODEX_USAGE_REPORTER_KEY` 为独立长随机密钥，并仅交给主代理上报组件；未配置时上报接口返回 503。设备心跳密钥不能上报 Token。

M4 代理在现有设备凭据映射中绑定本页面的 `deviceId`。从实际模型响应或 SSE 最终事件解析 usage 后，POST 到 `/api/codex/usage`；Authorization 使用独立 reporter key。不得上传提示词、回答正文、主账户凭据或原设备 API Key。

```json
{
  "device_id": "从设备登记获取的UUID",
  "response_id": "模型响应ID，重试必须复用",
  "model": "上游实际返回的模型名",
  "outcome": "completed",
  "occurred_at": "2026-10-18T12:00:00+08:00",
  "input_tokens": 1200,
  "cached_input_tokens": 800,
  "output_tokens": 300,
  "reasoning_tokens": 100
}
```

上述数字仅是协议示例，不是生产使用量。input + output 才是总 Token；缓存输入和推理 Token 分别是父计数的子集，不再次相加。没有 usage 的失败/中断请求以 input/output 均为 null 上报。按设备和响应ID去重，首次最终上报生效；上报组件需持久化重试队列并确认响应中的 `recorded`，避免丢失。未登记、停用或人员已禁用的设备不会接受新的用量。

今日按北京时间划分；“—”表示尚未收到计量数据。存在 unknownRequests 时已知用量仅代表已计量部分。该页面不会追溯现有代理没有保存的历史 Token。

## 发布与数据库

上线前由数据库管理员执行 `backend/migrations/20261018_codex_devices.sql`，并给应用数据库角色授予 `codex_ops` schema 的 USAGE、roster 的 SELECT、新增 devices 和 usage_events 表所需的 SELECT/INSERT/UPDATE。迁移仅新增独立设备和用量表；回退应用版本不删除已有遥测。

代码沿现有固定 Git commit 发布引擎准备、验证和切换，不直接修改活动发布目录。真实 M4 上报组件及各成员设备心跳必须分别接入后，才有完整实时统计。
