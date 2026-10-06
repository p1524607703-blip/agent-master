# 业务报告「按父商品」自动导出

从 Amazon Seller Central **业务报告 → 按 ASIN → 详情页面销售和流量（按父商品）**
自动导出日级 / 周级 CSV，三站（现启用川鹏2号、欧德思美站）串行跑，落盘归档。

通道：紫鸟浏览器 + ZClaw Bridge（9480/9481），URL 导航 + 官方「下载 (.csv)」按钮。
**不碰任何店铺写操作**，只读 + 下载。

---

## 一、日期口径（最容易踩坑，先读这段）

| 事实 | 说明 |
|---|---|
| 业务报告的日界是**太平洋时间** | 页面快照时间显示 `GMT-7/GMT-8` 即为 PDT/PST，不是美东、更不是北京 |
| URL 日期区间是**左闭右开** | `fromDate` 含、`toDate` **不含**；取 D 日单日要传 `fromDate=D&toDate=D+1` |
| 取数日 = 太平洋当日 − 1 | 保证拿到的是**已结算完整**的一天 |

对照用户口径（已逐条验算一致）：

```
北京 9/8 09:00 运行
  → 太平洋 9/7 18:00  → 太平洋当日 = 9/7
  → 目标 = 9/7 − 1 = 9/6        ✅ 与「北京9/8 → 选9/6」一致
```

周报：**北京时间周二**触发，导出上一个太平洋周（周一 ~ 周日）。

---

## 二、用法

```bash
cd /Users/panjinlong/Documents/agent-master/business-report

node br_pull.js                                   # 自动算日期, 跑已启用店铺(日+周二追加周报)
node br_pull.js --from 2026-09-06 --to 2026-09-06 # 手动指定范围
node br_pull.js --weekly                          # 强制追加周报
node br_pull.js --stores 川鹏2号                   # 只跑指定店(逗号分隔)
node br_pull.js --force                           # 已存在的文件也重下
node br_pull.js --no-download                     # 只验证日期链路, 不下载(排障用)
node br_pull.js --skip-verify                     # 日期校验失败也强行下载
```

---

## 三、输出

`out/` 目录，文件名自带范围（CSV 内容**没有日期列**，所以日期只能靠文件名识别）：

| 类型 | 命名 | 示例 |
|---|---|---|
| 日报 | `BR_<店铺>_daily_<YYYY-MM-DD>.csv` | `BR_川鹏2号_daily_2026-09-06.csv` |
| 周报 | `BR_<店铺>_weekly_<YYYYMMDD>-<YYYYMMDD>.csv` | `BR_川鹏2号_weekly_20260831-20260906.csv` |

列（16 列，中文表头，UTF-8 BOM）：（父）ASIN / 标题 / 会话数-总计 / 会话-总计-B2B /
转化率-移动应用-B2B / 会话百分比-移动应用 / 会话百分比-浏览器 / 会话百分比-浏览器-B2B /
已订购商品数量 / 已订购商品数量-B2B / 商品会话百分比 / 商品会话百分比-B2B /
已订购商品销售额 / 已订购商品销售额-B2B / 订单商品总数 / 订单商品总数-B2B

**幂等**：目标文件已存在且非空则跳过；重跑安全，不会重复下载。

日志：`logs/run_<北京日期>_<模式>.log`

---

## 四、前置条件

1. 紫鸟浏览器已启动，`127.0.0.1:9480/9481` 在监听
2. 目标店铺在紫鸟里登录态正常
3. 账号有**业务报告**访问权限（洁博利美站即因无此权限而停用）

---

## 五、实现要点（排障先看这里）

- **URL 驱动，不点日期控件**：日期直接编码进 URL
  `#/report?id=102:DetailSalesTrafficByParentItem&fromDate=…&toDate=…&columns=…`。
  页面上 `kat-date-picker` 是 shadow DOM 里的 lit 组件，注入 `value` 能改显示值，
  但点「应用」经常带不出数据——**URL 直开更稳**。
- **表格 UI 经常渲染不出数据行**（`usdCount` 恒为 0，页面只剩表头）：
  这是 Amazon 前端的锅，**不影响下载**。所以就绪判定只看日期控件是否回读到目标值，
  不依赖页面画出数据行。别再去折腾「为什么表格是空的」。
- **紫鸟代理会瞬态 `chromewebdata` 网络错误**：脚本先访问 `/home` 预热，
  再进报告页并最多重试 3 次。
- 下载落盘后按 mtime 捕获新文件（Amazon 原始名如 `BusinessReport-08-9-26.csv`），
  再 rename 成规范名；会等 1.5s 确认大小不再增长，避免拿到半截文件。
- 落盘后校验：是否 xlsx 伪装（PK 头）、行数 < 2 视为空表、表头是否含「（父）ASIN」。

---

## 六、故障速查

| 症状 | 原因 | 处理 |
|---|---|---|
| `no targetId` / `open failed` | 店铺未登录、紫鸟未起、代理网络错误 | 检查紫鸟与登录态；脚本已内置重试 |
| 日期回读 MISMATCH | Amazon 改版或 URL 参数失效 | 用 `--no-download` 看 pickers 实际值 |
| CSV 只有表头（1 行） | 当天该店确无数据，或权限不足 | 人工到后台确认该店该日是否有量 |
| 文件名撞车被跳过 | 同日已跑过 | 加 `--force` |
| 两个店铺同一时刻抢跑 | 两个 automation 并存 | 脚本内串行，只保留一个每日任务 |

---

## 七、定时任务（WorkBuddy 自动化）

| id | 名称 | 频率 |
|---|---|---|
| `80763423-45b5-4bf7-94d5-c4ba814d35ed` | 业务报告按父商品每日导出 | 本机每日 21:00（EDT）= 北京次日 09:00 |
| `d1dd8b4c-9fc6-4e11-98de-b1b1321fae85` | 时区校正（冬令时） | 2026-11-01 一次性，把 BYHOUR 改回 20 并自我续建 |

rrule 的 `BYHOUR` 按本机（America/New_York）解释：
夏令时 21 → 北京 09:00；冬令时 20 → 北京 09:00。换季由上面的校正任务自动处理。

---

## 九、入 RDS

**目标表已存在，不要新建**：`core.business_report_parent_asin_period`（owner `amazon_ads_admin`）。
16 个指标列与本 CSV 完全对齐，唯一键 `(account_id, report_start_date, report_end_date, parent_asin)`。

表按「期间」存储：单日存 `(D, D)`，周快照存 `(周一, 周日)`，靠 start/end 区分，互不覆盖。
查询时**注意别把日数据和周快照混加**。

`account_id` 用的是 **Amazon 广告账户 ID**，不是紫鸟 storeId：

| 店铺 | account_name | account_id |
|---|---|---|
| 川鹏2号 | WHITIN | `amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh` |
| 欧德思美站 | BLOOMNEXT | `amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919` |

```bash
python3 br_to_rds.py                    # 导入 out/ 下全部 CSV
python3 br_to_rds.py --file out/xx.csv  # 单个文件
python3 br_to_rds.py --dry-run          # 只解析校验不写库
python3 br_to_rds.py --force            # 忽略 file_hash 去重强制重导
```

幂等两重：`import_batches.file_hash` 唯一 + 目标表 `ON CONFLICT DO UPDATE`
（Amazon 回溯修正历史数据时会被更新，而不是静默丢弃）。

**连接**（2026-09-21 更新）：现行入库脚本是 **`br_child_to_rds.py`**，它从
`amazon-ads-console/backend/.env` 的 `RDS_DATABASE_URL` 读连接（拆成 `PG*` 环境变量），
目标库 **`amazon_ads_v2`**，用户 `amazon_ads_admin`。
下文提到的 `br_to_rds.py` 是**旧版**（连旧实例 `121.41.134.56` / 库 `amazon_ads`），
该实例已整机退役，脚本现已改为直接报错并指向 `br_child_to_rds.py`。

清洗规则：千分符 / `US$` 前缀 / 百分号全部剥离，非法值落 NULL；
`title` 为空时用 `parent_asin` 回填（该列 NOT NULL）。

---

## 十、店铺开关

`br_pull.js` 顶部 `STORES` 数组，`enabled: false` 即跳过。
洁博利美站（`16468050574114`）因账号无业务报告访问权限已停用，拿到权限改回 `true` 即可。
