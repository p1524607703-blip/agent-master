# LOG — 变更日志

> 按时间倒序记录每次知识库变更。每次 Ingest / Update / Lint / Archive 操作后必须追加记录。

---

## 2026-09-27

- **类型**: Update / Correction
- **操作**: 修正 BA 下载管理器「清理」的假信号，并更新 SQP 周覆盖
- **涉及**: `ba-export/ba_sqp_weekly.py`、`wiki/AI工程/Amazon-Brand-Analytics-SQP与SCP-口径与现状.md`、`logs/LOG.md`
- **摘要**: BA SQP 周更任务正常跑完（目标周 2026-09-26，灌库 1000 行，WHITIN 由 28 周 → **29 周 / 29,000 行**，覆盖 2026-03-14→2026-09-26）。过程中实测证伪了一个长期假象：**Amazon BA 下载管理器没有任何删除入口** —— 行内永远只有「下载」按钮，表头 8 个 `more_vert` 全是列宽拖拽把手，真实 pointer 悬停也不揭示隐藏菜单；`node.remove()` 只摘当前 DOM，刷新即重现（实测日志写「已移除」后 37 秒行仍在）。已把 `remove_dm_row()` / `prune_dm()` 的日志措辞改为「已从当前页面摘掉（客户端，刷新会重现）」，并在 wiki 页新增第 5 节说明「防重复靠目标周匹配 + 灌库幂等，不靠 DM 清理」。未触碰任何 Amazon 账号 / 广告设置。

---

## 2026-09-22

- **类型**: Organize / Index Rebuild
- **操作**: 按 Karpathy 三层结构归位散落知识文章与广告资料，重建 Wiki 索引
- **涉及**: `wiki/`、`raw/广告数据/Y10/`、`logs/INDEX.md`、`logs/LOG.md`
- **摘要**: 将 6 篇根目录知识文章归入个人成长、SOP、跨境电商与 AI 工程主题；将 Y10 原始广告导出移入 `raw/` 并保留原文件名，将广告分析交付物移入 `wiki/attachments/`；为迁入页面补齐基础元数据、摘要、关联和来源说明；根据当前 151 篇 Wiki Markdown 页面重建索引，并新建个人知识库导航。未修改原有 `raw/` 文件内容，也未改动代码项目。


## 2026-09-21

- **类型**: Query / Create / Update
- **操作**: 沉淀 BA 报告口径，并补齐旧库退役后的文档缺口
- **涉及**: `wiki/AI工程/Amazon-Brand-Analytics-SQP与SCP-口径与现状.md`（新建）、`wiki/AI工程/阿里云RDS-amazon_ads_v2-库表结构.md`、`logs/INDEX.md`、`logs/LOG.md`
- **摘要**: 回答「SCP 是干什么的」——SQP 按**搜索词**切、SCP 按 **ASIN/目录条目**切，SCP 是 BA 里唯一以商品为行主键的漏斗报告，且自带「展示时价格/配送/可售状态」，用于把转化差归因到价格带或配送；它也是唯一能直接对接 `app.child_asin_mapping` 运营组归属的 BA 报告。同时核实：现行主库 `amazon_ads_v2` **没有** `search_catalog_performance_*` 任何表（旧库 30,177 行 / 2024-08-31→2026-08-29 已随旧库退役），故 SCP 当前悬空，并写明「只 CREATE 不 DROP」的复活三步。顺带把 2026-09-21 新建的 v2 库表结构页与已退役旧库页一并登记进 INDEX。

## 2026-09-02

- **类型**: Query / Create
- **操作**: 研究并沉淀 DeerFlow 咨询分析 Skill 方法评估
- **涉及**: `wiki/AI工程/工具参考/DeerFlow咨询分析Skill方法与评估.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 核对 ByteDance DeerFlow 2.0 仓库、`consulting-analysis` 最新 `SKILL.md` 及文件历史，整理“分析框架 → 外部采数与制图 → 咨询报告”的两阶段职责、数据契约、真实性协议、图文叙事和质量检查；评估其证据追踪、心理推断、数据质量、固定篇幅和执行闭环缺口，并提出适配本知识库三层架构的四段式方案。未修改 `raw/`。

## 2026-09-01

- **类型**: Update / Publish
- **操作**: 精简 Pacvue AMC 飞书教程
- **涉及**: 飞书文档 `USm9dZaDDo93b7x2uuJceshZnKh`, `wiki/SOP与工作流/Pacvue-AMC激活与DSP-SA批量数据导出SOP.md`, `logs/LOG.md`
- **摘要**: 按用户要求覆盖精简飞书教程，仅保留原 3.2“当前 Pacvue AMC 激活页模板”、第六章“AMC 分析报告与受众实验”、7.2“常规数据导出频率”和第九章“导出后质量检查”，并重排为连续四章；飞书链接保持不变，目录核验确认其他章节均已删除。本地完整 SOP 继续保留，来源标签改为“飞书精简教程”。

- **类型**: Query / Create / Publish
- **操作**: 创建 Pacvue AMC 激活与 DSP/SA 批量数据导出教程
- **涉及**: 飞书文档 `USm9dZaDDo93b7x2uuJceshZnKh`, `wiki/SOP与工作流/Pacvue-AMC激活与DSP-SA批量数据导出SOP.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 结合 Pacvue 当前 `adsboostorwhitinsneakerus` AMC 激活控制台、Pacvue 官方接入/回填/报表口径文档及 Amazon Ads 官方 AMC audience 说明，整理 DSP → AMC 授权顺序、SA Entity 前置授权、Measurement/Audience 边界，以及第一批 6 份 Sponsored Ads、5 份 DSP、4 份 AMC 报告清单；补充字段、90 天按日导出、频率、命名、数据质量、历史窗口差异和 WHITIN 三天执行计划。教程已发布为飞书 Docx，创建受众、应用投放和预算/出价修改仍要求人工确认。

## 2026-08-25

- **类型**: Query / Create
- **操作**: 编写 pgAdmin 连接阿里云 RDS PostgreSQL 操作指南
- **涉及**: `wiki/SOP与工作流/pgAdmin连接阿里云RDS-PostgreSQL操作指南.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 结合当前 amazon_ads 实例配置与阿里云、pgAdmin、PostgreSQL 官方文档，整理连接信息准备、内外网选择、最小范围 IP 白名单、Verify-Full SSL 与 PEM 根证书、pgAdmin 字段填写、只读 SQL 验收、常见错误排查和安全检查清单；明确普通运营不获取 RDS 凭据，直连人员不使用裸 IP、不开放 0.0.0.0/0，管理员账号仅用于维护。

## 2026-08-24

- **类型**: Query / Security Review / Ingest
- **操作**: 审计 FBA 重测与退款导出的 IP 暴露和亚马逊店铺关联风险
- **涉及**: `wiki/SOP与工作流/亚马逊多店铺自动化-IP暴露与关联风险控制.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 审计紫鸟 FBA 重测 Skill、ZClaw 单步脚本和插件全量关键词，确认现有重测流程只控制指定紫鸟店铺标签页，无独立 HTTP/API 直连；当前 5 个店铺绑定 IP 均存在且互不重复。结合紫鸟官方设备网络与“本地访问网页”规则、IETF WebRTC IP 隐私规范及 AWS 请求日志字段，明确浏览器内导出、外部下载器/脚本二次请求、WebRTC 旁路和本地访问域名的风险边界，并建立上线检查清单。当前插件未发现独立退款导出模块，需在具体实现出现后补充下载域名与落地方式验收。

## 2026-08-21

- **类型**: Query / Ingest / Update
- **操作**: 建立亚马逊 FBA 重量和尺寸重新测量申请 SOP，并校正紫鸟生产适配边界
- **涉及**: `wiki/SOP与工作流/亚马逊FBA重量和尺寸重新测量申请SOP.md`, `wiki/AI工程/工具参考/紫鸟CLI功能指南.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 根据用户提供的 6 张 Amazon Seller Central 标注截图，将“输入 FNSKU → 选择重新测量及配送费赔偿 → 读取资格 → 选择无自有测量数据 → 包装未变化但 Amazon 测量错误 → 选择真实包装类型 → 继续”的页面操作整理为影刀可实现的标准流程；增加输入字段、文本优先元素定位、资格文案放行、状态码、批量防重、不可逆动作不重试、截图与工单编号留痕规则。因截图未覆盖最终成功页，将步骤 10“继续”和最终成功核验拆开，未知提交页必须暂停。同步记录用户确认的当前生产边界：macOS 下紫鸟浏览器自动化以影刀适配为准，ZClaw 在重新端到端验收前不作为生产路径。

- **类型**: Correction / Personal Account Distribution
- **操作**: 将亚马逊广告 Codex 插件分发从错误的公司工作区前提改为个人版无绑定安装器
- **涉及**: `docs/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `wiki/SOP与工作流/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, 两个 Amazon Ads GitHub Marketplace
- **摘要**: 根据测试机反馈，移除 Business/公司 OpenAI 工作区前提，明确 GitHub 备份不能复制个人账号的应用授权；运营和开发部仓库分别新增个人版安装器，由 Codex 为目标个人账号生成专属应用映射。现有 10 工具只读应用、25 工具管理员应用及两个生产 Tunnel 均不修改。Secure MCP Tunnel 仍需关联目标个人 Platform 组织/ChatGPT 个人空间；任意个人账号完全自助分发则需带 OAuth 的公共 HTTPS MCP。本条纠正取代此前日志中的公司工作区前提。

- **类型**: Publish / Security Hardening / Verification
- **操作**: 发布开发部专用 25 工具管理员 Codex 插件到私有 GitHub
- **涉及**: `wiki/AI工程/亚马逊广告数据分析与运营-v2插件.md`, `logs/LOG.md`, 私有仓库 `p1524607703-blip/amazon-ads-admin-codex-marketplace`
- **摘要**: 新建私有 Marketplace `amazon-ads-admin-team` 和插件 `amazon-ads-admin-full-access`，绑定负责人现用的同一个“亚马逊广告数据分析与运营-v2”应用，不修改生产 Tunnel、MCP 或 RDS 权限。实时验收仍为 25 个工具（10 读、14 个受控写、1 个数据库管理员），应用专属权限为“允许所有操作”；仓库当前及历史敏感项命中 0，本机已从私有 GitHub 安装并确认 enabled。后续已按本日纠正改为每位开发人员使用自己的 GitHub 与个人版 ChatGPT/OpenAI 账号，并为各自账号生成应用映射。

## 2026-08-20

- **类型**: Publish / Update
- **操作**: 将运营安装口令缩短为一句话并把全部注意事项内置到 GitHub 插件
- **涉及**: `docs/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `wiki/SOP与工作流/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `logs/LOG.md`, GitHub 仓库 `p1524607703-blip/amazon-ads-codex-marketplace`
- **摘要**: 运营现在只需向 Codex 发送“请直接为我安装并验收公司的亚马逊广告运营只读插件”加 GitHub 地址。自动添加/刷新 Marketplace、安装、重新开任务、10/10/0/0 验收、不得安装 pgAdmin 等数据库客户端、不得索取 RDS 凭据以及不碰原 25 工具插件的规则均已写入公开 README 和插件 Skill；插件缓存版本已刷新、本机重新安装并确认 enabled。

- **类型**: Publish / Security Hardening
- **操作**: 将运营只读 Codex 插件仓库改为 Public 并清理历史关联
- **涉及**: `docs/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `wiki/SOP与工作流/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `wiki/AI工程/亚马逊广告数据分析与运营-v2插件.md`, `logs/LOG.md`, GitHub 仓库 `p1524607703-blip/amazon-ads-codex-marketplace`
- **摘要**: 按用户要求将安装仓库改为公开分发。公开前扫描当前文件和全部提交历史，确认无 RDS 地址、密码、证书、Tunnel ID、API key 或客户数据；因旧历史曾包含另一个应用技术标识，发布前将远端主分支整理为只包含当前运营只读版的干净根提交，并在本机受限目录保留可恢复备份。仓库公开不改变权限边界，数据仍只对获准的公司 OpenAI 工作区成员开放，后端继续保持 10 个只读工具、0 写入、0 管理员能力，原 25 工具插件不变。

- **类型**: Publish / Verification / Security Hardening
- **操作**: 上线独立运营只读插件并完成 Codex、ChatGPT 网页端和 GitHub 分发验收
- **涉及**: `docs/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `wiki/SOP与工作流/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `logs/LOG.md`, 私有仓库 `p1524607703-blip/amazon-ads-codex-marketplace`
- **摘要**: 新建并连接“亚马逊广告数据分析（运营只读）”应用，独立 Tunnel 与只读 MCP 运行正常；实际工具目录验收为总工具 10、只读 10、写入 0、数据库管理员 0，并使用 RDS 独立只读角色和只读事务。私有 GitHub Marketplace 已发布且本机 Codex 安装成功，SOP 回填唯一安装链接。原“亚马逊广告数据分析与运营-v2”仍为 25 个工具，原生产 Tunnel 和现有应用均未修改。

- **类型**: Update / Security Hardening
- **操作**: 将运营接入方案改为 Codex 必装、GitHub 私有分发和独立 10 工具只读副本
- **涉及**: `wiki/SOP与工作流/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `wiki/AI工程/亚马逊广告数据分析与运营-v2插件.md`, `docs/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 按用户确认的产品路线，明确运营必须安装 Codex，并由 Codex 从公司私有 GitHub Marketplace 安装插件；现有网页端 25 工具生产插件及 `amazon-ads-local` Tunnel 永久保持不动。运营版改为独立 MCP、独立 RDS 强制只读角色、独立 Secure MCP Tunnel、独立 OpenAI 应用和独立 GitHub 插件包，验收口径固定为总工具 10、只读 10、写入 0、管理员 0；补充越权工具自动停用规则和员工无需接触任何数据库/隧道密钥的开箱流程。

- **类型**: Query / Ingest / Publish
- **操作**: 建立运营 AI 接入阿里云 RDS 与 ChatGPT 网页端 SOP，并准备 GitHub 脱敏公开版
- **涉及**: `wiki/SOP与工作流/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `docs/运营AI接入阿里云RDS与ChatGPT网页端SOP.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 核对 OpenAI 官方 MCP、ChatGPT Developer mode、Secure MCP Tunnel 文档与阿里云 RDS PostgreSQL 连接、白名单、SSL、权限文档，明确 ChatGPT 网页端不会读取本地 Codex 配置，运营电脑不需要直连 RDS。结合现有 amazon-ads-data MCP 与本机 Tunnel 实现，设计“运营专用 MCP（移除管理员 SQL 且运行时无管理员凭据）→ Secure MCP Tunnel → ChatGPT 开发者模式应用”的团队接入方案，补充管理员一次性配置、员工 5–10 分钟接入、只读验收、撤权、故障排查和 Codex 可选路径。因 GitHub 仓库为公开仓库，公开版只保留通用步骤和占位符，不写入 RDS 地址、实例 ID、Tunnel ID、runtime API key 或密码。

## 2026-08-17

- **类型**: Publish / Update
- **操作**: 将亚马逊自然单增长方法综述同步整理为飞书云文档
- **涉及**: 飞书文档 `Moe8dGQEFo30oexlswicv7CSnie`, `wiki/跨境电商/亚马逊自然单增长方法综述-2023至2026.md`, `logs/LOG.md`
- **摘要**: 将本地 Markdown 转换为飞书可读结构并创建《亚马逊自然单增长方法综述（2023–2026）》；完整保留 25 类方法频次与合理性排序、42 天方案、38 篇核心资料和 99 篇完整清单，原文 10 张配图全部转为飞书图片块。因用户身份 refresh token 已过期，使用在线的应用身份创建，CLI 已将当前飞书用户授予 full_access 可管理权限；随后通过飞书读取接口核对目录、图片数量和关键章节均完整，并把协作链接回填到本地知识页。

- **类型**: Query / Ingest
- **操作**: 扩展检索并建立 2023–2026 亚马逊自然单增长方法综述
- **涉及**: `wiki/跨境电商/亚马逊自然单增长方法综述-2023至2026.md`, `wiki/跨境电商/亚马逊自然单增长与广告依赖诊断.md`, `wiki/attachments/亚马逊自然单增长方法综述-2023至2026/`（10 张原帖图片）, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 使用知乎开放平台围绕自然单、广告依赖、关键词排名、TACOS、Listing 与广告位等 12 组查询检索 120 条结果，去重并限定 2023 年以后得到 99 篇资料；深读 38 篇核心帖（27 位作者，31 篇全文、7 篇搜索摘要，约 11.75 万字），按文档与作者去重把观点编码为 25 类方法，并结合 Amazon 官方 Sponsored Products、搜索词报告、广告位与 Search Query Performance 资料评估合理性。文档完整保留 99 篇筛选清单，给出高频方法排序、争议观点降级、42 天执行与停止条件，保存 10 张带来源说明的原文图；排除刷单、刷评和操纵行为，并明确广告类型/广告位直接提升自然排名没有官方因果证明。

- **类型**: Query / Update
- **操作**: 检索知乎帖子并建立亚马逊自然单增长与广告依赖诊断方案
- **涉及**: `wiki/跨境电商/亚马逊自然单增长与广告依赖诊断.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 使用知乎开放平台 CLI 分四组检索自然单不足、广告订单占比、关键词自然位、TACOS 与 Listing 承接，筛选 6 篇高相关帖子；结合 Amazon Ads 官方 Sponsored Products、搜索词报告和 Search Query Performance 资料，区分卖家经验与官方可验证能力，沉淀原因树、28 天最小数据包、关键词动作矩阵及 14 天执行方案。明确不以广告订单占比单指标决策、不默认 TOS 或某广告类型必然推自然位，并排除刷单等违规方法。

- **类型**: Update
- **操作**: 替换并验证知乎 CLI Access Secret
- **涉及**: macOS 钥匙串中的 `zhihu-cli` 凭证, `wiki/AI工程/工具参考/知乎开放平台CLI与MCP.md`, `logs/LOG.md`
- **摘要**: 按用户提供的新 Access Secret 更新 CLI 独立钥匙串凭证，通过 `auth status --verify` 在线验证及 `me contents --type all --limit 1` 最小业务验收；未在回复、日志或知识库记录密钥及其片段。旧 `zhihu_search` MCP 使用独立钥匙串条目，本次未修改。

- **类型**: Query / Update
- **操作**: 安装并初始化知乎官方 Skill/CLI，核对本地知乎 MCP
- **涉及**: `~/.codex/skills/zhihu`（Skill 0.3.0）, `~/Library/Application Support/zhihu-cli`（CLI 0.3.0）, `wiki/AI工程/工具参考/知乎开放平台CLI与MCP.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 从知乎开发者 CDN 下载并校验官方 Skill ZIP（SHA-256 `2af2647c468a366050a39dd78b8d844eccaeb679d91a56cd134573c0b383e4df`），安装 Skill 与 darwin-arm64 CLI 0.3.0；安全复用旧 `zhihu_search` MCP 钥匙串凭证完成 CLI 在线认证与最小本人内容读取验收。确认旧 MCP 是本地 `mcp-remote` 到知乎官方 SSE 的桥接器且仅提供站内搜索；新 CLI 另支持全网搜索、热榜、直答及本人内容。未记录凭证，旧 MCP 保持启用。

## 2026-08-13

- **类型**: Query / Update
- **操作**: 导入两账户 2026-W33 小时级报告入库并清理 incoming
- **涉及**: `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`；数据库批次 7/8/9/10
- **摘要**: 核对 data/incoming 下川鹏/欧德思两账户 4 个文件后，经 `amazon-ads-data scan` 将两小时级 CSV（08-02~08-08）写入 RDS：批次 7（川鹏 71,660 源行→70,110 事实行）、批次 9（欧德思 35,098→18,980），日级表未受污染；两"最近 30 天搜索词+广告位"XLSX 因 openpyxl 维度元数据缺失解析为 0 行且库内无搜索词/广告位表，隔离于 data/failed/2026-W33 待建表后重导；incoming 已清理至仅剩 .gitkeep。

- **类型**: Ingest
- **操作**: 摄入三个 ChatGPT 会话原始内容，重建当前主线工作知识体系
- **涉及**: `wiki/SOP与工作流/亚马逊广告数据优化-主线工作全景.md`, `wiki/跨境电商/亚马逊广告-分时竞价实验复盘-2026-08.md`, `wiki/跨境电商/亚马逊广告-日内规律与类目机会曲线方法论.md`, `wiki/跨境电商/亚马逊DSP与AMC-代理商方案与分析框架.md`, `wiki/AI工程/亚马逊广告数据分析与运营-v2插件.md`, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`（更新）, `wiki/SOP与工作流/主线任务.md`（更新）, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 完整读取三个 ChatGPT 会话（《会议纪要分析与任务整理》6 turns、《广告数据分析与优化》40 turns、《周会报告工作总结》6 turns）并核对 turnCount 一致后，沉淀为 1 个主线知识入口 + 4 个主题页：四大项目主线（分时/TIB、数据基础设施、DSP+AMC、方法论标准化）与 7 项待办；W8K6 预算规则与 ZJ1 三条分时竞价的完整复盘数字、三类结果与处理状态；账户级日内规律（06–11 高效率带/15–17 高吞吐带/18–20 第二转化窗口）与类目机会曲线方法论；DSP 代理商方案与 AMC 四路径框架；插件读写隔离架构与 19 工具。更新 TIB 沉淀方案实施现状（阿里云 RDS 已上线、UPSERT 回刷为当前最优先、上云推荐阿里云新加坡）并填充主线任务页。

- **类型**: Lint / Update
- **操作**: 自查修正本次摄入与数据库导出的逻辑错误并补充遗漏
- **涉及**: `wiki/AI工程/阿里云RDS-amazon_ads-库表结构.md`, `wiki/SOP与工作流/亚马逊广告数据优化-主线工作全景.md`, `wiki/跨境电商/亚马逊广告-日内规律与类目机会曲线方法论.md`, `wiki/跨境电商/亚马逊广告-分时竞价实验复盘-2026-08.md`, `wiki/跨境电商/亚马逊DSP与AMC-代理商方案与分析框架.md`, `wiki/AI工程/亚马逊广告数据分析与运营-v2插件.md`, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 修正 RDS 库表结构计数错误（实际 12 张表 + 7 个视图，原误写 13+6）；实测确认本地 PostgreSQL 127.0.0.1 为同结构开发副本（5 Schema、5 个导入批次）；实测确认 RDS 为覆盖式更新（8-06 批次 71,065 行已被 8-08 批次同窗口覆盖，DO NOTHING 排除）但无 raw_* 历史层，归因成熟速度研究暂不可做；补充"会话附件未包含在导出中"的来源完整性声明、会议"现在不要做"八件事、下次复盘五项检查；将全景页在途实验状态改为"会话结论（执行待确认）"，并标注 W8K6 15 点单小时两版数字差异。

- **类型**: Query / Update
- **操作**: 新建产品-类目映射表并导入两账户类目映射
- **涉及**: `amazon-ads-data/migrations/003_product_category_mapping.sql`（新建）, RDS 新表 `core.product_category_mapping`（466 行）, `wiki/AI工程/阿里云RDS-amazon_ads-库表结构.md`（重生成）, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 按用户确认口径（产品名=推广商品 SKU 第二段，类目=Amazon「推广的商品品类」中文翻译，16 个取值）解析川鹏/欧德思两账户推广商品报告 CSV 共 165,084 行，去重为 466 条映射幂等写入新表；发现同一产品名常对应多个 Amazon 大类（ASIN 变体分类差异），已记录使用注意；源 CSV 移入 data/archive/2026-W33、incoming 清空且保留子文件夹；另发现项目 migrate 命令因线上缺 ads_owner 角色失败（schema 实归 amazon_ads_admin），003 迁移已按此调整并经管理员直连执行。

- **类型**: Query / Update
- **操作**: 产品类目映射表回填父 ASIN、剔除未分类并计算主类目
- **涉及**: RDS `core.product_category_mapping`（395 行、109 产品、109 主类目）, `amazon-ads-data/migrations/003_product_category_mapping.sql`（加 row_count/is_primary 列）, `outputs/产品主类目与全类目清单-2026-08-13.csv`, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 删除 71 行"未分类"（含 WHITIN W96/Z30/Z31/Z32 四个仅有未分类的产品）；为 395 行回填 parent_asin（父 ASIN 去重列表，个别 -1）与 row_count；按行数对每产品标记 is_primary 主类目（5 个产品主类目仅 1 行样本）；导出 109 个产品的"主类目+全类目清单"CSV。

- **类型**: Query / Update
- **操作**: 按人工口径回补水鞋/赤足鞋产品并修正主类目
- **涉及**: RDS `core.product_category_mapping`（400 行、113 产品）, `outputs/产品主类目与全类目清单-2026-08-13.csv`, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 用户人工口径：Z30/Z31/Z32 与 Z10 同属水鞋、W96 为赤足鞋；将 4 个产品加回（手工行，含行数与父 ASIN），Z10 新增"水鞋"手工主类目行并降级原有 6 条 Amazon 类目行为佐证；重新导出 113 产品的清单 CSV。

- **类型**: Query / Update
- **操作**: 按 K=Kids 命名规则修正水鞋家族与童鞋主类目
- **涉及**: RDS `core.product_category_mapping`（404 行）, `outputs/产品主类目与全类目清单-2026-08-13.csv`, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 用户口径：代号含 K=Kids、无 K=成人；据此将 Z10/Z20/Z21/Z30/Z31/Z32 定成人水鞋、Z1K01/Z1K02 定儿童水鞋，WK102/S8K2 主类目切为童鞋；审计发现并列出待确认项（含 K 但非 Kids 的低样本怪码 ABK39ABK34/BU30PK35/KBW94W9K01；无 K 但 Amazon 归童鞋的 C10/OA7D/YFP1）。

- **类型**: Query / Update
- **操作**: 删除失效产品并恢复 S8K2 运动鞋主类目
- **涉及**: RDS `core.product_category_mapping`（399 行、110 产品）, `outputs/产品主类目与全类目清单-2026-08-13.csv`, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 按用户确认删除失效产品 C10/OA7D/YFP1（5 行）；S8K2 主类目恢复"运动鞋"（用户说明其为儿童鞋的运动鞋产品，K 已隐含 Kids 属性）；重导清单 CSV。

- **类型**: Query / Update
- **操作**: 统一 W702 代号并细化赤足鞋主类目，演示 WK 系列 TIB×ROAS 时段分析
- **涉及**: RDS `core.product_category_mapping`（USW702→W702 更名，WK101=儿童赤足鞋、W96/W702=成人赤足鞋）, `outputs/产品主类目与全类目清单-2026-08-13.csv`, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 确认活动名 W702 与 SKU 代号 USW702 为同一产品（SKU 带 US 前缀），统一为 W702；赤足鞋家族主类目细化（WK101=儿童、W96/W702=成人）；用 core.campaign_hourly 演示 WK 系列（31 条活动）TIB 代理指标（90% 花费小时/最后花费小时/活跃小时）与三小时时段花费占比×成熟 ROAS 分布：WK101 高峰在 03-05(5.52)/15-17(5.79)、WK102 在 06-08(6.38)/15-17(6.02)，00-02 普遍最弱(0.92)。

- **类型**: Update / Lint
- **操作**: 重构类目映射为规范化四表两视图并完成覆盖率修复(Codex 审查要求 A-I)
- **涉及**: `amazon-ads-data/migrations/004_product_category_normalization.sql`（新增）, `amazon-ads-data/scripts/migrate_product_category.py`（新增）, `amazon-ads-data/scripts/audit_product_category.py`（新增）, RDS 新表 `core.product_alias / product_category_evidence / product_business_category / product_parent_asin` 与新视图 `analytics.v_product_category_flat / v_hourly_business_category`, 备份表 `core.product_category_mapping_bak_20260813` 与 `data/backups/product_category_mapping-2026-08-13.tsv`, `wiki/AI工程/阿里云RDS-amazon_ads-库表结构.md`（重生成）, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `outputs/产品主类目与全类目清单-2026-08-13.csv`, `logs/LOG.md`
- **摘要**: 按 Codex 只读审计结论修复类目映射：旧表 401 行快照备份并冻结；新建别名层(活动/SKU 双来源, 高置信自动解析 6 个如 BRY10→Y10、WTW8K2→W8K2、WTW51→W51, 36 个 needs_review 保留证据)、Amazon 原始类目证据(390 行)、业务主类目(110 产品, manual/amazon_dominant+置信度+原因可追溯, 每账户+标准产品唯一)、父 ASIN 桥接(105 行一行一值, 32 个 -1/非法值排除)；人工口径(WK102=童鞋、S8K2=运动鞋、水鞋/赤足鞋家族、失效产品)全部保留；活动脏命名经推广商品报告证据解析 20 个；修复后花费覆盖率 WHITIN 69.33%→88.90%、BLOOMNEXT 38.80%→99.33%，剩余未映射为多产品系列投放(如 W81女 覆盖 10 个产品代号)与失效产品(C10)；事实表行数与基线一致, 未做任何修改。**【⚠️ 本条首轮覆盖率结论已被 2026-08-14 Codex 第二轮复审纠正并作废:88.90% 系 needs_review 误计 mapped 且口径不一致所致;现行有效结论见下方"二轮整改"条目(WHITIN 71.42%→83.99%、BLOOMNEXT 38.80%→99.33%,双口径)。88.90% 请勿引用。】**

## 2026-08-13

- **类型**: Update / Lint
- **操作**: 类目映射二轮整改(Codex 复审 8 项要求)
- **涉及**: `amazon-ads-data/migrations/004_product_category_normalization.sql`, `amazon-ads-data/scripts/migrate_product_category.py`, `amazon-ads-data/scripts/audit_product_category.py`（重写）, RDS 约束(`CHECK(is_primary)`、alias 枚举加 `excluded`)与视图 `analytics.v_hourly_business_category`（仅 resolved 落业务类目）, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 修正 needs_review 误计入 mapped（视图仅 resolved 别名连接业务类目；W8K2 多产品活动不再计覆盖）；消除 9 个"resolved 但无业务类目"矛盾（新增 excluded 状态，C10=excluded 不恢复类目，其余降 needs_review）；业务主类目增加强约束 CHECK(is_primary)；两脚本 psql 失败即非零退出并验证错误传播（迁移注入测试 exit 1 数据回滚、审计坏查询 exit 2）；manual/USER_CONFIRMED/EXCLUDED 全部改 (account,code) 键防跨账户污染；覆盖率改为同一 derive 规则、product_line 与 derived_code 双口径且 mapped 仅计 resolved：修复前 WHITIN 442/563 lines、71.42%，BLOOMNEXT 50/73、38.80%（与 Codex 复核一致）；修复后 WHITIN 511/563、83.99%，BLOOMNEXT 67/73、99.33%；审计补事实表聚合基线（rows/impressions/clicks/spend/purchases/sales/max(updated_at) 全等）、视图聚合全等、旧表备份双向差异 0。

- **类型**: Update / Lint
- **操作**: 类目映射三轮整改(Codex 第二轮复审 6 项)
- **涉及**: `amazon-ads-data/migrations/004_product_category_normalization.sql`（去掉 DROP VIEW、封死视图语义后门）, `amazon-ads-data/scripts/audit_product_category.py`（epoch 毫秒基线常量、双口径覆盖率、main() 守卫）, `logs/LOG.md`
- **摘要**: 修复审计脚本在系统 python3 下崩溃的问题（max(updated_at) 基线改为 epoch 毫秒常量 1786677660136/1786065311179，与数据库 floor(epoch*1000) 同口径截断，±1ms 容差）；覆盖率补双口径（derived_code matched/total 与 product_line matched/total 并列：修复前 WHITIN codes 63/93 lines 442/563、BLOOMNEXT 12/23 与 50/73；修复后 WHITIN 81/93 与 511/563、BLOOMNEXT 18/23 与 67/73）；视图 j CTE 改为仅 alias resolution_status='resolved' 才设置 resolved_canon（无 alias 记录一律待确认，堵住同名映射后门），RDS 已重放且视图/事实六项聚合全等；004 去掉 DROP VIEW 改用 CREATE OR REPLACE 并注明旧结构升级路径；LOG 首轮 88.90% 结论已标注作废。审计以系统 python3 实际跑通，真实 exit code=0，全部 invariant PASS。

- **类型**: Query / Update
- **操作**: 川鹏 TIB 活动报告入库 campaign_tib_snapshot
- **涉及**: `amazon-ads-data/scripts/import_tib_snapshot.py`（新增）, RDS `core.import_batches`（批次 11）与 `core.campaign_tib_snapshot`（237 行）, `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 用户提供 `川鹏TIB数据7:1-8:9.csv`（Amazon 活动级 TIB 报告, 300 行, 周期 2026-07-01~08-09）：无活动 ID 列, 按活动名关联 hourly/daily 后匹配 237 行写入 `campaign_tib_snapshot`（SP 109 行, 其中 91 行有 TIB 值平均 85.25;SB/SD/ST 的 TIB 列为空——Amazon 仅 SP 提供该字段）；63 行未匹配均为 8/11~8/14 新建活动（小时级数据尚未覆盖）, 脚本幂等可重跑回填；文件副本已归档 data/archive/2026-W33。

- **类型**: Query / Update
- **操作**: 梳理活动命名与运营/产品线判定规则
- **涉及**: `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 从 amazon-ads-data 代码（parsers.product_line_from_name 取名称前两段）与 RDS 实测（core 表 product_line 含"XH1-W81女 视频""DD1-S81 展示"等脏值，managed_campaigns 为显式传入的精确值）确认现状规则与缺陷；归纳 8 个运营代号（WHITIN: ZJ1/XH1/ZF1/LB1/DD1/YT1；欧德思: XM1/XM2），提出 v2 判定规则（运营代号=首个"-"前缀、产品代号=第二段首个空格前、投放类型后缀不入产品线）并列入待办（修正解析函数、回刷脏值、建立 dim_owner 代号→人名映射）。

- **类型**: Query / Update
- **操作**: 梳理 deepseek-harness 四种 Agent 预设模式并记录模式切换约定
- **涉及**: `wiki/AI工程/deepseek-harness-四种Agent预设模式.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 按用户指示从 deepseek-harness 仓库（本地 checkout 的 apps/cli/config/agent-presets/*/preset.yml）确认四种内置预设：标准模式（standard，当前会话使用）、PTC 模式（code）、极简模式（minimal）、创造模式（cordis），记录各自官方描述与适用场景；约定后续每项任务由 AI 判断是否适合切换其他模式并在切换前提醒用户。

- **类型**: Query
- **操作**: 连接本地 pgAdmin 与阿里云 RDS，导出 amazon_ads 库表结构并沉淀为 wiki 页面
- **涉及**: `wiki/AI工程/阿里云RDS-amazon_ads-库表结构.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 从本地 pgAdmin 4 桌面版（~/.pgadmin/pgadmin4.db）定位「阿里云 RDS - amazon_ads」连接，经 macOS 钥匙串读取 amazon_ads_admin 密码，psql 以 sslmode=verify-full 直连 121.41.134.56:5432（PostgreSQL 18.3）导出结构：实例内 5 个数据库（_supabase / amazon_ads / postgres / rdsadmin / supabase_db）；amazon_ads 库 5 个 Schema（core / analytics / ops / chatgpt_ops / public）、12 张表 + 7 个视图、314 列、16 个主键/唯一约束、8 个外键、26 个索引，全量写入 wiki 页面并同步索引。

## 2026-08-06

- **类型**: Query / Update
- **操作**: 将广告数据方案升级为 PostgreSQL、BlazeSQL 与 Codex 分层架构
- **涉及**: `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 根据用户已下载 BlazeSQL 并确定采用 PostgreSQL 的决定，将原 SQLite 起步方案更新为 PostgreSQL 正式主库；明确 BlazeSQL 安装后不会自动授权当前 Codex 访问数据库，设计 `ads_ingest`、`ads_analyst`、`ads_operator` 最小权限角色，以及近期、成熟、复查到期、归因待刷新和导入健康分析视图；BlazeSQL 负责问答和看板，Codex 通过独立只读桥接完成 TIB 复核、知识沉淀与定期提醒。

- **类型**: Query / Update
- **操作**: 扩展广告报表入库、成熟刷新和活动跟进提醒设计
- **涉及**: `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 明确当前仅有方案文档、尚未创建专用 SQLite 数据库和自动任务；将成熟判断改为同时使用统计日期、广告产品和最新报表导出时间，增加成熟版本待刷新视图、近期/回填/成熟三种分析模式，以及 `campaign_watchlist`、复查日志、动作后过程与成熟验收时间、到期活动视图和每日文件扫描提醒流程。

- **类型**: Query / Update
- **操作**: 明确日级广告活动报告的月度导出时间
- **涉及**: `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/LOG.md`
- **摘要**: 将混合广告类型的日级报告固定为每月 16 日导出上一个完整自然月，使月末最后一天达到 14 天归因活动的成熟口径；补充仅 Seller SP 可提前至每月 9 日、滚动区间受限时改导最近 60 天并通过 Upsert 锁定上月的执行规则。

- **类型**: Query / Update
- **操作**: 整理 TIB、小时级与日级广告报告的数据沉淀方案
- **涉及**: `wiki/SOP与工作流/亚马逊TIB与广告报告数据沉淀方案.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 回看《TIB优化初筛分析》最近 5 个对话回合，统一小时级过程监控、日级成熟结果、TIB 周期快照和广告变更记录的职责；明确在自动任务只能选择最近 7 天时，每周五或周六固定导出“上周”，并补充 SP 与 14 天归因活动的成熟度、SQLite 表结构、唯一键 Upsert、版本覆盖和分阶段实施方案。

## 2026-08-02

- **类型**: Output
- **操作**: 整理并生成四广告分时竞价与晚间延展 Word 分析文档
- **涉及**: `wiki/attachments/四广告分时竞价与晚间延展分析-2026-08-02.docx`, `wiki/跨境电商/四广告分段竞价与晚间延展分析-2026-08-02.md`, `logs/LOG.md`
- **摘要**: 将四广告小时流量、ROAS、预算截断、搜索词质量和两阶段测试方案整理为 9 页正式 Word 报告，包含 3 张图表与 10 张分析表；统一执行摘要、分活动动作卡、加价与延展时段、预算释放规则及 7 天验证门槛，并完成中文字体兼容、图片替代文本、表格结构和逐页渲染检查。

- **类型**: Query / Update
- **操作**: 分析四条亚马逊广告的 TIB 小时流量与搜索词，建立晚间延展和分时竞价方案
- **涉及**: `wiki/跨境电商/四广告分段竞价与晚间延展分析-2026-08-02.md`, `wiki/attachments/XM四广告分段竞价分析-2026-08-02.ipynb`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 核对 18,214 行 TIB 与 883 行搜索词数据，确认搜索词的点击、花费、购买和销售按活动与 TIB 精确一致，并纠正“只取完整日期范围行”的漏数风险；识别四活动日花费平台化和下午断流形成的预算截断信号，划分立即小幅加价、保价延展和释放预算时段，同时以无订单搜索词花费占比和品牌/泛词差异作为分时加价前置护栏。

## 2026-07-30

- **类型**: Ingest
- **操作**: 转录并分析 Amazon Ads Academy《利用DSP广告打造流量闭环》视频
- **涉及**: `wiki/SOP与工作流/利用DSP广告打造流量闭环-视频转录与案例分析.md`, `wiki/attachments/亚马逊DSP流量闭环-*.jpg`, `wiki/SOP与工作流/初识亚马逊DSP-视频转录与关键帧分析.md`, `wiki/SOP与工作流/亚马逊DSP模型预测竞价与程序化竞拍逻辑.md`, `wiki/SOP与工作流/亚马逊DSP链入与链出广告活动逻辑.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 在不操控附加浏览器的前提下，从课程页面公开数据定位 51 分 04 秒 4K 视频，完成 1090 个中文语音片段识别、12 张关键帧校对和结构化转录；整理 DSP 多维优化、AMC 高意向受众、认知—考虑—转化—忠诚四阶段闭环、耳机品牌案例、DSP 与搜索广告协同及旺季三阶段打法，并将讲师预算比例、历史效果数字和已过时的自助投放/视频库存/计费表述与 Amazon 当前官方规则明确分离。

- **类型**: Output
- **操作**: 整合并生成 Amazon DSP 三章知识笔记 DOCX
- **涉及**: `outputs/亚马逊DSP知识笔记/亚马逊DSP知识笔记-视频转录-模型预测-链入链出.docx`, `logs/LOG.md`
- **摘要**: 将视频转录与关键帧分析、模型预测竞价与程序化竞拍、链入与链出广告活动三篇知识页整合为 26 页 DOCX；统一封面、静态目录、三级标题、表格、提示框、页眉页脚和 10 张关键帧，完成中文字体兼容、编号重置、跨页控制、图片替代文本、压缩包完整性及逐页渲染检查。

- **类型**: Ingest
- **操作**: 转录并分析 Amazon Ads Academy《初识亚马逊DSP》视频
- **涉及**: `wiki/SOP与工作流/初识亚马逊DSP-视频转录与关键帧分析.md`, `wiki/attachments/亚马逊DSP初识-*.jpg`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 在不操控附加浏览器的前提下，从课程页面公开数据定位 21 分 10 秒原始视频，完成中文音频识别、4K 画面场景检测和 10 张关键帧校对；整理消费者旅程、DSP 与程序化定义、广告格式、三层流量资源、七类受众、创意路线、五项优势、Huggies 案例、漏斗投放矩阵及自助/托管服务，并标注 2023 年课程和历史案例数字的时效边界。

- **类型**: Ingest
- **操作**: 提取并解析 Amazon Ads Academy 的 DSP 广告活动类型课件 JSON
- **涉及**: `wiki/SOP与工作流/亚马逊DSP链入与链出广告活动逻辑.md`, `wiki/SOP与工作流/亚马逊DSP模型预测竞价与程序化竞拍逻辑.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 直接读取课程 JSON，整理链入与链出广告活动的目标位置、两类顾客流和测验案例；明确活动类型由点击后的目的地而非广告展示位置决定，补充链入 ASIN 与链出像素反馈的差异、三类业务案例、选择决策树及上线诊断清单，并依据当前 Amazon Ads 公开资料标注课程历史资格表述的边界。

- **类型**: Update
- **操作**: 补充 DSP 像素关联与转化反馈说明
- **涉及**: `wiki/SOP与工作流/亚马逊DSP模型预测竞价与程序化竞拍逻辑.md`, `logs/LOG.md`
- **摘要**: 增加像素关联定义、站外事件回传流程、Page View/Add to Cart/Lead/Purchase 事件用途、ASIN 与像素关联的适用场景，以及错误关联对报表归因和竞价模型反馈的影响。

- **类型**: Ingest
- **操作**: 提取并解析 Amazon Ads Academy 的 DSP 程序化竞拍课件 JSON
- **涉及**: `wiki/SOP与工作流/亚马逊DSP模型预测竞价与程序化竞拍逻辑.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 直接读取课程公开的 `contentObjects.json`、`articles.json`、`blocks.json` 和 `components.json`，整理 DSP/SSP、模型预测行为、竞价优化模型、基础/最高竞价、竞价方案、竞价遮蔽及 1–8 步竞价周期；区分 Amazon O&O 内部竞拍与第三方 SSP 外部竞拍，并用 CPC 案例解释预测概率如何在约束下转化为展示竞价。

## 2026-07-28

- **类型**: Ingest
- **操作**: 完成 BRONAX W8K4 美国站 SP 广告交叉诊断
- **涉及**: `wiki/跨境电商/W8K4-SP广告诊断与优化方案.md`, `outputs/W8K4广告诊断-2026-07-28/`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 读取 W8K4 文件夹内 6 份广告原始报表，交叉核对活动、定向与达成转化商品；识别两个手动广泛活动占 82.78% 花费但仅贡献 52.64% 销售，以及 barefoot 未覆盖定向残差 $321.79、残差 ACOS 119.22% 的预算黑洞。通过 OpenCode 与 DeepSeek 三轮复核纠正光环、竞价时点、残差来源和活动归因误判，形成 0–48 小时、3–7 天、8–14 天优化方案，并生成可复算明细和可浏览分析报告。

## 2026-07-24

- **类型**: Update
- **操作**: 补充 Windows 属性标签与 XMP dc:subject 的验收边界
- **涉及**: `wiki/跨境电商/亚马逊AI逼真人物媒体标签合规与批处理方案.md`, `logs/LOG.md`
- **摘要**: 根据微软 `System.Keywords` 元数据策略，明确 Windows 对 JPEG/TIFF 会合并 XMP dc:subject、IPTC Keywords 和 Windows EXIF Keywords，资源管理器中看到同名标签不能单独证明 Amazon 指定 XMP 字段存在；PNG、MP4、MOV 更不应依赖 Windows 属性界面。最终验收统一使用 ExifTool 指定读取 `XMP-dc:Subject`。

- **类型**: Update
- **操作**: 打包 Amazon AI 媒体标签 Windows 64 位与 macOS 跨平台离线便携版
- **涉及**: `outputs/Amazon_AI_Media_Tagger_Portable_Win64_macOS_v1.2.zip`, `outputs/Amazon_AI_Media_Tagger_Portable/`, `outputs/amazon-ai-media-labeler/`, `wiki/跨境电商/亚马逊AI逼真人物媒体标签合规与批处理方案.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 提供 Windows `START_HERE.bat` 与 macOS `START_HERE_MAC.command` 双入口和 ASCII 文件路径，内置官方 ExifTool 13.59 两套运行依赖、许可证及来源校验信息；接收方解压后可离线使用。Windows 与 macOS 官方原包 SHA2-256 均与官方校验文件一致，跨平台便携 ZIP 通过完整性测试；macOS 已用未打标 JPG、MP4 完成首次写入、备份、校验和重复运行测试。v1.2 预先创建 `REPORTS` 并附报告位置说明，同时在工作区保留已解压目录，避免从压缩包内直接运行或误找报告。

## 2026-07-23

- **类型**: Update
- **操作**: 创建 Amazon AI 逼真人物媒体 Windows 批量打标与扫描工具包
- **涉及**: `outputs/amazon-ai-media-labeler/`, `wiki/跨境电商/亚马逊AI逼真人物媒体标签合规与批处理方案.md`, `logs/LOG.md`
- **摘要**: 提供可拖放单文件或文件夹的 BAT 工具，批量追加准确的 `contains-synthetic-performer` XMP 标签并自动扫描；生成完整 CSV、通过、缺失、重复和错误报告，保留原文件备份。使用正向、缺失和重复控制样本验证扫描分流准确。

- **类型**: Update
- **操作**: 创建 Amazon AI 逼真人物媒体标签合规与批处理方案
- **涉及**: `wiki/跨境电商/亚马逊AI逼真人物媒体标签合规与批处理方案.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 根据 Seller Central 新规明确商品信息与 A+ 图片/视频的打标边界，制定人工分流、ExifTool BAT 批量追加 `contains-synthetic-performer`、CSV 校验和上传前复核流程；实测 JPEG 与 MP4 可保留原关键词、避免重复写入，且 MP4 视频编码流哈希在打标前后保持一致。

## 2026-07-22

- **类型**: Ingest
- **操作**: 对照 Alexa for Shopping 优化案例建立当前阶段与后续路线图
- **涉及**: `wiki/SOP与工作流/Alexa-for-Shopping优化当前阶段与后续路线图.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 结合广告经理提供的10页案例、AJ2-Y90与Y10意图结果及既有Alexa黑盒测试，判断当前处于Week 0诊断与Week 1执行准备阶段；明确补齐评论、Category Listings Report、优化前基线、Listing/Q&A/A+改造、意图簇广告上线和优化后复测的顺序，并标注案例中不可直接视为固定算法公式的经验性建议。

## 2026-07-21

- **类型**: Update
- **操作**: 将 Amazon 图片工作台商品同步改为链接精确匹配
- **涉及**: `apps/amazon-image-studio/`, `apps/alexa-recommendation-auditor/`, `wiki/AI工程/工具参考/Amazon图片工作台项目分析.md`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `logs/LOG.md`
- **摘要**: 工作台新增必填 Amazon PDP 链接并在本地规范化站点和 ASIN；扩展后台只读取已经打开且与链接同站点、同 ASIN 的商品页，不再猜测活动页或最近页面，同时为旧 service worker 空响应提供重新加载诊断。策划字段白名单、预览确认、同 ASIN 缓存约束和手动/JSON 模式保持不变。

## 2026-07-19

- **类型**: Update
- **操作**: 实现 Amazon 图片工作台商品详情页自动同步与策划上下文隔离
- **涉及**: `apps/amazon-image-studio/`, `apps/alexa-recommendation-auditor/`, `wiki/AI工程/工具参考/Amazon图片工作台项目分析.md`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: Chrome 扩展新增六站点策划专用商品上下文桥接，按同窗口优先规则读取 PDP，删除价格、履约、评论、Rufus 对话与账户信息，并以 15 分钟、同 ASIN 缓存约束防止串商品；图片工作台新增同步/JSON预览确认，导入时重置旧提示词与策划状态，正文按不可信数据边界进入 AI 策划，手动输入继续保留且同步本身不调用模型或生图。

- **类型**: Update
- **操作**: 补充 Amazon Ads 新统一报告的分时投放时间维度说明
- **涉及**: `wiki/SOP与工作流/亚马逊广告营销优化规划方案与学习路径.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 根据新统一报告界面，区分日期、周、月中的一天、月、年份、一周中的某一天、小时和日期范围的分组口径；明确最佳流量时间分析应优先选择“日期 + 小时 + 广告活动”，并用点击、转化率与 ROAS/ACOS 联合判断高价值时段。

## 2026-07-17

- **类型**: Update
- **操作**: 修复 Alexa 自动发送并设计 Amazon 图片工作台自动采集桥接
- **涉及**: `apps/alexa-recommendation-auditor/`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `wiki/AI工程/工具参考/Amazon图片工作台项目分析.md`, `wiki/跨境电商/亚马逊商品标题与Item-Highlights新规-2026.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: Alexa 执行器改为识别 Rufus 语义提交控件并自动逐题递进，增加 Amazon 首页强制刷新和 content script 版本握手；同时沉淀图片工作台的手动/自动双模式、版本化 JSON 合约与 Chrome bridge 方案，并依据 Amazon 官方公告澄清 2026-07-27 新规是 75 字符标题加 125 字符 Item Highlights，而非强制 GEO 标题格式。

## 2026-07-16

- **类型**: Update
- **操作**: 拆分 Alexa 插件开发与使用文档并建立固定飞书同步发布流程
- **涉及**: `apps/alexa-recommendation-auditor/`, 飞书开发文档 https://my.feishu.cn/docx/WSVfdI5iooArKvxhbpDcRJL9nhb, 飞书使用手册 https://my.feishu.cn/docx/Z8hNd4efYo0nuOx3FC0cQ8E7nvf, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `logs/LOG.md`
- **摘要**: 新增独立开发文档和运营使用手册；建立 `VERSION` 唯一版本源、CHANGELOG、追加式开发日志、版本一致性工具与发布门禁。两份固定飞书文档已创建、覆盖同步并回读校验；后续文档更新由本地 Markdown 统一发布，文档哈希或版本未同步时 `release:check` 将失败。

- **类型**: Update
- **操作**: 为 Alexa 推荐诊断插件增加简体中文提问链路
- **涉及**: `apps/alexa-recommendation-auditor/`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `logs/LOG.md`
- **摘要**: 侧边栏新增简体中文选项并持久化到运行；15个鞋类固定题、页面动态槽位、品牌/ASIN辅助题和Hermes受控改写均保持所选语言，同时沿用相同证据、角色与评分口径。新增Unicode中文证据匹配、中文必需词与越界动作校验及回归测试；87项测试、类型检查和生产构建通过。

- **类型**: Update
- **操作**: 安装 LinkFox CLI 与 Alexa 技能并补充工具边界
- **涉及**: `/Users/panjinlong/.codex/skills/e-commerce-find-skills/`, `/Users/panjinlong/.codex/skills/linkfox-amazon-alexa-search/`, `CLAUDE.md`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `wiki/AI工程/工具参考/紫鸟CLI功能指南.md`, `logs/LOG.md`
- **摘要**: 安装 `linkfoxskill` 0.1.13 并为 Codex 初始化电商技能路由；指定旧 slug 返回 404 后，安装市场现行替代技能 `linkfox-amazon-alexa-search` 1.0.4。对照源码明确 LinkFox 单轮云端 Alexa 问答与本地批量黑盒诊断插件的差异，并记录紫鸟 CLI 1.0.7 没有原生广告/AMC 命令、ZClaw UI 自动化和 Amazon Ads API/AMC workflow 的实施边界。

- **类型**: Update
- **操作**: 将 Alexa 推荐诊断插件模型链路改为 Hermes Agent 单一入口
- **涉及**: `apps/alexa-recommendation-auditor/`, `/Users/panjinlong/Documents/amc-hermes-dashboard/docs/ai-model-gateway-and-run-log.md`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 验证本机 Hermes Agent v0.11.0 为最新版本，启用仅回环可访问的 OpenAI 兼容 API 与 Dashboard，并关闭 API 平台全部工具集；插件移除 DeepSeek 直连旁路，记录 Hermes 会话ID、模型、耗时、用量和确定性回退原因。验收确认 API、会话与日志链路可用，但当前 DeepSeek 凭据返回 402 余额不足，真实运行前须在 Hermes 本机更换未暴露且有余额的凭据。

- **类型**: Update
- **操作**: 安装并整理紫鸟 CLI 功能指南
- **涉及**: `wiki/AI工程/工具参考/紫鸟CLI功能指南.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 验证并全局安装 `@ziniao-open/cli` 1.0.7，确认本地 ZClaw Bridge 连通，梳理服务端 OpenAPI、账号权限、部门员工、角色设备、店铺浏览器、页面操作、多步骤自动化、通用 API、配置与诊断能力。

## 2026-07-15

- **类型**: Update
- **操作**: 将 Alexa 推荐诊断插件升级为鞋类通用 V2 题集与开发者审计闸门
- **涉及**: `apps/alexa-recommendation-auditor/`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 实现鞋类固定模板加页面证据动态槽位、受控 DeepSeek 改写、题集草稿编辑/停用/审批锁定、完整问题与评分审计日志、父子ASIN核验、主分与基线/负控制/零售/辅助/诊断角色隔离；新增公开可复核的完整评分口径、证据词法匹配规则与精度门槛，并明确人工审阅清单不改变版本化代码评分。

- **类型**: Update
- **操作**: 将 AJ2-Y90 搜索词意图需求报告写入飞书文档
- **涉及**: 飞书文档 https://my.feishu.cn/docx/LSild0viXo5zDAxH5eAcoZc0nlc, `outputs/amazon-intent-cluster/AJ2-Y90/report/AJ2-Y90飞书文档.md`, `wiki/跨境电商/AJ2-Y90搜索词意图需求报告-2026-07-15.md`, `logs/LOG.md`
- **摘要**: 创建并回读校验完整飞书报告，覆盖执行摘要、数据质量、功能与场景意图、选择条件、商品承接度、广告与 Listing 建议及证据边界。

- **类型**: Update
- **操作**: 创建品牌分析与搜索热度驱动的开品报告方法
- **涉及**: `wiki/跨境电商/亚马逊品牌分析与搜索热度驱动的开品报告方法.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 将18字段语义意图分类扩展为需求规模、趋势稳定性、购买深度、竞争结构和产品可行性五层开品框架，明确第三方搜索热度、品牌分析漏斗和自有品牌查询范围的证据边界。

- **类型**: Ingest
- **操作**: 完成 AJ2-Y90 搜索词意图需求报告与全量质检
- **涉及**: `outputs/amazon-intent-cluster/AJ2-Y90/report/`, `wiki/跨境电商/AJ2-Y90搜索词意图需求报告-2026-07-15.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 汇总 2,394 个唯一自然语言搜索词，应用 Prompt 1.1 确定性标准化和上层同义归并，在不使用 ACOS、CVR、点击、订单或销售额的条件下识别基础品类、足弓支撑、湿区场景、舒适缓震和颜色款式等主要意图；生成并独立校验 Notebook、XLSX、JSON 与交互式报告。

- **类型**: Update
- **操作**: 创建 Alexa 商品推荐诊断插件并沉淀架构说明
- **涉及**: `apps/alexa-recommendation-auditor/`, `wiki/AI工程/工具参考/Alexa商品推荐诊断插件.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 实现 Chrome MV3 扩展、NestJS/Prisma/SQLite 本地分析服务、DeepSeek 结构化分析、确定性推荐指数和 Vue 独立报告页；支持15×3盲测、2轮辅助认知、逐轮Top 5与隐私遮盖截图、硬停止安全控制、意图槽位表现与广告渠道建议。类型检查、10项单元测试、生产构建和本地健康/配对检查通过，生产依赖审计为0漏洞。

- **类型**: Update
- **操作**: 创建 Amazon 图片工作台项目分析
- **涉及**: `wiki/AI工程/工具参考/Amazon图片工作台项目分析.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 基于 GitHub 当前主分支、关键源码、项目元数据与本地构建验证，梳理 Amazon Listing/A+ AI 图片工作台的功能边界、技术架构、API Key 风险、项目健康度及与现有飞书 A+ 工作流的衔接方式；19 个测试文件、252 项测试通过，生产构建成功。

## 2026-07-14

- **类型**: Update
- **操作**: 创建亚马逊搜索词意图簇字段与无绩效指标分类规则
- **涉及**: `wiki/SOP与工作流/亚马逊搜索词意图簇字段与无绩效指标分类规则.md`, `logs/INDEX.md`, `logs/LOG.md`
- **摘要**: 明确搜索词字段在不使用 ACOS、CVR、订单等绩效指标时可以形成语义意图簇，但不能单独判断商业价值；建立领域门控、意图槽位、潜在任务、证据分级、置信规则和语义流转边界，并补充品牌、价格、否定条件、歧义与 ASIN 承接字段。

## 2026-06-10

- **类型**: Ingest
- **操作**: 转录并整理 AMC 广告诊断闭环与 Audience 实验会议
- **涉及**: `wiki/SOP与工作流/AMC广告诊断闭环与Audience实验会议纪要-2026-06-10.md`, `wiki/attachments/meeting-20260610/会议转录清理版-2026-06-10.txt`, `logs/INDEX.md`, 飞书文档 https://my.feishu.cn/docx/OfKyd7EZxoBT3qx0J8Rc0xHQnOb, 钉钉文档 https://alidocs.dingtalk.com/i/nodes/93NwLYZXWyggk2d4TZ6KjB30JkyEqBQm
- **摘要**: 对约 69 分钟会议音频完成中文转录与术语校正，梳理 AI 广告诊断闭环、Measurement/Audience 边界、Rule-based 与 Lookalike 实验、付费订阅标签、Hermes 产品化、权限分工和行动项，并将推断内容独立标注为 GPT建议。

## 2026-06-05

- **类型**: Update
- **操作**: 创建 AMC 受众细分与 Hermes 网页方案
- **涉及**: `wiki/SOP与工作流/AMC受众细分与Hermes网页方案.md`, `logs/INDEX.md`, 飞书文档 https://my.feishu.cn/docx/UvSwdTwenokqV0xjGCtcPpLMnBc
- **摘要**: 基于知乎文章中的 ai.xmars.com 截图、作者对 AMC 自定义人群和 SP/SB 人群溢价的理解，以及本地 `amc-hermes-dashboard` 页面结构，沉淀模板库、路径分析、受众创建向导、关键词 x 受众矩阵和实验复盘台的产品方案，并同步创建飞书 Docx 文档。

## 2026-06-01

- **类型**: Update
- **操作**: 创建 OpenCode AI 编码代理工具参考页
- **涉及**: `wiki/AI工程/工具参考/OpenCode-AI编码代理.md`, `logs/INDEX.md`
- **摘要**: 梳理 OpenCode 的定位、终端 TUI、浏览器 Web 页面、IDE 扩展和基础启动命令，补充其与 Claude Code/Codex CLI 类工具的关系。

## 2026-05-26

- **类型**: Update
- **操作**: 创建 AMC 新版新人入门飞书 Docx 并同步本地知识库
- **涉及**: `wiki/SOP与工作流/AMC新版查询结果表新人入门规划.md`, `logs/INDEX.md`, 飞书文档 https://my.feishu.cn/docx/F08Cd129aoe25BxnSRWci326nyh
- **摘要**: 新建《AMC 新版查询结果表新人入门：从仪表盘到广告动作》飞书 Docx，不覆盖旧版教程；文档面向运营新手，包含 AMC 与广告后台类比、核心字段解释、新版 Base 20 张表分层、7 个业务问题、7 张 V2 仪表盘截图占位、新人练习题和 AI 分析边界，并将新链接回写到本地规划页。

- **类型**: Update
- **操作**: 补导入 AMC 路径分析表并重规划新人入门路径
- **涉及**: `wiki/SOP与工作流/AMC新版查询结果表新人入门规划.md`, `wiki/SOP与工作流/AMC清洗后数据质量审查与仪表盘建议.md`, `logs/INDEX.md`, 飞书多维表格 https://my.feishu.cn/base/SkeGbjBLhasz7Ls9VdXcC4lFnge
- **摘要**: 将 `AMC_Targeting_First_Last_Assist` 和 `Campaign 路径宽表` 两张 Sheet 导入新版 AMC Base，重命名为 `18_AMC_Targeting_First_Last_Assist` 与 `19_Campaign_Path_Wide`，修正导入时误识别的计数字段类型，并沉淀新版新人教程规划，覆盖核心字段、表间关联、仪表盘阅读和纯 AI 分析路径。

## 2026-05-22

- **类型**: Update
- **操作**: 重建 AMC 飞书 V2 仪表盘
- **涉及**: `wiki/SOP与工作流/AMC清洗后数据质量审查与仪表盘建议.md`, 飞书多维表格 https://my.feishu.cn/base/SkeGbjBLhasz7Ls9VdXcC4lFnge
- **摘要**: 更新 `lark-cli` 与飞书 Skills，修复关键数值字段单位样式，创建 6 张仪表盘辅助表，删除旧的 9 个 DeepSeek 仪表盘，重建 7 张 V2 仪表盘，并补充搜索词归因问题看板、流量质量看板和否定词候选审核视图。

- **类型**: Ingest
- **操作**: 创建 AMC 清洗后数据质量审查与仪表盘建议
- **涉及**: `wiki/SOP与工作流/AMC清洗后数据质量审查与仪表盘建议.md`, `logs/INDEX.md`
- **摘要**: 只读审查飞书多维表格《清洗后的 AMC 数据》，整理字段类型、单位、小数位、百分比、日期、ID、重复字段和现有仪表盘配置问题，并给出适合仪表盘化的表和原因。

## 2026-05-21

- **类型**: Update
- **操作**: 补充 AMC API 对接难度与等待时间判断
- **涉及**: `wiki/SOP与工作流/AMC查询用例与自动化对接方案.md`
- **摘要**: 增加 AMC 后台开通、Amazon Ads API access、OAuth 授权、workflow 执行器、定时导出入表等阶段的繁琐程度、卡点和时间预估。

- **类型**: Update
- **操作**: 同步 AMC 查询用例文档到飞书
- **涉及**: `wiki/SOP与工作流/AMC查询用例与自动化对接方案.md`, 飞书文档 https://my.feishu.cn/docx/UKH1dxZioohXooxN4PTcwXVinph
- **摘要**: 将本地 AMC 查询用例与自动化对接方案创建为飞书 Docx 文档，并在本地来源区补充飞书同步链接。

- **类型**: Ingest
- **操作**: 创建 AMC 查询用例与自动化对接方案
- **涉及**: `wiki/SOP与工作流/AMC查询用例与自动化对接方案.md`, `logs/INDEX.md`
- **摘要**: 梳理 AMC 适合的查询类型、最佳业务用例、第一批 SQL 模板方向、Amazon Ads API 自动化执行 workflow、下载 CSV/S3 输出并写入钉钉 AI 表或本地文件的方案。

## 2026-05-20

- **类型**: Update
- **操作**: 创建 LibTV-Skill 使用说明
- **涉及**: `wiki/AI工程/工具参考/LibTV-Skill使用说明.md`, `logs/INDEX.md`
- **摘要**: 梳理 `libtv-skill` 的触发条件、核心原则、5 个主要脚本与公共模块、标准生成/编辑/追加会话工作流、轮询策略、输出格式和敏感凭据注意事项。

- **类型**: Ingest
- **操作**: 创建亚马逊创建广告活动页面分模块教学
- **涉及**: `wiki/SOP与工作流/亚马逊创建广告活动模块教学.md`, `wiki/attachments/amazon-ads-create-campaign/`, 飞书教程 https://my.feishu.cn/docx/RkSDdb0IfoDVztxR5eAcHL5InBc
- **摘要**: 基于用户提供的创建广告活动长截图和本地只读滚动截图，生成 7 张分模块标注图，解释广告组、商品选择、投放方式、默认竞价、否定关键词、否定商品、竞价方案、广告活动设置、多站点启动、规则自动化和提交按钮的中英文含义与风险等级。

- **类型**: Ingest
- **操作**: 创建亚马逊广告组合 Portfolios 模块教学
- **涉及**: `wiki/SOP与工作流/亚马逊广告组合模块教学.md`, `wiki/attachments/amazon-ads-portfolio/`, 飞书教程 https://my.feishu.cn/docx/RkSDdb0IfoDVztxR5eAcHL5InBc
- **摘要**: 结合用户提供的广告组合页截图与 `广告组合 Portfolios_5月_19_2026.csv`，生成页面结构示意图、组合数据分析仪表盘、组合类型汇总、真实案例诊断和优化观察路径，并准备追加到飞书教程。

- **类型**: Ingest
- **操作**: 制作亚马逊广告活动页操作教程（截图标注 + 飞书文档 + Obsidian 存档）
- **涉及**: `wiki/SOP与工作流/亚马逊广告活动页操作教程.md`, 飞书教程 https://my.feishu.cn/docx/RkSDdb0IfoDVztxR5eAcHL5InBc
- **摘要**: 截取亚马逊 Campaign Manager 页面首屏，生成 29 点标注图，创建飞书教程文档（含编号解释表、字段速查表、新手观察路径、高风险按钮提醒），并本地存档。

- **类型**: Ingest
- **操作**: 将飞书广告规划方案同步存档为本地 Obsidian 页面
- **涉及**: `wiki/SOP与工作流/亚马逊广告营销优化规划方案与学习路径.md`, `logs/INDEX.md`
- **摘要**: 归档亚马逊广告营销优化的目标、学习路径、报表字段、广告评价规则、AI 分析流程、AMC/API 后续方向与两周执行计划。

- **类型**: Ingest
- **操作**: 将会议零散笔记整理为本地 Obsidian 工作计划页
- **涉及**: `wiki/SOP与工作流/视频广告素材与亚马逊广告分析工作计划.md`, `logs/INDEX.md`
- **摘要**: 整理视频素材研究、Y10/Y11 亚马逊广告分析、AMS/AMC 学习路线、lark-cli 与 libtv-skill 工具分工，并补充近期执行清单。

## 2026-05-06

- **类型**: Restructure
- **操作**: 整体架构迁移至 Karpathy 三层结构
- **涉及**: 全库
- **摘要**: 创建 raw/ + wiki/ + logs/ + AGENTS.md；迁移全部内容至三层架构；移出选品工具/企业网站/竞品采集脚本代码项目至 vault 外；清理根目录散落文件和图片
