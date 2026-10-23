# 一设备一 Key 接入 rc.10

先安装 Codex 和 [BigPizzaV3/CodexPlusPlus](https://github.com/BigPizzaV3/CodexPlusPlus/releases)，已有可用版本不必升级或重登。Windows 需要 Python 3.9+（含 py/pythonw）和可用且支持P-256签名的 TPM 2.0；Mac 需要 Python 3.9+、Secure Enclave，包内 macos-key 为通用程序（Apple Silicon最低macOS12，Intel最低macOS13且须有Secure Enclave）。硬件不支持时停止，不改成软件密钥。

## 只需完成四步

1. 将公开包解压到本机。管理员创建本人的设备记录并单独交付 HTTPS Base URL、该设备 Key 和模型名；不要把 Key 发到群聊、在线文档或公共盘。
2. Windows 双击 `1-安装并申请.cmd`；Mac 运行 `1-安装并申请.command`。填入管理员交付的 HTTPS 地址和设备 Key（隐藏输入）。程序在当前用户私有目录安装连接器、生成硬件密钥，显示设备指纹，并添加当前用户登录启动。不会读取、修改或关闭原 Codex。
3. 将设备指纹交管理员核对。管理员在控制台“设备绑定”批准这一个指纹。不要仅凭服务器候选指纹自行批准。未批准前模型调用返回403。
4. Windows 双击 `2-查看本机配置.cmd`；Mac 查看 `~/Library/Application Support/CodexDeviceRelay/bound/provider.txt`。在 Codex++ 新增**非当前**供应商，选择“纯 API / Responses”，从此文件填写本地地址与本地 Key，模型使用管理员交付值。保存后从“Codex多开”启动独立实例。

不点“设为当前”或全局“重启Codex”；不复制主账户 auth.json、OAuth、CODEX_HOME 或 Codex++ 数据库。不要把步骤2的服务器 Key 当作步骤4的本地 Key。使用两个 Key 是为了让 Codex++ 保持普通配置，设备签名由本机连接器处理。

## 验收与恢复

先从供应商获取模型列表，再在独立实例发送测试消息、读取随机本地文件，并核对控制台具体 Token。原窗口/PID、主配置摘要和独立实例目录应分别核对；本包不操作 Codex++ 内部数据库。纯 API 不提供官方账户身份，Work browser 等需要官方身份的功能不能据此绕过。

只复制服务器 Key 到另一台电脑无法请求模型；使用另一台硬件密钥签名同样被拒绝。复制 Mac 配置中的 enclave-wrapped handle 也不能把硬件私钥迁往另一台电脑。Windows 密钥不导出，只由 TPM 提供签名。没有实施远程硬件证明：管理员需确认使用了本包并核对指纹，不能批准来源不明的自制客户端。已被控制的原设备可能被当作远程签名/转发机器，本方案不承诺阻止这种主动串通。

换机时管理员撤销旧 Key，创建新 Key并重新批准；撤销保留历史 Token。旧式仅填 HTTPS+Key 的配置须升级本连接器，不能继续绕过绑定。服务器不强制中断发布前已接收的任务。没有触碰主机原官方直连登录。

需要停止：只停止本连接器（不要结束所有Python/Codex进程）。Windows 删除当前用户启动目录中的 `CodexBoundConnector.cmd`，按脚本完整路径定位本连接器进程并停止；Mac 执行 `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.codex-device-relay.bound.plist` 后移除该 plist。关闭本次多开即可回到原Codex。不要恢复或覆盖原账户认证文件。

## 证据边界

公开包不含任何设备 Key、账号登录材料、私钥或预批准身份。服务器支持 Windows/Mac 的同一协议；Windows TPM、安装体验和 Codex++ 桌面多开必须在实际 Windows 设备上另行验收，Mac 或协议测试不能冒充 Windows 实机结果。每次请求签名包含方法、路径、请求正文哈希、时间和一次性随机数；服务器数据库阻止跨进程和重启后的重放。
