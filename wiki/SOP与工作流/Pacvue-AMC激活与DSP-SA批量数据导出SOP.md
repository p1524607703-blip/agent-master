---
tags: [SOP与工作流, 亚马逊广告, Pacvue, AMC, DSP, Sponsored-Ads, 数据导出]
date: 2026-09-01
status: 现行
---

# Pacvue-AMC激活与DSP-SA批量数据导出SOP

> [!summary] 摘要
> 本页整理 Pacvue AMC 激活的前置授权、Measurement 与 Audience 的边界，以及 WHITIN 美国站首批 DSP、Sponsored Ads 和 AMC 批量数据清单。第一轮推荐导出 6 份 SA、5 份 DSP，并运行 4 份 AMC 报告；统一使用最近 90 天、按天、截至昨天的数据，先完成人工诊断，再决定是否建立受众或批量修改广告。

## 核心知识

### AMC 激活顺序

Pacvue 官方要求先连接 DSP，再授权 AMC：

1. Pacvue DSP → My Account → Authorization，授权 Amazon DSP profile。
2. 将 DSP profile 切换为 Managed，启动数据同步。
3. AMC Console → AMC Account → Authorize，授权 AMC instance。
4. 如果 AMC 与 DSP 使用不同 Amazon 登录账号，手动选择要绑定的 instance。
5. 将 AMC instance 切换为 Managed，并为人员分配 instance 权限。
6. SA Entity 需先在 Pacvue My Account 完成 Authorization；即使不切换为 Manage/Billable，也应完成授权，避免新 AMC instance 申请转入人工流程。

新建 AMC instance 时需准备：DSP Advertiser ID、SPA Entity ID、SPA Marketplace、SPA 是否已连接 Pacvue、Advertiser Name、Pacvue Admin Username，并按 Pacvue 指引联系 `amconboarding@pacvue.com`。

### Measurement 与 Audience 的边界

| 类型 | 输出 | 用途 | 边界 |
|---|---|---|---|
| Measurement | 聚合、匿名报告 | 路径、漏斗、频次、重叠、新客、复购 | 不导出用户明细 |
| Audience | 可激活人群包 | DSP/SD 定向，SP/SB 人群加价 | 人群直接推送广告账户，不下载名单 |

Amazon 官方说明，AMC audience 可推送到 Amazon DSP 或 Sponsored Ads；规则型 audience 成功创建后，最长可能需要约 48 小时才可使用。每个 audience 必须配置包含、排除、ASIN、窗口、刷新频率、投放渠道、预算、KPI、对照组和停止条件。

### 第一批批量导出清单

#### Sponsored Ads：6 份 P0

1. Campaign：SP、SB、SD，按天。
2. Ad Group：SP、SB、SD，按天。
3. Targeting / Keyword：SP、SB、SD，按天。
4. Search Term：SP、SB、SD，按天。
5. Advertised Product / ASIN：SP、SD，按天。
6. Placement：至少 SP，按天。

P1 再补 Purchased Product、Ads/Creative、Budget/Rule/History。所有表保留 marketplace、profile、campaign/ad group/target/ad/creative/ASIN ID，以及 impressions、clicks、spend、orders、units、sales、NTB 基础指标。CTR、CPC、CVR、ACOS、ROAS 在清洗阶段统一计算。

#### DSP：5 份 P0

1. Advertiser / Order / Line Item / Creative 层级绩效，按天。
2. Audience Performance。
3. Reach & Frequency。
4. Supply Source / Inventory / Site-App / Device。
5. Conversion / Product。

P1 再补 Creative/Video、Geography、Time of Day。保留 attribution type/window、currency、timezone 和 marketplace；Video、STV、Display 不只按 ROAS 横向比较，还要看 reach、frequency、viewability、video completion、DPV 与 NTB。

#### AMC：4 份首批报告

1. 营销漏斗：定位曝光、点击、详情页、加购、购买的流失。
2. 广告类型重叠：判断 DSP 与 SP/SB/SD 的互补或重复。
3. 转化路径和预算分配：识别首触、助攻、末触。
4. 触达和曝光频率：寻找频次甜点区和疲劳区。

随后按需要运行分时探索、赞助广告目标关键词购买路径、赞助广告定向关键词表现、新客网关 ASIN、NTB 趋势、RFM、复购和 CLTV。Retail Purchases、Brand Store Insight 等模板依赖相应数据订阅或 Paid Features。

### 时间范围与频率

- 第一次导出：最近 90 天、按天、截至昨天，包含 Active 与 Paused。
- 每日：Campaign、预算、花费、订单、销售额、状态。
- 每周：Ad Group、Targeting、Search Term、ASIN、Placement、DSP Audience、Supply、Creative。
- 每两周：频次、路径、重叠、漏斗、NTB、受众实验中期检查。
- 每月：CLTV、RFM、复购、交叉购买、区域/设备和预算重分配。

> [!warning] 历史窗口不是单一数字
> Pacvue 新连接 Amazon 数据默认回看 60 天；Pacvue 2026-07 回填文档写 AMC 自定义查询可回看 13 个月；Amazon 当前 AMC 产品页宣传广告流量信号最长 25 个月；Pacvue 当前 Retail Purchases 模板显示最长 5 年。它们对应不同数据源、套餐和版本，应以实际 AMC instance 的日期与数据源说明为准。

### 数据质量规则

1. Campaign 作为最完整总盘；Ad Group、Targeting、Search Term 应能与其基本对齐。
2. Ads、Advertised Product、Placement 可能低于 Campaign；SB 不提供与 SP/SD 相同的商品级拆分。
3. 不包含当天数据：Pacvue Campaign 可能每 3 小时同步，其他报表通常每天一次。
4. ID 使用文本；比例底层值保持 0–1；金额保留货币；日期统一时区。
5. 标注点击/浏览归因、归因窗口与 NTB 口径。
6. AMC 小样本缺行可能来自隐私聚合阈值，不自动判断为导出失败。
7. 创建 audience、应用投放、改预算/出价/否词均需人工确认。

### WHITIN 第一轮执行

1. 验证 `adsboostorwhitinsneakerus` 的 DSP、SA、AMC 授权和人员权限。
2. 导出 SA 六份 P0 与 DSP 五份 P0，最近 90 天、按天。
3. 运行营销漏斗、广告类型重叠、转化路径和预算分配、触达和曝光频率。
4. 输出三张人工决策表：预算重分配、受众测试、搜索词/定向动作。
5. 先人工复核一轮，再将有效规则转为 Pacvue 批量操作表或自动化规则。

## 关联

- [[AMC查询用例与自动化对接方案]]
- [[AMC受众细分与Hermes网页方案]]
- [[AMC清洗后数据质量审查与仪表盘建议]]
- [[亚马逊DSP与AMC-代理商方案与分析框架]]
- [[利用DSP广告打造流量闭环-视频转录与案例分析]]

## 来源

- 飞书精简教程（仅保留模板、AMC 分析与受众实验、导出频率、质量检查）：[Pacvue AMC 激活实操教程｜DSP + Sponsored Ads 批量数据导出与分析清单](https://my.feishu.cn/docx/USm9dZaDDo93b7x2uuJceshZnKh)
- Pacvue 官方：How To Connect AMC Data into Pacvue，https://support.pacvue.com/hc/en-us/articles/21560003000221-How-To-Connect-AMC-Data-into-Pacvue
- Pacvue 官方：Onboarding Advertising Data Into Pacvue，https://support.pacvue.com/hc/en-us/articles/12179926149021-Onboarding-Advertising-Data-Into-Pacvue-All-Platforms
- Pacvue 官方：Historical Data Backfill Process，https://support.pacvue.com/hc/en-us/articles/17201544327197-Historical-Data-Backfill-Process
- Pacvue 官方：Understanding Metric Discrepancies Between Different Reports，https://support.pacvue.com/hc/en-us/articles/37791565812893-Understanding-Metric-Discrepancies-Between-Different-Reports
- Amazon Ads 官方：Amazon Marketing Cloud，https://advertising.amazon.com/solutions/products/amazon-marketing-cloud
- Amazon Ads 官方：Custom audiences in Amazon Marketing Cloud，https://advertising.amazon.com/help/GR6KFNDJAUEJB66P
- Amazon Ads 官方：Create a lookalike or rule-based audience，https://advertising.amazon.com/help/GXCLLP4FBHRE2PDD
- Pacvue 当前 AMC 激活控制台：实例 `adsboostorwhitinsneakerus`，2026-09-01 核对
