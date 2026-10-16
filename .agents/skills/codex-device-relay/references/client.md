# Mac / Windows 客户端接入

Windows完整步骤、PowerShell命令与验收清单见 [Windows专用指南](windows.md)。

安装前记录原供应商、Codex配置位置与当前进程，仅备份实际要改动的配置到私有目录。优先新增纯API供应商并用「Codex多开」启动，原主管继续运行。

| 字段 | 填写内容 |
|---|---|
| 名称 | 本设备可识别名称，如relay-win-01 |
| 模式 | 纯 API |
| 协议 | Responses |
| Base URL | 管理端已验证的https://实际私网域名/v1 |
| Key | 此设备独立网关Key |
| 模型 | 实际目录中的已验证名称，当前基线gpt-6.1-sol |

主项目是BigPizzaV3/CodexPlusPlus。同名其它仓库的格式不能混用。macOS/Windows均按实际CPU架构选择正式发布文件，并核对所需Codex运行环境；不承诺跨版本菜单名相同。纯API允许无ChatGPT登录；1.8.0内置多开支持符合条件的单一API供应商，不直接启动聚合或模型路由供应商。现有模型源直接使用官方身份，不要求客户端再建聚合。

主项目存在携带Key的供应商导入URL，但本部署包不采用，以免Key进入URL、浏览记录或进程参数。没有核对过的导入能力时按真实界面录入，不发明通用JSON导入功能。

## 验收

把管理员交付的Key保存在仓库外本机私有文件。POSIX权限600；Windows使用当前用户私有目录并核对ACL，不放共享盘。不要在命令中直接写Key。

先运行probe（认证和模型目录，无真实模型调用），再加 `--live` 发一次真实请求。回执默认位于当前用户 `.local/share/codex-device-relay/<设备代号>/`。脚本通过只证明网络、设备认证、目录和流式，不代表Codex++界面已保存或桌面任务已执行。

在当前设备的独立测试目录创建probe.txt，写随机标记。在新纯API多开窗口要求只读文件并仅返回内容，核对实际工具调用和准确结果，再跟进一轮验证上下文。若有CLI，可用独立配置/SQLite目录补测后台只读任务，不能代替Codex++多开界面验收。

钉钉、飞书、紫鸟等本地工具仍须本设备分别登录授权。纯API不保证官方账号插件入口完全等价；不得宣称共享主管历史、ChatGPT记忆或其它设备会话。

## 失败与回滚

| 现象 | 先检查 |
|---|---|
| DNS/超时 | Tailscale同私网、主机在线、访问规则、Serve确实已发布 |
| 401 | 设备Key；区分网关拒绝与上游登录失效 |
| 404 | /v1位置和模型路径；内部诊断路径404属于预期 |
| 429 | 并发/排队、账户限额、Retry-After；不堆积重复任务 |
| 502 | 6160能否连接9542、源实例和上游登录 |
| 证书错误 | DNS名、证书和系统时间；不使用insecure |

回滚仅关闭本次新多开，恢复本次改动和原供应商，保留主管。撤销Key后确认本设备被拒绝、其它设备仍可用；记录已执行业务动作，避免重试重复写入。

来源：[README](https://github.com/BigPizzaV3/CodexPlusPlus/blob/v1.8.0/README.md)、[多开](https://github.com/BigPizzaV3/CodexPlusPlus/blob/v1.8.0/apps/codex-plus-manager/src-tauri/src/commands.rs)、[供应商导入](https://github.com/BigPizzaV3/CodexPlusPlus/blob/v1.8.0/crates/codex-plus-core/src/provider_import.rs)。
