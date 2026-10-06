# automation-1788161096564 执行记忆

## 2026-09-06 执行 (北京 09:00 / 本机 21:03 EDT)

- **前置检查**: `ziniao-cli doctor` 全绿; `extract_data mode=running` 含 storeId 27661378824000(川鹏2号) → 浏览器在线、Bridge 正常。
- **导出周**: latest 模式算出的上周六 = **2026-08-29**(报告周期 2026-08-23~08-29)。
- **发现的 BUG(关键)**: 管线 `drain_dm.py` 第15行硬读 `/tmp/dm_tid.txt`,但该文件**从无任何步骤生成** → 阶段2 直接 FileNotFoundError,每周自动化此前都卡死在阶段2。
  - **修复**: 改 `drain_dm.py`,用 `visit_page` 导航下载管理器并解析返回的 `targetId`(自包含,不再依赖外部缓存文件),同时写回 `/tmp/dm_tid.txt` 供调试。仅改本地脚本,未触碰任何 Amazon 账号设置。
- **重跑结果**: 阶段1 因 done.txt 命中跳过; 阶段2 下载 sqp+scp 两个 2026-08-29 CSV 到磁盘; 阶段3 各 1000/5290 行灌入 RDS(core.search_query_performance_weekly / core.search_catalog_performance_weekly)后删本地。
- **异常**: 无 ABORT/THROTTLE/超时。
- **磁盘**: 0 个 BA Week CSV(干净)。
- **RDS 现状**: scp 30177 行(2024-08-31 → 2026-08-29); sqp 5000 行(2026-08-01 → 2026-08-29)。本次新增 scp +5290、sqp +1000。
- **管线日志**: /tmp/dm_drain_pipeline_20260906_210925.log

## 注意事项
- 修复后管线已自愈,后续每周应正常;若某次报 "无法解析 targetId" 多为 Bridge 掉线/浏览器被关,按用户规则不自行开浏览器。
- **前置自检口径（EXIT=3 时照此逐项验）**：① `ziniao-cli doctor` 有无 FAIL；② `ziniao-cli zclaw invoke extract_data --args '{"mode":"running"}'` 的 `items` 是否含 `27661378824000`——**返回 `items:[] total:0` = 真·没开浏览器**（不是掉登录，别误判）；③ 隧道 `nc -z 127.0.0.1 15432`。
- 只读查库姿势：`psycopg**2**` 未装，用 `~/Documents/amazon-ads-data/.venv/bin/python` 的 **psycopg3**（或 `/opt/homebrew/bin/psql`），连接参数从 `amazon-ads-console/backend/.env` 的 `RDS_DATABASE_URL` 解析。
- sqp 单周上限 1000 搜索词(Amazon 限制),5 周=5000 行符合预期;scp 无硬上限。

## 2026-09-13 执行 (本机 22:30 EDT) — 未成功 / 被 RDS 网络阻断

- **前置**: doctor 全绿; extract_data 含 27661378824000 → 浏览器/Bridge 正常。
- **目标周**: LATEST = 2026-09-05。Phase1 日志标记 GEN scp/sqp 2026-09-05,但 DM 实际为空(独立只读探针确认 0 行)→ 0 文件落盘,Phase3 无数据可灌。
- **阻断根因**: RDS `pg_hba.conf` 拒绝出口 IP `112.49.170.54`(端口可达但不在白名单)。两条凭据均报相同错误 → 排除密码问题,确认为 **IP 白名单/安全组**问题(自 09-06 成功运行后 IP 或白名单已变)。重试 2 次均失败。
- **假信号**: `drain_dm.existing_weeks()` 连接失败返回空集 → 日志 `RDS 已有周: scp=0 sqp=0` 为假,无法确认 RDS 真实状态。Step4 SQL 同样无法执行。
- **数据缺口缓解**: 删除 done.txt 中 `scp/sqp:2026-09-05=done` 两条假标记(仅本地缓存,未动账号),避免未来运行永久跳过 09-05。
- **磁盘**: 0 个 BA Week CSV(干净)。
- **未做**: 未下载/未改任何 Amazon 账号或广告设置。
- **待用户**: 在阿里云 RDS `amazon_ads` 安全组/pg_hba 加入出口 IP `112.49.170.54`;生效后重跑管线补 09-05(指定周回灌)。
- **产物**: ba-export/run_report_20260913.md

## 2026-09-20 执行 (本机 22:30 EDT) — 未成功 / 目标 RDS 主机已退役 🔴

- **前置**: doctor 全绿; extract_data 含 27661378824000 → 浏览器/Bridge 正常。非前置问题。
- **目标周**: LATEST=2026-09-12; 但 DM 里 Amazon 实际可用最新周 = 2026/09/13~2026/09/19。
- **阻断根因（性质变了）**: 指令指定的 `121.41.134.56` **整机不可达**(ping 100% 丢包 / nc TCP timeout / psql timeout),
  **不是** 09-13 那种 pg_hba 白名单拒绝。该机即 `amazon-ads-data/migrations/012` 注释点名的「旧服务器」。
  而 `pipeline.sh`/`ba_to_rds.py`/`drain_dm.py` 三脚本 PGHOST 全硬编码此机 → **整套 ba-export 目的地已不存在**。
- **现行主库** = `pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com`, DB `amazon_ads_v2`:
  - `core.search_query_performance_weekly` 存在, 78000 行, 2026-03-14→**2026-09-05**, 3 品牌(WHITIN/BRONAX/JOOMRA)各 26 周×1000
  - `core.search_catalog_performance_weekly` **不存在**(information_schema 计数 0)
  - 现代化加载器 = `amazon-ads-data/scripts/import_sqp_v2.py --mode weekly`, 命名 `搜索查询绩效_<BRAND>_<YYYY-MM-DD>.csv` + 品牌子目录, 表头是 2026-09 新格式(`展示次数-总计`)
- **本次操作失误（已记录，勿重犯）**: 我把 `MODE=latest` 当 **argv** 传给 `ba_export.sh`(`bash ./ba_export.sh MODE=latest`),
  脚本只读 **env** → MODE 回落 `both` → **从 2024-01-06 全量回灌**, 跑约 8 分钟后 pkill 终止。
  **正确调用 = `MODE=latest bash ./pipeline.sh`（env 前缀）**。
  - 清理: done.txt 追加的 22 条假 done 标记已还原到 75 行(备份 /tmp/done.txt.bak-*)。
  - 残留: 紫鸟 DM 新增 **22 个 pending 项**(10 个 2024 陈旧 SCP + 12 个重复的 2026/09/13–09/19 SQP), 未下载未删除。
- **顺带查出真 BUG**: `ba_export.sh` 的 **sqp** URL 周参数失效 —— 11 次不同周请求全部落成同一区间 `2026/09/13–2026/09/19`;
  对照同批 scp 请求区间逐一正确 → 只有 sqp 参数不生效, 会配合 done.txt 静默错标。
- **未执行**: Phase2/Phase3 (目的地已死, 跑下去只会堆文件且灌库必失败, 违反"不留本地文件")。
- **磁盘**: 0 个 BA Week CSV ✅
- **未做**: 未改任何 Amazon 账号/广告设置; DM 项未点击未删除。
- **待用户拍板**: (a) weekly 任务迁到 amazon-ads-data/import_sqp_v2.py; (b) SCP 是否要新写"只 CREATE 不 DROP"的 migration
  (`ba-export/sql/create_tables.sql` 含 `DROP ... CASCADE`, 原样跑会连 sqp 一起删); (c) ba_to_rds.py **不能**简单改向新库
  (ON CONFLICT 缺 brand_name 与新表 UK 不匹配; source_batch_id 是 bigint 却传字符串)。
- **产物**: ba-export/run_report_20260920.md

## 2026-09-21 执行（本机 03:59–04:02 EDT）— ✅ 成功 / 迁移完成

- **迁移落地**：weekly 任务从已退役的 `ba-export/pipeline.sh`(+旧库) 迁到新脚本 `ba-export/ba_sqp_weekly.py`，
  目标库 `amazon_ads_v2`，加载器 `amazon-ads-data/scripts/import_sqp_v2.py --mode weekly`。automation prompt 已整体重写。
- **补洞完成**：回灌 **2026-09-12** 与 **2026-09-19** 两周（各 1000 行）→ WHITIN 由 26 周涨到 **28 周 / 28,000 行**，max = 2026-09-19。
- **关键修复**：新下载的 SQP CSV 表头是 2026-09 新格式（`曝光：曝光总量` 全角冒号 + 首行元数据行 `品牌=["WHITIN"],…` + 尾部多一列 `报告日期`），
  而加载器只认旧格式 `展示次数-总计`。已给 `import_sqp_v2.py` 加 `HEADER_ALIASES` / `IGNORED_HEADERS` / `parse_meta_line()` / `canon_header()`，
  两种格式都能吃。
- **关键修复（下载侧）**：BA 下载按钮是 `<span>`，**JS 的 `el.click()` 是合成事件、React 不认**（表现为「点了没反应、文件不落盘」）。
  必须先给目标行打唯一属性标记，再用 Bridge 的 `click_element(selector=…)` 发**真实指针事件**。已固化进 `ba_sqp_weekly.py`。
- **DM 清理**：清掉 23 行陈旧项（重复的 09-13~09-19 SQP + 10 个 2024 年 SCP）。`--prune-dm` / `--dry-run` 已实现。
- **范围**：本任务**只跑 WHITIN**。BRONAX / JOOMRA 仍停在 26 周 / 2026-09-05（品牌 id 不同，未跑）。
  SCP 现行**无归宿**（新库无表），本任务不碰。
- **未做**：未改动任何 Amazon 账号 / 广告设置。
- **产物**: `ba-export/ba_sqp_weekly.py`(新)、`ba-export/ba_dl_sqp.py`(新)、`ba-export/ba_sqp_weekly.log`

## 2026-09-21 后续（04:30–04:45 EDT）— ✅ 广告报告链路修复 + 缺口补齐

> 本轮是承接用户四项指令（改新库 / 确认 SCP / SQP 迁移 / 补齐广告报告自动化）的收尾执行。

- **根因定位**：被暂停的「广告报告」自动化 `16126452…` 之所以 20/20 报告全失败（退出码 3「系统性故障」），
  不是掉登录也不是订阅被删，而是 **`download_ad_reports.js` 用逐字符精确比对订阅名**，
  而控制台订阅名已被改成 `<店名> 报告名 30D 日期 Copy`。**且只改等待函数没改点击函数**会表现为
  「日志说找到了、紧接着抛找不到」的自相矛盾。
  → 已改成**归一化匹配**（抹空白 + 抹结尾 `Copy` + 唯一后缀命中，歧义则报 `ambiguous[...]`），
  `waitForReportLink` 与 `clickScript` **两处同源**。
- **补上缺失的后半截**：`pipeline.sh` 只下载不灌库；老邮件渠道被 macOS TCC `-10004` 拦死。
  → 新建桥接 `ad-reports-export/ziniao_30d_to_report_daily.py`（紫鸟下载目录 → 按加载器命名暂存 → 调
  `import_account_30d_reports.py` → `core.report_*_daily`），带**数据日期闸门**（最新数据日期 < 今天-3 天判旧快照，整家不灌）。
- **附带修复**：`import_account_30d_reports.py` 原硬判「恰好 18 个文件」→ 改**逐账户 6 类齐全**校验；
  `config.json` 补上欧德思/洁博利/美国AMS 的「投放」与「达成转化的商品」30D 报告（此前从未下载过），
  移除川鹏2号不存在的「搜索词 / CPO」订阅。
- **实战结果**：欧德思美站 + 美国AMS 各 6 类报告全绿 EXIT=0（数据窗口 2026-08-22..09-20）；
  灌库 `files=12 inserted=254,479 updated=118,030`；**`core.report_*_daily` 两账户由 09-14 推进到 09-20**，
  09-13~09-20 逐日无断档（`report_business_*` 属另一管线，仍 09-19）。
- **未完成**：洁博利美站（JOOMRA DIRECT）**掉登录**（跳 `ap/signin`），磁盘只有 09-07 旧快照被闸门拦下 → 待人工重登；
  重登后跑一轮即自动补齐（30D 滚动窗口）。自动化 `16126452…` 已修好 prompt 并**恢复 ACTIVE**。
- **未做**：未改动任何 Amazon 账号 / 广告设置。
- **产物**: `ad-reports-export/2026-09-21_广告报告灌库补齐.md`、
  `wiki/AI工程/Amazon-Brand-Analytics-SQP与SCP-口径与现状.md`（回答「SCP 干什么用」）、
  `wiki/AI工程/阿里云RDS-amazon_ads_v2-库表结构.md`（补 SCP 缺失警告）、`logs/INDEX.md`、`logs/LOG.md`

### SCP 结论（本轮已沉淀成 wiki 页）
SQP 按**搜索词**切，SCP 按 **ASIN/目录条目**切。SCP 是 BA 里唯一以商品为行主键的漏斗报告，
自带「展示时价格/配送/可售状态」，用于把转化差归因到价格带或配送；也是唯一能直接对接
`app.child_asin_mapping` 运营组归属的 BA 报告。**现行主库 `amazon_ads_v2` 没有任何
`search_catalog_performance_*` 表**（旧库 30,177 行 / 2024-08-31→2026-08-29 已随退役机器消失）→ SCP 当前悬空。
复活三步（未执行）：① 写**只 CREATE 不 DROP** 的 migration（别跑 `create_tables.sql`，它含 `DROP ... CASCADE`）；
② 照 `import_sqp_v2.py` 加加载器；③ 下载侧加 SCP 分支。

## 2026-09-21 第二轮（05:10–05:45 EDT）— ✅ 洁博利补齐 + 同名重复订阅修复 → **18/18 全绿**

用户告知「洁博利可以登录了」并追问「新广告活动名后缀带 Copy 有没有弄错」。

### 匹配逻辑复核：没弄错
探针抓取洁博利真实订阅名 13 条，6 个 30D 报告均为 `<店名> 报告名 30D 日期 Copy`，
归一化后后缀唯一命中。**但第一跑只有 5/7**，暴露两个真问题：

### 问题 1：洁博利根本没有 CPO 订阅（配置是我猜的）
按「欧德思/AMS 有 → 洁博利也该有」的**命名规律**配了 `洁博利 推广的商品 每日CPO单双计算`，实际不存在
→ 每轮白等 120s。已从 config 移除。🔴 **教训：不要用命名规律推断订阅是否存在，先跑探针抓真实列表。**

### 问题 2：🔴 同名重复订阅（本轮最有价值的发现）
| 报告名 | 上次修改时间 | 下次运行 | 性质 |
|---|---|---|---|
| `洁博利 广告位 30D 日期 Copy` | 2026-09-17 09:56 | 2026-09-22 09:19 | ✅ 活 |
| `洁博利 广告位 30D 日期` | 2026-08-15 16:16 | — | ⛔ 僵尸 |
| `洁博利 搜索词 30D 日期 Copy` | 2026-09-17 09:54 | 2026-09-22 09:50 | ✅ 活 |
| `洁博利 搜索词 30D 日期` | 2026-08-15 16:17 | — | ⛔ 僵尸 |

归一化后同名 → 旧策略「多候选报 `ambiguous` 拒绝猜」→ **该类报告永久失败**。
第一跑搜索词侥幸成功（轮询那刻僵尸行未渲染）、广告位失败 —— **两者都是定时炸弹**。
**修复**：`__mtime()` 取 ag-grid 行内「上次修改时间」→ `YYYYMMDDHHmm`，多命中最取新者。
实测日志 `⚠ 报告名同名重复订阅，已取…newest-mtime[洁博利广告位30D日期|202609170956]` → 选活的那个。
🛟 兜底：挑错 → 下游新鲜度闸门拦住不灌库。

### 技术要点
- 报告列表是 **ag-grid 虚拟滚动**（`clientH=289 / scrollH=2700`，DOM 只常驻 ~11 行）→ 一次 `querySelectorAll` 拿不全，**必须滚动**。
  已把只读探针固化进技能：`probe_report_links.py`（滚动收集 + 自动报归一化重名组）/ `probe_report_rows.py`（行元数据）。
- **僵尸订阅特征**：`下次运行时间 = —` 且「上次修改时间」停在很久以前。
- `ziniao-cli zclaw invoke page visit` 会报 `accepts 1 arg(s), received 2` → 正确形式 `ziniao-cli page exec --store-id <id> --script '...'`。

### 结果
- 下载：洁博利 **6/6 EXIT=0**；灌库 `files=18 inserted=59,321 updated=39,012 skipped=872,203 hash_skipped_files=12`
- **JOOMRA DIRECT 由 09-14 → 09-20** → **3 店 × 6 表 = 18/18 覆盖 `2026-08-15/16 .. 2026-09-20`，逐日无断档**
- config 校准为 **4 店 25 份**（川鹏2号 5 / 欧德思 7 / 洁博利 6 / 美国AMS 7）；自动化 prompt 已同步重写「已知情况」

### 待人工（账号设置，AI 不动）
① 洁博利 2 条僵尸重复订阅建议删除；② 洁博利缺「每日CPO单双计算」订阅，若需该口径需补建。

## 2026-09-27 执行（本机 22:48–22:54 EDT）— ✅ 成功

- **前置**：doctor 全绿；川鹏2号浏览器在运行。**一条命令** `ba-export/ba_sqp_weekly.py` 全流程跑通，退出码 0，无需 `--week` 补洞。
- **目标周**：**2026-09-26**（最近一个严格早于北京今日的周六）。
- **下载**：成功。DM 第 2 次探测即就绪；真实指针事件点击 → 落盘 `…_简单_Week_2026_09_26.csv`（224,262 bytes）→ 暂存改名 `US_搜索查询绩效_品牌视图_WHITIN_Week_2026-09-26.csv`。
- **灌库**：`import_sqp_v2.py --mode weekly` → **1,000 行**（batch_id=487，insert 1000 / skipped 0 / success，week 2026-09-20~09-26）。
- **RDS 现状**：WHITIN **29 周 / 29,000 行**（2026-03-14→**2026-09-26**）；BRONAX 26 周、JOOMRA 26 周（均 2026-03-14→2026-09-05，本次未跑）。
- **本地干净**：staging 空；紫鸟下载目录零 `*搜索查询绩效*Week*`。顺手清掉一个 **09-21 遗留**的 `…_Week_2026_09_19.csv`（数据已在库，纯冗余）。
- **🔴 本轮最有价值的发现：BA 下载管理器没有任何删除入口（长期假象被证伪）**
  - 行内**永远只有「下载」一个控件**；表头 8 个 `more_vert` 全是**列宽拖拽把手**（`role=separator`），不是 kebab 菜单。
  - 真实 `pointerover`/`mouseover` 悬停也不揭示隐藏菜单；无 `kat-menu/[role=menu]` 删除项。
  - `rows[0].remove()` **只摘当前 DOM**：日志写「已移除」→ **37s 后刷新页面，行原样重现**（实测）。
  - 09-21 那轮"清掉 23 行"也不是我们删的，是 **Amazon 自行过期回收**。
  - **影响≈0**：防重复靠「只按目标周匹配」+「`file_hash` 去重 + `ON CONFLICT DO UPDATE`」两道幂等闸门。
- **已修**：`remove_dm_row()` 改摘**同名全部**行（原只摘 `rows[0]`）；docstring 写清"客户端行为、非真正清空"；
  日志措辞「已移除/已清理」→「已从当前页面摘掉（客户端，刷新会重现）」，消除假信号。`py_compile` 通过。
- **知识库同步**：wiki `Amazon-Brand-Analytics-SQP与SCP-口径与现状.md`（新增 §5 + §4 数字更新）、`logs/LOG.md`。
- **未做**：未触碰任何 Amazon 账号 / 广告投放设置；未做 SCP（新库无表）。
- **教训（写入脚本 docstring）**：`el.click()` 合成事件 React 不认（下载按钮）× `node.remove()` 纯客户端 React 会重渲染回来（DM 行）
  —— **同一类同源错误**。凡"操作后要持久生效"的动作，一律真实指针事件 + **事后刷新复验**，别信日志成功文案。

## 2026-10-05 执行（本机 20:52 EDT）— ❌ 未执行 / EXIT=3 前置不满足（浏览器未开）

- **一条命令** `ba_sqp_weekly.py` → **EXIT=3**，日志：`前置检查: 川鹏2号 浏览器未运行`，7s 内退出（未做任何下载/点击）。
- **独立复验（确认脚本没冤枉人）**：doctor 全绿（API Key 有效/客户端已登录/Bridge 连通）；
  `extract_data mode=running` 返回 **`items:[] total:0`** → **一台浏览器都没开**，**不是**掉登录。按红线**未自行开浏览器**。
- **顺带只读体检**：DB 隧道 `127.0.0.1:15432` **OPEN**；`core.search_query_performance_weekly` 连接正常，**总 81,000 行**：
  WHITIN **29 周** 2026-03-14→**2026-09-26**（29,000）；BRONAX / JOOMRA 各 26 周 2026-03-14→2026-09-05（各 26,000）。
- **目标周（未取）**：**2026-10-03**（严格早于北京今日 10-06 的最近周六）→ 缺口 **1 周**。
- **本地**：staging 空、0 个 `*Week_*.csv` → 干净 ✅。未触碰任何 Amazon 账号 / 广告投放设置。
- **待人工**：紫鸟客户端手动打开川鹏2号 → 原命令重跑即补齐（幂等，无需 `--week`）。若届时仍报缺周，退出码 3/4/5/6/7 分别对应前置/无条目/点击/未落盘/灌库失败。

