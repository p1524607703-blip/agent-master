# 主机端准备

仅在用户要求配置主机入口或管理设备Key时使用。这是在已有本机试点上补私网接入，不是从零安装账户模型源的脚本。

前置：官方身份模型源127.0.0.1:9542可用，设备认证入口127.0.0.1:6160/v1可用且仅放模型路径；主机和客户端属于同一Tailscale私网。配置路径、PID及维护方式以当前设备实际盘点为准，不照抄其它机器的私有路径。不打印deviceKeys或上游登录文件。

## 发布

先读 `tailscale serve status --json`，保留已有服务。443已承载其它服务时选明确的其它HTTPS端口，Base URL写实际端口，不reset整份配置。

在主机接入操作已获授权时，保留入口回环监听，用Serve发布，例如：

```bash
tailscale serve --bg --https=443 http://127.0.0.1:6160
```

若HTTPS未启用，按Tailscale提示由有权限的人完成设置，不绕过管理端。用实际返回的FQDN形成https://实际设备域名/v1；样例域名或另一台100.x地址不代表已发布地址。

访问策略限定试点设备和服务端口，并保留网关Key认证。Serve只向tailnet发布，不换成公网Funnel，不暴露9542或helper内部路径。

## 设备Key

每台分配不同的至少32随机字节Key，设备代号与指纹登记，不在Git或在线文档留明文。使用现有网关deviceKeys映射，私有备份后原子更新目标条目，不轮换其它设备Key或覆盖local-test。若入口仅启动时加载配置，用现有维护工具重载/仅重启入口，避免退出模型源与主管。

验证原设备仍可用、新Key成功、错误Key拒绝、新设备可单独撤销。本Skill无内置服务器Key、SSH账号或默认管理员凭据；客户端自己生成的Key不会自动在服务器生效。

## 验收

- 实际Serve域名、HTTPS证书和访问规则有效。
- 目标设备无Key/错误Key401，正确Key能列模型。
- /backend/status等内部路径不放行。
- 新设备真实流式完整、原客户端仍正常；日志不记录认证头或账户令牌。

当前并发2、连接16、排队10秒是本机试点参数，不能当作账户容量承诺。

来源：[Serve命令](https://tailscale.com/docs/reference/tailscale-cli/serve)、[Serve说明](https://tailscale.com/docs/features/tailscale-serve)、本机认证与恢复验收。
