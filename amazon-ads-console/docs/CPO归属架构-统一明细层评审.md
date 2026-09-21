# CPO 归属架构评审：GPT「统一明细层」方案 vs 当前实现

> 2026-09-18 · 所有数字来自 `amazon_ads_v2` + `amazon_ads` 只读实测查询（脚本见文末）
> 前置文档：`数据架构与ER图.md` · `五层分表设计与连接方案.md` · `架构评审-矩阵式宽表的取舍.md`

---

## 一、先把 GPT 那套话翻译成人话

他讲了三件事，前两件是**否定**，第三件是**主张**：

| # | 他的意思 | 翻译 |
|---|---|---|
| 否定 1 | 不能"全账户先汇总成总数，再把总数分给 XM/ZJ/AJ" | 汇总之后再分钱，分不清每一块钱属于哪个产品 → 不可逆 |
| 否定 2 | 不能"每个运营单独跑一套代码" | 同一指标 N 套实现 → 口径漂移 → 管理层和运营层对不上数 |
| 主张 | **一套计算引擎，一次完成归属，多层汇总输出** | 明细层打全标签 → 聚合层级只是 GROUP BY 不同 → 分发是权限不是算法 |

一句话：**"先归属、后聚合"**，且归属只做一次。

### 他这条链路其实你已经做到了

| 步骤 | GPT 原文 | 当前系统实现 | 状态 |
|---|---|---|---|
| 1 | 全账户统一原始明细层 | `core.report_{advertised_product,purchased_product,business_parent_asin}_daily` 等事实表已落库 | ✅ 已实现 |
| 2 | 产品归属 父ASIN→产品号→运营组 | `app.product_mapping`（128 父ASIN）+ `_mapping()`，广告侧命中率 **100%**、业务侧 **98.5%** | ⚠️ 已实现但跨库内存拼接 |
| 3 | 特殊广告分摊（SB 集合） | 无任何分摊逻辑，拆不出即丢进「未归属」 | ❌ 未落地（实测优先级最低，见第三节） |
| 4 | 明细打标签 operator/ad_type/product | `_build()` 在内存里打 `operator_group` / `ad_type` / `product_code` | ⚠️ 运行时，未落表 |
| 5 | 产品×运营×广告类型×日期 日级事实表 | 无此表，每次查询现算 | ❌ 未物化 |
| 6 | 产品/运营/公司 CPO 分层汇总 | `operator_cpo_summary` + `_summarize`，同一函数按层级分组 | ✅ 已实现 |
| 7 | 登录后按运营组分发 | `/my-cpo` + `ROLE_HOME`，组别由服务端会话推导，不接收前端传参 | ✅ 已实现 |

> **结论：7 步里 3 步已完成、2 步是"运行时而非物化"、1 步未落地、1 步有跨库隐患。**
> 他的"关键点是运营归属一定要在最终聚合之前完成"——**当前代码已经完全遵守这条**（先按父ASIN映射到产品/运营，再聚合）。
> 所以这是一次口径确认，不是一次重构。

---

## 二、他没看到的三个硬约束

### 约束 1：跨库。这是他方案落地的唯一真门槛

```
amazon_ads     （应用库，8 MB）    → app.product_mapping、app.product_roster、iam.*
amazon_ads_v2  （数据仓库，2.3 GB）→ core.report_*_daily、core.import_batches
```

PostgreSQL **不支持跨库 JOIN**。当前系统的做法是：Python 侧把两边分别拉出来，在内存里 `mapping.get(parent_asin)` 拼。

所以 GPT 建议的 ⑤「日级事实表」如果建在 `amazon_ads_v2`，就必须**先把 `app.product_mapping` 单向快照进 v2**；反过来若要建在应用库，就要把广告事实复制过去。
→ 这是必须先拍板的架构决策，他没提，因为他不知道你有双库。

### 约束 2：「产品级」的键不是产品代号，是 (产品代号, 父ASIN, 账户边界)

实测：**117 个 confirmed 父ASIN → 109 个产品代号**，一对多存在。
同一产品代号可以跨账户存在，而业务报告只到父ASIN 粒度。

若按"产品代号"直接聚合，会出现**A 账户的广告花费 ÷ B 账户的业务订单**——分子分母不同源，CPO 直接失真。
现有代码用 `bucket()` 的四元组键 `(group, productCode, parentAsin, accountScope)` 正是为此，且注释里明确写了原因。**这个设计必须保留**，不能简化成 GPT 表里的"产品"一列。

### 约束 3：分摊救不了分母

GPT 的 ③「SB 集合分摊」解决的是**分子归谁**。但请看第三节——当前 40.6% 的缺口缺的是**分母**，分摊方式怎么改都补不上。

---

## 三、实测：真正的缺口在哪

### 3.1 广告花费构成（2026-08-15 ~ 09-14，31 天）

| 账户 | 广告类型 | 有效花费 | 能否在业务报告找到 |
|---|---|---:|---|
| BLOOMNEXT | Sponsored Products | 264,356.92 | ✅ 100% |
| JOOMRA DIRECT | Sponsored Products | 263,564.95 | ❌ **0%** |
| anac1973 (C3S8S) | Sponsored Brands | 247,468.53 | ⚠️ 220,594.86 可 / **26,873.67 不可** |
| JOOMRA DIRECT | Sponsored Brands | 21,063.44 | ❌ 0% |
| BLOOMNEXT | Sponsored Brands | 16,490.99 | ✅ 100% |
| BLOOMNEXT | Sponsored Display | 9,866.36 | ✅ 100% |
| JOOMRA DIRECT | Sponsored Display | 4,018.38 | ❌ 0% |
| — | 父ASIN 为 NULL/-1（不可识别） | 31,026.77 | — |
| | **合计** | **857,856.34** | |

⚠️ **AMS 是纯 SB 账户**：`anac1973 (C3S8S)` 全部花费 = 247,468.53，占广告总花费 **29%**，且**没有自己的业务报告**——必须靠"同日父ASIN 在哪个业务账户出现"反推归属（`resolve_ad_scope`），一对多时按规则不猜、直接丢弃。

### 3.2 三项完整日只有 7 天

| 日期 | 业务报告 | 推广的商品 | 达成转化的商品 |
|---|---:|---:|---:|
| 09-06 ~ 09-09 | ✅ | ✅ | ✅ |
| **09-10 / 09-11** | **0 行** | ✅ | ✅ |
| 09-12 ~ 09-14 | ✅ | ✅ | ✅ |
| 09-15 / 09-16 | ✅ | **0 行** | **0 行** |

→ 可算 CPO 的完整日 = **09-06/07/08/09/12/13/14 共 7 天**。
→ 09-10、09-11 业务报告**完全没入库**（不是"日期范围用宽了"），需补拉；广告侧缺 09-15/09-16。

### 3.3 单日缺口解剖（2026-09-14）

| 去向 | 金额 | 占比 | 性质 |
|---|---:|---:|---|
| 已配对，可算 CPO | 7,270.40 | 56.0% | 雪敏 5,588.29 / 子娟可算部分 1,357.47 / 雨珊 235.34 / 雅婷 81.42 / 丹丹 7.88 |
| **缺业务报告分母** | **3,812.10** | **29.4%** | 爱菊全部花费。洁博利 JOOMRA 无业务报告权限 |
| 部分缺业务侧 | 1,458.56 | 11.2% | 子娟：AMS SB 花费当天未找到唯一业务账户 |
| 无产品映射（未归属） | 435.72 | 3.4% | 26 个广告单，全窗口此类仅占 3.6% |
| **合计** | **12,976.78** | | |

**结论：能靠"分摊规则"救回来的只有最后一行 3.4%。**
前两行合计 **40.6%** 缺的是分母——分子（广告花费）一直都在，是分母（业务订单）不存在。

### 3.4 映射质量本身不是问题

| 侧 | 父ASIN 数 | 命中映射的覆盖 |
|---|---:|---|
| 广告侧 | 53 | 花费覆盖 **100.0%**（52/53） |
| 业务侧 | 248（BLOOMNEXT 56 / WHITIN 194） | 订购量覆盖 **98.5% / 99.0%** |
| 广告 ∩ 业务 | **41** | — |

→ 真正的瓶颈不是"映射不准"，而是**广告侧父ASIN 与业务报告父ASIN 的重合面只有 41 个**（53 个广告父ASIN 里 12 个在业务报告找不到）。

---

## 四、两个真 bug（与 GPT 无关，实测发现）

### Bug 1：周/月粒度的 `final_cpo` 永远为 False

```
operator_cpo_summary('2026-09-14', 'weekly')
→ period_start=2026-09-14, period_end=2026-09-20, expectedDays=7, coverageDays=1, final_cpo=False
```

`_period_range()` 把周期末尾算成**未来日期**，`period_complete = complete_days == expected` 因此永远不成立。
只要用户选"本周"，页面上永远不会出现"最终"标记——而本周本来就只有 1 天数据是正常的。
→ **修法**：把 `period_end` 截到"最后一个三项完整日"再算 `expectedDays`。

### Bug 2：全局 `final_cpo` 被 $435.72 一票否决

```
mapping_clean = unmappedAdSpend <= 0.005 and businessUnmappedOrders <= 0.005
final_cpo = complete_days and mapping_clean and ...
```

只要「未归属」桶里有一分钱，**整页所有运营都拿不到最终标记**，即使雪敏当天是干净的 100% 配平。
这不是错，是过保守——但代价是：只要洁博利永远没业务报告，这个全局标记可能永远是 False，最终演变成一个没人看的状态位。
→ **修法**：`final_cpo` 下移到运营粒度（每行已经有 `finalCpo`，但被全局位压制），全局位改成"数据完整度百分比"这类可读指标。

---

## 五、采纳建议（按优先级）

### P0 —— 不涉及代码，但决定 40% 数据能不能算

| # | 动作 | 影响 |
|---|---|---|
| P0-1 | **拿洁博利（JOOMRA）的 Seller Central 业务报告权限** | 唯一能让 29.4% 广告花费复活的动作。分摊规则、架构重构都做不到 |
| P0-2 | 补拉 09-10、09-11 业务报告 | 完整日 7 → 9 天 |
| P0-3 | 给 AMS 的 $26,873.67 建**静态归属表**，替代"同日反推" | 消除 11.2% 缺口，且不再依赖当天业务报告是否恰好覆盖该父ASIN |

### P1 —— 架构改进，建议做但不紧急

| # | 动作 | 理由 |
|---|---|---|
| P1-1 | 拍板跨库方向：`app.product_mapping` 单向快照进 v2，再物化 `core.cpo_product_daily` | GPT 的 ⑤ 落地前提。注意双库约束 |
| P1-2 | 事实表键必须是 `(stat_date, product_code, parent_asin, account_scope, ad_type)` | 见约束 2，不能只用 product_code |
| P1-3 | 修 Bug 1 / Bug 2 | 周月粒度 + 最终标记可用性 |
| P1-4 | 事实表加 `allocation_method` 列（先全填 `explicit_parent_mapping`） | 为将来分摊留位置，零成本 |

**关于物化的必要性要说清楚**：单日广告事实只有 6,233 行，全窗口 19.7 万行——**性能不是理由**。
物化的真实收益只有三条：① 口径冻结（今天算出来的数明天不会变）② 可审计（能追到"这一块钱为什么归 XM"）③ 前端查询从"跑 3 条大 SQL + 内存 join"变成单表扫。
如果这三条你不需要，**不做也完全可以**，当前的运行时计算在正确性上和它等价。

### P2 —— 最后做

| # | 动作 | 理由 |
|---|---|---|
| P2-1 | SB 集合分摊规则 + `allocation_method` | 实测只影响 3.6%（$31k/全窗口），且需要业务先定义分摊口径（按转化单数？按花费占比？按销售额？） |

---

## 六、复核 SQL

```sql
-- ① 广告花费按 账户 × 广告类型 拆分
SELECT account_name, ad_product, count(*) rows, round(sum(spend),2) spend
FROM core.report_advertised_product_daily
GROUP BY 1,2 ORDER BY 4 DESC NULLS LAST;

-- ② 父ASIN 可识别性
SELECT CASE WHEN advertised_product_parent_id IS NULL
              OR advertised_product_parent_id IN ('','-1')
            THEN 'NULL/-1 不可识别' ELSE '有父ASIN' END k,
       count(*) rows, round(sum(spend),2) spend
FROM core.report_advertised_product_daily GROUP BY 1;

-- ③ 广告花费中有多少能在业务报告里找到父ASIN
WITH ad AS (
  SELECT account_name, ad_product, advertised_product_parent_id parent, sum(spend) spend
  FROM core.report_advertised_product_daily
  WHERE advertised_product_parent_id NOT IN ('','-1') GROUP BY 1,2,3
), b AS (SELECT DISTINCT parent_asin FROM core.report_business_parent_asin_period)
SELECT ad.account_name, ad.ad_product,
       round(sum(ad.spend),2) spend_all,
       round(sum(CASE WHEN b.parent_asin IS NOT NULL THEN ad.spend ELSE 0 END),2) spend_in_biz
FROM ad LEFT JOIN b ON b.parent_asin=ad.parent
GROUP BY 1,2 ORDER BY 3 DESC;

-- ④ 三项完整日
WITH b AS (SELECT report_start_date d FROM core.report_business_parent_asin_period
           WHERE report_start_date=report_end_date GROUP BY 1),
     a AS (SELECT stat_date d FROM core.report_advertised_product_daily GROUP BY 1),
     p AS (SELECT stat_date d FROM core.report_purchased_product_daily GROUP BY 1)
SELECT b.d::text 完整日 FROM b JOIN a USING(d) JOIN p USING(d) ORDER BY b.d;

-- ⑤ 逐来源日期覆盖（找缺哪天）
SELECT d::text d,
       (SELECT count(*) FROM core.report_business_parent_asin_period b
         WHERE b.report_start_date=report_end_date AND b.report_start_date=t.d) biz,
       (SELECT count(*) FROM core.report_advertised_product_daily a WHERE a.stat_date=t.d) adv,
       (SELECT count(*) FROM core.report_purchased_product_daily p WHERE p.stat_date=t.d) pur
FROM generate_series(DATE '2026-09-06', DATE '2026-09-16', INTERVAL '1 day') t(d) ORDER BY 1;

-- ⑥ 映射规模（应用库 amazon_ads，需带 PG* 连接）
SELECT status, count(*) rows, count(DISTINCT parent_asin) parents,
       count(DISTINCT product_code) products, count(DISTINCT operator_group) groups
FROM app.product_mapping GROUP BY 1 ORDER BY 2 DESC;
```

> 注：`app.product_mapping` 在**应用库**，`core.report_*` 在**数据仓库**，两条 SQL 必须分别用 `PG*` / `RDS_PG*` 连接执行。
