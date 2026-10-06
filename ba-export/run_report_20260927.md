# BA SQP 周更执行报告 — 2026-09-27

> 自动化任务 `automation-1788161096564` ｜ 本机 22:48–22:54 EDT（北京 09-28 10:48–10:54）
> 店铺：川鹏2号（紫鸟 storeId `27661378824000`）｜ 品牌：**仅 WHITIN**（brand=473922）

## 一、结论速览

| 项 | 结果 |
|---|---|
| 目标周 | **2026-09-26**（周区间 2026-09-20 ~ 2026-09-26） |
| 下载 | ✅ 成功（DM 第 2 次探测就绪，真实指针事件点击后落盘 224,262 bytes） |
| 灌库 | ✅ **1,000 行**（batch_id=487；insert 1000 / skipped 0 / status=success） |
| RDS 周覆盖 | WHITIN **29 周 / 29,000 行**，2026-03-14 → **2026-09-26** |
| 本地是否干净 | ✅ staging 空；紫鸟下载目录零 `*搜索查询绩效*Week*` |
| 异常 | 无。退出码 **0**，未触发任何补洞分支 |

## 二、RDS 现状（`amazon_ads_v2.core.search_query_performance_weekly`）

| brand_name | 周数 | min | max | 行数 |
|---|---|---|---|---|
| BRONAX | 26 | 2026-03-14 | 2026-09-05 | 26,000 |
| JOOMRA | 26 | 2026-03-14 | 2026-09-05 | 26,000 |
| WHITIN | **29** | 2026-03-14 | **2026-09-26** | **29,000** |

- WHITIN 逐周无缺口：`2026-03-14` 起连续 29 个周六，每周 1,000 行（Amazon 单品牌单周硬上限）。
- BRONAX / JOOMRA 本次**按约定不跑**，仍停在 2026-09-05。
- SCP（搜索目录绩效）现行**无归宿**（`amazon_ads_v2` 无 `search_catalog_performance_*` 表），本任务不碰。

## 三、本轮发现：🔴 下载管理器（DM）根本没有删除入口

任务第 7 步要求「移除下载管理器里那一行」。实测**做不到** —— 并且暴露出原脚本的一个假信号：

| 证据 | 观察 |
|---|---|
| 行内控件 | **永远只有「下载」一个**（`kat-icon[name=file_download]`），无删除/移除按钮 |
| 表头 8 个 `more_vert` | 全是**列宽拖拽把手**（宿主 `div[role=separator][draggable=false]`），**不是** kebab 菜单 |
| 悬停探测 | 派发真实 `pointerover` / `pointerenter` / `mouseover` / `mouseenter` 后，行的子元素**无任何新增**；页面无可见 `kat-menu` / `[role=menu]` 删除项 |
| 持久性 | 日志写「已移除 DM 行」→ **37 秒后 `goto_dm()` 刷新，行原样重现** |

**结论**：`rows[0].remove()` 是**纯客户端摘除**，只作用于当前 DOM；React 一重渲染 / 页面一刷新就被服务端数据还原。
Amazon 侧那些条目是由 **Amazon 自行过期回收**的（2026-09-21 那轮"清掉"的 23 行，09-27 看已不在 —— 但那不是我们删的）。

**对自动化的影响 ≈ 0**，因为防重复下载靠的是两道**幂等闸门**，不靠 DM 清理：
1. 下载侧只按**目标周**匹配（`endDate == week_slash`）→ 陈旧周条目不会被误点；
2. 灌库侧 `import_batches.file_hash` 去重 + `ON CONFLICT (marketplace, brand_name, week_start_date, week_end_date, search_query) DO UPDATE`。

### 已做的修正（`ba-export/ba_sqp_weekly.py`）
- `remove_dm_row()`：改为摘掉**同名全部**行（原实现只摘 `rows[0]`，同名重复只清一条）；
- `remove_dm_row()` docstring：写清"客户端行为、非真正清空 Amazon 列表、勿夸大"；
- 日志措辞：`已移除 DM 行` → `已从当前页面摘掉 DM 行（客户端，刷新会重现）`；
  `prune_dm 完成，清理 N 行` → `prune_dm 完成，本页摘掉 N 条 ｜注：Amazon DM 无删除接口，刷新会重现，靠幂等兜底`。
- `py_compile` 通过；`--prune-dm --dry-run` 复跑正常。

## 四、本地清理

- `ba-export/staging/WHITIN/` → **空**。
- 紫鸟下载目录 → 本轮文件已删；另清掉一个 **09-21 遗留**的 `US_搜索查询绩效_品牌视图_简单_Week_2026_09_19.csv`（224,635 bytes，2026-09-21 03:57；其 09-19 周数据早已入库，纯冗余）。
- 复查：该目录下 `*搜索查询绩效*Week*` 匹配数为 **0**。

## 五、排障要点（沿用，未变）

退出码：`3`=前置不满足 / `4`=DM 未出现该周条目 / `5`=定位或点击失败 / `6`=240s 未落盘 / `7`=灌库失败（保留本地待排查）。
补洞：`ba_sqp_weekly.py --week YYYY-MM-DD`（幂等）。日志：`ba-export/ba_sqp_weekly.log`。

## 六、安全声明

本任务**只做**：读取 BA 页面、下载报告、写 RDS、清理本地文件、管理自己的下载任务。
**未做**：未修改任何广告投放设置（预算/出价/活动状态），未改动任何 Amazon 账号设置。
