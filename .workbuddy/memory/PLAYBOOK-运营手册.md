# 运营手册 · 细节沉淀（配合 MEMORY.md 使用）

> MEMORY.md 只留跨会话必需的结论；本文件承接长尾操作细节。按需读取，不必每次全读。

## A. 数据库细节

### A.1 `core.import_batches` 字段
`batch_id`(identity) / `file_name` / `file_hash`(char64, 唯一约束) / `source_path` / `report_type` / `report_start_date` / `report_end_date` / `exported_at` / `export_time_source` / `imported_at` / `source_row_count` / `valid_row_count` / `failed_row_count` / `import_status`(processing|success|partial|failed) / `error_message` / `metadata`(jsonb) / `account_id` / `account_name` / `source_kind` / `source_url` / `data_level` / `target_table` / `inserted_row_count` / `updated_row_count` / `skipped_row_count` / `schema_version`(默认 v2.0)。

⚠️ 陷阱：列名是 `file_name` 而不是 `source_file_name`；没有 `row_count` 列。失败批次若留在 `import_status='processing'`，会因 file_hash 撞唯一约束挡住重试 → 先删非 success 的同 hash 批次。

### A.2 `amazon_ads_v2` 现状（2026-09-15 实测）
- schema：`core`、`public`（空）、`stg`（只有 `load_tmp` text 暂存表）
- `core` 关系（9 个）：`ad_daily`（分区表）+ `ad_daily_2026_08/09/10/11` + `ad_daily_default`、`import_batches`、`search_term_daily`、`search_term_target_period`
- 行数：ad_daily 89,801 / search_term_daily 102,761 / search_term_target_period 1,564,100 / import_batches 20
- ad_daily 的 data_level：targeting 62,021、purchased_product 16,097、placement 6,829、advertised_product 2,457、campaign 2,397
- 唯一账户：`amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz`（anac1973 / C3S8S），2026-08-15 ~ 2026-09-13

### A.3 `amazon_ads`（应用库）现状
- schema：`public`、`iam`
- `iam.roles`(role_code PK, display_name, description, created_at)：super_admin / management / operator
- `iam.users`(user_id identity, username, email, password_hash, display_name, role_code FK, operator_code, status, created_at, updated_at) + 两个唯一索引（lower(username)、lower(email) WHERE email IS NOT NULL）+ CHECK：operator 必须带 operator_code，非 operator 必须为空
- `iam.user_sessions`(session_id, user_id FK CASCADE, token_hash char64 唯一, created_at, expires_at, last_seen_at, revoked_at) + CHECK expires_at > created_at
- **没有 `iam.schema_migrations`** → 说明是手写 SQL 落的，没走 migrate_local.py
- owner 全 = `amazon_ads_admin`

### A.4 权限与能力
- `alicloud_rds_admin`：超级用户（不可用）
- `amazon_ads_admin`：rolsuper=f，rolcreaterole=t，rolcreatedb=t，rolbypassrls=t，属 `pg_rds_superuser`
- `postgres`：rolsuper=f，**非真超管**
- 可装扩展：`postgres_fdw` 1.2、`dblink` 1.2、`pg_cron` 1.6、`pgcrypto` 1.4、`file_fdw` 1.0；已装仅 `plpgsql`
- **跨库 JOIN 不可行** → 需 `postgres_fdw`（在两库各建 foreign server + user mapping）或应用层双 DSN

## B. 控制台后端引用的表 — 存在性核验（2026-09-15 实测 `to_regclass`）

| 对象 | amazon_ads | amazon_ads_v2 |
|---|---|---|
| core.subscribed_campaign_daily | ✗ | ✗ |
| core.subscribed_product_daily | ✗ | ✗ |
| core.subscribed_product_cpo_daily | ✗ | ✗ |
| core.subscribed_search_term_daily | ✗ | ✗ |
| core.subscribed_placement_daily | ✗ | ✗ |
| core.business_report_parent_asin_period | ✗ | ✗ |
| core.operator_name_mapping | ✗ | ✗ |
| core.product_alias | ✗ | ✗ |
| core.import_batch（单数） | ✗ | ✗ |
| core.import_batches（复数） | ✗ | ✓ |
| analytics.v_campaign_daily_product_resolved | ✗ | ✗ |
| chatgpt_ops.product_roster | ✗ | ✗ |
| chatgpt_ops.product_mapping_overrides | ✗ | ✗ |
| cpo_jobs / cpo_job_issues | ✗ | ✗ |
| campaign_product_rules / campaign_ad_type_mapping | ✗ | ✗ |
| iam.users / iam.roles / iam.user_sessions | ✓ | ✗ |
| core.ad_daily / search_term_daily / search_term_target_period | ✗ | ✓ |

线上实测（uvicorn 已在 127.0.0.1:8000 跑）：`/api/health` → ok；`/api/reports`、`/api/dashboard/overview`、`/api/operator-cpo` → `Internal Server Error`；`/api/product-mappings` → 返数据（来自 `reference/product_mapping/*.csv`，DB 查询被 `except: []` 吞掉）；`/api/cpo-jobs` → mock。

## C. 控制台代码地图

```
amazon-ads-console/
├── backend/
│   ├── .env                     # DATABASE_URL → amazon_ads（含明文密码，600 权限）
│   ├── configure_rds.py         # DATABASE 硬编码 "amazon_ads"，交互式验密码后写 .env
│   ├── run_rds.py               # 从 DATABASE_URL 拆出 PG* 环境变量再起 uvicorn:8000
│   ├── migrations/001_iam_identity.sql, 002_iam_user_sessions.sql
│   ├── scripts/local_db.sh      # 本地 cluster：55432 / adsight_local / adsight_dev
│   ├── scripts/migrate_local.py # 只允许 localhost:55432（硬护栏）
│   ├── scripts/seed_local_iam.py# 种 3 个账号：admin / management_demo / operator_zj
│   └── app/
│       ├── main.py              # CORS 白名单 5173+15173；启动预热 operator_cpo_summary
│       ├── core/{config,db,passwords}.py
│       ├── models/domain.py     # cpo_jobs / cpo_job_issues / campaign_product_rules / campaign_ad_type_mapping
│       ├── api/routes.py        # 全部业务路由（单体，无鉴权依赖）
│       ├── api/auth.py          # /api/auth/{login,me,logout} + require_session
│       └── services/
│           ├── auth.py          # asyncpg 直连 iam.*
│           ├── rds_query.py     # psql 子进程执行 SQL → json_agg
│           ├── real_data.py     # 看板/趋势/产品/报告（读 core.subscribed_*）
│           ├── operator_cpo.py  # 运营单双视图（读 core.business_report_*）
│           ├── cpo_reference.py # CPO 参考基线
│           ├── cpo_imports.py   # 上传校验/入库（core.import_batch + business_report_parent_asin_period）
│           ├── product_mapping.py / product_mapping_admin.py  # chatgpt_ops.* + CSV 兜底
│           └── cache.py / mock_data.py
├── frontend/src/{views,components,stores/session.ts,router/index.ts,api/client.ts}
├── docs/AdSight_API接口文档_V1.0.md   # 17 个已实现接口 + 待开发清单
├── docs/工程规范化补齐方案.md          # 8 阶段欠条体检报告
└── reference/                        # CPO SOP 参考答案、产品映射 CSV、v2/v3 构建脚本
```

关键缺口：
- `api/routes.py` 里业务接口**无 `Depends(require_session)`** → 登录形同虚设
- `AppSidebar.vue` 无角色过滤 → 运营能进全部页面
- `frontend/src/api/client.ts` 所有请求 `catch → fallback` → 静默假数据
- 无独立 git，父仓库 `agent-master` 也未跟踪该项目（`git ls-files` 为 0）
- `backend/tests/` 空；`frontend/src/components/HelloWorld.vue` 是脚手架残留

## D. 广告报告管线细节

4 店合计 **23 份**订阅报告（2026-09-23 调整后：川鹏2号 5 / 欧德思美站 6 / 洁博利美站 6 / 美国AMS 6）。
🔴 **2026-09-23 起 CPO 报告（`<店名> 推广的商品 每日CPO单双计算`）不再纳入自动化**，已从 `config.json` / `config-core2.json` / 任务 prompt 全部移除
（原因：7 天窗口、且不进 `core.report_*_daily`，纯冗余）。原本 25 份＝欧德思 7 + 美国AMS 7，各含 1 份 CPO。
**自动化现在只跑 6 类 30D 报告**；30D 报告名四店通用。**川鹏2号没有「搜索词 30D 日期」订阅**（洁博利 6 份齐、川鹏 5 份）。
⚠️ **别按命名规律推断订阅是否存在**，必须用探针抓真实列表（§D.1.3）。
skill `ziniao-ad-report-download`，`downloadTimeoutMs` ≥1800s、`skipIfFreshHours` 20h。
控制台生成时间（北京）：搜索词 09:02 / 推广的商品 09:34 / 广告活动 09:39 / 广告位 09:45（CPO 08:21 已成历史）。
⚠️ 未修 bug：文件新鲜度按美东日判断、任务锚北京 → 非重下店铺的数据永久落后一天（建议 20h→12h 或用 UTC+8 判断）。

CSV 解析统一：utf-8-sig；Excel `="..."` 包装；日期 `2026年8月25日` → 正则 `^(\d{4})年(\d{1,2})月(\d{1,2})日$`；百分比 `0.6098%` 存 `0.6098`。

### D.1 两条管线的分工（2026-09-21 二次厘清 —— 结论已翻转，别再引用旧版）

| 管线 | 脚本 | 落库目标 | 状态 |
|---|---|---|---|
| ① 紫鸟订阅报告下载 | skill `ziniao-ad-report-download/pipeline.sh` | **本身不灌库**（只下载+校验新鲜度） | ✅ 可用（已修） |
| ①' **紫鸟 → 事实层桥接** | `ad-reports-export/ziniao_30d_to_report_daily.py` | **`core.report_*_daily`** | ✅ **2026-09-21 新建，现行主入口** |
| ①'' 订阅报告灌库（旧） | `ad-reports-export/subscribed_reports_to_rds.py` | `core.subscribed_*`（**表已不存在**） | 🔴 废弃 |
| ② 邮件渠道 | `amazon-ads-data/scripts/download_account_30d_mail_reports.py` → `import_account_30d_reports.py` | `core.report_*_daily` | 🔴 **被 macOS TCC（-10004）拦死** |

**2026-09-21 的关键翻转**：上一版手册写「② 邮件渠道是现行唯一入口、① 与事实层无关」——**这已不再成立**。
- ② 依赖 `osascript` 读 Apple Mail，实测报 `-10004 权限违例`；`~/Library/Mail/` 也被 TCC 拒（`Operation not permitted`）→ **彻底断**。
- 取而代之：把 ① 下载下来的 CSV 用 ①' 桥接脚本按加载器要求的命名搬好，再调 `import_account_30d_reports.py`。**同一条事实层，换了取数来源。**
- ①' 覆盖 **3 个账户**：欧德思(BLOOMNEXT) / 洁博利(JOOMRA DIRECT) / 美国AMS(anac1973)。⚠️ **川鹏2号(WHITIN) 不参与事实层**，桥接脚本自动跳过。
- 🔑 **30D 报告是滚动 30 天窗口** → 补缺口**不需要按天回灌**，一次成功即补齐最近 30 天（含所有漏掉的日子），幂等 upsert。

### D.1.1 紫鸟报告下载的三个坑（2026-09-21 实测，全部已修）

1. 🔴 **报告名匹配曾是「逐字符精确相等」** → 控制台里订阅名被人改成
   `<店名> 广告活动 30D 日期 Copy` 后，**4 店 20 个报告 100% 失配**，
   全部失败 → 触发「全部失败=系统性故障」退出码 3。
   症状极像「订阅被删 / 掉登录」，其实是比对太脆。
   → 已改为**归一化匹配**：抹空白 + 抹结尾 `Copy` + **唯一后缀命中**；
   命中多个报 `ambiguous[...]` 交人工，不猜。config 里写干净名即可。
   ⚠️ `waitForReportLink`（等待）和 `clickScript`（点击）**两处必须同源** ——
   只改一处会出现「日志说找到了、紧接着抛找不到」的自相矛盾现象。
2. 🔴 **「只看文件在不在」会拿旧快照冒充成功**：下载目录长期躺着上次成功的文件
   （实测 2026-09-08 那批至今还在）。某店掉登录 → 下载失败 → 旧文件原地不动。
   → 桥接脚本加了**数据日期闸门**：最新数据日期 < 今天-3 天判「过期、这是旧快照」，
   整家不灌。（`verify_freshness.py` 也会判，但桥接不能依赖它。）
3. 🔴 **`import_account_30d_reports.py` 原来硬判「必须恰好 18 个文件」**
   （3 账户 × 6 类）。某家店掉登录就整批拒绝。
   → 已改为**逐账户齐全**校验（账户数不限，但每个目录必须 6 类各一份），
   报错能指出到底缺哪一类。30D 窗口下「少一家不灌」纯属自伤。
4. ⚠️ 川鹏2号 **没有「搜索词 30D 日期」订阅**
   （它有一份「川鹏 受众 30D 日期 Copy」）→ 已从 config 移除，
   否则每轮判 MISSING、白等 20 分钟重下。
   （「每日CPO单双计算」同理，且 2026-09-23 起 CPO 已在四店全面下架。）
5. ⚠️ 洁博利美站 **2026-09-21 掉登录**（跳 `amazon.com/ap/signin`）→ 需人工重登。

### D.1.2 端到端跑通记录（2026-09-21 实测，可作基准）

**一次成功打通「下载 → 灌库」全链路，补齐了 2026-09-15 ~ 09-20 的缺口。**

| 环节 | 结果 |
|---|---|
| 下载 | 欧德思美站 + 美国AMS 各 6 类 30D 报告 + 各自 CPO 报告，**全绿 EXIT=0** |
| 数据窗口 | 两店 6 类报告均为 **2026-08-22 .. 2026-09-20** |
| 灌库 | 12 文件 · inserted **254,479** · updated **118,030** · skipped 251,113（幂等命中） |
| 桥接脚本 | `ad-reports-export/ziniao_30d_to_report_daily.py`（⚠️ 其 `print_rds_status()` 曾因 `%-18s` 未转义崩 `TypeError`，已修） |
| 加载器 | `import_account_30d_reports.py` 改「逐账户齐全」校验后**首次实战通过** |

**补齐结果（`core.report_*_daily` 6 张表，max(stat_date)）**

| 账户 | 改前 | 改后 | 备注 |
|---|---|---|---|
| BLOOMNEXT（欧德思） | 2026-09-14 | **2026-09-20** | 09-13~09-20 连续无断档 ✅ |
| anac1973 (C3S8S)（美国AMS） | 2026-09-14 | **2026-09-20** | 09-13~09-20 连续无断档 ✅ |
| JOOMRA DIRECT（洁博利） | 2026-09-14 | 2026-09-14 ⛔ | **掉登录，未灌** —— 重登后下一轮 30D 窗口自动兜住 |

**行数（6 表）**：BLOOMNEXT 广告活动 4,311 / 广告位 14,753 / 投放 94,876 / 搜索词 177,576 / 推广的商品 161,576 / 达成转化的商品 45,883；
anac1973 广告活动 2,954 / 广告位 8,395 / 投放 74,304 / 搜索词 224,221 / 推广的商品 5,631 / 达成转化的商品 34,615。

**注意**：`report_business_*` 两张表（业务报告侧）不受本管线影响，BLOOMNEXT / JOOMRA / WHITIN 均停在 **2026-09-19**，属独立管线（§E）。

> 📌 **别把「CSV 窗口」当成「库窗口」**（2026-09-21 追问触发）。
> 单次下载的 30D CSV 只有**滚动 30 天**（本次 = 2026-08-22 .. 2026-09-20）；
> 但库里是**历史累积 upsert**，比 30 天长：
> `report_campaign_daily` 实测 BLOOMNEXT `08-16..09-20`(36 天) / anac1973 `08-15..09-20`(37 天) / JOOMRA `08-16..09-20`(36 天)，
> 三账户均**逐日连续无断档**。多出来的那几天来自更早那轮成功导入的窗口，不是脏数据。
> 库里窗口要变长只能靠「跑得越频繁、窗口滑动留下的轨迹越宽」，**它不会自己往前延伸**。

### D.1.3 洁博利补齐 + 同名重复订阅修复（2026-09-21 第二轮，18/18 全绿）

第一轮（欧德思 + 美国AMS）全绿后，第二轮补洁博利时第一跑只有 5/7，暴露两个真问题：

1. **洁博利根本没有「每日CPO单双计算」订阅** —— 我按 `欧德思/AMS 有 → 洁博利也该有` 的规律**猜**了一个名字配上，
   实际不存在。⚠️ **别用命名规律推断订阅是否存在**，必须用探针抓真实列表。
   （洁博利只有 6 份 30D 订阅；川鹏2号 5 份，同样无 CPO。）→ 已从 config 移除。
   （📌 2026-09-23 后续：**CPO 已在四店全面停止自动化导出**，这个坑连同报告本身一起退役。）
2. 🔴 **洁博利存在「同名重复订阅」** —— 这是本轮最有价值的发现：

| 报告名 | 状态 | 上次修改时间 | 下次运行 | 性质 |
|---|---|---|---|---|
| `洁博利 广告位 30D 日期 Copy` | 已完成 | 2026-09-17 09:56 | 2026-09-22 09:19 | ✅ 活 |
| `洁博利 广告位 30D 日期` | 已完成 | 2026-08-15 16:16 | — | ⛔ 僵尸 |
| `洁博利 搜索词 30D 日期 Copy` | 已完成 | 2026-09-17 09:54 | 2026-09-22 09:50 | ✅ 活 |
| `洁博利 搜索词 30D 日期` | 已完成 | 2026-08-15 16:17 | — | ⛔ 僵尸 |

归一化后两组各自完全同名 → 旧的「多候选即报 `ambiguous` 拒绝猜」策略会让**该类报告永久失败**。
第一跑「搜索词」侥幸成功（轮询那刻僵尸行未渲染）、「广告位」失败 —— **两者其实都是定时炸弹**。

**修复**：`download_ad_reports.js` 的 `__mtime()` 从行内（ag-grid pinned 左列最后一格）取「上次修改时间」
转 `YYYYMMDDHHmm`，**后缀命中多个时取最新者**，日志打 `⚠ 报告名同名重复订阅，已取…`。
实测选中 `202609170956`（活的那个），未误取 08-15 僵尸。
🛟 兜底：挑错 → 下游「数据日期 ≥ 今天-3 天」闸门拦住，不会把旧快照灌进库。

**技术要点（下次别再摸索）**：
- 列表是 **ag-grid 虚拟滚动**（实测 `clientH=289 / scrollH=2700`，DOM 只常驻 ~11 行）→
  `querySelectorAll` 一次只拿得到视口附近几行，**必须滚动才能抓全**。
  技能里已放两个只读探针：`probe_report_links.py`（滚动收集 + 报重名组）/ `probe_report_rows.py`（抓行元数据）。
- 「下次运行时间」为空（`—`）+ 上次修改停留在很久以前 = **僵尸订阅**的可靠特征。

**第二轮结果**：洁博利 6/6 EXIT=0；灌库 `files=18 inserted=59,321 updated=39,012`（欧德思/AMS 被 file_hash 跳过）；
**JOOMRA DIRECT 由 09-14 推进到 09-20**。至此 **3 店 × 6 表 = 18/18 全部覆盖 2026-08-15/16 .. 2026-09-20，逐日无断档**。

**遗留（均属账号设置，AI 不动）**：① 洁博利控制台有 2 条僵尸重复订阅，建议人工删除；
② ~~洁博利缺「每日CPO单双计算」订阅~~ → **2026-09-23 作废**：CPO 报告已按用户要求整体移出自动化，无需补建。

### D.2 邮件渠道细节（Amazon 报告邮件 = 只有链接，没有附件）

> ⚠️ 本节描述的是**已被 TCC 拦死的备选路径**，保留供将来放行权限后复用。

邮件**不含附件**，正文只有 **48h 预签名 S3 直链** → 剥后缀解码后 **curl 直下，免登录后台**。
剥后缀正则：`/\d+/[0-9a-f][0-9a-f-]*/[A-Za-z0-9_\-=]+=452$`（**UUID 是 53 位，不是 36 位**）。
**渠道选型：走 QQ 邮箱**。脚本目录 `agent-master/ads-email-import/`。

**封控风险评估（2026-09-15）= 本环节不会触发封控**：
1. curl 的是 Amazon 自己签发的预签名 URL，免登录、无 Cookie；
2. Ads 官方支持在 report delivery 直接指定收件人邮箱；
3. 报告是聚合数据，不含 PII。

真正风险在**投递路径**而非邮箱品牌：
- ✅ 推荐：直接在 Ads 报告 delivery 收件人填 QQ 邮箱（Amazon 直投，邮件头干净）
- ❌ 划掉旧方案「Gmail 转发到 QQ」：转发会留 `Received:` / `X-Forwarded-*` 链，是投递路径分析唯一可见痕迹
- ⚠️ **一店一地址**：多店铺汇入同一 QQ = 弱关联线索，用子地址或分邮箱
- 🔴 **红线**：该邮箱**绝不可承担登录验证码 / OTP 汇聚**——OTP 时序特征是关联判定硬指标
- 真实痛点只有**可用性**：QQ 会拦带 S3 链接的 HTML 邮件 → 需把 `@amazon.com` 加白 + 退避重试

## E. 业务报告「按父商品」细节

- 权限：川鹏 + 欧德思启用；**洁博利无权限**（`enabled:false`，与广告权限两回事）
- 日界 = 太平洋时间；URL 左闭右开（单日 D → `fromDate=D&toDate=D+1`）
- `#/report?id=102:DetailSalesTrafficByParentItem&…`
- 表格 UI 常不出数据行但下载照样正确 → 就绪判断只看日期控件回读
- `kat-*` 是 shadow DOM lit 组件，**坚持 URL 驱动，不要注入日期**
- CSV 无日期列，靠文件名
- `br_to_rds.py`：`file_hash` 去重 + `ON CONFLICT DO UPDATE`（Amazon 会回溯修正）；title 空用 parent_asin 回填；自带补洞（扫最近 3 天）
- ⚠️ 别在太平洋凌晨手动跑当天（写残缺数据，且定时任务因文件已存在会跳过）

## F. 广告变更历史细节

- 真实 URL：`advertising.amazon.com/cm/history?entityId=…`（`/bulk-operations` 是左侧另一项）
- **CDP target id == Bridge `--target-id`**：`lsof -nP -iTCP -sTCP:LISTEN | grep ziniaobro` 找端口 → `curl 127.0.0.1:<port>/json/list` 枚举标签页 → `page exec --target-id`（川鹏2号 = 39380）
- 数据接口 `POST /cm/api/event-history?method=history`，**必带 `X-CSRF-token`**（无 → 403；用 GET → 404）；token 用 hook `window.fetch` + 点一次翻页捕获
- ⚠️ **10000 条硬截断且丢最旧**（7/1–9/13 实际 19,150）→ 7 天分片 + `totalRecords>=9000` 二分；`pageSize` 后端上限 10000
- 日期边界太平洋（-07:00）；**接口不返回操作者**
- 落盘：页面内 Blob 写进店铺 `downloadFolderPath`（别走 Bridge 返回，8.6MB 会截断）
- 筛选映射：竞价调整=`PLACEMENT_GROUP`、竞价方案=`SMART_BIDDING_STRATEGY`、预算=`BUDGET`、时间安排=`SCHEDULE`、状态=`STATUS`（落 CAMPAIGN.filters）；竞价=`BID`（AD_GROUP.DEFAULT_BID_AMOUNT + TARGETING_CLAUSE.BID_AMOUNT）
- **枚举须全翻译**（否则运营看不懂），导出后用 Counter 查残留英文
- ⚠️ 别用 `page visit` 导航在用的业务标签页（会被顶掉、内存丢）→ 一律 CDP `/json/new` 另开
- entityId：川鹏2号 `ENTITYD81ZAK5R7NX1`、欧德思 `ENTITY2RBS3FEZP3EW1`、洁博利 `ENTITY3OP6GF4YN1V0X`、AMS `ENTITY2BZ837BIZY5W9`（**只留本地，别进公开仓库**）

## G. FBA 重测细节

- 终态页伪装：`重量和尺寸相关问题 / FNSKU 详细信息 / 包裹尺寸… / 整页 0 button`。真身份在 DOM：`data-step-attr → currentStepName="inform_seller_not_eligible_for_re_measurement_p4s_usertask"`、`currentStepType="Success"` → **判定用步骤名，不看文案**
- 终端页能读出该 FNSKU 的尺寸 ⇒ FNSKU 在本账号内（读不到才该怀疑跑错店铺）
- 2026-09-15 复核：非库存类异常 10 条全部重跑 → 10/10 仍落地"不符合资格"，且每条都先过「起始步骤」校验、读到的尺寸各不相同 → 真被拒，不是残留页误读，当月不必再试
- 「每月 120 条上限」已证伪：9 月累计 XH1 154 + ZJ1 44 ≈ 198 条仍在跑
- 账号级限流：2026-09-15 08:56–11:05 可提交 77 条；13:48 后 XH1 重试 10 条 + YS1 全新 36 条的前 3 条全被拒（同一终态步骤）。全新 SKU 也被拒 = 账号当前无法受理新申请。疑日频上限或滚动窗口；**下次跑批即可证伪**（次日一早放行 = 日频/短期限流，仍全拒 = 月级限制）
- 判额度用**探针**：`allowSubmit=false` 跑到"继续"硬停 = 额度活，且不耗额度
- 必备防护：①就绪探测须命中起始步骤 `obtain_fnsku_for_us_...`；②终态页须校验 FNSKU 与当前一致，不一致 = 上条残留 → 重载；③`ALREADY_SUBMITTED` 但本 SKU 从未点过"继续" → 判残留页，**绝不记成功**
- 控制台熔断缺口：只认基础设施失败（`/结构|网络|targetId|exec|步数超限|连续/`），「不符合资格」被归业务失败不触发 → 用 `watch_run.py` 补（连续 3 条 not-eligible 自动暂停，基线法）
- 档位默认 aggressive（间隔 5–10s），长跑先切 balanced(10–20s)/conservative(20–40s)
- 跑批纪律：改 `state.json` 前**必须先停服务**（否则内存覆盖磁盘）；`pending` 元素是对象 `{sku, ts(ms)}`；换批必留根 `state.<组>-<日期>.json`；**看门狗必须用基线法**（`base_fail=len(failed)`，只看切片）；交付表名 `<运营组> 重测SKU <日期>.xlsx`
- v1.3.3 起 `saveState` 持久化 `inProgress`/`submitClicks` + 残留自动进 `failed` 并标注是否点过"继续" → 修掉「断电→漏账→重提=重复提交」
- 运营组现状：XH1 续跑中（源 186 条）、ZJ1 已完成 44/44
- GitHub `p1524607703-blip`：`ziniao-fba-controller`（v1.3.5）、`ziniao-ad-change-history`（v1.1.0）

## H. DSP

- ⚠️ RDS 完全不含 DSP 数据（`campaign_daily.ad_product` 只有 SP/SB/SD/STV）→ 任何"DSP 占比 0%"结论都是假的
- 只能从广告控制台手动导 CSV（`~/Downloads/DSP_广告活动_30D_日期.csv`）。字段：展示量/可见展示量/CTR/vCTR/总成本/购买量/品牌新客购买量/单次购买成本/销售额/长期销售/ROAS/长期ROAS
- 命名 `BRAND - 产品 - 阶段 - 受众 - KPI`；阶段 AW/CS；受众 All Audiences / Customer Acquisition P+ / Remarketing P+ / SIM / CMP；KPI Total Roas / CPDPV / eCPDPV（P+ = Performance+）
- 站内无「长期销售/长期ROAS」，DSP 有；长期比即时高 25–34% → 品牌广告复盘被系统性低估
- 待办 P0：建 `core.dsp_campaign_daily`（主键 = 广告主账户 + 活动编号 + 日期）
- WHITIN DSP 基线（2026-08-14~09-09，27 天）：花费 $4,515 / 销售 $48,308 / ROAS 10.70 / 长期 ROAS 13.75 / NTB 55.1% / CPA $2.63；同期站内 SP 3.91、SB 3.30、SD 5.58、STV 3.43 → DSP 是 SP 的 2.7 倍。在投：Toddler(W81K)、Clogs(Y71)
- 两个问题：①可见率仅 30.8%（CS 24.9%）②Clogs 效率优却只拿 34.7% 预算
- ③9/3 加量 54% → ROAS 掉 25–35%（用 BRONAX 做对照组排除季节性）。**加量纪律**：单次 ≤20–30%，观察 5–7 天；DSP 转化有 1–3 天归因延迟，最近 3 天不可信

## I. 「一份报告一张表」的 6 张事实表（2026-09-15 建）

| 表 | 行数 | 业务列 | 主键（在 account_id / ad_product / stat_date 之外追加） |
|---|---:|---:|---|
| `core.report_campaign_daily` | 2,397 | 20 | campaign_id |
| `core.report_placement_daily` | 6,829 | 36 | campaign_id, ad_group_id, placement |
| `core.report_targeting_daily` | 62,021 | 41 | campaign_id, ad_group_id, target_id |
| `core.report_advertised_product_daily` | 2,457 | 43 | campaign_id, ad_group_id, advertised_product_id |
| `core.report_purchased_product_daily` | 16,097 | 17 | campaign_id, ad_group_id, purchased_product_id |
| `core.report_search_term_daily` | 102,761 | 28 | campaign_id, ad_group_id, search_term |

共同结构：主键列 + 该报告实测有值的业务列 + `source_file_name` / `source_file_hash` / `row_hash` / `batch_id`(FK→`core.import_batches`) / `first_imported_at` / `loaded_at`。
每表都有：PK、`batch_id` 真外键、`(account_id, stat_date)` 索引、`campaign_id`(+`ad_group_id`) 索引、维列索引、表注释。共 70 条约束。

生成方式：`ads-email-import/_build_report_tables.py`（从 `information_schema` 逐列统计非空数，只保留有值的列）→ 产出 `sql/003_report_tables.sql`，可重复执行（先 DROP）。

### I.1 关键性质
- **`report_purchased_product_daily` 物理上没有 `spend` / `impressions` / `clicks` / `ctr_pct` / `cpc` / `acos_pct` / `roas`** → 想拿它算 ACOS 都算不出来。防呆做在 schema 层，不靠文档纪律。
- **投放侧四表 sum(spend) 守恒**：campaign = placement = targeting = 127,762.80；advertised_product = 127,698.66（差 64.14，系去重 192 行）。跨表对账时以这个为准。
- 主键冲突**直接报错**（迁移用普通 INSERT，不写 `ON CONFLICT DO UPDATE`）→ 不再有静默覆盖风险。
- 加载顺序：维表未建，事实表暂不互建外键（切面关系不是实体关系）；只「事实表 → `import_batches`」建 FK。

### I.2 已顺手修好的两处
1. `report_search_term_daily.ad_product` 由活动报告按 `(account_id, campaign_id)` 回填 → 102,761 行全部 = `Sponsored Brands`（原为空串）。
2. `source_file_name` / `source_file_hash` 从 `import_batches` 回填 100%（ODS 两列原全空 → 此前**没有行级文件血缘**，只能靠 `batch_id` 追到批次）。

### I.3 ODS 层保留
`core.ad_daily`（78 列宽表 + 月分区）与 `core.search_term_daily` **均未删除**，作为贴源层继续接收新导入。
将来只需在 ETL 尾部把 ODS 行分派进 6 张 report 表即可。

## J. 在售产品主数据（app.product_roster）核验明细

### J.1 源表结构（在售产品.xlsx，3 个 sheet，表头均在第 1 行）

| sheet | 列数 | 表头 |
|---|---:|---|
| WHITIN | 13 | 序号 / 款式图片 / 款号 / 分类 / 前台链接 / 排名 / 近30天销量预估 / 销量预估 / 评分 / 码段 / 工厂 / 负责的运营小组（+1 空列） |
| BRONAX | 9 | 序号 / 款式图片 / 款号 / 分类 / 前台链接 / 评分 / 码段 / 工厂 / 负责的运营小组 |
| Joomra | 9 | 同 BRONAX |

**真实数据行**：WHITIN 108 / BRONAX 19 / Joomra 22 = **149**。
⚠️ 三表的 `max_row` 是 113/104/127，多出来的行**全是真空行**（BRONAX r21–r104、Joomra r24–r127 无任何值），不是隐藏行、不是合并单元格。用 `max_row-1` 当行数会虚高一倍。

### J.2 字段要点
- **没有 ASIN 列**。ASIN 在「前台链接」里：`https://<slug>/dp/<ASIN>?...` → 正则 `/dp/([A-Z0-9]{10})`
- 链接前缀有两种脏数据形态：`https://newtab@www.amazon.com/...`（多数）与 `https://www.amazon.com/dp/...`（后追加的行）→ 只需 `.replace('://newtab@','://')`
- 「负责的运营小组」是人名串：多人用 `+`，多组用 `、`；可能带站点前缀（`美站`/`欧站`）和后缀备注（如 `欧站王爱菊要备注贴标`）
- 后 8 行（r17–r20 / r23）序号为空 = 后期追加款
- 4 个未上架款（WHITIN ZK601/602/603/605）链接为空

### J.3 计数字典（供对账）
- 分类 13 个：赤足鞋 62 / 运动鞋 43 / EVA拖鞋 14 / 水鞋 10 / 冷粘组合拖鞋 4 / 凉鞋 4 / 其他-乐福鞋 3 / 其他-厨房鞋 2 / 其他-棉鞋 2 / 其他-休闲鞋 2 / 其他-安全鞋 1 / 其他-赤足乐福鞋 1 / 其他-棉靴 1
- 工厂 9 个：好快 100 / 煜创 14 / 新德辉 10 / 森林酷鸟 7 / 凯辰 6 / 鑫泉 4 / 浩步 4 / 揭阳腾信 3 / 日胜皇 1
- 主导运营组 10 个：AJ 27 / XM 23 / ZJ1 23 / DD1 18 / LB1 13 / LW 12 / YS1 11 / ZF 10 / XH1 8 / YT1 4
- 跨品牌重名款号 5 个：Y15(W/B) / W20(W/J) / W30(W/J) / S5(W/J) / S71(W/B)
- 缺失：评分 7、ASIN 4、序号 9

### J.4 人名 → 组码（开发端维护，改 `PERSON_TO_GROUP`）
| 人名 | 组码 | 人名 | 组码 |
|---|---|---|---|
| 刘子娟 / 刘贞珍 | ZJ1 | 李丽斌 | LB1 |
| 阴鑫华 | XH1 | 谢丹丹 | DD1 |
| 林雅婷 | YT1 | 胡雪敏 | XM |
| 王爱菊 | AJ | 史雨珊 | YS1 |
| 林文 | LW | 王珍凤 | ZF |
| 林敏 / 沈玉灵 / 王卓玲 / 郑兰兰 | *（组员，不设码）* | | |

### J.5 建表 DDL 与用法
见 `backend/scripts/load_product_roster.py` 内的 `DDL` 常量。要点：
- `UNIQUE (brand, product_code)` —— 款号品牌内唯一（跨品牌会重名）
- 数组列 `operator_names` / `operator_groups` 保序，与「第一人=主导组」规则配合
- `is_listed` 由是否有父 ASIN 推导
- `row_hash` = brand|code|category|size_range|factory|parent_asin|operator_text 的 SHA-256
- 全量重刷：`TRUNCATE` 后 `\copy` 灌入（主数据是权威基准，不做增量合并）
- 复制方式：**先写临时 CSV，再用客户端 `\copy`**。⚠️ `psql -f -` 下 `COPY ... FROM STDIN` 的 `\.` 终止符会被当数据行；⚠️ `\copy` 是元命令不能塞进 `-c`

## K. 业务报告入库与 CPO 打通

### K.1 三方 ASIN 体系（最容易踩的坑）
| 集合 | 数量 | 来源 |
|---|---:|---|
| 广告事实父 ASIN | 37 | `core.report_advertised_product_daily.advertised_product_parent_id` |
| 业务报告父 ASIN | 428 | `core.report_business_parent_asin_period.parent_asin` |
| 在售产品主数据 ASIN | 145 | `在售产品.xlsx` 前台链接 `/dp/<ASIN>` |

- **广告 ∩ 业务报告 = 31** → CPO 分母可算
- **广告 ∩ 在售产品 = 0**、业务报告 ∩ 在售产品 = 9
- ⚠️ 结论：**主数据里的 ASIN 是子 ASIN（前台展示变体），广告/业务报告用的是父 ASIN**。要打通主数据与投放数据，必须补一张「父子 ASIN 映射」，光靠 ASIN 相等匹配做不到。

### K.2 表与加载器
- 表：`core.report_business_parent_asin_period`（DDL `business-report/sql/004_business_report_table.sql`）
  - 主键 `(account_id, report_start_date, report_end_date, parent_asin)`
  - 期间语义：单日 `(D,D)`；周快照 `(周一,周日)`。两者共存不互相覆盖
  - 兼容视图 `core.business_report_parent_asin_period` → 新表
- 加载器 `business-report/br_to_rds.py`
  - 连接改为读 `amazon-ads-console/backend/.env` 的 `RDS_DATABASE_URL`（原硬编码旧 RDS `121.41.134.56` / `postgres` / `~/.pgpass`）
  - `--init-ddl` 首次建表；`--dry-run` 只解析；`--force` 忽略 file_hash 去重
  - 幂等：文件级 `import_batches.file_hash` 唯一 + 行级 `ON CONFLICT DO UPDATE`
  - 落盘方式：先写临时 CSV 再客户端 `\copy`（避开 `-f -` 下 `COPY FROM STDIN` 的 `\.` 解析坑）
  - 店铺 → 账户：川鹏2号 = WHITIN `…42jh8psyvhiiiitpm4rnj4qhh`；欧德思美站 = BLOOMNEXT `…dfa7o7cwdl371d634ew58i919`；洁博利无权限
- 实测：18 份文件（2 店 × 8 日 + 2 周），**1,968 行**，全部 success

### K.3 父 ASIN → 运营组 的桥
```
campaign_name 第2段 → 取首 token → 归一化 → app.product_roster.product_code → owner_group
例如  ZJ1-W30 头条 低价 11.18
      第2段 = "W30 头条 低价 11.18"   注意不是纯款号！还要再切空格
      首 token = W30 → roster 查到 owner_group = ZJ1
```
- 归一化 `_norm_code()`：剥结尾的 `女 / 男 / W / M`（`W51女`→`W51`、`S71W`→`S71`、`W823男`→`W823`）
- 实测 **31/37 = 84%** 可桥；剩 6 个（S71W、W2030、W51女、W51男、W63、W85、W823男）在原表里确实对不上，归入「未归属」分组而不是硬塞

### K.4 控制台口径
- `dashboard_overview`：业务侧**限定在「当日有投放的父 ASIN」**，保证分子分母同口径，不让非投放商品稀释分母
- `dashboard_trend`：花费只取活动层（口径唯一）；广告单/广告销售额取推广的商品层；业务侧按窗口内被投放过的 ASIN 限定
- `_operator_rows`：广告侧与业务侧**共用同一套 ASIN→运营组 归属**（原先广告侧按活动名前缀、业务侧按 ASIN，两口径不一致）
- 质量标记 `ad_business_account_mismatch`：广告账户（anac1973）与业务报告 Seller 账户（WHITIN/BLOOMNEXT）不是同一个 ID，配对只能靠 ASIN —— 这个事实必须一直对外声明

### K.5 已知数据问题
- 🔴 **09-10 / 09-11 业务报告疑似日期范围用宽了**
  - 09-10 有 311 个 ASIN（邻居 129~164），其中 **166 个只在那天出现**（其他天只有 2~17 个独有）
  - 09-10 / 09-11 已订购商品数 10,619 / 10,590，是邻居（5,593~7,424）的 1.5~2 倍
  - 两个文件创建于 09-13 21:34 / 21:44（补拉窗口），09-12 是 21:31
  - 后果：这两天 CPO 被低估（0.58 / 0.48 vs 其他天 1.06~1.25）
  - **待办：重拉这两天核对**
- ✅ 周报可信：与 8 天并集重合 351/352

## L. 业务报告日期超宽的处理 与 父子 ASIN 映射方案

### L.1 日期超宽的识别与修正（可复用的判定法）
`business-report` 拉取用 URL 左闭右开，单日 D 应传 `fromDate=D&toDate=D+1`。
2026-09-13 的补拉窗口把 `toDate` 传成了 `fromDate+2`，导致：

| 文件名 | 实际覆盖 | 订单数 |
|---|---|---:|
| `…daily_2026-09-10.csv` | (09-10, 09-11) | 10,619 |
| `…daily_2026-09-11.csv` | (09-11, 09-12) | 10,590 |
| `…daily_2026-09-12.csv` | (09-12, 09-12) 正常 | 5,593 |

**判定方法（两个独立证据，互相印证）**
1. **订单数反解**：设 a=9/10、b=9/11、c=9/12 真值 → `F10=a+b`、`F11=b+c`、`F12=c`，
   可解出 a=5,622 / b=4,997 / c=5,593，自校验 `b+c=10,590=F11` 精确吻合，且反解值全部落回邻居区间
2. **集合包含**：`set(F11文件) ⊇ set(F12文件)` 为 True（129/129）→ F11 多含了 09-12 那天
3. 辅助信号：异常文件的创建时间挤在补拉窗口内（21:31~21:44），且 ASIN 数（311）远超邻居

**修正方式（关键设计）**
只把 `report_end_date` 从 D 改成真实结束日，**不删行、不改数值**。
因为所有单日查询都带 `report_start_date = report_end_date`，
改完之后这两天**自动退出 CPO 分母**，页面显示「缺业务报告」而不是一个放大 1.8 倍的错数。
重拉回正确文件后新批次会自动覆盖。脚本：`business-report/fix_wide_period_batches.py`（`--dry` 预览，会先探主键冲突）。

### L.2 父子 ASIN 映射：四个信号
基准 = **业务报告父 ASIN**（用户拍板）。主数据存的是子 ASIN，两者交集为 0，必须靠信号搭桥。

| 信号 | 做法 | 命中/428 | 特点 |
|---|---|---:|---|
| A | 报告**标题含款号**（词边界正则） | 109 (25%) | 零歧义，但只覆盖主数据里有的款号 |
| B | 广告 `campaign_name` 第 2 段款号（归一化剥 `女/男/W/M`） | 36 (8%) | 运营自己命名，可信度高 |
| C | 前台链接 slug 与标题的**重合系数** \|A∩B\|/min(\|A\|,\|B\|) ≥0.7 | 59 (14%) | 召回高、误配风险高。⚠️ 别用 Jaccard（slug 短、标题长，天然偏低） |
| D | Seller Central「管理库存」导出 | — | **唯一能到 100% 且零歧义的源** |

⚠️ **A ∩ B = 28，仅 19 一致，9 个冲突（32%）**。例：`B0GX1MVGZ9` 标题 `Z32` vs 活动名 `W75V2`。
→ **单信号绝不自动采信**。

### L.3 分层置信度规则（`build_parent_child_map.py`）
| 情形 | signal | confidence | status |
|---|---|---|---|
| A∩B 且一致 | `both` | high | confirmed |
| 仅 B / 仅 A | `campaign_code` / `title_code` | medium | confirmed |
| A 与 B 冲突 | `both` | low | **pending_review**（两候选都写进清单） |
| 仅 C | `slug_overlap` | low | **pending_review** |
| 全未命中 | `none` | none | **unmatched** |

实测分布：**confirmed 103 (24%) ／ pending_review 63 (15%) ／ unmatched 262 (61%)**

产出物：
- `amazon-ads-console/reference/product_mapping/父子ASIN映射_待核验.csv`（428 行，含父ASIN/款号/运营组/子ASIN列表/信号/置信度/冲突/标题）
- 表 `amazon_ads.app.asin_parent_map`（PK `parent_asin`；`match_signal` / `confidence` / `status` / `evidence` / `conflict` / `verified_by` / `verified_at`）—— **当前为空，不灌低置信度猜测**

⚠️ 踩坑：脚本第一版只读 `RDS_DATABASE_URL`（v2），把 `app.*` 表建到了数据仓库 → `app.*` 属应用层，必须用 `DATABASE_URL`。

### L.4 覆盖率天花板
主数据只有 144 个款号 / 149 个产品，业务报告却有 428 个父 ASIN（含已下架、非主数据品牌）。
所以**自动化匹配的上限受主数据规模限制**，不是算法问题。要覆盖全量必须补权威导出。

## M. 控制台角色 / CPO 细节（原 MEMORY.md §2 长尾）

### M.1 角色路由（2026-09-15 建）
- `ROLE_HOME` / `homeFor` 在 `router/index.ts`，登录后按角色跳首页（运营 → `/my-cpo`，其余 → `/dashboard`）
- **运营页 `/my-cpo`**（`MyCpoView.vue`）：只保留「CPO 单双数据情况」一个模块，列与管理页逐列一致（含「运营」列），行不可点
- 守卫：运营**只准** `/my-cpo`（其余一律回 `/my-cpo`）；非运营访问 `/my-cpo` → `/operator-cpo`
- 侧边栏按角色分流：运营固定单项（`visibleGroups` computed，防首屏先渲染管理端导航），不显示拖拽/恢复按钮、**不读写**本地布局缓存
- 后端 `GET /my-cpo` **带 `Depends(require_session)`**，运营组从会话 `operatorCode` 推导（`ZJ1`→`ZJ`），**不接收前端传参**（防越权）
- 🔴 但 `api/routes.py` 其余业务接口**全无 `Depends(require_session)`**

### M.2 运营 CPO 的单账户陷阱
管理页 `/operator-cpo` 的运营汇总原本**只取 1 个账户**（anchor = 洁博利 `7v98vtwh`，只有 AJ 活动 → 线上长期只出「爱菊」一行）。已给 `operator_cpo_summary` 加 `all_accounts` 开关；**用户拍板：运营页跨全部账户汇总，管理页保持单账户不动**（两页对爱菊数字会不一致，属已知取舍）。

### M.3 CPO 缺口结构（2026-09-18 实测，单日 09-14 口径）
当日总花费 $12,976.78，只有 **56.0%** 进得了运营 CPO 分子：
- `$3,812.10 (29.4%)` **爱菊全部花费缺业务报告分母** ← 洁博利 JOOMRA 无业务报告权限（全窗口花费 $288,646.77 100% 无分母）。**最大单块缺口，分摊规则救不了（缺的是分母）**
- `$1,458.56 (11.2%)` **子娟部分缺业务侧** ← AMS `anac1973 (C3S8S)` 是**纯 SB 账户**（花费 $247,468.53，占广告总花费 29%），无自己业务报告，靠"同日父 ASIN 在哪个业务账户出现"反推，一对多直接丢
- `$435.72 (3.4%)` 无产品映射「未归属」桶 ← 全窗口仅 3.6%（$31,026.77 父 ASIN 为 NULL/-1）
→ **能靠"SB 分摊规则"救回的只有 3.4%**；要提覆盖率，动作在数据权限（P0-1 拿洁博利业务报告权限 / P0-3 给 AMS 建静态归属表）。

### M.4 两个实锤 bug（2026-09-18 发现，未修）
- **Bug 1 —— 周/月粒度 `final_cpo` 永远 False**：`_period_range()` 把周期末尾算成未来日期 → `period_complete = complete_days == expected` 永不成立。实测 `operator_cpo_summary('2026-09-14','weekly')` → `expectedDays=7, coverageDays=1, final_cpo=False`。修法：`period_end` 截到"最后一个三项完整日"
- **Bug 2 —— 全局 `final_cpo` 被未归属桶一票否决**：`mapping_clean = unmappedAdSpend<=0.005 and businessUnmappedOrders<=0.005`，只要「未归属」有一分钱，**整页所有运营都拿不到最终标记**。修法：`final_cpo` 下移到运营粒度

### M.5 跨库约束（物化事实表的硬门槛）
`app.product_mapping` 在**应用库** `amazon_ads`，`core.report_*` 在**数据仓库** `amazon_ads_v2`，**PG 不支持跨库 JOIN** → 当前靠 Python 内存 `mapping.get()` 拼。要物化 `core.cpo_product_daily`，必须先把映射**单向快照进 v2**。另：事实表键必须是 `(date, product_code, parent_asin, account_scope, ad_type)`，**不能只用 product_code**（117 父ASIN → 109 产品代号，一对多，否则 A 账户花费 ÷ B 账户订单）。

### M.6 两个易误判点
- ✅ `cpo_imports.py` 写的是**视图**不是 bug：`core.business_report_parent_asin_period` 是 VIEW（over 基表 `core.report_business_parent_asin_period`，relkind=r 且有 PK），写入视图落到基表，是兼容层设计
- ⚠️ 看板默认落地「川鹏 / 2026-08-26」该日**无业务报告** → 首屏 CPO 显示「—」，不是故障
- ⚠️ 启动后端**必须用工具后台模式**（`nohup &` 会被回收）；两进程：后端 8000、前端 5173

### M.7 架构评审归档
`amazon-ads-console/docs/CPO归属架构-统一明细层评审.md`（2026-09-18，含 GPT「统一明细层」方案逐条对照 + 跨库约束 + 6 条复核 SQL）。**结论：GPT 那条 ①→⑦ 链路里 3 步已完成、2 步是"运行时而非物化"、1 步未落地——是口径确认，不是重构。**

## N. 广告费用分摊 SOP 口径（川鹏 AMS + 站内）

源文档在用户桌面、**不在本仓库**：`~/Desktop/周报告汇总/川鹏_AMS及站内广告费用分摊_SOP_V1.7.2_执行口径锁定版_2026-09-17.md`（23 章 / 887 行）；配套人话版 `川鹏广告费用分摊新旧算法说明.md`。
⚠️ **与 CPO 是两条完全不同的线**：CPO = 广告费 ÷ 业务销售额（控制台那套）；**本 SOP = 广告费在运营小组之间的再分配**。别混用。

### N.1 旧 vs 新
- 旧：`Campaign 总花费 ÷ 总归因件数 = 平均单价` → 各产品按归因件数直接领钱；跨组**有封顶**（不超原始花费）→ 创建组永远非负
- 新：先查户口（Campaign ID → 实际推广商品 → 成交 ASIN/SKU → 款式 → 运营小组，正向成交必须 100% 唯一映射），再算产品正常成本并做高低成本修正，**取消封顶**，允许创建组负承担

### N.2 修正三档（核心公式）
设 Campaign 原始平均单价 `c = Campaign 总花费 ÷ Campaign 总归因件数`；目标产品正常成本 `n = 该产品自己广告花费 ÷ 该产品自己广告归因件数`（**自己归因 ≥ 10 件**基准才有效）。

| 判定 | 最终分摊单价 |
|---|---|
| `c ≤ n × 0.5` | `n × 0.8` |
| `n × 0.5 < c < n × 2` | `c`（原样） |
| `c ≥ n × 2` | `n × 1.25` |

- ⚠️ **阈值是闭区间**：正好 `c = n × 0.5` 或 `c = n × 2` 都**触发修正**（SOP 写作 `≤` / `≥`）
- ⚠️ **修正价仍偏离正常成本**（落在 0.8n 与 1.25n）——设计意图是「往正常价靠一步」，不是拉到正常价：低成本从 0.2n 补到 0.8n（补偿但不全额），高成本从 2.5n 压到 1.25n（惩罚但不免单）
- ⚠️ **只改单价**：不改件数、不改账户总额。金额 = 修正单价 × 有效归因件数，**不封顶**，超出部分由创建组负承担吸收
- 验证算例（n=$10、C 归因 500 件其中 P 占 200 件）：c=$2 → 单价 $8 → P 承担 $1,600、创建组 -$600；c=$6 → 单价 $6 → $1,200 / $1,800；c=$25 → 单价 $12.50 → $2,500 / $10,000。三档均满足 `总花费 = 创建组 + 其他组`

### N.3 修正的适用范围（排除项，容易搞错）
只有**普通跨组 Halo** 才执行 0.5 / 2 倍修正。以下一律**不执行**：
1. **同小组不同款 Halo** — 保留归因事实、不产生组间转移、费用留在创建组
2. **Campaign 实际直接推广的其他组产品** — 属于该产品「自己的广告效果」，按 **Campaign 原始平均成本**分摊
3. **产品自己广告归因 < 10 件** — 基准无效，按原始平均成本
4. 有花费 0 归因 → 100% 创建组承担、不跨组、不修正
5. 有归因无花费 → 不进分摊、不反推成本（仅留 $0 审计记录）

### N.4 跨账户归因不对称专项保护
对象：**欧德思 XM1 / XM2、洁博利 AJ**。**只有当月在该来源实际投放过，才允许承接该来源的 Halo**；AMS 与川鹏站内资格独立、**不能互借**；未通过资格的 Halo 保留原始归因但不参与分摊，费用回创建组、且不得在后续修正中重新进入。**专项保护优先于高低成本修正。**

### N.5 其他硬约束
- 广告范围：SP + SB/SBV + SD + STV，**只要当月有真实花费就进池**（0 归因也进）；**Campaign ID 是唯一主键**，同 ID 只算一次（防 SB/SBV 双标签重复计费）；ID 必须按**文本**读取，禁浮点 / 科学计数法 / 截断
- 成本先按 Campaign ID 汇总整月；归因件数按 `Campaign ID + 成交 ASIN/SKU` 汇总后再算
- 优先级：实际推广商品 **>** Campaign 名称；原始成交 ASIN/SKU **>** 旧加工结果
- **映射可复用，金额必须全量重算**（不沿用上期金额/花费/件数/跨组额）
- **9 件 vs 10 件**是边界验收门
- 分币 `ROUND_HALF_UP`，多目标用最大余数法，**差额只能在本 Campaign 内解决**（不得跨 Campaign 借额）
- 交付 Excel 固定 8 页签 + 表头/列宽/配色/冻结窗等全版式，**不得加技术页/调试页/过程页**
- 证据不足且**影响金额** → 停止交付，**不猜不补不凑**；仅影响 $0 审计 → 可出结果但须列明缺口

### N.6 两套成本 + 执行顺序（用户确认的理解要点）
- **要算的不是一套成本，是两套**：① 每个 Campaign 一个原始单价 `c`；② 每个产品一个正常成本 `n`。两套都**当月全量重算**，不许沿用上期
- **关键因果**：`n` 的分子分母（"自己广告"花费 / "自己广告"归因件数）**不能直接取**，必须先完成归因三分类（自己广告 / 同组 Halo / 跨组 Halo）才能筛出来 → **先分类、后算基准**。这是整条链上最容易倒着做错的一步
- `n` 是 **AMS + 川鹏站内合并一套**基准（不是各来源各一套）
- 四份输入缺一不可：广告活动（花费）+ 达成转化的商品（归因件数）+ 推广的商品（推广归属）+ 映射表（ASIN/SKU → 款式 → 小组）

### N.7 跨组款号归属口径（2026-09-21 用户拍板 + 全量验证）

**判定链（唯一正确路径）**：`子 ASIN ──唯一──▶ 父 ASIN ──唯一──▶ 运营组`。三条边全部唯一，已用全库 7,236 个子 ASIN 验证，**冲突数全为 0**（子ASIN→多组 0 / 子ASIN→多父 0 / 父ASIN→多组 0）。
**推论：款号 `product_code` 不参与分组** —— 只是产品系列标签，不进分组键、不进 GROUP BY。归因侧只给子 ASIN 时**不需要先找父 ASIN**，一步定组，覆盖归因件数 **99.72%**。

全库跨组款号恰好 **7 个**，分三类（裁决表 → `~/Desktop/周报告汇总/跨组款号裁决表_2026-09-21.csv`，口径文档 → 同目录 `跨组款号归属口径_V1_2026-09-21.md`）：

| 类别 | 款号 | 裁决 | 依据 |
|---|---|---|---|
| **A 同人分细组** | `S71` | **算同组**（XM1+XM2 合并） | 两细码同属**胡雪敏**（`operator_name_map`：胡雪敏→XM）。**全库唯一真正双投的款号**：XM1 `B0DGCM33J2` $13,345.85 ／ XM2 `B0DK7YD2KT` $23,179.71 |
| **B 双投共款** | `W30`/`W63`/`W85` | 按**各自父 ASIN** 定组，可由子 ASIN 反推 | 两边子 ASIN 集合**完全不重叠**（0 重叠）→ 无歧义 |
| **C 男女款分列** | `W75V2`/`W81V2`/`W81V5` | 按父 ASIN 定组（**性别天然区分**） | 男女款在 Amazon 本就是独立 listing（独立父 ASIN）→ 「男女款区别」=「父 ASIN 不同」。规律：**XH1(阴鑫华)=女款 / ZJ1(刘子娟)=男款，3 款 100% 一致零例外**；款号命名里也带约定（`W81女`/`W87男`/`W87女`） |

⚠️ **类别 B 的重大偏差（与用户描述不符，需业务确认 Halo 口径）**：用户说 W30/W63/W85 是"两个运营同时投广告"，但**广告侧只有 ZJ1 在投，YS1 侧零投放（$0.00 / 0 行）**：

| 款号 | YS1 广告花费 | ZJ1 广告花费 |
|---|---|---|
| W30 | **$0.00** | $743.55（1 个活动） |
| W63 | **$0.00** | $14,148.38（3 个活动） |
| W85 | **$0.00** | $1,883.57（5 个活动） |

而 **YS1 侧的成交真实存在，全部挂在别人的活动下 = 标准跨组 Halo**：W63 有 **126 件 / $5,415.99** 挂在 ZJ1 活动下；W85 有 53 件 / $2,175.33；W30 有 58 件 / $2,002.88（另有少量挂 XM1 / YT1）。
**影响**：W63 的 ZJ1 活动，`c` 的分母含 YS1 的 Halo 则为 720 件（`c`=$19.65），剔除则为 594 件（`c`=$23.82）—— **差 21%，决定 ZJ1 要不要把成本分给 YS1**。方案甲（Halo 计入分母）= ZJ1 补贴 YS1；方案乙（Halo 剔除分母）= 按负承担/跨组分摊另行处理。**待业务拍板，不擅自定。**

### N.7.1 跨组口径复核修订（2026-09-21；含 V1.2 重大更正）

> 🔴 **V1.2 更正（务必先读）**：下面 ② 里写的「按父列筛 67 件 / 按子ASIN链 136 件，真实 136」**是错的**。
> 真相：`川鹏_达成转化的商品.csv` 的**父 ASIN 列 100% 为空**（18,938/18,938 units），`AMS_` 那份只 0.2% 空。
> 两份是**同一账户 anac1973 相隔一天导出的两个「30 天翻滚窗口」快照**（川鹏 08-15~09-13 / AMS 08-16~09-14），重叠约 29 天、内容约 95% 相同，**被叠加导入**。
> **所以 136 是虚增值，去重真值 = 72 件 / $3,032.91。** 广告侧同理：ZJ1 的 W63 花费 `$14,148.38` 去重后 = **`$7,310.26`**。
> **正确取数三步**：① 子 ASIN 链定位 → ② **按 `(账户,日期,活动,广告组,成交ASIN)` 去重取 max** → ③ 再聚合。少第 ② 步就拿到虚增值。
> **全库去重真值**：广告侧 `$857,856.34 → $734,801.87`（虚增 `$123,054.47`）；归因侧 `113,080 → 94,887 件`、`$3,248,953.84 → $2,609,168.25`（虚增 18,193 件 / $639,785.59）。**三套独立算法（FULL OUTER JOIN / 择一快照 / 排除重复文件）结果分毫不差。**

> **🔴 V1.3 补（2026-09-21）：两份快照的关系已钉死 —— 同一账户，重叠期 AMS ⊇ 川鹏**
> ① **同一账户**：两份 `account_id` 都是 `amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz`、`account_name` 都是 `anac1973 (C3S8S)` → **不存在「川鹏账户 vs AMS 账户」，只有一个账户的两份窗口导出**。
> ② **重叠期 08-16~09-13**：行级键（日期+活动ID+广告组ID+商品名）全外连接 → **仅川鹏有 = 0 键 / $0.00**，仅 AMS 有 253 键 / $7,134.01，两边都有 2,346 键（数值 85.9% 相同）；活动层面仅川鹏有 = 0 个，仅 AMS 有 4 个。→ **正确说法是「AMS 包含川鹏」，不是反过来。**
> ③ **但不等同**：AMS 多 7 天（09-14~09-20，$23,470.90）+ 4 个活动；川鹏多 1 天（**08-15，$4,644.19**，这是它唯一不可替代的部分）。全期「仅川鹏有」111 键里 82 键在 08-15，其余 29 键是每天 1 键的渲染差异行。
> ④ **差异成因**：同一份报告两条导出通道渲染商品名方式不同 —— `AMS_` 文件 3,174 行 **100% 带 `__advertised__<hash>`**；`川鹏_` 文件 2,457 行 **0% 带 hash**、其中 30 行商品名 = `-1`（占位，$2,275.04）。实证：活动 `ZJ1-W823男 视频 小词广泛 4.9` 2026-08-20 同组同花费 $94.52，AMS 写 `WHITIN Men Wide Hi-Top…Grey Gum 11` + hash，川鹏写 `-1` + 空。**→ 去重键一旦含商品名，这些行永远配不上对。**
> ⑤ **去重机制没坏，坏的是键**：批次 213/214/215（广告位/活动/投放）跳过率 96.7% / 96.6% / 97.0% ✅；批次 216/217/218（推广的商品/搜索词/达成转化的商品）跳过率 **0%** 🔴。
> ⑥ **导入时间线**：批次 54 = `川鹏_推广的商品` 2026-09-15 14:27 → 先落 **V1 旧表 `core.ad_daily`**，V1→V2 迁移时整批带 `batch_id=54` 平移进新表；批次 216 = `AMS_推广的商品` 2026-09-16 11:04 直接灌新表，**2,640 行全插 0 跳过**。
> ⑦ **逐表虚增**（口径=逐日期择一，最新快照优先）：`advertised_product` 花费 $275,023.11→$151,968.64（虚增 **$123,054.47**）｜`search_term` $275,467.49→$152,348.13（虚增 $123,119.36）｜`purchased_product` 销售额 $1,431,027.13→$791,241.54（虚增 **$639,785.59**）、件数 40,760→22,567（虚增 **18,193**）｜`targeting` 仅残留 $1,707.15｜`campaign` 与 `placement` **虚增 $0.00（已正确去重）**。
> ⚠️ **各表虚增不可相加**（同一笔花费在多表各算一次，加起来 $247,880.98 是幻觉）；**分摊只能取 `core.report_advertised_product_daily` 一张表。**
> ⚠️ **写 SQL 别用 `sum(a.v + b.v)`** —— 某日期只有一侧有值时该式为 NULL 会静默丢数据，必须 `sum(COALESCE(a.v,0)+COALESCE(b.v,0))`。我第一版就踩了这个坑，把「库里」算小了 $28,115。
> 🔧 脚本：`~/.workbuddy/skills/amazon-ad-cost-attribution-audit/scripts/snapshot_relation.py`（多源账户识别 → 同一性判定 → 行级子集关系 → 逐表虚增）

> **🔴 V1.3 补2（2026-09-21）：那 4 个「AMS 独有活动」是窗口差异，不是「只在 AMS 投的广告」**
> 用户曾推论「AMS 多出的活动 = 只在 AMS 账户里投的广告」→ **已被证伪**。
> ① 那 4 个（`YT1-WK103 视频 广泛girl-audience WR31` / `YS1-Z10 头条旗舰店water shoes广泛-09.16三款` / `YT1-WK101 视频 ASIN BU31` / `ZJ1-W85816351 头条 大词广泛 9.19`）**首个有数据日期都在 09-14~09-18**，存在期全在 09-14 之后，**重叠期(≤09-13)花费全部 = $0.00**；活动名里直接写着创建日（`09.16`、`9.19`）。川鹏窗口 09-13 关闭 → 物理上照不到。
> ② **窗口对齐（只比共同覆盖的 08-16~09-13）后：活动数 AMS 102 = 川鹏 102，两边都有 102，仅川鹏有 0，仅 AMS 有 0。**
> ③ **运营组覆盖 8 = 8，逐组活动数逐一相等**：AJ1 22/22 ｜ AJ2 4/4 ｜ DD1 4/4 ｜ XM1 6/6 ｜ XM2 9/9 ｜ YS1 2/2 ｜ YT1 20/20 ｜ ZJ1 35/35；花费差合计仅 **$799.08**（0.6%），全部来自商品名 `-1` 渲染差异行。
> ④ 另有 11 个「重叠期花费 = 0」的老活动（首日 08-16/08-17）**在川鹏文件里也有** → 分界线严格卡在 09-13/09-14。
> 🔴 **结论：川鹏那份文件里装着全部 8 个运营组（含 YS1/AJ1/AJ2/DD1），不是「只有川鹏的人」。文件名「川鹏」是可随时改的订阅标签，≠ 账号范围、≠ 品牌范围、≠ 运营组范围。不存在「投在川鹏」与「投在 AMS」两批广告 —— 只有一个账户的一批广告被两个订阅各导一次。** 正确动作是**只留一份、按日期取最新**，不是「把 AMS 补进川鹏」。

**① 「YS1 零投放」应表述为「该款号上零投放」。**

按活动名前缀统计全库广告花费：XM1 $220,516.58 ｜ AJ2 $199,157.04 ｜ ZJ1 $139,272.26 ｜ XM2 $138,677.79 ｜ AJ1 $127,133.21 ｜ **YS1 $19,104.12** ｜ YT1 $12,051.29 ｜ DD1 $1,944.05。
YS1 在投 $19,104，只是投在**别的产品**上（`B0DSGD3CKR` $8,620.67 / `B0DSFVZND6` $8,234.06 / `B0CRD8YW24` $2,249.39），一个都没落在 7 个跨组款号里。**报告里必须写「该款号上未投」。**

**② 归因侧 `purchased_product_parent_id` 空值 —— 定性已更正（见上方红色块）。**

空值率参考（V1.2 已定性为「文件问题」而非「列问题」）：BLOOMNEXT 0.0% ｜ JOOMRA 1.3% ｜ **anac1973 50.3%** ｜ 全表 17.2%。
**取数规矩不变（且必须加上去重）**：

```
🚫 禁止： WHERE purchased_product_parent_id = '<父ASIN>'
✅ 必须： WHERE purchased_product_id IN (<该父ASIN的全部子ASIN>)   ← 只此一步不够！
        再按 (stat_date, campaign_id, ad_group_id, purchased_product_id) 去重取 max(units)
```

⚠️ **两张表写法不能混用**：广告侧 `advertised_product_parent_id` 正常可用，归因侧不可用。

**③ W63 的 YS1 侧按活动前缀拆（**去重真值**）**：ZJ1 **67 件** ｜ YT1 3 件 ｜ XM1 1 件 ｜ YS1（自有活动，花费 $0）1 件 → 合计 **72 件 / $3,032.91**。**ZJ1 占 93.1%，Halo 结论不变。**（原样含虚增为 126/6/2/2 = 136 件）

**③b Halo 影响重算（去重真值）**：W63 的 ZJ1 活动花费 **$7,310.26**；ZJ1 自家 W63 归因 **315 件**；YS1 挂在 ZJ1 活动下 **67 件**。
→ 分母含 Halo = 382 件 → `c` = **$19.14**；分母不含 Halo = 315 件 → `c` = **$23.21**。**仍差 21.3%**（原 V1.1 算的 21% 巧合守住 —— 因为分子分母同时被虚增约一倍，**但绝对金额全错**）。

**③c W63 的 YS1 侧 100% 是 Halo**：Amazon 自带 `halo_units/halo_sales` 列，取去重值测得 halo_units = 72 = units（100%）。即该侧**没有任何一笔是「看了 W63 广告买 W63」**。
全库同口径：**73.0%** 的归因件数是 halo（82,523 / 113,080）；其中**跨父 ASIN（跨商品线）14,141 件 / $454,626.64** —— 这才是真正会引发跨运营组结算的部分。

**④ 7 款号广告侧投放全景（去重真值）**：

| 款号 | 父 ASIN | 组 | 广告花费（去重） | 状态 |
|---|---|---|---|---|
| S71 | `B0DGCM33J2` | XM1 | $13,345.85（单源，干净） | ✅ |
| S71 | `B0DK7YD2KT` | XM2 | $21,118.10（原样 $23,179.71） | ✅ |
| W30 | `B0D4JVR9V6` | YS1 | $0.00 | ❌ |
| W30 | `B0DRV4NG1P` | ZJ1 | $391.10（原样 $743.55） | ✅ |
| W63 | `B08LPXY2R4` | YS1 | $0.00 | ❌ |
| W63 | `B0D3ZRW4D6` | ZJ1 | $7,310.26（原样 $14,148.38） | ✅ |
| W85 | `B0CGLRTDVN` | YS1 | $0.00 | ❌ |
| W85 | `B0CLV667HH` | ZJ1 | $951.51（原样 $1,883.57） | ✅ |
| W75V2 | `B0BW4783S9` | XH1 女 | $0.00 | ❌ |
| W75V2 | `B0DPWWH9LH` | ZJ1 男 | $1,228.16（原样 $2,384.69） | ✅ |
| W81V2 | `B0FRNCXHZC` / `B0CW13XPHN` | XH1 女 / ZJ1 男 | $0.00 / $0.00 | ❌❌ |
| W81V5 | `B0DLB3VG96` / `B0DKBQTXWN` / `B0HH3NKDBK` | XH1 女 / ZJ1 男 ×2 | $0.00 ×3 | ❌❌❌ |

**结论**：① `S71` 是唯一真双投 → 「算同组」必须执行；② `W81V2`/`W81V5` 广告侧完全 $0；③ `XH1`（阴鑫华）在这 3 个男女款上一分未投。

### N.7.2 款号跨品牌重名 & JOOMRA「AJ 投 ZJ1 的货」（2026-09-21 用户提问触发；当晚被用户纠正，已定性翻转）

> 🔴 **2026-09-21 晚 · 用户纠正 + 全链复核后翻转**：本节 B 段的 `B0DTK7FK2M` 当初被定性为「用前缀还是用父 ASIN 的口径之争」——**错了**。真相是**映射表里有一行脏数据**。用户原话：「前端表里的 W20 应该是 AJ 运营店铺的 **W20J（W2030J）**，归属 **B0DTK7FK2M**」。

**A. 跨 scope 重名款号 —— 从 5 个修正为 4 个**

| 款号 | 涉及 scope | 组 | 判定 |
|---|---|---|---|
| ~~`W20`~~ | ~~JOOMRA / WHITIN~~ | ~~ZJ1 / ZJ1~~ | ❌ **不是重名**，是错标（见 B） |
| `Y15` | BLOOMNEXT / WHITIN | LB1 / LB1（28 / 1 行） | ✅ 真重名，同组 |
| `Y70` | BLOOMNEXT / WHITIN | XM1 / XM1（22 / 43 行） | ✅ 真重名，同组 |
| `YG02` | BLOOMNEXT / WHITIN | XM1 / XM1（1 / 54 行） | ✅ 真重名，同组 |
| `YG10` | BLOOMNEXT / WHITIN | XM1 / XM1（19 / 24 行） | ✅ 真重名，同组 |

→ 这 4 个**两边都同组，不串组**；但按 `product_code` 聚合而不带 `account_scope` 会把两边子 ASIN 合并。**铁律：按款号下钻，`GROUP BY` 必须带 `account_scope`。**
> ⚠️ **`W20` 被证伪**：`app.child_asin_mapping` 里 `product_code='W20'` 共 70 行 = WHITIN/ZJ1 **69 行**（父 `B0D4F33NRM`，真 W20）+ JOOMRA/ZJ1 **1 行**（父 `B0DTK7FK2M`，**错标**）。把那 1 行改成 `W2030J`/`AJ1` 后，**W20 就只剩 WHITIN 一家**。此前「5 个跨品牌重名」的结论建立在脏数据上。

**B. 🔴 真根因：`B0DTK7FK2M` 下有 1 行「自指 + 错标」把整行 product_mapping 带偏了**

`B0DTK7FK2M` 的真实身份（Amazon 官方业务报告佐证，**163 个子 ASIN 全部报它为父、7,852 行、08-01~09-20 单值无冲突**）：
- 自身标题 = `Joomra Women's Trail Running Barefoot Shoes Zero Drop Minimalist Sneakers`（**真实在售 listing**，不是虚拟父体）
- `child_asin_mapping` 下 **162 行**：其中 **161 行 = `W2030J` / AJ1** ✅，**1 行 = `W20` / ZJ1** ❌

那一行就是：
```
child_asin = B0DTK7FK2M   parent_asin = B0DTK7FK2M   product_code = W20   operator_group = ZJ1
```
**自指行（child = parent），款号错 + 组错。** `product_mapping` 按 parent_asin 聚合时被这一行带偏 → 整条登记成 `W20 / Joomra / ZJ1 / status=mixed_parent`。

**后果（费钱的那一步）**：用 `advertised_product_parent_id='B0DTK7FK2M'` 归组时，该父下 **$71,332.51**（10,684 行 / 108 个子 ASIN，08-15~09-20，**数据已从 $46,756.63 长大**）全部算给 **ZJ1**；而它 **100% 由 23 个 `AJ1-*` 前缀活动产生**。
→ **ZJ1 多背 $71,332.51，AJ1 少算 $71,332.51。**

> 🔴 **此前「口径之争」的判断作废**：当初写「用前缀归组 → 算给 AJ；用父 ASIN 归组 → 算给 ZJ1，差 $46,756.63，这证明父 ASIN 才是唯一锚点」。
> **正确表述是：这跟口径无关，是数据错。** 父 ASIN 仍然是唯一锚点，只是**这个父 ASIN 的映射行需要先修**。
> ⚠️ **教训**：当「活动名前缀」与「父 ASIN 映射」冲突时，**先怀疑映射表那几行**（尤其自指行），别急着上升成方法论之争。

**待执行的修正（2 行，等用户确认后执行；PK 是 `parent_asin`，单行更新不会撞唯一键）**

```sql
-- 修正 1：product_mapping
UPDATE app.product_mapping
   SET product_code='W2030J', operator_group='AJ1', status='confirmed'
 WHERE parent_asin='B0DTK7FK2M';           -- 改前: W20 / ZJ1 / mixed_parent

-- 修正 2：child_asin_mapping 的那行自指
UPDATE app.child_asin_mapping
   SET product_code='W2030J', operator_group='AJ1'
 WHERE child_asin='B0DTK7FK2M' AND parent_asin='B0DTK7FK2M';
```

**C. `B0DTK7FK2M` 之外，AJ 前缀活动投的货（复核后 ✅ 无其它问题）**

| 父 ASIN | 花费（原样） | 映射表登记 | 前缀 | 一致？ |
|---|---|---|---|---|
| `B0965389V6` | $123,672.30 | Y11/AJ2 | AJ2 | ✅ |
| `B0DLJ82KFX` | $32,873.62 | S5/AJ1 | AJ1 | ✅ |

**D. 顺带查清：`W2030J` 名下 3 个父 ASIN + 58 行空父**

| 父 ASIN | 子行数 | 自指行 | 组 |
|---|---|---|---|
| （空） | **58** | 0 | AJ1 |
| `B0DTK7FK2M` | 161 | 0 | AJ1 |
| `B07TT6CMHM` | 1 | 1 | AJ1 |
| `B0DDSZ5PDF` | 1 | 1 | AJ1 |

→ **58 行 `parent_asin` 为空的全是 `W2030J` / AJ1 / JOOMRA**，且**在 Amazon 业务报告里查不到任何一个**（无业务数据）→ 无证据支持补父，**暂不动**，待业务确认这批子 ASIN 是否已废。
→ 另 3 行 `HB001`/AJ1/JOOMRA 的 `parent_asin` 也为空（同类问题）。

**E. 全库自指行规模：140 行**（旧文档写 135，已增长）。Top：`YG10`/XM1 2 行、`W2030J`/AJ1 2 行、`W20`/ZJ1 2 行、`Y70`/XM1 2 行、`Z31`/LW1 2 行、`W81V5`/ZJ1 2 行、`S601`/AJ2 2 行、`S885`/DD1 2 行……
→ **自指行不破坏分组（child=parent 时父唯一），但会**：① 让 `product_mapping` 的「一个父一行」被单行带偏（本例就是）；② 父子数统计虚高。**建议把自指行的 product_code/operator_group 与同父多数行对齐。**

### N.7.3 父体合并留下的「僵尸父 ASIN」—— W81V5 双 ZJ1 父的真相（2026-09-21 用户看前端截图提问）

**现象**：前端「产品映射」按 ZJ1 筛选，W81V5 出现两行 —— `B0DKBQTXWN` 和 `B0HH3NKDBK`，用户怀疑 `B0DKBQTXWN` 是坏数据。

**结论：两个 ASIN 都合法（10 位 / 格式合规 / 都在 Amazon 业务报告里），但 `B0DKBQTXWN` 是 2026-08-28 一次父体合并前的旧父体，应该退休。**

🔑 **判定「父体合并」的时间线指纹**（拿子 ASIN 逐日看 Amazon 官方 `parent_asin`）：

| 期间 | Amazon 报的父 | 含义 |
|---|---|---|
| 2026-08-01 ~ 08-27 | `B0DKBQTXWN` | 旧父体 |
| **2026-08-28（仅 1 天）** | **各子 ASIN 报「自己」** | **合并过渡态指纹** |
| 2026-08-29 ~ 09-20 | `B0HH3NKDBK` | 新父体 |

受影响子 ASIN：`B0DKBTMYCK` / `B0DKBTRBWZ` / `B0DKBW8K6G` / `B0FNJG4WW5` / `B0DKBV36LP`（`B0DKBWYXSQ` 是 08-28~09-08 自指，过渡期更长）。
→ **「某天全部子 ASIN 都报自己为父」= 亚马逊那次合并操作留下的指纹**，比任何日志都好用。

**旧父 vs 新父 的可判据**：

| | `B0DKBQTXWN`（旧） | `B0HH3NKDBK`（新） |
|---|---|---|
| 自身标题 | **`B0DKBQTXWN`（标题=ASIN）** | `WHITIN Men's Wide Leather Barefoot Fashion Sneakers W81V5` |
| 性质 | **虚拟父体**（无自身 listing） | 真实 listing 被提升为父 |
| 自身行最后日期 | **2026-08-27** | 2026-09-16（仍活） |
| 合并后作为父的行数 | **0**（彻底失去全部子） | 141 |

**影响面**：`B0DKBQTXWN` 下 15 个子 ASIN，**7 个合并后彻底断流**（`B0DKBQTXWN`/`B0DKBT4GDT`/`B0DKBTK8YB`/`B0DKBV6JVQ`/`B0DKBV7Y74`/`B0DKBV2NB`/`B0DKBWYXSQ`），8 个存活但已改挂新父。
⚠️ **`app.product_roster` 里 W81V5 的「前台链接」= `/dp/B0DKBV6JVQ`** —— 而 `B0DKBV6JVQ` 正是**合并后已死的子 ASIN**（数据止于 08-19）。**主数据的链接也过期了。**

**对归因的影响：0。** 两个父都是 `W81V5` / `ZJ1`，同组同款号 → 分摊结果不变。**只是前端多一行「僵尸父体」。**

> 🔴 **`status` 机制的盲区（重要）**：`product_mapping.status` 现有 3 个取值 —— `confirmed` 124 ｜ `confirmed_no_business` 10 ｜ `mixed_parent` **仅 1**（就是 N.7.2 的 `B0DTK7FK2M`）。
> **`mixed_parent` 只抓「一个父 → 多个款号/组」，抓不到「同款号同组但有多个父（合并残留）」。**
> 所以 W81V5 的僵尸父仍然是 `confirmed`，W81V2 的 `B0FRNCXHZC`/`B0CW13XPHN` 同理。**建议加一条体检规则：同 `(brand, product_code, operator_group)` 下出现 >1 个父 ASIN → 全部降级为待人工确认。**

**怎么看「标题=ASIN」**：全库有 **110 个** ASIN 的标题等于自身 → 虚拟父体是普遍现象（被当成父的 ASIN 共 676 个）。**判据：标题=ASIN 且自身行在某个日期后彻底消失 = 已废父体。**

### N.8 组码 ↔ 运营对照（`app.operator_name_map`，15 行）

| 组码 | 运营 | 备注 |
|---|---|---|
| AJ | 王爱菊 | **粗码**；细码 AJ1/AJ2 |
| XM | 胡雪敏 | **粗码**；细码 XM1/XM2 |
| ZJ1 | 刘子娟 | 同时含 刘贞珍 |
| YS1 | 史雨珊 | |
| XH1 | 阴鑫华 | |
| LB1 | 李丽斌 | |
| YT1 | 林雅婷 | |
| DD1 | 谢丹丹 | |
| ZF | 王珍凤 | **粗码** |
| LW | 林文 | **粗码** |
| — | 林敏 / 沈玉灵 / 王卓玲 / 郑兰兰 | 只在组员位置出现，不单独设组码 |

⚠️ **这张表里 `XM`/`AJ`/`ZF`/`LW` 是粗码，只是人名字典，不能用来定组**。定组一律以 `child_asin_mapping.operator_group` 的 3 位细码为准（与 O.3 的 roster 粗码问题是同一个坑）。

## O. 映射表与事实表体检结论（2026-09-19）

配套只读脚本（`amazon-ads-console/backend/`）：`_mapping_audit.py`（表总览/任意SQL）、`_mapping_coverage.py`（覆盖率）、`_mapping_paths.py`（逐笔路径+缺口）、`_mapping_gaps.py`（导出缺口CSV）、`_mapping_state.py`（映射现状快照）、`_p0_dup.py`/`_p0_cmp.py`/`_p0_excess.py`（P0 重复导入对账三连）、`_mapping_verify.py`（多路径兜底验收）、`_mapping_rootcause.py`（缺口按父ASIN归因）、`_mapping_gap_export.py`（2026-09-21 复核导出）、`_crosscode_rule.py`（跨组款号验证）、`_crosscode_export.py`（裁决表导出）。
连库姿势：`.venv/bin/python` + `app.core.config.settings`，复刻 `run_rds.py` 的 `_configure_pg_env` 拆 DSN 成 `PG*`/`RDS_PG*` 后走 `psql` 子进程。⚠️ `backend/.env` 不能 `source`（含 `&` → zsh parse error）。⚠️ **跨库不能 JOIN**：`app.*` 在 `amazon_ads`、`core.*` 在 `amazon_ads_v2`，覆盖计算必须在 Python 里做。⚠️ `psql -t -A` 回传的是**字符串**，`f"{n:>7,}"` 会 `ValueError: Cannot specify ',' with 's'`，记得 `int()`。

### O.1 映射表选型（结论）
| 表 | 行数 | 用途 | 判定 |
|---|---|---|---|
| **`app.child_asin_mapping`** | **7270** | 成交ASIN → product_code → operator_group | ✅ **主表**。三列零空值；覆盖归因件数 **99.7%**；含 `account_scope`（WHITIN 5525 / BLOOMNEXT 899 / JOOMRA DIRECT 846，正好对齐 SOP 跨账户保护）；组码 12 个 3 位细码 `AJ1 AJ2 DD1 LB1 LW1 XH1 XM1 XM2 YS1 YT1 ZF1 ZJ1`；`mapping_status` 全表 `parent_inherited`（= 7169 行机械继承 + 101 行 high 人工核对）；**parent_asin→组 0 冲突** |
| `app.product_mapping` | 128 | 父ASIN → product_code → operator_group | ✅ 广告侧。覆盖花费 **96.4%** |
| `app.asin_parent_map` | 116 | 同上 | ⚪ **product_mapping 的真子集**（116 ⊂ 128），共有键冲突 0 → 冗余快照，可交叉校验不当源（**推翻旧记忆「为空」**）|
| `app.product_roster` | 149 | 在售主数据 | 🚫 不能定组（O.3）|
| `app.operator_name_map` | 15 | 人名 → 组码 | ⚪ 字典 |

### O.2 🔴 P0 事实表重复导入（anac1973，阻断级）
`川鹏_*` 与 `AMS_*` 两份源文件实为**同一账户 anac1973 (C3S8S)** 数据，日期错开一天几乎全重叠 → 双份入库。
| 表 | 现状 | 去重后 | 虚增 |
|---|---|---|---|
| `report_campaign_daily` | $131,641.92 | 同 | **0%** ✅（两份不重叠，侥幸干净）|
| `report_advertised_product_daily` | $254,462.00 | $131,407.53 | **+93.6%（$123,054.47）** |
| `report_purchased_product_daily`（件数） | 37,687 件 | 19,494 件 | **+93.3%（18,193 件）** |
| `report_purchased_product_daily`（销售额） | $1,322,776.45 | $682,990.86 | **+93.7%（$639,785.59）** |

（2026-09-21 精算，用 `_p0_excess.py` 的 FULL OUTER JOIN 口径；虚增额占全库广告总花费 $857,856.34 的 **14.3%**）

- 机制：同 Campaign-日两行，**仅 `advertised_product_id` 不同** —— `''` vs `__advertised__<hash>` 占位符 → 去重键没覆盖此差异。实例：campaign `137718483524592`「XM2-S71 头条wide广泛」(SB)，两行 spend/impressions/clicks/purchases 全等
- **仅 anac1973 一个账户中招**（BLOOMNEXT / JOOMRA DIRECT 零重复）
- 致命链：单价 = 花费 ÷ 归因件数 → 件数翻倍 → 单价腰斩 → 大面积误触「低成本修正」→ 跨组金额/负承担/小组汇总全错
- 修法：去重键改 `(account_scope, campaign_id, stat_date, 归因商品标识)`，并把 `__advertised__*` 占位符与空串归一；或按 `(account_scope, campaign_id, stat_date, ad_product)` 保留单行
- 检验 SQL（可复用）：见体检报告 §六，核心是 `count(DISTINCT source_file_name) > 1` per `(account_name, campaign_id, stat_date)`

### O.3 🔴 P1 roster 组码体系不一致
- `product_roster.owner_group` 用 **2 位粗码**：`AJ`(27) / `XM`(23) / `LW`(12) / `ZF`(10) → **72/149 行**
- 映射表用 **3 位细码**：`AJ1`/`AJ2`/`XM1`/`XM2`/`LW1`/`ZF1`；两组码**仅 6 个重合**
- **是粒度丢失，不是格式问题**：胡雪敏(XM) 同带 XM1+XM2、王爱菊(AJ) 同带 AJ1+AJ2 → 粗码**无法还原**细码
- 附带：**`product_roster.parent_asin` 列名误导，实际存的是子 ASIN**。145 个有值 ASIN 中仅 **4** 个匹配 `product_mapping.parent_asin`、**115** 个匹配 `child_asin_mapping.child_asin`（对应「源自前台链接 `/dp/<ASIN>`」）
- 处理：roster 只取品牌/品类/工厂等主数据，**定组一律以映射表为准**

### O.4 🟡 P2 child_asin_mapping 跨 scope 重复
7168 行 / 7134 唯一 `child_asin` / 7168 唯一 `(account_scope, child_asin)` → **34 个 child_asin 同现 BLOOMNEXT+WHITIN**，但 `product_code`/`operator_group` **完全一致** → 只需去重，无需裁决。**JOIN 必须带 `account_scope`**（否则这 34 行归因件数翻倍）。

### O.5 缺口清单（已导出 → `~/Desktop/周报告汇总/映射体检_2026-09-19/`）
- 归因侧 **150 个 ASIN / 723 件（0.6%）**：Joomra 拖鞋凉鞋、BRONAX 拖鞋、WHITIN 童鞋/鞋垫，多为 `B0G*`/`B0H*` 新款
- 广告侧 **20 组 / $31,109.33（3.6%）**：`NULL` $24,555.58（含 `__advertised__c65f37b2cb1ae26c89e9` 独占 $13,542.64）／`-1` $6,471.19
- 交付：`映射表体检报告_2026-09-19.md` + 3 份缺口 CSV

### O.6 可计算口径（建议顺序）
```
成交侧：report_purchased_product_daily
        → 先按 (account_scope, campaign_id, stat_date, purchased_product_id) 去重
        → JOIN child_asin_mapping 的 (account_scope, child_asin) → product_code + operator_group
广告侧：report_campaign_daily        ← 费用池唯一口径（当前干净，直接用）
        report_advertised_product_daily → 仅确认「实际推广了哪些产品」，必须先按 (campaign_id, stat_date) 去重
        → JOIN product_mapping 的 parent_asin
组码：一律用映射表 3 位细码；roster 只补主数据
```

### O.7 复核结论（2026-09-21，GPT 完成父子映射后）

产出：`~/Desktop/周报告汇总/映射体检_2026-09-21/`（复核报告 + 5 份缺口 CSV）。

**① 映射表本体 ✅ 通过。** `child_asin_mapping` 7,270 行（较 09-19 的 7,168 增 102），5 列**全部 0 空值**；`parent_asin→operator_group` **0 冲突**；34 个子 ASIN 跨 scope 重复已确认**全部同组同款号**（只需去重）；**7 个款号跨组**（`S71` XM1/XM2；`W30`/`W63`/`W85` YS1/ZJ1；`W75V2`/`W81V2`/`W81V5` XH1/ZJ1）→ **分组只能按父 ASIN，禁止按款号**。**裁决细则见 §N.7。**

**①b 数据质量：135 条自指行**（`child_asin = parent_asin`，父 ASIN 被当成自己的子 ASIN 登记）。样例：`B08LPXY2R4→B08LPXY2R4`(YS1/W63)、`B0BW4783S9→B0BW4783S9`(XH1/W75V2)、`B0C8T8PB6T→B0C8T8PB6T`(XH1/W81K)、`B09ZHS5Y7D→B09ZHS5Y7D`(LB1/Y15)。**不破坏分组**（自指也是唯一映射到自己的组），但会让「父子 ASIN 数」统计虚高、让「子 ASIN 反推父 ASIN」在这 135 条上退化成自反 → **建议清理或标记**。

**② 广告侧（成本池：《推广的商品》）总花费 $857,856.34**

| 路径 | 花费 | 占比 |
|---|---|---|
| P0 父ASIN 命中 `product_mapping` | $826,747.01 | 96.37% |
| P1 父ASIN缺失→子ASIN 命中 `child_asin_mapping` | $3,027.18 | 0.35% |
| P3 父ASIN 命中 `child_asin_mapping.parent_asin` | $82.56 | 0.01% |
| **可映射合计** | **$829,856.75** | **96.74%** |
| P4 残留 | $27,999.59 | 3.26% |

- 残留**不是漏映射，是没有 ASIN**：父 ASIN 为 `NULL`/`-1`、商品名为空。其中 **$22,730.52 全部是一个占位符 `__advertised__c65f37b2cb1ae26c89e9`**（304 行，跨 3 账户共享，挂在「视频 / 流媒体」活动下 = Amazon 对视频流媒体广告不给单品 ASIN 的占位值）
- ⚠️ **口径别混**：父 ASIN 为 `NULL`/`-1` 的行总共 **$31,026.77**；其中 $3,027.18 的 `advertised_product_id` 本身是真 ASIN、已由 P1 接走；真正无 ASIN 可查的是 **$27,999.59**
- ✅ **残留 100% 可归组**：按 `campaign_name` 首段前缀 → `AJ2` $8,925.02 / `XM1` $7,582.10 / `XM2` $5,960.54 / `ZJ1` $3,584.76 / `YT1` $3,136.00 / `AJ1` $1,838.35（1,474 行，零无法识别）。**GPT 没走这条路**

**③ 归因侧（《达成转化的商品》）** 总 113,080 件，未映射 **311 件（0.28%）**。按账户 JOOMRA DIRECT 234 / anac1973 76 / BLOOMNEXT 1。品牌字段 310 件为空。**广告侧反查救援率 = 0%**（这批产品根本没投广告，纯 Halo）。

**④ 业务侧（`report_business_child_asin_daily`）** 总订购量 582,381，未映射 **6,067 件（1.04%）**/ 546 子ASIN / **246 父ASIN**。根因 = **整条产品线从未登记**，不是零星漏 ASIN。头部 7 条（时间跨度全为 2026-08-01~09-19 满 50 天，**非新品**，且**广告花费 $0 = 纯自然流量**）：

| 父ASIN | 账户 | 子数 | 未映射订购量 | 广告花费 |
|---|---|---|---|---|
| `B0FWRX7MDC` Joomra Pillow Slippers | JOOMRA DIRECT | 33 | 1,862 | $0 |
| `B0CNTHY16W` WHITIN Replacement Insole | WHITIN | 14 | 1,308 | $0 |
| `B0GGXJ3KCY` Joomra Trail Running | JOOMRA DIRECT | 47 | 1,019 | $0 |
| `B0GJRFJ4CD` Joomra Toddler Wide Toe | JOOMRA DIRECT | 40 | 610 | $0 |
| `B0FGHZN7WX` WHITIN Toddler Wide Barefoot | WHITIN | 33 | 476 | $0 |
| `B0GWHYKH8D` WHITIN Women's Wide Toe Walking | WHITIN | 41 | 391 | $0 |
| `B0GG8H1N7H` WHITIN Wide Minimalist Barefoot | WHITIN | 29 | 238 | $0 |

> 归因侧那 310 件缺口 = 17 个父 ASIN 构成（业务侧全量口径则是 246 个）。这些线**不影响成本池分子（广告花费 0），只影响分摊分母（Halo 件数）**。

**⑤ P0 重复导入仍未修** —— 见 O.2，阻断级，按 SOP 第十九章不得输出最终分摊结果。

---

## P. 环境 / 时区 / 凭证（2026-09-28 从 MEMORY.md 迁入）

### P.1 时区（定时任务必读）
- 本机 `America/New_York`，用户按北京时间表述。rrule 的 `BYHOUR` 按**本地**解释、无 TZID。
- 夏令时本地 = 北京 −12h；冬令时 = 北京 −13h（切换点 2026-11-01 / 2027-03-14）
  → 锚北京的循环任务须配一次性 DST 校正。

### P.2 环境坑（每条都踩过）
- 事实表日期列叫 **`stat_date`**（不是 `report_date`）；SQL 必须写 `core.report_*`（`search_path` 不含 core）。
- psql `-t -A` 回传字符串：`f"{n:>7,}"` 会 ValueError → 先 `int()`；含制表符 → `-F '|~|'`。
- macOS BSD `grep` **不支持 `\|`** → 多模式须 `grep -E "a|b"`；zsh 下 `--include=*.py` 要加引号；
  别对 `~` 全盘 find/grep（TCC 刷屏 + 卡死）。
- 一条 SQL 报错会让整个事务 abort → 批量体检要**每次新建连接**。
- `import_batches` 主键是 `batch_id`（不是 `id`），`account_name` 等列可为 NULL →
  Python 格式化前必须 `str()` 兜底。
- macOS 无 `timeout` 命令（用 `gtimeout`）；`ziniao-cli store open` 用 `--id`（不是 `--store-id`）。

### P.3 凭证 / 数据库
- 唯一在跑：`pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com:5432`（PG 18.4），用户 `amazon_ads_admin`，
  SSL verify-full + `~/.postgresql/root.crt`，密码在 `amazon-ads-console/backend/.env`。服务器时区 Asia/Shanghai。
- ⚠️ `.env` 是 SQLAlchemy URL，psql 不能直吃也不能 `source`（含 `&`）→ 用 `app.core.config.settings` 拆成 `PG*`/`RDS_PG*`。
- 旧库 `121.41.134.56` **已整机退役** → 见到旧地址就当错误。

### P.4 实体 / 权限矩阵（2026-09-28 实测）
- 卖家实体：川鹏2号 `ENTITYD81ZAK5R7NX1`｜欧德思 `ENTITY2RBS3FEZP3EW1`｜美国AMS `ENTITY2BZ837BIZY5W9`
- **DSP 实体**（独立于卖家实体）：川鹏2号 `ENTITY1F7KI15KHQ4NT`（advertiser `592097575016190071`）、
  欧德思 `ENTITY1HER9YF1XGURE`、洁博利 `ENTITY150ACVBTS0BKE`（advertiser `587334646438449249`）
- 🔴 **美国AMS 无任何 DSP 入口**（该账号不能建 DSP，别再试）

### P.5 紫鸟店铺坐标 + 浏览器语言（2026-09-28 实测）
数据根：`~/Library/Application Support/ziniaobrowser/userdata/chrome_<storeId>/`

| 店铺 | storeId | 出口 IP | `intl.accept_languages` |
|---|---|---|---|
| 川鹏2号 | 27661378824000 | 47.236.198.129 | 🔴 `en,en-GB` |
| 欧德思美站 | 16371114318833 | 8.218.199.241 | `en-US` |
| 洁博利美站 | 16468050574114 | 8.219.11.152 | `en-US` |
| 易孚美站 | 16388408873341 | — | — |
| 美国AMS | 16213949758625 | — | — |

店铺语言在 `<profile>/Default/Preferences` 的 `intl.accept_languages`
（**改前必须先关店，Chrome 退出会覆写**）。

---

## Q. DSP 建单页「国家/地区」崩溃 —— 未定因（进行中）

诊断报告：`agent-master/dsp-debug/DSP建单报错-诊断报告.md`（以「**五次修正**」为最新版）。
已耗 5 轮排查、6 条假说翻车 —— **别再从零重跑排查**，先读该报告。

### Q.1 三家实测（同机、同内核 `chrome_64_138.1.2.80`）
| 店铺 | 语言 | 结果 |
|---|---|---|
| 川鹏2号 27661378824000 | `en,en-GB` | ❌ 崩 |
| 欧德思 16371114318833 | `en-US` | ❌ 也崩 |
| 洁博利 16468050574114 | `en-US` | ✅ 正常 |

### Q.2 最硬的净结论
**输入完全相同、输出不同** —— 带 `versionID` 的资源 URL 全等；唯一不带版本号的 locale 分包已跨店铺实测
**字节 hash 相同**（`countrySelector--zh-CN.chunk.js` 200 · 4564B · hash `4734e298` · 注册模块 **504**，
与 vendors chunk 硬编码的 `n.bind(null,504)` 吻合）。

### Q.3 站得住的
- 与 OS 无关（同机同内核结果不同）；与浏览器无关（纯 Chrome 也复现）。
- 崩点在 `orderMFEWebsiteVendors.chunk.js` 偏移 `1515533` 的
  `e.translationImports[n]().then(e=>s(e.default.translations))`（连带 `GeneralSectionV2.js:2:576` 的
  `e[a].call()`），属 webpack 模块解析失败族。

### Q.4 🔴 已翻车、别再引用（6 条）
① 亚马逊半截发布 ❌
② "7+1 chunk 版本错配是根因" ❌（三家 `verGroups` 逐字相同）
③ "`versionID` = 构建号" ❌（它 = 文件级上传时间戳）
④ "Windows 那台吃旧缓存" ❌（两个 profile 都无磁盘 HTTP 缓存）
⑤ "切账号显示语言到 en-US 可绕过" ❌（路径不对）
⑥ "浏览器 `Accept-Language` 是唯一分界变量" ❌（欧德思 `en-US` 也崩）

### Q.5 当前首选假设
**加载顺序竞态 → webpack 运行时归属错乱**：每个 MFE chunk 各带一份 runtime 却共用
`window.webpackJsonp`，`_push` 最后写入者生效；locale 包异步插入 → 落错 runtime → `n(504)` 不是翻译模块。
旁证：三店走不同代理节点、延迟画像稳定 → 该店铺稳定地"赢/输"；洁博利多加载一整套 Module Federation
（`d3a3saarspcyfn`×8 含 `remoteEntry.js`、`d369o5h5zn8mv7`×15），资源 300 vs 238。
待做（成本递增）：① 用户对川鹏建单页连按几次 F5，若偶尔成功 = 竞态实锤；② 对洁博利连续 reload N 次（需授权）；③ 给洁博利出口限速后重开。
⚠️ **教训**：n=2~3 环境里的"完美分离"随时可能是巧合 → 下结论前先把"能加样本"的机会用光。

### Q.6 兜底路径
换代理节点 / Bulk 批量建单 / 复制订单 `DSP_test1`（`593592435600181806`）/ Ads API。
取证手法见技能 `ziniao-cdp-page-forensics`（§5.0 第一步先看 `exceptionThrown[].url`，直接点名出事的 chunk；§5.5 跨店铺 A/B 对照法）。

### Q.7 「转化跟踪 → 商品 → 上传 CSV（ASIN 批量）」内部机制（2026-09-29 实测扒清）

只读探针：**`agent-master/dsp-debug/dsp_page_probe.js <storeId> [entityId] [advertiserId]`**
（一次性输出站点勾选状态 / 上传接口 / 页面告警 / 是否崩）。

**页面性质**：老版建单页 = **jQuery + React dropzone**（不是 §Q.1 那个纯 MFE 页面）。
`/orders/new` 仍会加载 `orderMFEWebsiteVendors.chunk.js` 等 MFE chunk（即 §Q 出事的那个）。

**上传链路的三个接口**（从页面内联脚本 `#asinFileUploaderContainer` 的 props 里读出来）：

| 用途 | 接口 |
|---|---|
| 上传文件 | `POST /dsp/rdo/api/upload-asin-file?csrfAuthToken=<渲染时内嵌>` |
| 关联任务状态 | `GET /dsp/rdo/api/asin-association-status` |
| 已关联数量 | `GET /dsp/<ENTITY>/rdo/api/asin-count` |
| 下载官方模板 | `GET /dsp/rdo/api/asin-bulk-upload-file-template?entityId=<ENTITY>` |

**⭐ 最重要的两条机制（决定了怎么判读报错）**：

1. **上传 ≠ 关联**。源码注释原文：
   *"there is no actual asin association happening in this step. Actual asin association happens in save"*
   → 上传只是把 CSV 存下换一个 `fileId`；**真正的 ASIN 关联发生在「保存订单」时**。
   所以「上传成功但显示 No Product.」在保存前是**正常的**。
2. **上传失败的判定 = `onUploadCompleted(result)` 里 `result` 为空或没有 `fileId`**
   → 组件会把已选文件**丢掉**（清空 file input），界面回到初始的
   `Drop .csv file to upload` + `No Product.`（`noAsinMsg`）。
   → **看到「回到初始态 + No Product.」= 那次上传请求本身没成功**，
   **不是**"文件里的 ASIN 有问题" —— 文件内容有问题走的是另一条路
   （`invalidFormatAsinSize` / `invalidDomainAsinSize` / `duplicateAsinSize` → 只弹"部分未添加"警告，**仍会拿到 fileId**）。

**站点（亚马逊域）复选框**：`添加商品 → 亚马逊域 → 选择站点` 是一组 `input[type=checkbox]`
（`amazon.com`=1、`amazon.ca`=7、`com.br`、`com.mx`、`Prime Now US/CA`、`Fresh Stores US`、`Whole Foods Market US`），
**新建订单页默认全不勾**，且页面自带告警 `选择一个或多个亚马逊站点`。
→ 排查上传类故障时**先看这组勾选**：没勾站点，即使上传成功，后续也关联不上。

**官方模板实况**（2026-09-29 拉到，200 / 579 字节）：表头就是
`ASIN,Featured,Domain,,*** Instructions ***`，CRLF，**列 1–4 空、说明文字全在第 5 列**。
⚠️ 人工填表时的典型坑：直接在官方模板上行内替换，**把 ASIN 填到了带说明文字的行上**
（例如 `B09MVVGKPW,,amazon.com,,amazon.com`）—— 因为有引号包裹的说明列存在，
**这是"文件看起来不对"的头号嫌疑，但实测并非致命**（见 2026-09-29 日志的逐项排除）。

---

## R. 健康度快照

### R.1 2026-09-23（4 店 23 份全绿 + 灌库成功）
- ✅ 广告订阅 23/23 全新鲜、数据到 **09-23**；`core.report_*_daily` 三账户 **08-15/16..09-23 逐日**
  （BLOOMNEXT/JOOMRA 起 08-16、anac1973 起 08-15；`WHITIN` 仅存于 `advertised_product`，停 09-20）。
- ✅ SQP WHITIN 到 09-19，BRONAX+JOOMRA 26 周 / 09-05。🔴 SCP 彻底断流。
- ⚠️ 待人工（账号设置，AI 不动）：洁博利 2 条僵尸重复订阅。

### R.2 僵尸文件（勿误读为「本店有该订阅」）
川鹏下载目录有 **3 份僵尸 CPO CSV**（停在 09-08~09-22）+ **1 份僵尸「搜索词 30D 日期.csv」**
（川鹏，08-10..09-08，该订阅已从 config 移除）→ 永不更新，不影响灌库。

### R.3 川鹏2号 代理故障史（稳定结论）
- 2026-09-22：`page visit` 全 `CDP_ERROR`，但 **`page content` 能读到页面**
  → CDP 通道活着，**不是 Bridge 死、也不是掉登录**。错误页自爆真因 `ERR_CONNECTION_CLOSED` +
  出口 IP `47.236.198.129` = **该店代理节点连不上 advertising.amazon.com**。
- 判读口诀：**content 通 + visit 挂 = 店铺代理/网络问题**；掉登录会看到登录页而非 ERR_CONNECTION_CLOSED。
  对照实验：同一 `page visit` 打到另一家店若返回 `✓ 页面已导航` → 证明是单店问题。
  `store close --id` + `store open --id --url` 对该故障**无效**。
- ✅ 2026-09-23 已**自愈**（无需人工换节点）：09-22 故障 → 09-23 5/5 正常下载。

