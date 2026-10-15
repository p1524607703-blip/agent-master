# Codex++ 多设备接入方案与配置 Skill

版本codex-device-relay-v0.1.0，2026-10-15发布。适用本人少于20台Mac/Windows设备：模型源集中在主机，各设备使用Codex++纯API与独立设备Key，任务工具仍在各设备本地执行。当前只完成本机试点，跨设备接入按真实验收推进。

- [完整架构方案与流程图](../../.agents/skills/codex-device-relay/references/architecture.md)
- [安装后供Codex执行的Skill](../../.agents/skills/codex-device-relay/SKILL.md)
- [Mac / Windows客户端接入](../../.agents/skills/codex-device-relay/references/client.md)
- [主机私网入口与设备Key准备](../../.agents/skills/codex-device-relay/references/host.md)
- [M6远程试点](../../.agents/skills/codex-device-relay/references/m6.md)

主分支采用保护规则；本包提供固定版本标签，可直接安装，无需等待方案PR合并。

## 在另一台设备交给Codex

把下面这段发给**目标设备上已有可用连接的Codex**：

```text
请从 https://github.com/p1524607703-blip/agent-master/tree/codex-device-relay-v0.1.0
安装 .agents/skills/codex-device-relay 到本机用户级Skill目录。
阅读并使用 $codex-device-relay，帮当前设备接入已有Codex++模型服务。
先运行doctor，保留正在工作的主管和原模型入口；使用独立纯API供应商及多开实例。
实际私网Base URL和本设备Key文件由我在本机私下提供，不从公开仓库寻找凭据。
缺少服务地址、Key、软件或界面权限时，先完成能做的准备，准确列出剩余步骤。
最后分别验收认证、模型目录、完整流式和本地工具，并把回执保存在仓库外。
```

若从仓库直接使用，打开仓库后可从 `.agents/skills/codex-device-relay` 发现Skill；要跨项目使用，把整个目录复制到当前用户的 `~/.codex/skills/codex-device-relay`。Windows的`~`同样指当前用户目录。已有同名Skill先比较版本并保留必要备份，不盲目覆盖。新增Skill未出现在技能列表时重新载入技能或在合适的空闲时机新开聊天；本次安装任务不要中途重启正在执行的主管。

Skill负责流程与校验，不能凭空取得服务器Key、系统权限或远程桌面。完全没有模型连接的新设备，需要先用可用入口或手动完成首次字段录入，不能要求一个尚不能调用模型的Codex自行完成启动。

## 每台设备仍需的本地信息

| 信息 | 来源 |
|---|---|
| 实际私网HTTPS Base URL（包含/v1） | 主机发布并验收后交付 |
| 本设备独立Key | 主机管理员私下签发；不使用示例Key |
| 已发布模型 | 当前本机基线gpt-6.1-sol，按实际目录确认 |
| 本地工具权限 | 钉钉、飞书、紫鸟等在本设备分别授权 |

公开仓库只包含脱敏方案和可复用工具，不保存实际设备IP/DNS、账号OAuth、设备Key、SSH用户名或主机指纹。客户端不复制主机auth.json。

## 随附自动检测

Python3.9及以上，仅标准库。macOS通常用`python3`，Windows可用`py -3`。以下域名和文件路径是示例，使用前换成私下交付的真实值。

```bash
python3 .agents/skills/codex-device-relay/scripts/relay_device.py doctor
python3 .agents/skills/codex-device-relay/scripts/relay_device.py probe --base-url https://relay.example.ts.net/v1 --device-id mac-02 --key-file /private/path/device.key
python3 .agents/skills/codex-device-relay/scripts/relay_device.py probe --base-url https://relay.example.ts.net/v1 --device-id mac-02 --key-file /private/path/device.key --live
```

默认probe验证无Key/错误Key拒绝与模型目录，不调用模型。`--live`额外发起一次真实Responses请求，要求准确随机标记和`response.completed`。HTTPS校验开启，不跟随重定向，不使用环境HTTP代理，也不改系统网络。回执不含Key，保存在用户私有目录；POSIX Key文件须为600权限，Windows需核对文件ACL。

通过脚本不代表桌面多开、工具或Key撤销通过：这些在回执中明确保持未验收。脚本不会安装软件、直接改写Codex++设置、开启Serve或开启SSH。

## M6不在身边

可通过已有受信SSH或M6自身的Codex完成安装，不要求人在机器旁边。但TCP22/5900可连接仅说明服务端口开放；仍需确认SSH主机身份、实际系统用户名及可用登录。当前尚未完成M6认证、模型接入或远程安装。保留M6为下一台测试设备，不把未执行测试标成已完成。

主机私网入口和独立设备Key也须先准备好；当前6160仅本机回环监听。模型接通后，主管自动派任务到M6仍需后续跨设备执行器。

## 本次验证范围

- Skill格式验证通过，本机doctor识别macOS arm64、Codex、Codex++和在线Tailscale。
- 8项本地HTTP模拟测试通过：认证、目录不调用模型、单次完整流式、不完整流式拒绝、未发布模型拒绝、重定向不泄露Key、回执脱敏/不重复覆盖、POSIX密钥权限。
- 本次未在Windows实际运行，未完成M6部署或新的真实跨设备模型调用。

```bash
python3 .agents/skills/codex-device-relay/scripts/test_relay_device.py
```
