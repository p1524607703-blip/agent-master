---
tags: [AI工程, 数据库, 亚马逊广告, 已归档]
date: 2026-08-13
status: 已归档
---

# 阿里云RDS-amazon_ads-库表结构（旧实例·已退役）

> [!warning] 本页描述的是**已退役**的旧实例，请勿据此连接
> 旧实例 `121.41.134.56`（域名 `pgm-bp18chyrycgz5q42zo.pg.rds.aliyuncs.com`，库 `amazon_ads`）**已整机退役**：
> ping 100% 丢包、`nc` TCP timeout、psql timeout。本页保留仅为历史对照（analytics / ops / chatgpt_ops 三 schema
> 在新库中**均已不存在**）。
>
> **现行主库请看 [[阿里云RDS-amazon_ads_v2-库表结构]]**（`pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com:5432` / `amazon_ads_v2`）。
> 归档日期：2026-09-21。

> [!summary] 摘要（历史）
> 阿里云 RDS PostgreSQL 18.3 实例（PGM-BP18CHYRYCGZ5Q42ZO）上 amazon_ads 库的完整结构：实例内 5 个数据库、amazon_ads 库 5 个 Schema（core / analytics / ops / chatgpt_ops / public）、18 张表与 9 个视图的字段、主键、唯一约束、外键与索引，以及本地连接方式与角色权限。

## 核心知识

### 1. 实例与连接信息（历史，已失效）

| 项目 | 值 |
|------|-----|
| 实例 ID | PGM-BP18CHYRYCGZ5Q42ZO（❌ 已退役） |
| 公网地址 | pgm-bp18chyrycgz5q42zo.pg.rds.aliyuncs.com（hostaddr 121.41.134.56）❌ 不可达 |
| 端口 / 版本 | 5432 / PostgreSQL 18.3 |
| SSL | sslmode=verify-full，root.crt 位于 ~/.postgresql/root.crt |
| 默认时区 | America/New_York（amazon-ads-data config.toml） |
| 本地客户端 | pgAdmin 4（桌面版，连接名「阿里云 RDS - amazon_ads」，用户 amazon_ads_admin） |
| 密码管理 | macOS 钥匙串：service=amazon-ads-rds-amazon_ads_admin；各角色见 amazon-ads-data/src/amazon_ads_data/db.py |

> [!note] 连接方式
> 密码不落盘：`security find-generic-password -a <role> -s <service> -w` 从钥匙串读取后经 psql / psycopg 连接；本地另有一份开发副本 127.0.0.1:5432（pgAdmin 连接「Amazon Ads（管理员）」）。

### 2. 实例内数据库

| 数据库 | 大小 | 说明 |
|--------|------|------|
| _supabase | 7910 kB |  |
| amazon_ads | 101 MB | 主业务库（广告报表 + 运营动作） |
| postgres | 7846 kB |  |
| rdsadmin | 7974 kB |  |
| supabase_db | 24 MB |  |

### 3. Schema 职责

| Schema | Owner | 职责 |
|--------|-------|------|
| analytics | amazon_ads_admin | 只读分析视图（统一日级、成熟版、复查到期、归因刷新、导入健康、TIB 最新） |
| chatgpt_ops | amazon_ads_admin | ChatGPT 侧运营（托管活动、动作提案、复盘、变更审计） |
| core | amazon_ads_admin | 广告原始数据（日/小时级报表、TIB 快照、导入批次、产品线映射） |
| ops | amazon_ads_admin | 运营动作（观察名单、变更日志、复查日志） |
| public | pg_database_owner | 系统默认（无业务对象） |

### 4. 表与视图结构

#### analytics.v_attribution_refresh_due（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 是 | — |
| 2 | account_name | pg_catalog.text | 是 | — |
| 3 | ad_product | pg_catalog.text | 是 | — |
| 4 | campaign_id | pg_catalog.text | 是 | — |
| 5 | campaign_name | pg_catalog.text | 是 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | stat_date | pg_catalog.date | 是 | — |
| 8 | report_exported_at | pg_catalog.timestamptz | 是 | — |
| 9 | mature_after | pg_catalog.date | 是 | — |
| 10 | attribution_status | pg_catalog.text | 是 | — |
| 11 | days_overdue | pg_catalog.int4 | 是 | — |

#### analytics.v_campaign_daily_unified（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 是 | — |
| 2 | account_name | pg_catalog.text | 是 | — |
| 3 | ad_product | pg_catalog.text | 是 | — |
| 4 | campaign_id | pg_catalog.text | 是 | — |
| 5 | campaign_name | pg_catalog.text | 是 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | stat_date | pg_catalog.date | 是 | — |
| 8 | impressions | pg_catalog.int8 | 是 | — |
| 9 | viewable_impressions | pg_catalog.int8 | 是 | — |
| 10 | clicks | pg_catalog.int8 | 是 | — |
| 11 | spend | pg_catalog.numeric | 是 | — |
| 12 | purchases | pg_catalog.int8 | 是 | — |
| 13 | new_to_brand_purchases | pg_catalog.int8 | 是 | — |
| 14 | sales | pg_catalog.numeric | 是 | — |
| 15 | new_to_brand_sales | pg_catalog.numeric | 是 | — |
| 16 | long_term_sales | pg_catalog.numeric | 是 | — |
| 17 | report_exported_at | pg_catalog.timestamptz | 是 | — |
| 18 | attribution_window_days | pg_catalog.int2 | 是 | — |
| 19 | mature_after | pg_catalog.date | 是 | — |
| 20 | attribution_status | pg_catalog.text | 是 | — |
| 21 | data_source | pg_catalog.text | 是 | — |

#### analytics.v_campaign_mature_daily（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 是 | — |
| 2 | account_name | pg_catalog.text | 是 | — |
| 3 | ad_product | pg_catalog.text | 是 | — |
| 4 | campaign_id | pg_catalog.text | 是 | — |
| 5 | campaign_name | pg_catalog.text | 是 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | stat_date | pg_catalog.date | 是 | — |
| 8 | impressions | pg_catalog.int8 | 是 | — |
| 9 | viewable_impressions | pg_catalog.int8 | 是 | — |
| 10 | clicks | pg_catalog.int8 | 是 | — |
| 11 | spend | pg_catalog.numeric | 是 | — |
| 12 | purchases | pg_catalog.int8 | 是 | — |
| 13 | new_to_brand_purchases | pg_catalog.int8 | 是 | — |
| 14 | sales | pg_catalog.numeric | 是 | — |
| 15 | new_to_brand_sales | pg_catalog.numeric | 是 | — |
| 16 | long_term_sales | pg_catalog.numeric | 是 | — |
| 17 | report_exported_at | pg_catalog.timestamptz | 是 | — |
| 18 | attribution_window_days | pg_catalog.int2 | 是 | — |
| 19 | mature_after | pg_catalog.date | 是 | — |
| 20 | attribution_status | pg_catalog.text | 是 | — |
| 21 | data_source | pg_catalog.text | 是 | — |
| 22 | roas | pg_catalog.numeric | 是 | — |

#### analytics.v_campaign_recent_process（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 是 | — |
| 2 | account_name | pg_catalog.text | 是 | — |
| 3 | ad_product | pg_catalog.text | 是 | — |
| 4 | campaign_id | pg_catalog.text | 是 | — |
| 5 | campaign_name | pg_catalog.text | 是 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | period_start | pg_catalog.date | 是 | — |
| 8 | period_end | pg_catalog.date | 是 | — |
| 9 | impressions | pg_catalog.int8 | 是 | — |
| 10 | clicks | pg_catalog.int8 | 是 | — |
| 11 | spend | pg_catalog.numeric | 是 | — |
| 12 | purchases | pg_catalog.int8 | 是 | — |
| 13 | sales | pg_catalog.numeric | 是 | — |
| 14 | roas | pg_catalog.numeric | 是 | — |
| 15 | decision_scope | pg_catalog.text | 是 | — |

#### analytics.v_campaign_review_due（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | watch_id | pg_catalog.int8 | 是 | — |
| 2 | account_id | pg_catalog.text | 是 | — |
| 3 | ad_product | pg_catalog.text | 是 | — |
| 4 | campaign_id | pg_catalog.text | 是 | — |
| 5 | campaign_name | pg_catalog.text | 是 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | owner_name | pg_catalog.text | 是 | — |
| 8 | priority | pg_catalog.text | 是 | — |
| 9 | watch_reason | pg_catalog.text | 是 | — |
| 10 | target_roas | pg_catalog.numeric | 是 | — |
| 11 | next_review_date | pg_catalog.date | 是 | — |
| 12 | change_id | pg_catalog.int8 | 是 | — |
| 13 | change_type | pg_catalog.text | 是 | — |
| 14 | last_changed_at | pg_catalog.timestamptz | 是 | — |
| 15 | process_review_due | pg_catalog.date | 是 | — |
| 16 | mature_review_due | pg_catalog.date | 是 | — |
| 17 | review_status | pg_catalog.text | 是 | — |
| 18 | due_date | pg_catalog.date | 是 | — |
| 19 | due_reason | pg_catalog.text | 是 | — |
| 20 | recent_period_start | pg_catalog.date | 是 | — |
| 21 | recent_period_end | pg_catalog.date | 是 | — |
| 22 | recent_spend | pg_catalog.numeric | 是 | — |
| 23 | recent_sales | pg_catalog.numeric | 是 | — |
| 24 | recent_roas | pg_catalog.numeric | 是 | — |
| 25 | decision_scope | pg_catalog.text | 是 | — |

#### analytics.v_campaign_tib_latest（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 是 | — |
| 2 | ad_product | pg_catalog.text | 是 | — |
| 3 | campaign_id | pg_catalog.text | 是 | — |
| 4 | campaign_name | pg_catalog.text | 是 | — |
| 5 | product_line | pg_catalog.text | 是 | — |
| 6 | report_start_date | pg_catalog.date | 是 | — |
| 7 | report_end_date | pg_catalog.date | 是 | — |
| 8 | exported_at | pg_catalog.timestamptz | 是 | — |
| 9 | average_time_in_budget | pg_catalog.numeric | 是 | — |
| 10 | budget_amount | pg_catalog.numeric | 是 | — |
| 11 | bidding_strategy | pg_catalog.text | 是 | — |
| 12 | campaign_state | pg_catalog.text | 是 | — |

#### analytics.v_hourly_business_category（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 是 | — |
| 2 | campaign_id | pg_catalog.text | 是 | — |
| 3 | campaign_name | pg_catalog.text | 是 | — |
| 4 | product_line | pg_catalog.text | 是 | — |
| 5 | stat_date | pg_catalog.date | 是 | — |
| 6 | hour | pg_catalog.int2 | 是 | — |
| 7 | ad_product | pg_catalog.text | 是 | — |
| 8 | impressions | pg_catalog.int8 | 是 | — |
| 9 | clicks | pg_catalog.int8 | 是 | — |
| 10 | spend | pg_catalog.numeric | 是 | — |
| 11 | purchases | pg_catalog.int8 | 是 | — |
| 12 | sales | pg_catalog.numeric | 是 | — |
| 13 | attribution_status | pg_catalog.text | 是 | — |
| 14 | attribution_window_days | pg_catalog.int2 | 是 | — |
| 15 | campaign_code | pg_catalog.text | 是 | — |
| 16 | canonical_product_code | pg_catalog.text | 是 | — |
| 17 | business_category_cn | pg_catalog.text | 是 | — |
| 18 | category_source | pg_catalog.text | 是 | — |
| 19 | category_confidence | pg_catalog.text | 是 | — |
| 20 | alias_resolution | pg_catalog.text | 是 | — |

#### analytics.v_import_health（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | batch_id | pg_catalog.int8 | 是 | — |
| 2 | file_name | pg_catalog.text | 是 | — |
| 3 | report_type | pg_catalog.text | 是 | — |
| 4 | report_start_date | pg_catalog.date | 是 | — |
| 5 | report_end_date | pg_catalog.date | 是 | — |
| 6 | exported_at | pg_catalog.timestamptz | 是 | — |
| 7 | export_time_source | pg_catalog.text | 是 | — |
| 8 | imported_at | pg_catalog.timestamptz | 是 | — |
| 9 | source_row_count | pg_catalog.int4 | 是 | — |
| 10 | valid_row_count | pg_catalog.int4 | 是 | — |
| 11 | failed_row_count | pg_catalog.int4 | 是 | — |
| 12 | import_status | pg_catalog.text | 是 | — |
| 13 | error_message | pg_catalog.text | 是 | — |

#### analytics.v_product_category_flat（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 是 | — |
| 2 | canonical_product_code | pg_catalog.text | 是 | — |
| 3 | category_name_cn | pg_catalog.text | 是 | — |
| 4 | category_code | pg_catalog.text | 是 | — |
| 5 | mapping_source | pg_catalog.text | 是 | — |
| 6 | confidence | pg_catalog.text | 是 | — |
| 7 | status | pg_catalog.text | 是 | — |
| 8 | override_reason | pg_catalog.text | 是 | — |
| 9 | row_count | pg_catalog.int8 | 是 | — |
| 10 | is_primary | pg_catalog.bool | 是 | — |
| 11 | evidence_categories | pg_catalog.text | 是 | — |
| 12 | parent_asins | pg_catalog.text | 是 | — |

#### chatgpt_ops.campaign_actions（表）

> 大小 32 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | action_id | pg_catalog.int8 | 否 | — |
| 2 | managed_campaign_id | pg_catalog.int8 | 是 | — |
| 3 | account_id | pg_catalog.text | 否 | — |
| 4 | ad_product | pg_catalog.text | 否 | — |
| 5 | campaign_id | pg_catalog.text | 否 | — |
| 6 | campaign_name | pg_catalog.text | 否 | — |
| 7 | action_type | pg_catalog.text | 否 | — |
| 8 | action_status | pg_catalog.text | 否 | 'proposed'::text |
| 9 | action_at | pg_catalog.timestamptz | 否 | now() |
| 10 | previous_value | pg_catalog.text | 是 | — |
| 11 | new_value | pg_catalog.text | 是 | — |
| 12 | hypothesis | pg_catalog.text | 是 | — |
| 13 | expected_result | pg_catalog.text | 是 | — |
| 14 | rollback_condition | pg_catalog.text | 是 | — |
| 15 | process_review_due | pg_catalog.date | 是 | — |
| 16 | mature_review_due | pg_catalog.date | 是 | — |
| 17 | notes | pg_catalog.text | 是 | — |
| 18 | created_by | pg_catalog.text | 否 | CURRENT_USER |
| 19 | created_at | pg_catalog.timestamptz | 否 | now() |
| 20 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：action_id
- 外键：managed_campaign_id → chatgpt_ops.managed_campaigns.managed_campaign_id
- 索引：campaign_actions_campaign_idx（CREATE INDEX campaign_actions_campaign_idx (managed_campaign_id, action_at DESC)）
- 索引：campaign_actions_review_idx（CREATE INDEX campaign_actions_review_idx (action_status, process_review_due, mature_review_due)）

#### chatgpt_ops.campaign_reviews（表）

> 大小 24 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | review_id | pg_catalog.int8 | 否 | — |
| 2 | managed_campaign_id | pg_catalog.int8 | 是 | — |
| 3 | action_id | pg_catalog.int8 | 是 | — |
| 4 | review_stage | pg_catalog.text | 否 | — |
| 5 | outcome_status | pg_catalog.text | 否 | 'completed'::text |
| 6 | reviewed_at | pg_catalog.timestamptz | 否 | now() |
| 7 | evidence_start_date | pg_catalog.date | 是 | — |
| 8 | evidence_end_date | pg_catalog.date | 是 | — |
| 9 | spend | pg_catalog.numeric | 是 | — |
| 10 | sales | pg_catalog.numeric | 是 | — |
| 11 | roas | pg_catalog.numeric | 是 | — |
| 12 | decision | pg_catalog.text | 否 | — |
| 13 | next_action | pg_catalog.text | 是 | — |
| 14 | next_review_date | pg_catalog.date | 是 | — |
| 15 | notes | pg_catalog.text | 是 | — |
| 16 | created_by | pg_catalog.text | 否 | CURRENT_USER |
| 17 | created_at | pg_catalog.timestamptz | 否 | now() |
| 18 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：review_id
- 外键：action_id → chatgpt_ops.campaign_actions.action_id
- 外键：managed_campaign_id → chatgpt_ops.managed_campaigns.managed_campaign_id
- 索引：campaign_reviews_campaign_idx（CREATE INDEX campaign_reviews_campaign_idx (managed_campaign_id, reviewed_at DESC)）

#### chatgpt_ops.change_audit（表）

> 大小 128 kB，估算行数 48。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | audit_id | pg_catalog.int8 | 否 | — |
| 2 | table_name | pg_catalog.text | 否 | — |
| 3 | record_id | pg_catalog.int8 | 是 | — |
| 4 | operation | pg_catalog.text | 否 | — |
| 5 | old_row | pg_catalog.jsonb | 是 | — |
| 6 | new_row | pg_catalog.jsonb | 是 | — |
| 7 | changed_by | pg_catalog.text | 否 | SESSION_USER |
| 8 | changed_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：audit_id
- 索引：change_audit_record_idx（CREATE INDEX change_audit_record_idx (table_name, record_id, changed_at DESC)）

#### chatgpt_ops.managed_campaigns（表）

> 大小 64 kB，估算行数 10。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | managed_campaign_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | ad_product | pg_catalog.text | 否 | — |
| 4 | campaign_id | pg_catalog.text | 否 | — |
| 5 | campaign_name | pg_catalog.text | 否 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | owner_name | pg_catalog.text | 否 | 'panjinlong'::text |
| 8 | status | pg_catalog.text | 否 | 'active'::text |
| 9 | priority | pg_catalog.text | 否 | 'medium'::text |
| 10 | review_frequency_days | pg_catalog.int4 | 否 | 7 |
| 11 | next_review_date | pg_catalog.date | 否 | — |
| 12 | target_roas | pg_catalog.numeric | 是 | — |
| 13 | watch_reason | pg_catalog.text | 否 | — |
| 14 | notes | pg_catalog.text | 是 | — |
| 15 | created_by | pg_catalog.text | 否 | CURRENT_USER |
| 16 | created_at | pg_catalog.timestamptz | 否 | now() |
| 17 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：managed_campaign_id
- UNIQUE：account_id, ad_product, campaign_id
- 索引：managed_campaigns_review_idx（CREATE INDEX managed_campaigns_review_idx (status, next_review_date, priority)）

#### core.campaign_daily（表）

> 大小 8576 kB，估算行数 18013。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 否 | — |
| 2 | account_name | pg_catalog.text | 是 | — |
| 3 | ad_product | pg_catalog.text | 否 | — |
| 4 | campaign_id | pg_catalog.text | 否 | — |
| 5 | campaign_name | pg_catalog.text | 否 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | stat_date | pg_catalog.date | 否 | — |
| 8 | impressions | pg_catalog.int8 | 否 | 0 |
| 9 | viewable_impressions | pg_catalog.int8 | 否 | 0 |
| 10 | clicks | pg_catalog.int8 | 否 | 0 |
| 11 | spend | pg_catalog.numeric | 否 | 0 |
| 12 | purchases | pg_catalog.int8 | 否 | 0 |
| 13 | new_to_brand_purchases | pg_catalog.int8 | 否 | 0 |
| 14 | sales | pg_catalog.numeric | 否 | 0 |
| 15 | new_to_brand_sales | pg_catalog.numeric | 否 | 0 |
| 16 | long_term_sales | pg_catalog.numeric | 否 | 0 |
| 17 | report_exported_at | pg_catalog.timestamptz | 否 | — |
| 18 | attribution_window_days | pg_catalog.int2 | 否 | — |
| 19 | mature_after | pg_catalog.date | 否 | — |
| 20 | attribution_status | pg_catalog.text | 否 | — |
| 21 | source_batch_id | pg_catalog.int8 | 否 | — |
| 22 | created_at | pg_catalog.timestamptz | 否 | now() |
| 23 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, stat_date
- 外键：source_batch_id → core.import_batches.batch_id
- 索引：campaign_daily_campaign_date_idx（CREATE INDEX campaign_daily_campaign_date_idx (campaign_id, stat_date)）
- 索引：campaign_daily_date_status_idx（CREATE INDEX campaign_daily_date_status_idx (stat_date, attribution_status)）

#### core.campaign_hourly（表）

> 大小 82 MB，估算行数 178345。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 否 | — |
| 2 | account_name | pg_catalog.text | 是 | — |
| 3 | ad_product | pg_catalog.text | 否 | — |
| 4 | campaign_id | pg_catalog.text | 否 | — |
| 5 | campaign_name | pg_catalog.text | 否 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | stat_date | pg_catalog.date | 否 | — |
| 8 | hour | pg_catalog.int2 | 否 | — |
| 9 | impressions | pg_catalog.int8 | 否 | 0 |
| 10 | viewable_impressions | pg_catalog.int8 | 否 | 0 |
| 11 | clicks | pg_catalog.int8 | 否 | 0 |
| 12 | spend | pg_catalog.numeric | 否 | 0 |
| 13 | purchases | pg_catalog.int8 | 否 | 0 |
| 14 | new_to_brand_purchases | pg_catalog.int8 | 否 | 0 |
| 15 | sales | pg_catalog.numeric | 否 | 0 |
| 16 | new_to_brand_sales | pg_catalog.numeric | 否 | 0 |
| 17 | long_term_sales | pg_catalog.numeric | 否 | 0 |
| 18 | report_exported_at | pg_catalog.timestamptz | 否 | — |
| 19 | attribution_window_days | pg_catalog.int2 | 否 | — |
| 20 | mature_after | pg_catalog.date | 否 | — |
| 21 | attribution_status | pg_catalog.text | 否 | — |
| 22 | source_batch_id | pg_catalog.int8 | 否 | — |
| 23 | created_at | pg_catalog.timestamptz | 否 | now() |
| 24 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, stat_date, hour
- 外键：source_batch_id → core.import_batches.batch_id
- 索引：campaign_hourly_campaign_date_idx（CREATE INDEX campaign_hourly_campaign_date_idx (campaign_id, stat_date)）
- 索引：campaign_hourly_date_status_idx（CREATE INDEX campaign_hourly_date_status_idx (stat_date, attribution_status)）

#### core.campaign_product_line_mapping（表）

> 大小 16 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | pg_catalog.text | 否 | — |
| 2 | campaign_id | pg_catalog.text | 否 | — |
| 3 | product_line | pg_catalog.text | 否 | — |
| 4 | mapping_source | pg_catalog.text | 否 | 'manual'::text |
| 5 | active | pg_catalog.bool | 否 | true |
| 6 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：account_id, campaign_id

#### core.campaign_tib_snapshot（表）

> 大小 24 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | snapshot_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | ad_product | pg_catalog.text | 否 | — |
| 4 | campaign_id | pg_catalog.text | 否 | — |
| 5 | campaign_name | pg_catalog.text | 否 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | report_start_date | pg_catalog.date | 否 | — |
| 8 | report_end_date | pg_catalog.date | 否 | — |
| 9 | exported_at | pg_catalog.timestamptz | 否 | — |
| 10 | average_time_in_budget | pg_catalog.numeric | 是 | — |
| 11 | budget_amount | pg_catalog.numeric | 是 | — |
| 12 | bidding_strategy | pg_catalog.text | 是 | — |
| 13 | campaign_state | pg_catalog.text | 是 | — |
| 14 | source_batch_id | pg_catalog.int8 | 否 | — |
| 15 | created_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：snapshot_id
- UNIQUE：account_id, ad_product, campaign_id, report_start_date, report_end_date, exported_at
- 外键：source_batch_id → core.import_batches.batch_id

#### core.import_batches（表）

> 大小 48 kB，估算行数 5。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | batch_id | pg_catalog.int8 | 否 | — |
| 2 | file_name | pg_catalog.text | 否 | — |
| 3 | file_hash | pg_catalog.bpchar | 否 | — |
| 4 | source_path | pg_catalog.text | 否 | — |
| 5 | report_type | pg_catalog.text | 是 | — |
| 6 | report_start_date | pg_catalog.date | 是 | — |
| 7 | report_end_date | pg_catalog.date | 是 | — |
| 8 | exported_at | pg_catalog.timestamptz | 是 | — |
| 9 | export_time_source | pg_catalog.text | 是 | — |
| 10 | imported_at | pg_catalog.timestamptz | 否 | now() |
| 11 | source_row_count | pg_catalog.int4 | 否 | 0 |
| 12 | valid_row_count | pg_catalog.int4 | 否 | 0 |
| 13 | failed_row_count | pg_catalog.int4 | 否 | 0 |
| 14 | import_status | pg_catalog.text | 否 | — |
| 15 | error_message | pg_catalog.text | 是 | — |
| 16 | metadata | pg_catalog.jsonb | 否 | '{}'::jsonb |


约束与索引：

- PRIMARY KEY：batch_id
- UNIQUE：file_hash

#### core.product_alias（表）

> 大小 328 kB，估算行数 226。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | alias_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | alias_source | pg_catalog.text | 否 | — |
| 4 | alias_code | pg_catalog.text | 否 | — |
| 5 | canonical_product_code | pg_catalog.text | 否 | — |
| 6 | resolution_status | pg_catalog.text | 否 | 'resolved'::text |
| 7 | notes | pg_catalog.text | 是 | — |
| 8 | source_file | pg_catalog.text | 是 | — |
| 9 | created_at | pg_catalog.timestamptz | 否 | now() |
| 10 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：alias_id
- UNIQUE：account_id, alias_source, alias_code
- 索引：product_alias_canonical_idx（CREATE INDEX product_alias_canonical_idx (account_id, canonical_product_code)）
- 索引：product_alias_uniq（CREATE UNIQUE INDEX product_alias_uniq (account_id, alias_source, alias_code)）

#### core.product_business_category（表）

> 大小 144 kB，估算行数 110。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | business_category_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | canonical_product_code | pg_catalog.text | 否 | — |
| 4 | category_code | pg_catalog.text | 否 | — |
| 5 | category_name_cn | pg_catalog.text | 否 | — |
| 6 | mapping_source | pg_catalog.text | 否 | — |
| 7 | confidence | pg_catalog.text | 否 | — |
| 8 | status | pg_catalog.text | 否 | 'active'::text |
| 9 | override_reason | pg_catalog.text | 是 | — |
| 10 | row_count | pg_catalog.int8 | 否 | — |
| 11 | is_primary | pg_catalog.bool | 否 | true |
| 12 | source_file | pg_catalog.text | 是 | — |
| 13 | created_at | pg_catalog.timestamptz | 否 | now() |
| 14 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：business_category_id
- UNIQUE：account_id, canonical_product_code
- 索引：product_business_category_primary_idx（CREATE UNIQUE INDEX product_business_category_primary_idx (account_id, canonical_product_code) WHERE is_primary）
- 索引：product_business_category_uniq（CREATE UNIQUE INDEX product_business_category_uniq (account_id, canonical_product_code)）

#### core.product_category_evidence（表）

> 大小 352 kB，估算行数 390。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | evidence_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | canonical_product_code | pg_catalog.text | 否 | — |
| 4 | category_name | pg_catalog.text | 否 | — |
| 5 | category_code | pg_catalog.text | 否 | — |
| 6 | category_name_cn | pg_catalog.text | 否 | — |
| 7 | row_count | pg_catalog.int8 | 否 | — |
| 8 | source_file | pg_catalog.text | 否 | — |
| 9 | created_at | pg_catalog.timestamptz | 否 | now() |
| 10 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：evidence_id
- UNIQUE：account_id, canonical_product_code, category_name
- 索引：product_category_evidence_cat_idx（CREATE INDEX product_category_evidence_cat_idx (account_id, category_name)）
- 索引：product_category_evidence_uniq（CREATE UNIQUE INDEX product_category_evidence_uniq (account_id, canonical_product_code, category_name)）

#### core.product_category_mapping（表）

> 大小 576 kB，估算行数 395。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | mapping_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | product_code | pg_catalog.text | 否 | — |
| 4 | parent_asin | pg_catalog.text | 是 | — |
| 5 | category_name | pg_catalog.text | 是 | — |
| 6 | category_name_cn | pg_catalog.text | 是 | — |
| 7 | source_file | pg_catalog.text | 是 | — |
| 8 | created_at | pg_catalog.timestamptz | 否 | now() |
| 9 | updated_at | pg_catalog.timestamptz | 否 | now() |
| 10 | row_count | pg_catalog.int8 | 是 | — |
| 11 | is_primary | pg_catalog.bool | 否 | false |


约束与索引：

- PRIMARY KEY：mapping_id
- 索引：product_category_mapping_category_idx（CREATE INDEX product_category_mapping_category_idx (account_id, category_name)）
- 索引：product_category_mapping_cn_idx（CREATE INDEX product_category_mapping_cn_idx (account_id, category_name_cn)）
- 索引：product_category_mapping_uniq（CREATE UNIQUE INDEX product_category_mapping_uniq (account_id, product_code, COALESCE(parent_asin, ''::text), COALESCE(category_name, ''::text))）

#### core.product_category_mapping_bak_20260813（表）

> 大小 136 kB，估算行数 401。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | mapping_id | pg_catalog.int8 | 是 | — |
| 2 | account_id | pg_catalog.text | 是 | — |
| 3 | product_code | pg_catalog.text | 是 | — |
| 4 | parent_asin | pg_catalog.text | 是 | — |
| 5 | category_name | pg_catalog.text | 是 | — |
| 6 | category_name_cn | pg_catalog.text | 是 | — |
| 7 | source_file | pg_catalog.text | 是 | — |
| 8 | created_at | pg_catalog.timestamptz | 是 | — |
| 9 | updated_at | pg_catalog.timestamptz | 是 | — |
| 10 | row_count | pg_catalog.int8 | 是 | — |
| 11 | is_primary | pg_catalog.bool | 是 | — |

#### core.product_parent_asin（表）

> 大小 144 kB，估算行数 105。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | product_asin_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | canonical_product_code | pg_catalog.text | 否 | — |
| 4 | parent_asin | pg_catalog.text | 否 | — |
| 5 | source_file | pg_catalog.text | 否 | — |
| 6 | created_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：product_asin_id
- UNIQUE：account_id, canonical_product_code, parent_asin
- 索引：product_parent_asin_code_idx（CREATE INDEX product_parent_asin_code_idx (account_id, canonical_product_code)）
- 索引：product_parent_asin_uniq（CREATE UNIQUE INDEX product_parent_asin_uniq (account_id, canonical_product_code, parent_asin)）

#### ops.campaign_change_log（表）

> 大小 24 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | change_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | ad_product | pg_catalog.text | 否 | — |
| 4 | campaign_id | pg_catalog.text | 否 | — |
| 5 | campaign_name | pg_catalog.text | 否 | — |
| 6 | changed_at | pg_catalog.timestamptz | 否 | now() |
| 7 | change_type | pg_catalog.text | 否 | — |
| 8 | previous_value | pg_catalog.text | 是 | — |
| 9 | new_value | pg_catalog.text | 是 | — |
| 10 | hypothesis | pg_catalog.text | 是 | — |
| 11 | expected_result | pg_catalog.text | 是 | — |
| 12 | rollback_condition | pg_catalog.text | 是 | — |
| 13 | process_review_due | pg_catalog.date | 否 | — |
| 14 | mature_review_due | pg_catalog.date | 否 | — |
| 15 | review_status | pg_catalog.text | 否 | 'pending'::text |
| 16 | created_by | pg_catalog.text | 否 | CURRENT_USER |
| 17 | notes | pg_catalog.text | 是 | — |


约束与索引：

- PRIMARY KEY：change_id
- 索引：campaign_change_review_due_idx（CREATE INDEX campaign_change_review_due_idx (review_status, process_review_due, mature_review_due)）

#### ops.campaign_review_log（表）

> 大小 16 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | review_id | pg_catalog.int8 | 否 | — |
| 2 | watch_id | pg_catalog.int8 | 是 | — |
| 3 | change_id | pg_catalog.int8 | 是 | — |
| 4 | reviewed_at | pg_catalog.timestamptz | 否 | now() |
| 5 | review_stage | pg_catalog.text | 否 | — |
| 6 | decision | pg_catalog.text | 否 | — |
| 7 | evidence_start_date | pg_catalog.date | 是 | — |
| 8 | evidence_end_date | pg_catalog.date | 是 | — |
| 9 | spend | pg_catalog.numeric | 是 | — |
| 10 | sales | pg_catalog.numeric | 是 | — |
| 11 | roas | pg_catalog.numeric | 是 | — |
| 12 | next_action | pg_catalog.text | 是 | — |
| 13 | next_review_date | pg_catalog.date | 是 | — |
| 14 | reviewed_by | pg_catalog.text | 否 | — |
| 15 | notes | pg_catalog.text | 是 | — |


约束与索引：

- PRIMARY KEY：review_id
- 外键：change_id → ops.campaign_change_log.change_id
- 外键：watch_id → ops.campaign_watchlist.watch_id

#### ops.campaign_watchlist（表）

> 大小 24 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | watch_id | pg_catalog.int8 | 否 | — |
| 2 | account_id | pg_catalog.text | 否 | — |
| 3 | ad_product | pg_catalog.text | 否 | — |
| 4 | campaign_id | pg_catalog.text | 否 | — |
| 5 | campaign_name | pg_catalog.text | 否 | — |
| 6 | product_line | pg_catalog.text | 是 | — |
| 7 | owner_name | pg_catalog.text | 否 | — |
| 8 | status | pg_catalog.text | 否 | 'active'::text |
| 9 | priority | pg_catalog.text | 否 | 'medium'::text |
| 10 | review_frequency_days | pg_catalog.int4 | 否 | 7 |
| 11 | next_review_date | pg_catalog.date | 否 | — |
| 12 | target_roas | pg_catalog.numeric | 是 | — |
| 13 | watch_reason | pg_catalog.text | 否 | — |
| 14 | notes | pg_catalog.text | 是 | — |
| 15 | created_at | pg_catalog.timestamptz | 否 | now() |
| 16 | updated_at | pg_catalog.timestamptz | 否 | now() |


约束与索引：

- PRIMARY KEY：watch_id
- UNIQUE：account_id, ad_product, campaign_id

### 5. 权限角色

| 角色 | 可登录 | 超管 | 继承 |
|------|--------|------|------|
| DBA_YE | True | False | True |
| ads_ingest | True | False | True |
| ads_operator | True | False | True |
| alicloud_rds_admin | True | True | True |
| amazon_ads_admin | True | False | True |
| anon | False | False | True |
| aurora | True | True | True |
| authenticated | False | False | True |
| authenticator | True | False | False |
| blazesql_reader | True | False | True |
| chatgpt_operator | False | False | True |
| codex_reader | True | False | True |
| dashboard_user | False | False | True |
| postgres | True | False | True |
| replicator | True | True | True |
| service_role | False | False | True |
| supabase_admin | True | False | True |
| supabase_auth_admin | True | False | False |
| supabase_functions_admin | True | False | False |
| supabase_read_only_user | True | False | True |
| supabase_realtime_admin | False | False | False |
| supabase_replication_admin | True | False | True |
| supabase_storage_admin | True | False | False |

> [!note] 角色约定（来自《亚马逊TIB与广告报告数据沉淀方案》）
> `ads_ingest` 负责报表入库；`ads_analyst` 只读分析（BlazeSQL 问答/看板）；`ads_operator` 运营写入；`amazon_ads_admin` 为结构管理员。

## 关联

- [[阿里云RDS-amazon_ads_v2-库表结构]]（现行主库）
- [[亚马逊TIB与广告报告数据沉淀方案]]

## 来源

- 阿里云 RDS 实例 amazon_ads 库现场查询（2026-08-13，psql 直连导出）
- pgAdmin 4 本地保存的连接「阿里云 RDS - amazon_ads」
- amazon-ads-data 项目 config.toml / src/amazon_ads_data/db.py
