# 运营 AI 接入阿里云 RDS 与 ChatGPT 网页端 SOP

## 一句话结论

如果目标是在 ChatGPT 网页端查询云数据库，运营人员不需要先安装 Codex，也不应让每台员工电脑直接连接 RDS。正确做法是由公司部署一个运营专用 MCP 网关，再通过 ChatGPT Developer mode 应用连接；员工只获得应用使用权，不获得数据库密码或管理员权限。

## 推荐架构

```text
运营人员浏览器
    ↓ ChatGPT Developer mode 应用
OpenAI 工作区权限
    ↓ Secure MCP Tunnel（仅出站 HTTPS）
公司专用网关主机
    ↓ 运营专用 MCP（无任意 SQL/管理员工具）
阿里云 RDS PostgreSQL
    ├─ 分析数据：只读
    └─ 运营记录：受控写入并审计
```

## 管理员一次性准备

### 1. 建立运营专用 MCP

- 只提供业务查询、导入健康、活动跟进、动作记录和复查等工具。
- 不提供任意 SQL、建表、改权限、删库或数据库管理员工具。
- 运行环境不保存 RDS 管理员凭据。
- 分析数据只读；如需写入，只允许写入独立运营区，并记录审计日志。
- 删除、正式导入等高风险操作必须再次确认。

不要只在 ChatGPT 界面隐藏管理员工具。运营 MCP 必须从服务端取消注册这些工具，并且运行进程本身不能读取管理员凭据。

### 2. 收紧 RDS 权限与网络

- MCP 使用独立的最小权限数据库角色；不要把管理员账号发给员工。
- 网关与 RDS 同 VPC 时，只允许网关私网 IP；跨公网时，只允许网关固定公网 IP。
- 严禁在 RDS 白名单中加入 `0.0.0.0/0`。
- 使用 RDS 域名和 `sslmode=verify-full`，并在网关安装阿里云 CA 证书。
- 员工电脑不加入 RDS 白名单，不安装数据库证书，不保存 RDS 密码。

### 3. 配置 OpenAI Secure MCP Tunnel

1. 在 OpenAI Platform 创建运营专用 Tunnel。
2. 将 Tunnel 关联到目标 ChatGPT 工作区和 Platform Organization。
3. runtime API key 只保存在网关主机，不发给员工。
4. 给运营人员授予 `Tunnels Read + Use`，不要授予 `Manage`。
5. 工作区管理员允许指定成员使用 Developer mode。
6. 确保 `tunnel-client` 长期在线，并配置开机自启、健康检查和异常告警。

网关主机必须同时能访问 RDS 和 `api.openai.com:443`。如果选择中国大陆区域 ECS，应先完成网络连通性和合规验证；未验证前可使用一台长期在线、具有固定网络出口的公司设备试点。

## 运营人员网页端步骤

1. 使用公司账号登录正确的 ChatGPT 工作区。
2. 打开 **Settings → Security and login**，启用 **Developer mode**。
3. 打开 ChatGPT 的 **Plugins** 页面，点击加号创建开发者模式应用。
4. 应用名称填写管理员规定的名称，Connection 选择 **Tunnel**。
5. 选择管理员已关联的运营 Tunnel，或粘贴管理员通过内部渠道提供的 `tunnel_id`。不要索要 runtime API key。
6. 创建连接并检查工具清单：应看到业务查询和运营工具，不应看到任意 SQL 或管理员工具。
7. 新建聊天，从工具菜单选择 **Developer mode → 运营数据库**。
8. 执行下方三条只读验收提示词；通过后再开始正式业务操作。

### 验收提示词

```text
只使用“运营数据库”应用。先调用数据口径工具，告诉我当前目标是云端还是本地、SSL 模式、MCP 版本和工具数量；不要执行任何写入。
```

```text
只使用“运营数据库”应用，查询最近 5 次报告入库健康状态；不要修改数据。
```

```text
只使用“运营数据库”应用，列出当前待复查的业务对象；如果没有结果，请明确返回空集，不要编造或写入。
```

通过标准：目标为公司云数据库、SSL 为 `verify-full`、查询能返回真实结果或空集、工具清单没有管理员能力、未确认时不会写入或删除。

## 如果还需要 Codex

Codex 只是另一个客户端，不是 ChatGPT 网页端连接数据库的前置条件。

1. 从 OpenAI 官方渠道安装 Codex，并使用公司身份登录。
2. 由管理员提供运营专用远程 MCP 地址/OAuth，或将公司 Tunnel 关联到 Codex 使用的 Platform Organization；不要提供 RDS 密码。
3. 如果获得的是 Streamable HTTP 地址，在 Codex 的 **Settings → MCP servers → Add server** 中填写名称和 URL，完成认证后保存并重启。
4. 输入 `/mcp` 检查连接，再执行上面的只读验收提示词。

注意：Codex 的本地 MCP 配置不会自动出现在 ChatGPT 网页端。网页端仍需按上一节创建并选择 Developer mode 应用。

## 常见故障

| 现象 | 优先检查 |
|---|---|
| Developer mode 不显示 | ChatGPT 套餐、工作区策略、是否登录正确工作区 |
| Tunnel 列表为空 | Tunnel 是否关联目标工作区；员工是否有 `Tunnels Read + Use` |
| 工具调用失败 | 网关、`tunnel-client`、OpenAI 443、RDS 网络是否正常 |
| RDS 连接超时 | 网关 IP 白名单、安全组、路由、域名和端口 |
| SSL 校验失败 | CA 文件、RDS 域名、证书有效期和 `verify-full` 配置 |
| 新工具不出现 | 刷新应用元数据，重新关联并开启新聊天 |
| 出现管理员 SQL 工具 | 立即停用并撤销 Tunnel Use，修复服务端权限后再验收 |

## GitHub 安全规则

本文可以放在公开 GitHub，但只能保留通用步骤和占位符。以下内容不得提交：

- RDS 域名、公网 IP、实例 ID、用户名或密码；
- `tunnel_id`、runtime API key、OAuth 密钥或代理配置；
- `.env`、真实 `config.toml`、系统凭据导出、日志或数据库备份；
- 能绕过受控业务工具直接执行管理员 SQL 的配置。

Tunnel ID、工作区邀请和权限授予应通过公司内部渠道交付；数据库密码只保存在网关的系统凭据库中。

## 官方参考

- [OpenAI：Codex 与 ChatGPT 的 MCP 配置边界](https://developers.openai.com/codex/mcp)
- [OpenAI：ChatGPT Developer mode](https://developers.openai.com/api/docs/guides/developer-mode)
- [OpenAI：Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [阿里云：连接 RDS PostgreSQL](https://www.alibabacloud.com/help/en/rds/apsaradb-rds-for-postgresql/connect-to-an-apsaradb-rds-for-postgresql-instance)
- [阿里云：配置 IP 白名单](https://www.alibabacloud.com/help/en/rds/apsaradb-rds-for-postgresql/configure-an-ip-address-whitelist-for-an-apsaradb-rds-for-postgresql-instance)
- [阿里云：配置 SSL](https://www.alibabacloud.com/help/en/rds/apsaradb-rds-for-postgresql/configure-ssl-encryption-for-an-apsaradb-rds-for-postgresql-instance)
- [阿里云：PostgreSQL 细粒度权限管理](https://www.alibabacloud.com/help/en/rds/apsaradb-rds-for-postgresql/manage-permissions-in-an-apsaradb-rds-for-postgesql-instance)

