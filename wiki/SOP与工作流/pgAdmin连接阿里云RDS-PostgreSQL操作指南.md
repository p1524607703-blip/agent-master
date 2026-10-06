---
tags: [SOP, AI工程, 阿里云RDS, PostgreSQL, pgAdmin]
date: 2026-08-25
status: 现行
---

# pgAdmin连接阿里云RDS-PostgreSQL操作指南

> [!summary] 摘要
> 本指南说明如何用 pgAdmin 4 从本机连接 Amazon Ads 数据库。**连接方式已于 2026-09-30 变更**：数据库从阿里云 RDS 迁至腾讯云服务器自建 PostgreSQL，不再有公网直连入口，一律经本机 SSH 隧道（`127.0.0.1:15432` → 服务器 `127.0.0.1:5432`）、数据库层 `sslmode=disable`。因此下文关于「申请外网地址 / 配置白名单 / Verify-Full 证书」的步骤**已不适用**，保留仅为理解历史配置。现行填写方式直接看第 5 节。
>
> **标题里的「阿里云」为历史名称，文件未改名以免断链。**

## 核心知识

### 1. 连接前准备

先向 RDS 管理员确认以下信息，不要在聊天、邮件或知识库中记录明文密码：

| 信息 | 示例或说明 |
|------|------------|
| RDS 类型 | PostgreSQL |
| 连接地址 | RDS 控制台“数据库连接”页中的完整域名 |
| 端口 | 默认 `5432`，以控制台显示为准 |
| 数据库名 | 要使用的业务数据库，不要默认在系统库 `postgres` 中操作 |
| 用户名 | 优先使用个人专属、最小权限账号 |
| 密码 | 由管理员通过安全渠道单独提供 |
| CA 证书 | 开启 SSL 后，从 RDS 控制台下载的 PEM 文件 |

> [!warning] 权限边界
> 普通运营人员不应获得 RDS 地址、账号、密码或证书，应通过 [[运营AI接入阿里云RDS与ChatGPT网页端SOP|运营只读工具]]访问数据。只有数据库管理员、开发人员或明确获准的分析人员才使用 pgAdmin 直连。

### 2. 选择连接网络

根据 pgAdmin 所在位置选择地址和白名单 IP：

| pgAdmin 所在位置 | 使用的 RDS 地址 | 白名单中添加 |
|------------------|-----------------|--------------|
| 本地电脑、公司网络、家庭网络 | 外网地址 | 本机实际出口公网 IP |
| 与 RDS 同账号、同地域、同 VPC 的 ECS | 内网地址（推荐） | ECS 私网 IP |
| 不同 VPC 或跨地域环境 | 先建立 VPC 对等连接、云企业网或 VPN | 实际进入 RDS 的私网 IP |

本地电脑连接时的设置步骤：

1. 登录阿里云 RDS 控制台，进入目标 PostgreSQL 实例。
2. 打开“数据库连接”，确认是否已有外网地址；没有时按需开通。
3. 打开“白名单与安全组”，新建一个用途明确的白名单分组。
4. 仅添加当前电脑的实际出口公网 IP；单个地址可写成 `203.0.113.10` 或 `203.0.113.10/32`。
5. 保存后等待配置生效，再进行 pgAdmin 连接。

> [!danger] 禁止全网开放
> 不要把 `0.0.0.0/0` 留在生产实例白名单中。它代表允许任意公网 IP 尝试连接数据库。临时排障结束后，也应立即删除不再使用的 IP。

### 3. 配置 SSL（推荐）

当通过公网连接时，推荐使用 `Verify-Full`：既加密传输，也校验数据库证书和连接域名，可降低中间人攻击风险。

1. 在 RDS 实例中进入“数据安全性 → SSL”。
2. 选择云端证书，并让证书保护**实际要填写到 pgAdmin 的连接域名**。如果要用外网域名连接，应选择保护外网连接地址。
3. 等待实例状态恢复为“运行中”。首次开启、更换保护地址或关闭 SSL 可能导致实例重启和分钟级闪断，应安排在业务低峰期。
4. 下载 CA 证书并解压，pgAdmin 使用其中的 PEM 文件。
5. 将证书存放到仅当前用户可读取的固定位置，不要放在公开仓库或共享目录。

> [!note] 域名必须一致
> `Verify-Full` 会检查 pgAdmin 中的 `Host name/address` 是否与证书保护的域名一致。因此应填写 RDS 域名，不要改填解析后的 IP 地址。如果证书保护的是外网地址，也不能使用内网地址通过校验。

### 4. 在 pgAdmin 中登记服务器

1. 安装并打开 pgAdmin 4。首次使用时，按提示设置主密码；新版桌面版也可能使用系统密码存储来保护已保存的数据库密码。
2. 在左侧对 `Servers` 单击右键，选择 `Register → Server...`。
3. 在 `General` 页填写连接名称，例如 `阿里云 RDS - 业务库名`。
4. 在 `Connection` 页填写下表内容。

| pgAdmin 字段 | 填写内容 |
|--------------|----------|
| Host name/address | RDS 控制台显示的完整内网或外网域名 |
| Port | RDS 端口，通常为 `5432` |
| Maintenance database | 目标业务数据库名 |
| Username | RDS 数据库账号 |
| Password | 对应密码 |
| Save password? | 个人受控电脑可按需开启；共享电脑不要开启 |
| Role | 通常留空，只有管理员明确要求切换角色时才填写 |

5. 在 `Parameters` 页配置 SSL：

| pgAdmin 字段 | 推荐值 |
|--------------|--------|
| SSL mode | `Verify-Full` |
| Root certificate | 从 RDS 控制台下载并解压得到的 PEM 文件 |
| Host address | 留空；使用前面填写的 RDS 域名 |
| Connection timeout | 可保留默认值；网络较慢时可设为 `10`～`30` 秒 |

6. 单击 `Save`。连接成功后，左侧可展开 `Databases → 目标数据库 → Schemas`。

如果实例尚未开启 SSL，可临时使用 `Prefer`；但它不保证服务端身份校验，不应作为公网生产连接的最终配置。`Require` 只加密链路、不验证服务器真实性，也弱于 `Verify-CA` 和 `Verify-Full`。

### 5. 当前 amazon_ads_v2 实例填写参考

当前实例的完整结构与权限说明见 [[阿里云RDS-amazon_ads_v2-库表结构]]。pgAdmin 可按以下方式填写：

| 字段 | 值 |
|------|----|
| Name | `腾讯云 CPO - amazon_ads_v2` |
| Host name/address | `127.0.0.1`（**本机 SSH 隧道入口**，不是数据库服务器 IP） |
| Port | `15432`（隧道本地端口；服务器侧仍是 5432） |
| Maintenance database | `amazon_ads_v2` |
| Username | 日常查询用 `ads_readonly`；导入用 `ads_ingest`；管理维护才用 `amazon_ads_admin` |
| SSL mode | `Disable`（**外层 SSH 隧道已加密**，库层不再套 TLS） |
| Root certificate | 不需要（旧阿里云 `~/.postgresql/root.crt` 已作废） |

> [!danger] 旧地址全部作废（2026-09-30 迁移）
> 数据库已从阿里云 RDS 全量迁至腾讯云服务器自建 PostgreSQL，只监听服务器本地。
>
> - ❌ 阿里云 `pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com:5432` —— **已停写**
> - ❌ 更早的 `pgm-bp18chyrycgz5q42zo...` / `121.41.134.56` —— 早已整机退役（结构快照见 [[阿里云RDS-amazon_ads-库表结构]]，status=已归档）
> - ❌ 直接连服务器公网 `193.112.27.91:5432` —— **必然超时**，服务器不监听公网
> - ✅ 正确姿势：先确保本机隧道在跑（`lsof -nP -iTCP:15432 -sTCP:LISTEN`），再按上表填写

> [!warning] 隧道没起来时
> 本机隧道由登录启动项 `com.panjinlong.agent-server-db-tunnel` 常驻管理。若 15432 无监听：
> ```bash
> launchctl kickstart -k gui/$(id -u)/com.panjinlong.agent-server-db-tunnel
> ```
> 错误日志：`~/DatabaseBackups/aliyun-final-2026-09-30/database-tunnel-error.log`。

> [!note] 从另一台电脑连接
> 那台电脑上要么自开隧道（`ssh -N -L 127.0.0.1:15432:127.0.0.1:5432 -i <密钥> ubuntu@193.112.27.91`），
> 要么在 pgAdmin 的 `SSH Tunnel` 页直接填服务器 `193.112.27.91:22`、用户 `ubuntu`、私钥认证，
> 此时数据库页填 `127.0.0.1:5432`。

### 6. 连接后验证

连接成功不等于配置完全正确。右键目标数据库，打开 `Query Tool`，执行以下只读 SQL：

```sql
SELECT
    current_database() AS database_name,
    current_user AS login_user,
    inet_server_addr() AS server_ip,
    inet_server_port() AS server_port,
    version() AS postgres_version;

SELECT
    ssl,
    version AS tls_version,
    cipher
FROM pg_stat_ssl
WHERE pid = pg_backend_pid();
```

验收标准：

- `database_name` 是预期业务数据库。
- `login_user` 是分配给本人的账号，而不是误用其他人的管理员账号。
- `server_port` 与 RDS 控制台一致。
- `pg_stat_ssl.ssl` 为 `true`；使用 `Verify-Full` 时，连接建立前还会完成 CA 与主机名验证。
- 只读账号只能查询获准的 Schema、表或视图，不能创建、修改或删除数据。

### 7. 常见报错与处理

| 现象或报错 | 常见原因 | 处理方法 |
|------------|----------|----------|
| 连接超时 | 外网地址未开通、白名单不含实际出口 IP、网络或防火墙阻断端口 | 核对地址类型、当前公网 IP、白名单和本地网络；不要用全网开放来代替定位 |
| `connection refused` | 地址或端口错误、实例未处于运行状态 | 对照“数据库连接”页重新复制域名和端口，检查实例状态 |
| `no pg_hba.conf entry` 或访问被拒绝 | 白名单、SSL ACL 或客户端证书规则不匹配 | 核对白名单分组、网络类型及实例的 SSL/ACL 配置 |
| `password authentication failed` | 用户名或密码错误、账号被锁定或无登录权限 | 重新确认账号，必要时由管理员重置密码或检查账号状态 |
| `database ... does not exist` | `Maintenance database` 填错 | 改成真实业务数据库名 |
| `certificate verify failed` | CA 文件错误、证书已更换、保护地址和连接域名不一致 | 重新下载 PEM；确认 pgAdmin 填的是证书保护的 RDS 域名 |
| `hostname mismatch` | 使用了 IP、别名或未被证书保护的内/外网地址 | 改用证书对应的完整 RDS 域名 |
| 之前能连、现在超时 | 本地公网 IP 变化 | 查询当前实际出口 IP，由管理员更新最小范围白名单 |
| 能连接但看不到表 | 账号未获目标数据库、Schema 或对象权限 | 由管理员按最小权限补充 `CONNECT`、`USAGE`、`SELECT` 等必要授权 |

### 8. 安全检查清单

- [ ] 使用 RDS 域名，不使用裸 IP。
- [ ] 白名单只包含实际需要的 IP，不含 `0.0.0.0/0`。
- [ ] 公网连接使用 `Verify-Full` 和正确的 PEM 根证书。
- [ ] 每个人使用独立账号，不共享管理员账号。
- [ ] 查询人员使用只读角色；只有维护任务才使用管理员角色。
- [ ] 密码和证书不发送到群聊、不写入代码、不提交 Git 仓库。
- [ ] 共享电脑不勾选 `Save password?`。
- [ ] 临时接入完成后，删除临时白名单 IP 和不再使用的账号。
- [ ] 连接后用 `pg_stat_ssl` 验证当前会话确实启用了 SSL。

## 关联

- [[阿里云RDS-amazon_ads-库表结构]]
- [[运营AI接入阿里云RDS与ChatGPT网页端SOP]]
- [[亚马逊TIB与广告报告数据沉淀方案]]

## 来源

- [阿里云：连接 RDS PostgreSQL 实例](https://help.aliyun.com/zh/rds/apsaradb-rds-for-postgresql/connect-to-an-apsaradb-rds-for-postgresql-instance/)
- [阿里云：设置 RDS PostgreSQL IP 白名单](https://help.aliyun.com/zh/rds/apsaradb-rds-for-postgresql/configure-an-ip-address-whitelist-for-an-apsaradb-rds-for-postgresql-instance-1)
- [阿里云：开通或关闭 RDS PostgreSQL 外网地址](https://help.aliyun.com/zh/rds/apsaradb-rds-for-postgresql/apply-for-or-release-a-public-endpoint-on-an-apsaradb-rds-for-postgresql-instance)
- [阿里云：使用云端证书开启 SSL 链路加密](https://help.aliyun.com/zh/rds/apsaradb-rds-for-postgresql/configure-ssl-encryption-for-an-apsaradb-rds-for-postgresql-instance)
- [pgAdmin：Server Dialog](https://www.pgadmin.org/docs/pgadmin4/latest/server_dialog.html)
- [PostgreSQL：SSL Support](https://www.postgresql.org/docs/current/libpq-ssl.html)
