---
tags: [SOP, AI工程, Codex, ChatGPT, 阿里云RDS, MCP]
date: 2026-08-20
status: 现行
---

# 运营AI接入阿里云RDS与ChatGPT网页端SOP

> [!summary] 摘要
> 运营人员必须安装 Codex，并使用各自的个人版 ChatGPT/OpenAI 账号通过公开 GitHub 安装无绑定的“亚马逊广告运营只读个人版安装器”，不要求 Business 或公司工作区。现有网页端 25 权限插件永久保留不动；运营版只提供 10 个查询工具，不包含导入、增删改、任意 SQL 或管理员能力。

## 核心知识

### 1. 永久隔离原则

- 负责人现用的“亚马逊广告数据分析与运营-v2”保留 25 个工具，禁止为测试或运营接入修改其 MCP 注册、隧道、OpenAI 应用或数据库角色。
- 运营使用“亚马逊广告数据分析（运营只读）”，恰好 10 个查询工具；写入工具和管理员工具均为 0。
- 运营版是完整独立副本，不是在现有应用上切换只读模式。

### 2. 架构

```text
运营电脑的 Codex / ChatGPT 网页端（个人账号）
    ↓ 公开 GitHub 无绑定安装器 + 账号专属只读应用映射
独立 Secure MCP Tunnel
    ↓
独立只读 MCP（10 个固定查询工具）
    ↓
腾讯云库独立只读角色 ads_readonly（强制只读事务；经本机 SSH 隧道访问）
```

员工电脑不加入 RDS 白名单，不保存 RDS 密码、证书、Tunnel ID、runtime key 或管理员密钥。

### 3. 管理员上线流程

1. 部署只读 MCP，只注册数据口径、产品分类、导入健康、近期表现、成熟归因、活动日趋势、TIB、待复查、归因刷新到期和已管理活动查询。
2. 为进程使用独立数据库登录角色，只授予必要对象 `SELECT` 并强制只读事务。
3. 新建独立 Tunnel 与独立 OpenAI 应用；任何测试不得触碰 `amazon-ads-local` 和现有 25 工具应用。
4. GitHub 发布无固定应用 ID 的个人版安装器；负责人现有固定 `.app.json` 只作为恢复备份，不视为跨账号授权。
5. 使用 Secure MCP Tunnel 时，把获准运营的个人 Platform 组织和 ChatGPT 个人空间加入 Tunnel 关联范围；不要求 Business。
6. 必须在第二个个人账号上完成总工具 10、只读 10、写入 0、数据库管理员 0 的端到端验收后，才向运营发布链接。

### 4. 运营开箱即用流程

1. 下载并安装 OpenAI Codex。
2. 使用运营自己的个人版 ChatGPT/OpenAI 账号登录，不检查或要求公司工作区。
3. 把公开唯一安装链接 [amazon-ads-codex-marketplace](https://github.com/p1524607703-blip/amazon-ads-codex-marketplace) 交给 Codex，并要求它先安装 `amazon-ads-ops-personal-installer`。
4. 由安装器在当前个人账号中连接或注册名称明确带“运营只读”的应用，并生成个人本地插件；不要输入任何数据库或隧道密钥。
5. 新建任务调用 `get_ads_data_context`，确认 `10 / 10 / 0 / 0`。
6. 通过后即可用 Codex 分析；网页端则选择管理员发布的同名只读应用。

推荐给 Codex 的安装指令：

```text
请直接为我安装并验收公司的亚马逊广告运营只读插件：https://github.com/p1524607703-blip/amazon-ads-codex-marketplace
```

详细安装步骤、无需 pgAdmin、不得索取 RDS 凭据、10/10/0/0 验收和失败保护均内置在 GitHub README 与插件 Skill 中。

### 5. 失败保护

> [!warning] 发现越权工具立即停用
> 若工具目录出现 `import_ad_report`、`execute_database_admin_sql`、`create_*`、`update_*`、`delete_*` 或 `upsert_*`，立即停止使用并联系管理员。禁止通过修改现有 25 工具插件来排障。

### 6. GitHub 安全规则

- 仓库可以公开，但只能保存公开安装材料；GitHub 可见性不是数据权限边界。
- 只提交插件清单、只读 Skill、安装说明和无密钥验收内容。
- 不提交 RDS 地址/IP/账号/密码、证书、Tunnel ID、runtime/admin API key、日志、数据库备份或管理员 SQL 通道。
- 离职或转岗时撤销该个人账号的 Tunnel 关联和只读应用访问。

## 关联

- [[亚马逊广告数据分析与运营-v2插件]]
- [[阿里云RDS-amazon_ads-库表结构]]
- [[亚马逊TIB与广告报告数据沉淀方案]]

## 来源

- [OpenAI：Codex 插件](https://developers.openai.com/plugins/build/plugins)
- [OpenAI：Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels)
- [OpenAI：Codex MCP](https://developers.openai.com/codex/mcp)
- [OpenAI：ChatGPT Developer mode](https://developers.openai.com/api/docs/guides/developer-mode)
