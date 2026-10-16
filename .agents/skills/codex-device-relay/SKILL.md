---
name: codex-device-relay
description: 为本人 Mac 或 Windows 配置已有 Codex++ 私网模型入口，检查 Tailscale、设备 Key、Responses 流式及本地工具，并提供 M6 远程试点步骤。适用于第二台或后续设备接入；共享模型不等于跨设备任务调度。
---

# Codex 多设备接入

沿用用户已部署的 Codex++ 模型源，给当前设备配置纯 API 客户端。账户 OAuth 留在模型源；设备只持独立网关 Key。基线为 BigPizzaV3/CodexPlusPlus v1.8.0，升级时按实际版本核对界面与协议。

## 选择本次角色

- **当前设备接入**：默认读 [client.md](references/client.md)，支持 macOS/Windows。
- **Windows设备**：同时读 [windows.md](references/windows.md)，按原生PowerShell、Windows路径与Key ACL步骤接入；不要混用WSL配置或把脚本成功当成桌面验收。
- **主机入口准备或设备 Key 管理**：读 [host.md](references/host.md)，客户端不要自行改服务器。
- **M6 不在身边、远程试点**：读 [m6.md](references/m6.md)，先确认受信远程登录；在线或端口开放不等于已取得操作权限。
- **解释架构与进度**：读 [architecture.md](references/architecture.md)，区分已验证、待验收和后续功能。

## 最少输入

需要设备代号及系统/架构、管理端已验证的 HTTPS Base URL（含 `/v1`）、当前设备独立 Key、已验证模型名。当前模型基线为 `gpt-6.1-sol`，不能自行换别名。Key优先读取本机仓库外的私有文件，不要求用户把Key发在聊天里。

缺少地址或Key时，先完成环境盘点和安装准备，再报告缺口。不把示例地址或占位Key当作可用配置，不询问具体所在地。

## 保留主管会话的执行顺序

1. 运行 `scripts/relay_device.py doctor`，记录系统、Tailscale、Codex++和Codex状态。CLI与桌面安装分开检查。
2. 从主项目正式发布来源安装/核对Codex++及其所需Codex运行环境；已有可用软件不做无必要升级或重登。
3. 保留当前主管，新增独立纯API供应商：Responses、已发布Base URL、当前设备Key与模型。
4. 用Codex++「Codex多开」启动此单一API供应商，核对独立配置、数据库和会话目录；不要为了切换模型重启正在安装的主管窗口。
5. 先验收无Key/错误Key拒绝和模型目录，再在本次接入已授权的范围内发一条真实流式请求；最后在新实例验证本设备测试文件读取与多轮工具循环。
6. 回执保存在仓库外；界面、流式、工具和撤销分别验收，普通HTTP200不能替代完整任务验收。

界面工具不可用时，完成自动盘点、网络验证与字段准备，给出剩余的具体界面动作；不要猜测或直接改写Codex++内部设置/数据库，也不把准备字段称为已配置。官方桌面若被界面工具禁止访问，保持该边界。

## 随附工具

命令以当前Skill目录为基准；Windows通常用 `py -3` 替代 `python3`。示例域名不可直接使用。

```bash
python3 scripts/relay_device.py doctor
python3 scripts/relay_device.py probe --base-url https://relay.example.ts.net/v1 --device-id mac-02 --key-file /private/path/device.key
python3 scripts/relay_device.py probe --base-url https://relay.example.ts.net/v1 --device-id mac-02 --key-file /private/path/device.key --live
```

默认probe只查认证与目录；`--live`才消耗额度请求一次真实模型。脚本关闭本进程环境代理并禁止重定向，不改系统代理，保持HTTPS证书校验。它不安装软件、不改客户端配置、不启用远程管理。

## 关键边界

- 客户端 `127.0.0.1` 代表它自己。跨设备地址由主机发布，内部9542不分发。
- 不复制账户auth.json、OAuth或完整供应商数据库；设备Key不放Git、在线文档、URL、命令参数或终端输出。`--key-file`只传路径。
- 不需要为本次接入启用全机Surge网关或Tailscale出口节点；业务工具维持原线路并逐项授权验收。
- 共享模型不增加额度、不自动同步记忆，也不自动形成跨设备任务领取/取消/回传能力。
- 401区分设备Key与上游登录；429按Retry-After退避；502检查模型源；证书错误先修证书。诊断有界，不循环重试或关闭验证。

分别交付安装、私网、认证、目录、完整流式、桌面多开、本地工具、单台撤销和回滚状态；列出未通过项及本机回执路径。Windows或跨设备只在实际执行后才称为通过。
