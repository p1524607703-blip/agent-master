# ERRORS.md

错误记录

---

## [ERR-20260817-001] chatgpt_mcp_reboot_and_vpn_instability

**Logged**: 2026-08-17T22:31:00-04:00
**Priority**: high
**Status**: resolved
**Area**: infra

### Summary
Mac 重启后 ChatGPT 开发者 MCP 隧道没有自动恢复；首次补建的 LaunchAgent 又因
macOS 后台进程无法读取 Documents 目录及 MCP 命令路径含空格而失败。修复自启动后，
Cute Cloud 仍把中国区 RDS 连接置于不稳定的 TUN 路径，导致数据库连接间歇超时。

### Error
```text
ExceptionGroup: unhandled errors in a TaskGroup
Operation not permitted
fork/exec /Users/panjinlong/Library: no such file or directory
psycopg.errors.ConnectionTimeout: connection timeout expired
```

### Context
- 本地直接调用 MCP 工具可以访问阿里云 RDS，排除了 CSV、数据库结构和 GPT 权限问题。
- 重启后没有 tunnel-client/MCP 进程，也没有隧道健康文件。
- LaunchAgent 直接执行 Documents 中的脚本会被 macOS 隐私保护拒绝。
- tunnel-client 将带空格的 stdio 命令路径截断，需要无空格启动器。
- Cute Cloud 添加中国区 RDS 域名和 `121.41.134.56/32` 最高优先级 DIRECT 后，
  只读连接 10/10、管理员连接 3/3 通过。
  > ⚠️ 2026-09-21 更正：`121.41.134.56` 已整机退役（**现行主库改为
  > `pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com`，解析到 `47.110.28.12`**）。
  > Cute Cloud 的 DIRECT 规则需同步改为新域名 + `47.110.28.12/32`，否则代理规则命中不到新库。

### Suggested Fix
本地 ChatGPT MCP 应使用 LaunchAgent 的 RunAtLoad + KeepAlive，运行时部署到
`~/Library/Application Support`，stdio 入口放在无空格的 `~/.local/bin`。
中国区 RDS 域名和公网 IP 必须在 Cute Cloud 中显式 DIRECT，不能只依赖最终 GEOIP
规则；登录时先等待 VPN/OpenAI 网络就绪，再启动隧道。

### Metadata
- Reproducible: yes
- Related Files: `/Users/panjinlong/Documents/amazon-ads-data/scripts/tunnel-service`,
  `/Users/panjinlong/Documents/amazon-ads-data/scripts/deploy-tunnel-runtime`,
  `/Users/panjinlong/Library/LaunchAgents/com.panjinlong.amazon-ads-tunnel.plist`

---

## [ERR-20260806-001] local_postgresql_setup_verification

**Logged**: 2026-08-06T09:10:00Z
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
本地 PostgreSQL 安装先被过旧 Homebrew 的新版 bottle 安装步骤阻止；服务重启后的首次认证循环又因未等待就绪且未启用失败即停，产生了错误的成功尾行。

### Error
```text
Error: unknown install step: run
connection to server at "127.0.0.1", port 5432 failed: Connection refused
```

### Context
- Homebrew 6.0.2 无法处理 `ca-certificates` 新版 bottle 的 `run` 安装步骤。
- 更新 Homebrew 核心程序并重装 `ca-certificates` 后，PostgreSQL 16.14 安装成功。
- `brew services restart` 返回后，PostgreSQL 仍需要短暂启动时间。
- 首次循环没有 `set -e`，因此中间连接失败后仍执行了最后的成功提示。

### Suggested Fix
更新 Homebrew 后再安装新 bottle；服务重启后先用 `pg_isready` 等待就绪。所有认证和数据导入验收脚本必须启用 `set -e`，并以查询结果断言作为成功条件，不能只依赖最后一条输出。

### Metadata
- Reproducible: yes
- Related Files: `/opt/homebrew/var/postgresql@16/pg_hba.conf`, `/opt/homebrew/var/postgresql@16/postgresql.conf`

### Resolution
- **Resolved**: 2026-08-06T09:12:00Z
- **Notes**: Homebrew 已更新，PostgreSQL 16.14 已安装；再次使用失败即停和逐角色结果断言复测，全部 SCRAM 登录成功。

---

## [ERR-20260712-001] lark-doc-reference-install

**Logged**: 2026-07-12T23:30:00-04:00
**Priority**: high
**Status**: pending
**Area**: docs

### Summary
本机 `lark-doc` Skill 的 `SKILL.md` 要求读取 XML、样式和创建工作流参考文件，但安装目录中缺少这些必读文件。

### Error
```text
sed: /Users/panjinlong/.agents/skills/lark-doc/references/lark-doc-xml.md: No such file or directory
```

### Context
- 尝试按 `lark-doc` 的前置条件读取 `references/lark-doc-xml.md`、`references/style/lark-doc-style.md` 和 `references/style/lark-doc-create-workflow.md`。
- 当前安装目录仅包含部分 references，缺少 XML 与 style 子目录。

### Suggested Fix
重新安装或更新飞书 Skills 包，确保 `SKILL.md` 声明的所有 references 随包分发；修复前创建文档时只能使用现有 Markdown 参考或 CLI 帮助作为降级路径。

### Metadata
- Reproducible: yes
- Related Files: `/Users/panjinlong/.agents/skills/lark-doc/SKILL.md`

---

## [ERR-20260609-001] dingtalk_aitable_eventual_consistency

**Logged**: 2026-06-09T08:31:14Z
**Priority**: low
**Status**: resolved
**Area**: data

### Summary
钉钉 AI 表格新增记录成功后，立即查询可能暂时返回 0 条。

### Error
```text
audience_segments_amer_inmarket verification failed: expected 6, got 0
```

### Context
- Command/operation attempted: 创建 Subscriptions 数据表记录后立即回读验证。
- 实际情况: 数秒后重新查询可正常读取全部 6 条记录。

### Suggested Fix
钉钉 AI 表格写入后的验证应采用短间隔轮询，避免把异步落库延迟误判为写入失败。

### Metadata
- Reproducible: yes
- Related Files: `.tmp/dingtalk-subscriptions/import-subscriptions.mjs`

---

## [ERR-20260608-001] lark_cli_docs_create_absolute_path

**Logged**: 2026-06-08T03:27:23Z
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
`lark-cli docs +create` 不接受 `--content` 指向当前目录之外的绝对路径。

### Error
```text
--content: invalid file path: --file must be a relative path within the current directory
```

### Context
- Command/operation attempted: 使用绝对路径提交飞书文档 XML。
- Resolution: 切换到 XML 文件所在目录，并改用 `@./filename.xml`。

### Suggested Fix
调用 `lark-cli docs +create` 或 `docs +update` 时，先将工作目录切到内容文件目录，再传相对路径。

### Metadata
- Reproducible: yes
- Related Files: `.tmp/asi-lark/skeleton.xml`

---

## [ERR-20260605-003] github_publish_network_and_app_access

**Logged**: 2026-06-05T08:22:52Z
**Priority**: high
**Status**: pending
**Area**: infra

### Summary
Hermes 状态策略提交已在本地创建，但 HTTPS 推送持续超时，GitHub App 对目标仓库的写入接口返回 404。

### Error
```text
fatal: unable to access 'https://github.com/p1524607703-blip/amc-hermes-skills.git/':
Failed to connect to github.com port 443

GitHub API error 404: Not Found
```

### Context
- Local branch: `codex/hermes-status-policy-sync`
- Local commit: `6647334`
- `gh auth status` succeeded.
- Direct `curl https://github.com` also timed out.
- GitHub App branch creation could not access the repository for writes.

### Suggested Fix
网络恢复后执行 `git push -u origin codex/hermes-status-policy-sync`，再创建 PR；如 App 仍返回 404，检查 GitHub App 是否获准访问 `p1524607703-blip/amc-hermes-skills`。

### Metadata
- Reproducible: yes
- Related Files: `/Users/panjinlong/Documents/amc-hermes-skills`

---

## [ERR-20260605-002] git_push_unrelated_histories

**Logged**: 2026-06-05T08:22:52Z
**Priority**: medium
**Status**: resolved
**Area**: infra

### Summary
`amc-hermes-skills` 本地 `main` 与远端 `main` 来自两套独立初始化历史，直接推送被拒绝。

### Error
```text
! [rejected] main -> main (non-fast-forward)
error: failed to push some refs
```

### Context
- Command attempted: `git push origin main`
- Local and remote branches had no merge base.
- The required Hermes status-policy files existed only in the local tree.

### Suggested Fix
以 `origin/main` 创建协作分支，只从本地分支迁移所需文件，提交后推送新分支并通过 PR 合并；不要强推或合并无关历史。

### Metadata
- Reproducible: yes
- Related Files: `/Users/panjinlong/Documents/amc-hermes-skills`

### Resolution
- **Resolved**: 2026-06-05T08:22:52Z
- **Notes**: Adopted a remote-based collaboration branch and scoped file migration.

---

## [ERR-20260605-004] gh_api_query_shell_glob

**Logged**: 2026-06-05T07:05:03Z
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
`gh api` 路径包含 `?ref=main` 时未加引号，被 zsh 当作 glob 解析。

### Error
```text
zsh:1: no matches found: ...AsinAudiencePage.vue?ref=main
```

### Context
- 用 GitHub Contents API 核验默认分支文件。
- 给完整 API 路径加单引号后成功。

### Suggested Fix
所有包含 `?`、`&` 等查询字符的 `gh api` 路径都用单引号包裹。

### Metadata
- Reproducible: yes
- Related Files: `/Users/panjinlong/Documents/amc-hermes-dashboard`

---

## [ERR-20260605-003] github_https_timeout

**Logged**: 2026-06-05T06:30:00Z
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
使用 `git ls-remote` 实时核验 GitHub 分支时连接超时，改用已 fetch 的本地远程引用完成核验。

### Error
```text
fatal: unable to access 'https://github.com/p1524607703-blip/amc-hermes-dashboard.git/':
Failed to connect to github.com port 443 after 75002 ms
```

### Context
- GitHub HTTPS 出站连接短暂不可用。
- `refs/remotes/origin/*` 已包含此前成功 fetch/push 的分支提交。

### Suggested Fix
短暂网络超时时不要重复执行写操作；先用本地 remote refs 回答分支结构，恢复连接后再 fetch 验证。

### Metadata
- Reproducible: unknown
- Related Files: `/Users/panjinlong/Documents/amc-hermes-dashboard`
- See Also: ERR-20260605-002

---

## [ERR-20260605-002] gh_pr_view_timeout

**Logged**: 2026-06-05T04:35:00Z
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
草稿 PR 已成功创建，但随后用 `gh pr view` 二次读取时 GitHub GraphQL 请求超时。

### Error
```text
Post "https://api.github.com/graphql": dial tcp 20.205.243.168:443: i/o timeout
```

### Context
- PR 创建命令已返回成功 URL：`https://github.com/p1524607703-blip/amc-hermes-dashboard/pull/1`
- 本地分支与远程跟踪分支提交一致。

### Suggested Fix
PR 创建已有权威成功响应时，不因一次只读校验超时重复创建 PR；保留返回 URL，并在需要时稍后重试查询。

### Metadata
- Reproducible: unknown
- Related Files: `/Users/panjinlong/Documents/amc-hermes-dashboard`

---

## [ERR-20260605-001] lark_docs_update_format_flag

**Logged**: 2026-06-05T04:25:04Z
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
`lark-cli docs +update` 不支持 `--format` 参数，去掉该参数后即可执行文档更新。

### Error
```text
Error: unknown flag: --format
```

### Context
- Command/operation attempted: 向现有飞书文档追加网页端整改落地记录。
- CLI version: 1.0.45.

### Suggested Fix
`docs +fetch` 可使用 `--format json`，但当前版本的 `docs +update` 直接输出 JSON，不要附加 `--format`。

### Metadata
- Reproducible: yes
- Related Files: `/Users/panjinlong/.agents/skills/lark-doc/references/lark-doc-update.md`

---

## [ERR-20260521-001] hatch_pet_python_command

**Logged**: 2026-05-21T03:04:55Z
**Priority**: low
**Status**: resolved
**Area**: infra

### Summary
运行 hatch-pet 脚本时，系统没有 `python` 命令；改用 `python3` 后脚本正常执行。

### Error
```text
zsh:1: command not found: python
```

### Context
- Command/operation attempted: `python /Users/panjinlong/.codex/skills/hatch-pet/scripts/prepare_pet_run.py --help`
- Resolution: use `python3` for hatch-pet scripts in this workspace.

### Suggested Fix
以后调用本机 Python 脚本时优先使用 `python3`，除非项目明确配置了虚拟环境入口。

### Metadata
- Reproducible: yes
- Related Files: `/Users/panjinlong/.codex/skills/hatch-pet/scripts/prepare_pet_run.py`

---

## [ERR-20260520-001] local_chart_generation

**Logged**: 2026-05-20T07:14:16Z
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
生成广告组合分析仪表盘时，默认运行时缺少 `matplotlib`，随后改用 PIL 绘制图表。

### Error
```text
ModuleNotFoundError: No module named 'matplotlib'
```

### Context
- Command/operation attempted: 使用 bundled Python 读取 CSV 并用 matplotlib 输出组合分析图。
- Input: `/Users/panjinlong/Downloads/广告组合 Portfolios_5月_19_2026.csv`

### Suggested Fix
做轻量文档图表时优先使用已确认可用的 PIL；只有在确认 matplotlib 可用时再使用 matplotlib。

### Metadata
- Reproducible: yes
- Related Files: `wiki/attachments/amazon-ads-portfolio/portfolio-analysis-dashboard.png`

---

## [ERR-20260520-002] pil_line_arguments

**Logged**: 2026-05-20T07:14:16Z
**Priority**: low
**Status**: resolved
**Area**: docs

### Summary
PIL `ImageDraw.line` 调用时把起点和终点作为两个位置参数传入，导致 `fill` 参数冲突；修正为传入点列表。

### Error
```text
TypeError: ImageDraw.line() got multiple values for argument 'fill'
```

### Context
- Command/operation attempted: 绘制广告组合页面结构示意图的编号引导线。

### Suggested Fix
使用 `draw.line([point_a, point_b], fill=color, width=...)`，不要写成 `draw.line(point_a, point_b, fill=...)`。

### Metadata
- Reproducible: yes
- Related Files: `wiki/attachments/amazon-ads-portfolio/portfolio-page-structure.png`

---
