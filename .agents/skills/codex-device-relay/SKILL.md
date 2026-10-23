---
name: codex-device-relay
description: 为已授权的 Windows 或 Mac 设备配置已有 Codex++ HTTPS 模型入口，通过独立多开保留原 Codex，并验收真实用量、心跳和本地工具。适用于设备接入与控制台试点，不负责更换上游账户授权。
---

# Codex 多设备接入

沿用管理员已授权并部署的模型入口，给设备新增非当前的纯 API 供应商，再从 Codex++「Codex多开」启动独立测试实例。设备只持独立 Key，保留原主管窗口与官方账户。v0.2 试点按已核对的 BigPizzaV3/CodexPlusPlus v1.9.0 菜单执行；软件、桌面与 Windows 原生兼容性以目标机检查为准。

## 安装前置检查

先核对实际Codex++路径、版本及Windows架构，不能因PATH缺少命令就判未安装。确实未安装时，先从BigPizzaV3/CodexPlusPlus官方正式发布安装，再配置供应商；本Skill及设备包不包含安装器。已有兼容安装直接复用，保留原Codex窗口。具体下载来源和顺序见[Windows指南](references/windows-pilot.md)。

## Windows 控制台试点（含 XT）

收到私有 `device.json` 和 Windows 试点包时，优先读 [Windows 多开试点与人工操作](references/windows-pilot.md)，使用随包或 [scripts/windows_pilot.py](scripts/windows_pilot.py)。这是统一 HTTPS 接入，不要求 Tailscale。只有旧私网部署才读下方旧版 references/windows.md。

先记录原窗口/PID、当前供应商及实际主 CODEX_HOME 的配置摘要；只在本机私有目录保存，不输出认证正文。新增供应商时保持原供应商为当前项：不点新项的「设为当前」、不点全局「重启 Codex」，不注销主账户、不设置持久的全局 CODEX_HOME、不改默认 auth.json。不启用会修改整个安装包或全局插件配置的增强选项。

本轮不使用默认 `pending-provider-import.json`：核对的原生导入实现会更改管理器 active_relay_id。准备脚本只保存设备私有材料；AI 在有受支持界面工具时新增非当前供应商并保存，否则完成准备后交付文中人工点击步骤。不要为省去界面步骤直接改写管理器 settings.json 或内部数据库。若保存提示必须重启原 Codex，则停止该动作，保留原窗口。

从新供应商卡片多开后，核对独立 CODEX_HOME、会话数据库和用户数据目录；和原窗口共用任一目录时不继续测试。把主窗口仍存活、配置未被接入流程改写作为单独验收项。官方认证文件发生变化也可能是正常 Token 刷新，不能因此盲目回滚旧登录文件。

测试失败时只结束本次多开和心跳程序，回到原窗口；不退出所有 Codex。模型通、桌面通、文件工具通、Token 已计量、设备在线分别记录。模型请求或 GET /models 不产生在线绿点。`Work browser` 要求账户身份时，仅在新实例停用不兼容的浏览器能力或改做本地任务；不绕过身份检查、不修改主窗口全局插件。

## 持续在线与官方额度

限时心跳只用于测试。需要设备空闲时也在线时，读 [持续心跳与额度口径](references/presence-quota.md)，在用户已要求持续在线的设备执行新包的4-开启持续在线检测；仅当前用户登录启动，可用5停止、6移除，不修改主Codex。未在Windows实机执行前不能宣称已安装。

设备已记录Token之和仅为中转小计，不能冒充账户总Token。官方5小时/每周剩余与设备Token分列；账户全量Token无法核对时，设备占账户总量显示不可计算，不把两设备强制归一为100%，不拿本地会话库累计冒充跨设备总账。

## 选择本次角色

- **当前设备接入**：默认读 [client.md](references/client.md)，支持 macOS/Windows。
- **Windows控制台试点**：读 [windows-pilot.md](references/windows-pilot.md)；仅旧Tailscale私网方案再读 [windows.md](references/windows.md)。不要混用WSL配置或把脚本成功当成桌面验收。
- **主机入口准备或设备 Key 管理**：旧私网读 [host.md](references/host.md)；控制台试点读仓库的 `amazon-ads-console/docs/Codex人员设备与用量接入.md`，客户端不自行发布或改服务器。
- **M6 不在身边、远程试点**：读 [m6.md](references/m6.md)，先确认受信远程登录；在线或端口开放不等于已取得操作权限。
- **解释架构与进度**：读 [architecture.md](references/architecture.md)，区分已验证、待验收和后续功能。

## 最少输入

需要管理员交付并登记的设备标识、系统/架构、HTTPS Base URL（含 `/v1`）、当前设备独立 Key、模型名。控制台试点另外需要同源 heartbeatUrl。当前模型基线为 `gpt-6.1-sol`，不能自行换别名。Key从仓库外本机私有文件读取，不要求用户把Key发在聊天里；候选包不等于服务端已激活，先查认证与目录，404/503 时保留准备状态。

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
