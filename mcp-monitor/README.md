# 固定 MCP 分层监测脚本

Python 3.9+，仅用标准库。适用于这台 Mac 的现有五条 Tunnel。

## 一键本地检查

```sh
/usr/bin/python3 /Users/panjinlong/Documents/agent-master/mcp-monitor/monitor.py begin
```

输出本次 `run_id`。本地检查包括现有配置文件是否存在、健康/就绪/云端轮询指标、健康端点所属进程、launchd 状态。包装器不常驻不单独判为离线；不读取或输出配置中的凭证。

## 云端证据录入与报告

脚本不能取得当前 ChatGPT 会话的插件执行权。因此每日巡检任务必须实际调用插件，不能用本地 HTTP 或自建模型 API 代替。每个调用结束后记录当时 Unix 时间，并将原始 MCP 返回整体交给 `record`（不保存原始正文）。示例：

```sh
/usr/bin/python3 /Users/panjinlong/Documents/agent-master/mcp-monitor/monitor.py record --run-id RUN_ID --probe dsh --observed-at UNIX_SECONDS
```

默认从标准输入读完整返回 JSON；也支持 `--result-json`，不得在命令参数中传递含凭证的返回。调用方须对“当前会话实际调用”的来源真实性负责：这是证据汇总接口，不是独立的云端身份认证。不能录入往日结果。脚本拒绝过期、已结束批次，检查外层和正文错误，未知格式保持未验证。

探针对应：`seller` → get_sellersprite_database_stats；`ads_catalog` → 运营只读 get_ads_data_context；仅目录确认为 10/10/0/0 后调用 get_import_health(limit=1) 并录入 `ads_db`；`ziniao` → ziniao_cli_read doctor；`dsh` → deepseek_harness_bridge_info。调用异常也录入 isError/error；工具缺失不补造成功证据。

```sh
/usr/bin/python3 /Users/panjinlong/Documents/agent-master/mcp-monitor/monitor.py finish --run-id RUN_ID
```

报告位于 `/Users/panjinlong/Library/Application Support/mcp-monitor/latest.md`，同目录保留仅含状态的 JSON 历史。默认目录私有、文件权限 0600，写入采用原子替换和互斥锁。未录入项目始终是未验证。目标网页会话始终单列未验证，不能被当前任务的云端调用覆盖。当前仅五个既有 Tunnel 有本地探针，其余配置只盘点名称，不能报告“全部 MCP 通过”。

## 调度和修复边界

复用原来的每日 9 点、America/New_York 心跳任务，不另建计划、不改变时区。心跳先 begin，再通过插件取证，最后 finish。脚本自身不启动后台常驻进程，电脑/任务运行环境不可用时无法保证准点执行。

本脚本严格只读，不自动重启、安装 SQL 函数、切换权限、登录或操作业务数据。既有巡检任务仍依原来的授权与共享锁、宽限期、冷却规则决定安全修复；修复后创建新批次，重新调用同一插件验证，不以重启成功代替恢复证据。历史报告没有自动清理，以便追溯。`changed` 只是状态对比，通知仍由任务判断是否为新故障、恢复或需要用户行动；不得因首次基线或未验证项目重复通知。

## 测试

```sh
cd /Users/panjinlong/Documents/agent-master/mcp-monitor
/usr/bin/python3 -m unittest -v
```
