---
tags: [SOP与工作流, 亚马逊广告, AMC, 数据分析, 自动化]
date: 2026-05-21
status: 现行
---

# AMC查询用例与自动化对接方案

> [!summary] 摘要
> 本页说明 Amazon Marketing Cloud（AMC）适合回答哪些广告策略问题，以及后续如何用 Amazon Ads API 自动执行 AMC SQL、下载 CSV 结果，并写入本地或钉钉/飞书数据表。核心原则是：普通广告后台负责日常投放优化，AMC 负责跨触点、跨时间、用户路径和受众策略分析。

## 核心知识

### 什么时候用 AMC

AMC 适合解决普通广告后台看不清的问题，例如用户路径、跨广告类型影响、DSP 与 Sponsored Ads 组合效果、品牌新客、复购、广告触点顺序、频次、视频素材后的转化等。

不建议把 AMC 当成每天调价的第一工具。日常否词、出价、预算、广告活动状态仍优先看普通广告后台、搜索词报告、关键词报告和广告组合报表。

### 查询语句类型与最佳用例

| 查询类型 | 主要数据源 | 适合回答的问题 | 输出后怎么用 |
|---|---|---|---|
| 广告活动总览 | `sponsored_ads_traffic`, `amazon_attributed_events_by_conversion_time` | 哪些 Campaign 花费高、销售低、ROAS 差？ | 找优化优先级，回到普通广告后台调预算、否词、出价 |
| 搜索词与关键词质量 | `sponsored_ads_traffic` | 哪些搜索词点击多但不转化？哪些词值得迁移到手动精准？ | 生成否定词、手动广告关键词扩展清单 |
| 转化路径 | `amazon_attributed_events_by_conversion_time`, `amazon_attributed_events_by_traffic_time` | 用户购买前经历了哪些触点？先看到 DSP 后搜品牌词是否更容易转化？ | 判断上层广告是否有助攻价值 |
| 频次与触达 | `dsp_impressions`, `dsp_clicks`, `conversions` | 用户看到几次广告后转化率最好？频次过高是否浪费？ | 设定频次、预算和再营销策略 |
| DSP 与 Sponsored Ads 协同 | `dsp_impressions`, `sponsored_ads_traffic`, `conversions` | 同时接触 DSP 和 SP/SB 的用户是否更容易购买？ | 判断是否保留上层广告预算 |
| 新客与品牌光环 | `amazon_attributed_events_by_conversion_time` | 广告带来的是否是品牌新客？是否购买了同品牌其他 ASIN？ | 判断推广是否只吃老客，或是否带动品牌整体增长 |
| 视频素材效果 | `dsp_video_events_feed`, `dsp_impressions`, `conversions` | 视频播放完成率、四分位观看和后续购买有什么关系？ | 反哺视频脚本和美工素材方向 |
| 商品与 ASIN 迁移 | `conversions`, `amazon_attributed_events_by_conversion_time` | 广告推 A 商品，用户最后是否买 B 商品？ | 调整主推款、关联销售和产品组合 |
| 受众构建 | `conversions_with_relevance`, `dsp_views`, `sponsored_ads_traffic` | 哪些人看过/加购/点击但没买？哪些老客可复购或交叉销售？ | 创建 AMC audience，再同步到 DSP/广告投放 |
| 时间滞后与归因窗口 | `amazon_attributed_events_by_conversion_time`, `amazon_attributed_events_by_traffic_time` | 点击或展示后多久才转化？看转化时间还是流量时间？ | 设定报表观察周期，避免过早判断广告无效 |

### 第一批建议沉淀的查询模板

1. Campaign 效率诊断：按广告活动汇总 Spend、Sales、Purchases、ROAS、ACOS。
2. Search Term 浪费识别：找高点击、高花费、无订单或低 ROAS 搜索词。
3. 自动广告挖词：从自动广告中提取有订单搜索词，作为手动广告候选词。
4. 新客贡献：看新客购买、新客销售额、品牌光环购买。
5. 触点路径：按用户聚合购买前的曝光、点击、广告类型顺序。
6. DSP 助攻分析：比较只接触 Sponsored Ads、只接触 DSP、两者都接触的转化表现。
7. 频次分桶：按用户曝光次数分桶，计算转化率、销售额和浪费区间。
8. 视频素材复盘：按 creative 或 video event 汇总播放完成与购买关系。

### 自动化对接是否可行

可行。后续不需要你复制粘贴 SQL。推荐做成一个本地或云端的 AMC 查询执行器：

1. 本地维护 SQL 模板库，每个模板有名称、用途、参数、输出字段说明。
2. 脚本读取参数，例如日期范围、站点、广告活动、ASIN、查询模板名。
3. 调用 Amazon Ads API 的 AMC reporting workflow：创建/执行 workflow。
4. 轮询 workflow execution 状态，直到成功或失败。
5. 通过下载 URL 拉取 CSV，或从绑定 S3 bucket 读取结果。
6. 自动写入钉钉 AI 表、飞书表格、本地 CSV/Excel 或 Obsidian 附件。
7. 再由 AI 对结果做诊断，输出广告优化建议。

### 自动化需要的权限与参数

| 需要项 | 用途 | 备注 |
|---|---|---|
| Amazon Ads API access | 调用 AMC API | 需要开发者应用和授权 |
| Login with Amazon OAuth | 获取 access token / refresh token | 不应写入公开仓库 |
| AMC instanceId | 指定查询运行在哪个 AMC 实例 | 可从 AMC 后台或 API 获取 |
| AMC account / advertiser id | API header 必填 | 不是普通 Campaign ID |
| Marketplace ID | 指定站点 | 美国站常见为 `ATVPDKIKX0DER` |
| S3 bucket | 保存查询输出 | 可选，但做长期自动化更稳 |
| SQL 模板库 | 避免复制粘贴 | 后续可存本地、钉钉 AI 表或飞书表 |

> [!warning] 安全边界
> 查询和导出报表属于分析动作，不会直接改广告预算、出价或状态。但如果后续做 audience 创建、投放激活、预算/出价修改，就必须单独确认，不能自动执行。

### API 对接难度与等待时间判断

API 对接分成两个阶段：权限审批阶段和技术落地阶段。

| 阶段 | 繁琐程度 | 主要卡点 | 时间判断 |
|---|---|---|---|
| AMC 后台开通 | 中 | 账号是否符合 AMC 资格、是否有 sponsored ads 或 DSP 入口 | 如果账号已有资格，通常较快；如果走客户经理或权限申请，则不确定 |
| Amazon Ads API access | 高 | 需要创建 LWA 应用、提交 API access、等待审批、分配 API access | 官方要求申请和审批，但不承诺固定时长，建议预留 1-2 周缓冲 |
| OAuth 授权 | 中 | 回调地址、client id/secret、refresh token 保存 | 权限到位后可在半天内跑通 |
| AMC workflow 执行器 | 中低 | 请求头、instanceId、marketplaceId、advertiserId、轮询与下载结果 | 参数齐全后 1-2 天可做 MVP |
| 定时导出与入表 | 中 | S3 或 download URL、CSV 清洗、写入钉钉/飞书字段映射 | MVP 后再加 1-3 天 |

最稳妥的推进方式是：先确认账号是否已经能进入 AMC；再申请/确认 Amazon Ads API access；同时先做本地 SQL 模板库和钉钉字段字典，不让审批等待卡住学习进度。

### 推荐落地架构

```mermaid
flowchart LR
    A["钉钉/本地查询模板库"] --> B["AMC Query Runner"]
    B --> C["Amazon Ads API OAuth"]
    B --> D["AMC Workflow Execution"]
    D --> E["Download URL 或 S3"]
    E --> F["CSV / Excel / 钉钉AI表"]
    F --> G["AI广告诊断"]
    G --> H["人工复核后执行优化"]
```

### 与现有工作流的关系

- 钉钉 AI 表《AMC 数据源字段字典》已经完成 12 个核心数据源字段导入，可作为 SQL 编写和字段解释的字典。
- 普通广告后台仍负责日常执行：否词、预算、出价、暂停、创建广告活动。
- AMC 自动化负责定期生成更深层策略报表：路径、频次、协同、新客、视频素材效果。
- AI 负责把 AMC 输出转成运营语言：哪些广告要保留、哪些要降价、哪些词要否、哪些素材值得继续拍。

## 关联

- [[亚马逊广告营销优化规划方案与学习路径]]
- [[亚马逊广告活动页操作教程]]
- [[亚马逊广告组合模块教学]]
- [[亚马逊创建广告活动模块教学]]

## 来源

- 飞书同步文档：AMC查询用例与自动化对接方案，https://my.feishu.cn/docx/UKH1dxZioohXooxN4PTcwXVinph
- Amazon Ads 官方文档：Amazon Marketing Cloud Overview，https://advertising.amazon.com/API/docs/en-us/guides/amazon-marketing-cloud/overview
- Amazon Ads 官方页面：Amazon Marketing Cloud，https://advertising.amazon.com/solutions/products/amazon-marketing-cloud
- Amazon Ads 官方公告：Amazon Marketing Cloud APIs are now part of the Amazon Ads API，https://advertising.amazon.com/resources/whats-new/amc-api-available-on-amazon-ads-api/
- 钉钉 AI 表：AMC 数据源字段字典，https://docs.dingtalk.com/i/nodes/gvNG4YZ7Jneen4dLF9Zop03jV2LD0oRE
