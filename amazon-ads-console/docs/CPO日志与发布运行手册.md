# CPO 日志、Redis 监控与发布运行手册

## 可复现的主机配置

`scripts/install_infra.py` 是唯一配置入口；模板在 `deploy/infra/`。正式发布代码仍由 `scripts/release.py` 从已推送 Git commit 构建，不复制工作目录源码。

```bash
# 预览：不修改主机。
python3 amazon-ads-console/scripts/install_infra.py
# 在服务器从已校验的 release 内执行：不切换业务代码、不重启 CPO 服务。
sudo -n python3 /opt/agent/cpo/current/amazon-ads-console/scripts/install_infra.py --apply
```

安装器先备份所有改动文件与符号链接至 `/var/backups/cpo-infra/<UTC时间>-<随机值>/`，清理 `sites-enabled` 里被通配加载的 `.bak/.backup/.old/~` 文件到该备份目录，移除旧的 `cpo_api` 定义，并统一安装 JSON 格式。执行完整 `nginx -t`、全部 logrotate 规则的只读校验和 systemd 单元校验；成功才 reload Nginx。失败时恢复文件/链接/原 timer 状态；原盘上配置仍不合法时，保留现有 Nginx worker，不 reload 错误配置。

安装器只将 trace 环境变量写入服务及 drop-in，当前 CPO 进程在下一次正式发布/restart 时使用该变量。它不运行数据导入、seed、密码 reset 或 migration。

## 三条日志链路

| 日志 | 内容 | 位置与容量策略 |
| --- | --- | --- |
| 服务与 Redis 监控 | 应用输出、失败类别、Redis 异常/恢复状态 | journald 持久存储，`SystemMaxUse=2G`、`MaxRetentionSec=30day` |
| Nginx API access | JSON：请求 ID、方法、endpoint、状态、请求/上游耗时、合法 date/end_date/period | `/var/log/nginx/cpo_api_access.log`；复用唯一 nginx logrotate 规则，daily、30 档、maxage 30 日、100M 阈值、压缩 |
| 应用请求 trace | ASGI JSON 请求、阶段耗时、cache hit/miss、真实 release/commit、脱敏错误类别 | `/opt/agent/cpo/shared/traces/requests.jsonl`，0600 ubuntu；daily、30 档、maxage 30 日、20M 阈值、压缩 |

`cpo-logrotate.timer` 每小时检查容量，使用系统 logrotate 的同一状态文件/锁；正常 daily 任务继续使用同一规则，不创建重复通配规则。容量阈值不是逐字节硬上限：两次检查之间可暂时超过阈值；频繁超限轮转会优先保留最多 30 档，因此保留时间可能少于 30 日。`delaycompress` 保留最新轮转档未压缩，下一次轮转压缩它。

应用每条 trace 重开文件，支持 rename/create，不用有丢失窗口的 copytruncate。诊断 API 同时扫描当前文件、轮转档及历史 `.gz`，按时间、用户名、用户 ID 或请求 ID 查询。单次扫描上限 64MiB / 10 万行，最多返回 200 条；超限会明确提示，完整档案可在服务器查阅。

API access 不记录完整 query、请求 body、Authorization、cookie、referer、user agent；只允许验证过的日期和 `daily/weekly/monthly` 三种周期。Nginx 使用自己的随机 `$request_id` 覆盖用户传入值，传给后端，隐藏后端返回的同名 header，再给客户端添加一个 `X-Request-ID`。新增 API/login/SPA location 明确包含安全 header，401/429/404 也保留它们。

登录位置的 Nginx 规则按真实连接 IP 每分钟 60 次，允许瞬间 30 次，拒绝为 HTTP 429。该阈值给共享办公出口留有余量；跨地址、账号级别的失败限制由后端负责。只信任同机代理，客户端自行伪造 X-Forwarded-For 不能改变连接 IP。

## Redis 本地健康监控

`cpo-redis-watchdog.timer` 启动后 2 分钟开始，每分钟执行一次 PING，并以 inode/offset 游标读取 trace 的新 `request_complete.l2_error`，每次最多 1MiB。即使 PING 恢复可连，只要本次新请求出现 L2 错误也会告警；同一行不重复消费，轮转或截断会重建游标。第一次异常写 journald warning，持续异常每 15 分钟提醒，后续 PING 正常且无新请求错误时恢复只写一次 recovered。字段有 `CPO_COMPONENT=redis`、`CPO_HEALTH`、`CPO_ERROR_CLASS`、`CPO_FAILED_CHECKS`、`CPO_REQUEST_CACHE_ERRORS`；不输出 Redis URL、用户名、密码或异常原文，也不向外部发送消息。

状态文件 `/opt/agent/cpo/shared/watchdog/redis-state.json` 为 0600。Redis 异常不让 timer 停止；API 仍以 PostgreSQL 读取作为降级路径。

```bash
sudo -n systemctl status cpo-redis-watchdog.timer cpo-logrotate.timer
sudo -n journalctl -t cpo-redis-watchdog -o json --since '30 minutes ago'
sudo -n nginx -t
sudo -n logrotate --debug /etc/logrotate.conf
sudo -n journalctl --disk-usage
```

## 部署与回滚

发布工具分别固定应用 commit 与部署引擎 commit。引擎来自调用工作树的已推送 HEAD，两个 commit/tree 都经 GitHub API 核验；服务器再逐字节对照引擎脚本和 helper 的 Git blob，应用源码仍逐文件校验。这样回滚老 tag 时也保留新引擎的停服、清缓存和预热流程。

```bash
python3 amazon-ads-console/scripts/release.py prepare <已推送tag或commit>
python3 amazon-ads-console/scripts/release.py deploy <同一个tag或commit>
python3 amazon-ads-console/scripts/release.py rollback <以前成功的tag或commit>
```

激活顺序：校验与只读两库检查 → 停旧服务 → 删除 Redis 派生 snapshots → 切换前后端及 unit → restart → 等待鉴权边界返回 401（startup warmup 已完成）→ 预热最新 daily/monthly → 检查两库、公开前端 commit 和鉴权 → 记录成功。

清理只针对 `cpo:build:v1:*` / `cpo:complete-days:v1:*`，保留所有 `:lock`、会话和其他 key，并分批删除。停服务先于清理，避免旧进程重新写回旧快照；Redis 关闭时跳过，Redis 配置启用但不可用时停止此次激活并恢复旧代码。

候选失败时再次停候选服务、清其派生快照、恢复旧代码/前端/unit、restart、等待启动、按旧实现重新预热并健康检查。结果区分 `FAILED_ROLLED_BACK` 与 `FAILED_ROLLBACK_UNHEALTHY`；显式成功回滚记 `ROLLED_BACK`。数据库、业务映射、共享上传文件不随代码回滚。

每个 release 自己的 `release.json` 是版本诊断来源；`shared/current-release.json` 仅是部署汇总，不能替代进程正在使用的 release 元数据。发布时间和引擎身份也写入该 release 的公开 version.json。

## 本次主机修复记录

2026-10-06（America/New_York）：原 Nginx 因 `sites-enabled/default.bak.20261007T112830` 重复 default_server 而无法通过检查。原 unsafe log_format 记录原 query/referer。备份路径 `/var/backups/cpo-infra/20261007T034017Z-4f238bfc`，已移出加载目录并安装上述模板。验证：Nginx 检查/reload 成功；API 401、SPA 200、asset 404 均只有一个 X-Request-ID 且保留安全 header；同机 GET login burst 得到 31 个 405 与 14 个 429，不提交密码、不产生登录成功；fake token query 标记未进入独立 API JSON 日志。业务 release 仍为 `27e8590e6b3f664b3c1c44d44ba0756cf25e930b`（cpo-v1.0.2），修复过程未重启 CPO。

## 人工查看 bug

管理层登录 [系统诊断](https://193.112.27.91:80/diagnostics)，选时间和用户名，或粘贴页面复制的 Request ID。查看 HTTP 状态、快慢等级、数据库耗时、缓存与锁、版本及脱敏错误堆栈。运营人员可在自己的 CPO 页面复制或下载本次浏览器诊断记录交给管理层。

需核查主机时，在本机执行 `ssh -N -L 19090:127.0.0.1:9090 Agent-server`，打开 `https://127.0.0.1:19090` 的 Cockpit；日志中过滤 `cpo-console` 或 `cpo-redis-watchdog`。无需向公网开放管理端口。已有日志从启用时开始累计，无法补回过去未记录的请求。
