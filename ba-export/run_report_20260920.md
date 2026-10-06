# 川鹏2号 BA 周报管线 — 执行报告 (2026-09-20)

> 状态：**未成功 / 被「目标 RDS 主机已退役」阻断**，非浏览器问题、非脚本语法错误，但**管线目的地整体失效**。

---

## 1. 前置检查（通过 ✅）

| 检查项 | 结果 |
|---|---|
| `ziniao-cli doctor` | 全绿（配置 / API Key / 紫鸟客户端 / ZClaw Bridge） |
| `extract_data mode=running` | 含 `27661378824000`（川鹏2号），共 3 店在线 |
| Bridge `/health` (9481) | `ok:true, loggedIn:true, runningStores:3` |

结论：浏览器与 Bridge **正常**，前置无问题。

## 2. 目标周

`MODE=latest` 计算得 **2026-09-12**（上周六）。
但紫鸟下载管理器里 Amazon 实际可用的最新周为 **2026/09/13–2026/09/19**（周六 09-19 结束）。

## 3. 阻断根因（关键）🔴

**指令指定的 RDS 宿主机 `121.41.134.56` 整机不可达**，不是上周那种白名单拒绝：

```
ping 121.41.134.56          -> 3 packets transmitted, 100.0% packet loss
nc -z 121.41.134.56 5432    -> Operation timed out
psql -h 121.41.134.56 ...   -> connection ... failed: Operation timed out
```

这是**旧服务器**，已被官方文档点名退役 —— `amazon-ads-data/migrations/012_search_query_performance_tables.sql` 开头写着：

> 背景：migration 007（仅月表）当年跑在旧服务器（121.41.134.56）上，当前主库 amazon_ads_v2 里两张表都不存在，本迁移在主库重建。

而 `pipeline.sh` → `ba_to_rds.py` / `drain_dm.py` **三个脚本的默认 `PGHOST` 全部硬编码为 `121.41.134.56`**、`PGDB=amazon_ads`。
即：**整套 ba-export 管线的唯一目的地已经不存在了。**

**现行主库**（`amazon-ads-console/backend/.env`）：

```
host = pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com
db   = amazon_ads_v2   (数据仓库)  /  amazon_ads (应用库)
```

## 4. 本次操作失误（如实记录）⚠️

**我把 `MODE=latest` 当成了命令行参数传给脚本**，而 `ba_export.sh` 只读**环境变量**：

```bash
bash ./ba_export.sh MODE=latest     # ✗ 错：这是 argv[1]，脚本看不到 → MODE 回落默认值 both
MODE=latest bash ./pipeline.sh      # ✓ 对：env 前缀，pipeline.sh 再继承给 ba_export.sh
```

后果：`MODE` 为空 → 默认 `both` → **从 `START=2024-01-06` 开始全量回灌**。
运行约 8 分钟（北京 10:36–10:44）后已被 `pkill` 终止。

**副作用与已做的清理：**

| 副作用 | 处理 |
|---|---|
| `done.txt` 被追加 22 条**假 done 标记**（2024-09-14 ~ 2024-11-30，实际从未下载/入库） | ✅ 已还原到运行前的 75 行（备份 `/tmp/done.txt.bak-*`） |
| 紫鸟下载管理器新增 **22 个待下载项** | ⚠️ **未删除、未点击下载** — 见 §6 |
| Amazon 账号 / 广告设置 | ✅ **未做任何改动** |

> 补充：`pipeline.sh` 本身没问题，它 `MODE=$MODE` 只是打印+传参写法冗余；
> 真正生效路径是调用方用 env 前缀，`MODE` 带 export 属性后能被子脚本继承。**是我的调用方式错了。**

## 5. 顺带查出的真 BUG：`sqp` 的周参数失效 🔴

对照本次误触发产生的下载项（同一批生成、同一时刻）：

| 报表 | 请求的周参数 | 下载管理器里实际落成的报告区间 |
|---|---|---|
| scp | `weekly-week=2024-09-28 … 2024-11-30` | 与请求**逐一对应** ✅ |
| sqp | `weekly-week=2024-09-14 … 2024-11-23`（11 次） | **全部** = `2026/09/13 – 2026/09/19` ❌ |

即 `ba_export.sh` 里 sqp 的 URL 参数（`query-performance?...&weekly-week=`）**不生效**，Amazon 一律回落到「最新一周」。

影响：即使 RDS 活着，`MODE=latest` 或指定周回灌 sqp 拿到的都是最新一周，而 `done.txt` 却按**请求周**打 `done`
→ **静默错标**，正是 09-13 那次「GEN 了但 DM 为空 / 灌了错的周」这类怪现象的合理来源。

## 6. 紫鸟下载管理器当前队列（22 项，全部为本次误触发产生）

- **12 项** `搜索查询绩效 - 品牌 US 每周 2026/09/13–2026/09/19`（重复同一周，`pending`）
- **10 项** `搜索目录绩效 US 每周` — 2024/09/28、10/05、10/12、10/19、10/26、11/02、11/09、11/16、11/23、11/30（陈旧周，`pending`）

均为 `pending`，**未下载**。Amazon DM 项会自行过期；按用户红线，AI 未做删除或点击。
其中 **12 个 sqp 项是当前能拿到的「最新一周」，可用于补 09-12 / 09-19 两个缺口**（需用户决定走哪条入库路径）。

## 7. 未执行的部分

Phase 2（`drain_dm.py --download-only`）与 Phase 3（`load_local.py`）**均未运行**：

- 目的地已死 → Phase 3 必然失败，只会把 22 个 CSV 堆在磁盘，直接违反「不保留本地文件」；
- Phase 2 会把这 22 项（含 10 个陈旧 2024 周）全下载，纯属污染磁盘。

## 8. 磁盘状态 ✅

```
下载目录 BA Week CSV 数 = 0
搜索绩效查询/ 子目录 Week CSV 数 = 0
```

干净。（仅存历史 Month 文件，被管线正则严格排除。）

## 9. RDS 现状（指令第 4 步 SQL）

**旧库 `121.41.134.56`**：连不上（timeout），无法汇报。

**现行主库 `amazon_ads_v2`**：

| t | rows | min_end | max_end |
|---|---|---|---|
| sqp | **78000** | 2026-03-14 | **2026-09-05** |
| scp | — | — | **表不存在**（`information_schema` 计数 = 0） |

按品牌：`WHITIN / BRONAX / JOOMRA` 各 26 周 × 1000 行 = 26000 行，最新均到 2026-09-05。

## 10. 修复建议（待用户拍板）

1. **主路径迁移**：weekly 任务从 `ba-export/` 迁到 `amazon-ads-data/`
   - 加载器：`scripts/import_sqp_v2.py <品牌目录> --mode weekly` → `amazon_ads_v2.core.search_query_performance_weekly`
   - 命名约定：`搜索查询绩效_<BRAND>_<YYYY-MM-DD>.csv`，**按品牌建子目录**（brand 取自父目录名）
   - 表头是 2026-09 后的**新格式**（`展示次数-总计` / `点击量-总计` …），旧 `ba_to_rds.py` 的映射表不认
2. **`ba_to_rds.py` 不可简单改向新库**：它 `ON CONFLICT (marketplace, search_query, week_start_date, week_end_date)` 缺 `brand_name`，与新表 UK 不匹配；且 `source_batch_id` 实为 `bigint` 而它传的是字符串 `PIPELINE_20260920`。
3. **SCP 无归宿**：`amazon_ads_v2` 里 0 张 scp 表，全仓库只剩 `ba-export/sql/create_tables.sql` 一个 DDL ——
   而该文件第 9/56 行是 `DROP TABLE IF EXISTS ... CASCADE`，**原样执行会把 sqp 表一起删掉**。
   若决定保留 SCP，需另写一个**只 CREATE 不 DROP** 的 migration。
4. **`done.txt` 第 76 行隐患**：`scp:2024-09-14=done` 缺配对的 `sqp:2024-09-14`，本周误触发时被补上了；已回滚，周内该周仍未完整。

## 11. 红线确认

本次**未修改任何 Amazon 账号、广告投放或 Prime 相关设置**，仅做只读导出探测（导航 + DOM 读取）与本地文件/DOM 状态查询。
