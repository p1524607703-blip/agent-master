# 运营 AI 接入阿里云 RDS 与 ChatGPT 网页端 SOP

## 一句话结论

运营人员必须先安装 Codex，并使用各自的个人版 ChatGPT/OpenAI 账号，不要求 Business 或公司工作区。管理员将无账号绑定的“亚马逊广告运营只读个人版安装器”放在公开 GitHub 仓库，运营把仓库链接交给 Codex 后，由 Codex 完成 Marketplace 添加、为当前个人账号生成应用映射并验收权限；员工电脑不直连阿里云 RDS，也不保存数据库密码、隧道密钥或管理员凭据。

## 两套插件必须永久隔离

| 插件 | 使用人 | 工具 | 权限 |
|---|---|---:|---|
| 亚马逊广告数据分析与运营-v2 | 负责人 | 25 | 保留现有读取、受控写入和管理员能力，不修改 |
| 亚马逊广告数据分析（运营只读） | 运营 | 10 | 只查询；写入、导入、删除、SQL 和管理员能力均为 0 |

运营插件不是在现有插件上切换“只读开关”，而是独立的 MCP 服务、RDS 账号、Secure MCP Tunnel、OpenAI 应用和 GitHub 插件包。测试和修改只能发生在运营副本，禁止调整现有 `amazon-ads-local` 隧道或 25 工具应用。

## 安全架构

```text
运营人员电脑（个人版 ChatGPT/OpenAI 账号）
    ├─ Codex（安装公开 GitHub 个人版安装器）
    └─ ChatGPT 网页端（当前个人账号的只读应用映射）
              ↓
独立运营只读应用 + 独立 Secure MCP Tunnel
              ↓
独立只读 MCP（固定注册 10 个查询工具）
              ↓
阿里云 RDS PostgreSQL
    └─ 独立 SELECT 账号 + 强制只读事务
```

## 管理员一次性准备

1. 部署独立只读 MCP，只注册下列 10 个查询工具：
   - 数据口径、产品分类、导入健康；
   - 近期表现、成熟归因、单活动日趋势、TIB；
   - 待复查、归因刷新到期、已管理活动查询。
2. 使用独立 RDS 登录角色，只授予必要视图或表的 `SELECT`，并强制只读事务。
3. 新建独立 Secure MCP Tunnel；不要修改或复用现有网页端插件的隧道配置。
4. 为负责人注册独立的“运营只读”应用并确认工具恰好为 10 个；固定应用技术 ID 只作为负责人恢复备份，不视为跨账号授权。
5. 在 GitHub 发布不含 `.app.json` 账号绑定的个人版安装器。安装器在目标电脑上创建目标个人账号专属的应用映射。
6. 使用 Secure MCP Tunnel 时，把获准运营的个人 Platform 组织和 ChatGPT 个人空间加入该 Tunnel 的关联范围；这不要求 Business 订阅。
7. 由第二个个人账号在测试电脑完成 `10 / 10 / 0 / 0` 端到端验收后再发给运营。若要求任意个人账号无需管理员预关联即可使用，必须改用带 OAuth 的稳定公共 HTTPS MCP。

## 运营人员开箱即用流程

1. 从 OpenAI 官方渠道下载并安装 Codex。
2. 使用运营自己的个人版 ChatGPT/OpenAI 账号登录 Codex；不要检查或要求公司工作区。
3. 将公开唯一安装链接 [amazon-ads-codex-marketplace](https://github.com/p1524607703-blip/amazon-ads-codex-marketplace) 粘贴给 Codex，并发送：

```text
请直接为我安装并验收公司的亚马逊广告运营只读插件：https://github.com/p1524607703-blip/amazon-ads-codex-marketplace
```

安装、pgAdmin/RDS 凭据禁令、权限验收和失败保护均由 GitHub 仓库内的 README 与插件 Skill 自动提供，不再要求运营复制长指令。

4. Codex 先安装 `amazon-ads-ops-personal-installer`。若负责人备份的固定应用映射不能用于当前账号，则由安装器在当前个人空间创建连接并生成个人本地插件；员工不需要填写数据库地址、密码或 Tunnel runtime key。
5. 新建 Codex 任务，让它调用 `get_ads_data_context` 验收。
6. 验收通过后，运营可在 Codex 中让 AI 查询和分析，也可在其个人版 ChatGPT 网页端使用自己已连接的同名只读应用。

> [!warning]
> 如果出现 `import_ad_report`、`execute_database_admin_sql`、`create_*`、`update_*`、`delete_*` 或 `upsert_*`，立即停用该连接并联系管理员。不要尝试自行修复权限。

## 验收标准

| 指标 | 必须等于 |
|---|---:|
| 总工具数 | 10 |
| 只读工具数 | 10 |
| 写入工具数 | 0 |
| 数据库管理员工具数 | 0 |

再执行三项业务检查：查询最近报告入库健康、查询一条活动的近期表现、查询成熟归因结果。返回真实数据或明确空集即可；全过程不得产生任何写入。

## 网页端使用说明

- 网页端应用由安装器在目标个人账号中连接或注册；运营无需也不得复制负责人现有 25 权限应用。
- 如网页端缓存了旧工具目录，关闭旧会话并新建聊天；不要修改现有插件来“刷新”。
- 运营只获得应用使用权，不获得 Tunnel 管理权、runtime key 或 RDS 权限。
- 负责人继续使用原 25 工具插件；运营只使用名字明确带“运营只读”的新应用。

## GitHub 发布规则

- 仓库可以公开，但只能包含公开安装资料；GitHub 可见性不得承担数据权限控制。
- 允许提交：插件清单、只读 Skill、安装说明和无密钥的验收脚本。
- 禁止提交：RDS 域名/IP/账号/密码、证书、Tunnel ID、runtime/admin API key、OpenAI 密钥、本地日志、数据库备份和任何管理员 SQL 通道。
- 人员离职时撤销该个人账号的 Tunnel 关联和只读应用访问；公开仓库本身不作为权限边界。

## 常见故障

| 现象 | 处理 |
|---|---|
| Codex 找不到插件 | 确认网络可访问公开 GitHub，并让 Codex 重新添加 Marketplace |
| 首次安装要求授权 | 正常安全步骤，确认应用名称带“运营只读”后继续 |
| 提示没有公司工作区 | 安装说明错误；个人版是支持目标，不需要 Business 或公司工作区 |
| 个人账号看不到 Tunnel | 管理员把该账号的个人 Platform 组织/ChatGPT 个人空间加入运营只读 Tunnel 关联；不要索取 RDS 密码 |
| 工具不是 10 个 | 立即停止；管理员检查是否误绑现有 25 工具应用 |
| 查询失败 | 管理员检查独立 Tunnel、只读 MCP 和 RDS 只读账号，不让员工配置数据库 |
| 网页端仍显示旧目录 | 新建聊天或重新关联只读应用，禁止改动现有插件 |

## 官方参考

- [OpenAI：Codex 插件](https://developers.openai.com/plugins/build/plugins)
- [OpenAI：Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [OpenAI：Codex MCP](https://developers.openai.com/codex/mcp)
- [OpenAI：ChatGPT Developer mode](https://developers.openai.com/api/docs/guides/developer-mode)
