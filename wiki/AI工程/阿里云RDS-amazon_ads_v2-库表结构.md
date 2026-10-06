---
tags: [AI工程, 数据库, 亚马逊广告]
date: 2026-09-21
status: 现行
---

# 阿里云RDS-amazon_ads_v2-库表结构

> [!summary] 摘要
> 现行主库 `amazon_ads_v2`（**腾讯云服务器自建 PostgreSQL 18.6**，服务器 `193.112.27.91`，
> 数据库只监听服务器本地；本机经常驻 SSH 隧道 `127.0.0.1:15432` → `127.0.0.1:5432` 访问）的完整结构快照：
> 3 个 Schema（core / stg / public）、19 张表 + 2 个视图的字段/主键/唯一约束/索引。
> 本页的**结构信息仍然有效**；连接地址已于 2026-09-30 随迁移更新，见下方警告块。

> [!warning] 连接地址已迁移（2026-09-30，阿里云 → 腾讯云）
> 数据库已从阿里云 RDS **全量迁移到腾讯云服务器自建 PostgreSQL**：
> - 现行连接：`127.0.0.1:15432`（本机 SSH 隧道）→ 服务器 `127.0.0.1:5432`，`sslmode=disable`（外层 SSH 已加密）
> - 阿里云地址 `pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com:5432` **已停止写入**，不要再连
> - 更早的 `121.41.134.56`（域名 `pgm-bp18chyrycgz5q42zo...`，库 `amazon_ads`）早已整机退役，见 [[阿里云RDS-amazon_ads-库表结构]]（status=已归档）
> - 隧道常驻服务 `com.panjinlong.agent-server-db-tunnel`；只读/导入密码见 `database-role-credentials.json`
> - 完整迁移说明：`~/DatabaseBackups/aliyun-final-2026-09-30/腾讯云服务器数据库联通教程.md`

## 核心知识

### 1. 实例与连接信息

| 项目 | 值 |
|------|-----|
| 部署形态 | 腾讯云服务器自建 PostgreSQL（服务器 `193.112.27.91`，2026-09-30 由阿里云 RDS 迁入） |
| 本机连接地址 | `127.0.0.1:15432`（SSH 隧道入口）→ 服务器 `127.0.0.1:5432` |
| 端口 / 版本 | 15432（本机隧道）/ PostgreSQL 18.6 |
| 现行库 | amazon_ads_v2（数据仓库） |
| 应用库 | amazon_ads（RBAC / 主数据，iam.* + app.*） |
| SSL | `sslmode=disable`（外层 SSH 隧道已加密；旧阿里云 CA 已作废） |
| 账号 | 只读 `ads_readonly` / 导入 `ads_ingest` / 管理 `amazon_ads_admin` |
| 密码位置 | `~/DatabaseBackups/aliyun-final-2026-09-30/database-role-credentials.json`（权限 600） |
| 隧道服务 | `com.panjinlong.agent-server-db-tunnel`（launchd 常驻） |
| 服务器时区 | Asia/Shanghai |

> [!note] 双库分治
> PG 不支持跨库 JOIN，因此**应用层与数据层分库**：`amazon_ads` 放 IAM 与主数据（`iam.roles/users/user_sessions`、
> `app.product_roster`、`app.operator_name_map`、`app.product_mapping`、`app.child_asin_mapping`）；
> `amazon_ads_v2` 放全部事实数据（本页描述的就是它）。

> [!warning] mac 端连接姿势（2026-09-30 更新：已迁腾讯云）
> `.env` 里是 `postgresql+asyncpg://...` 的 SQLAlchemy URL，**psql 不能直接吃**（会报 `invalid connection option`）。
> 正确做法：拆成 `PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE` 环境变量再调 psql，或用 `ba-export/load_local.py` / `ads-email-import/_db.py` 里的解析逻辑。
> **现行参数**：`PGHOST=127.0.0.1`、`PGPORT=15432`（SSH 隧道）、`PGSSLMODE=disable`。
> 隧道没起来会表现为 `connection refused` / timeout，先跑
> `launchctl kickstart -k gui/$(id -u)/com.panjinlong.agent-server-db-tunnel`。

### 2. Schema 职责

| Schema | 职责 |
|--------|------|
| core | 全部事实数据：ODS 广告日报、事实层「一份报告一张表」、BA 周/月绩效、导入批次 |
| stg | 装载临时区（`stg.load_tmp`，COPY 中转用） |
| public | 系统默认，无业务对象 |

### 3. 对象总览

| 对象 | 类型 | 大小 | 估算行数 |
|------|------|------|----------|
| `core.ad_daily` | 分区父表 | 0 bytes | 0 |
| `core.ad_daily_2026_08` | 表 | 88 MB | 53,650 |
| `core.ad_daily_2026_09` | 表 | 60 MB | 36,151 |
| `core.ad_daily_2026_10` | 表 | 40 kB | 0 |
| `core.ad_daily_2026_11` | 表 | 40 kB | 0 |
| `core.ad_daily_default` | 表 | 40 kB | 0 |
| `core.business_report_parent_asin_period` | 视图 | 0 bytes | 0 |
| `core.import_batches` | 表 | 400 kB | 349 |
| `core.report_advertised_product_daily` | 表 | 173 MB | 198,450 |
| `core.report_business_child_asin_daily` | 表 | 207 MB | 342,859 |
| `core.report_business_parent_asin_period` | 表 | 1368 kB | 2,449 |
| `core.report_campaign_daily` | 表 | 7272 kB | 10,158 |
| `core.report_placement_daily` | 表 | 27 MB | 32,840 |
| `core.report_purchased_product_daily` | 表 | 103 MB | 106,305 |
| `core.report_search_term_daily` | 表 | 362 MB | 402,879 |
| `core.report_targeting_daily` | 表 | 173 MB | 198,672 |
| `core.search_query_performance_monthly` | 表 | 29 MB | 50,999 |
| `core.search_query_performance_weekly` | 表 | 45 MB | 78,000 |
| `core.search_term_daily` | 表 | 70 MB | 102,761 |
| `core.search_term_target_period` | 表 | 5835 MB | 4,455,019 |
| `core.v_business_parent_from_child_daily` | 视图 | 0 bytes | 0 |
| `stg.load_tmp` | 表 | 42 MB | 102,761 |

> [!info] 分区表
> `core.ad_daily` 是**声明式分区父表**（本身 0 行），实际数据在 `ad_daily_2026_08` / `_2026_09` / `_2026_10` / `_2026_11` / `_default` 各月分区。
> 查数直接查父表即可（自动分区裁剪）。

> [!warning] BA 报告只来了一半
> 对象总览里只有 `search_query_performance_weekly` / `_monthly`（**SQP，按搜索词**）。
> BA 的另一半 **SCP（搜索目录绩效，按 ASIN）在本库没有表**，旧库退役后彻底悬空。
> 两者的口径差别与复活步骤见 [[Amazon-Brand-Analytics-SQP与SCP-口径与现状]]。

### 4. 表与视图结构

#### core.ad_daily（分区父表）

> 大小 0 bytes，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | global_campaign_id | text | 是 | — |
| 11 | ad_group_id | text | 否 | ''::text |
| 12 | ad_group_name | text | 是 | — |
| 13 | stat_date | date | 否 | — |
| 14 | budget_currency | text | 是 | — |
| 15 | data_level | text | 否 | — |
| 16 | grain_level | text | 否 | — |
| 17 | dimension_key | text | 否 | — |
| 18 | placement | text | 是 | — |
| 19 | target_id | text | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | target_text | text | 是 | — |
| 21 | target_match_type | text | 是 | — |
| 22 | target_bid | numeric | 是 | — |
| 23 | target_type | text | 是 | — |
| 24 | target_status | text | 是 | — |
| 25 | advertised_product_id | text | 是 | — |
| 26 | advertised_product_name | text | 是 | — |
| 27 | advertised_product_parent_id | text | 是 | — |
| 28 | advertised_product_brand | text | 是 | — |
| 29 | advertised_product_category | text | 是 | — |
| 3 | manager_account | text | 是 | — |
| 30 | advertised_product_subcategory | text | 是 | — |
| 31 | advertised_product_group | text | 是 | — |
| 32 | advertised_product_sku | text | 是 | — |
| 33 | advertised_product_marketplace | text | 是 | — |
| 34 | purchased_product_id | text | 是 | — |
| 35 | purchased_product_name | text | 是 | — |
| 36 | purchased_product_marketplace | text | 是 | — |
| 37 | impressions | bigint | 是 | — |
| 38 | viewable_impressions | bigint | 是 | — |
| 39 | clicks | bigint | 是 | — |
| 4 | ad_product | text | 否 | ''::text |
| 40 | spend | numeric | 是 | — |
| 41 | purchases | bigint | 是 | — |
| 42 | sales | numeric | 是 | — |
| 43 | units | bigint | 是 | — |
| 44 | promoted_purchases | bigint | 是 | — |
| 45 | promoted_sales | numeric | 是 | — |
| 46 | promoted_units | bigint | 是 | — |
| 47 | halo_purchases | bigint | 是 | — |
| 48 | halo_sales | numeric | 是 | — |
| 49 | halo_units | bigint | 是 | — |
| 5 | portfolio_id | text | 是 | — |
| 50 | new_to_brand_purchases | bigint | 是 | — |
| 51 | new_to_brand_sales | numeric | 是 | — |
| 52 | new_to_brand_units | bigint | 是 | — |
| 53 | long_term_sales | numeric | 是 | — |
| 54 | detail_page_views | bigint | 是 | — |
| 55 | ctr_pct | numeric | 是 | — |
| 56 | vctr_pct | numeric | 是 | — |
| 57 | cpc | numeric | 是 | — |
| 58 | cvr_pct | numeric | 是 | — |
| 59 | cpa | numeric | 是 | — |
| 6 | portfolio_name | text | 是 | — |
| 60 | acos_pct | numeric | 是 | — |
| 61 | roas | numeric | 是 | — |
| 62 | promoted_cpa | numeric | 是 | — |
| 63 | promoted_cvr_pct | numeric | 是 | — |
| 64 | promoted_acos_pct | numeric | 是 | — |
| 65 | promoted_roas | numeric | 是 | — |
| 66 | new_to_brand_cpa | numeric | 是 | — |
| 67 | new_to_brand_cvr_pct | numeric | 是 | — |
| 68 | new_to_brand_acos_pct | numeric | 是 | — |
| 69 | new_to_brand_roas | numeric | 是 | — |
| 7 | campaign_id | text | 否 | — |
| 70 | long_term_roas | numeric | 是 | — |
| 71 | cost_per_detail_page_view | numeric | 是 | — |
| 72 | detail_page_view_rate_pct | numeric | 是 | — |
| 73 | row_hash | character | 否 | — |
| 74 | batch_id | bigint | 是 | — |
| 75 | source_file_name | text | 是 | — |
| 76 | source_file_hash | character | 是 | — |
| 77 | first_imported_at | timestamp with time zone | 否 | now() |
| 78 | updated_at | timestamp with time zone | 否 | now() |
| 8 | campaign_name | text | 是 | — |
| 9 | campaign_state | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, data_level, grain_level, campaign_id, ad_group_id, stat_date, dimension_key（ad_daily_pkey）
- 索引：idx_ad_daily_camp（CREATE INDEX idx_ad_daily_camp ON ONLY core.ad_daily USING btree (account_id, campaign_id, stat_date)）
- 索引：idx_ad_daily_main（CREATE INDEX idx_ad_daily_main ON ONLY core.ad_daily USING btree (account_id, data_level, stat_date, campaign_id)）
- 索引：idx_ad_daily_prod（CREATE INDEX idx_ad_daily_prod ON ONLY core.ad_daily USING btree (account_id, advertised_product_id)）

#### core.ad_daily_2026_08（表）

> 大小 88 MB，估算行数 53,650。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | global_campaign_id | text | 是 | — |
| 11 | ad_group_id | text | 否 | ''::text |
| 12 | ad_group_name | text | 是 | — |
| 13 | stat_date | date | 否 | — |
| 14 | budget_currency | text | 是 | — |
| 15 | data_level | text | 否 | — |
| 16 | grain_level | text | 否 | — |
| 17 | dimension_key | text | 否 | — |
| 18 | placement | text | 是 | — |
| 19 | target_id | text | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | target_text | text | 是 | — |
| 21 | target_match_type | text | 是 | — |
| 22 | target_bid | numeric | 是 | — |
| 23 | target_type | text | 是 | — |
| 24 | target_status | text | 是 | — |
| 25 | advertised_product_id | text | 是 | — |
| 26 | advertised_product_name | text | 是 | — |
| 27 | advertised_product_parent_id | text | 是 | — |
| 28 | advertised_product_brand | text | 是 | — |
| 29 | advertised_product_category | text | 是 | — |
| 3 | manager_account | text | 是 | — |
| 30 | advertised_product_subcategory | text | 是 | — |
| 31 | advertised_product_group | text | 是 | — |
| 32 | advertised_product_sku | text | 是 | — |
| 33 | advertised_product_marketplace | text | 是 | — |
| 34 | purchased_product_id | text | 是 | — |
| 35 | purchased_product_name | text | 是 | — |
| 36 | purchased_product_marketplace | text | 是 | — |
| 37 | impressions | bigint | 是 | — |
| 38 | viewable_impressions | bigint | 是 | — |
| 39 | clicks | bigint | 是 | — |
| 4 | ad_product | text | 否 | ''::text |
| 40 | spend | numeric | 是 | — |
| 41 | purchases | bigint | 是 | — |
| 42 | sales | numeric | 是 | — |
| 43 | units | bigint | 是 | — |
| 44 | promoted_purchases | bigint | 是 | — |
| 45 | promoted_sales | numeric | 是 | — |
| 46 | promoted_units | bigint | 是 | — |
| 47 | halo_purchases | bigint | 是 | — |
| 48 | halo_sales | numeric | 是 | — |
| 49 | halo_units | bigint | 是 | — |
| 5 | portfolio_id | text | 是 | — |
| 50 | new_to_brand_purchases | bigint | 是 | — |
| 51 | new_to_brand_sales | numeric | 是 | — |
| 52 | new_to_brand_units | bigint | 是 | — |
| 53 | long_term_sales | numeric | 是 | — |
| 54 | detail_page_views | bigint | 是 | — |
| 55 | ctr_pct | numeric | 是 | — |
| 56 | vctr_pct | numeric | 是 | — |
| 57 | cpc | numeric | 是 | — |
| 58 | cvr_pct | numeric | 是 | — |
| 59 | cpa | numeric | 是 | — |
| 6 | portfolio_name | text | 是 | — |
| 60 | acos_pct | numeric | 是 | — |
| 61 | roas | numeric | 是 | — |
| 62 | promoted_cpa | numeric | 是 | — |
| 63 | promoted_cvr_pct | numeric | 是 | — |
| 64 | promoted_acos_pct | numeric | 是 | — |
| 65 | promoted_roas | numeric | 是 | — |
| 66 | new_to_brand_cpa | numeric | 是 | — |
| 67 | new_to_brand_cvr_pct | numeric | 是 | — |
| 68 | new_to_brand_acos_pct | numeric | 是 | — |
| 69 | new_to_brand_roas | numeric | 是 | — |
| 7 | campaign_id | text | 否 | — |
| 70 | long_term_roas | numeric | 是 | — |
| 71 | cost_per_detail_page_view | numeric | 是 | — |
| 72 | detail_page_view_rate_pct | numeric | 是 | — |
| 73 | row_hash | character | 否 | — |
| 74 | batch_id | bigint | 是 | — |
| 75 | source_file_name | text | 是 | — |
| 76 | source_file_hash | character | 是 | — |
| 77 | first_imported_at | timestamp with time zone | 否 | now() |
| 78 | updated_at | timestamp with time zone | 否 | now() |
| 8 | campaign_name | text | 是 | — |
| 9 | campaign_state | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, data_level, grain_level, campaign_id, ad_group_id, stat_date, dimension_key（ad_daily_2026_08_pkey）
- 索引：ad_daily_2026_08_account_id_advertised_product_id_idx（CREATE INDEX ad_daily_2026_08_account_id_advertised_product_id_idx ON core.ad_daily_2026_08 USING btree (account_id, advertised_product_id)）
- 索引：ad_daily_2026_08_account_id_campaign_id_stat_date_idx（CREATE INDEX ad_daily_2026_08_account_id_campaign_id_stat_date_idx ON core.ad_daily_2026_08 USING btree (account_id, campaign_id, stat_date)）
- 索引：ad_daily_2026_08_account_id_data_level_stat_date_campaign_i_idx（CREATE INDEX ad_daily_2026_08_account_id_data_level_stat_date_campaign_i_idx ON core.ad_daily_2026_08 USING btree (account_id, data_level, stat_date, campaign_id)）

#### core.ad_daily_2026_09（表）

> 大小 60 MB，估算行数 36,151。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | global_campaign_id | text | 是 | — |
| 11 | ad_group_id | text | 否 | ''::text |
| 12 | ad_group_name | text | 是 | — |
| 13 | stat_date | date | 否 | — |
| 14 | budget_currency | text | 是 | — |
| 15 | data_level | text | 否 | — |
| 16 | grain_level | text | 否 | — |
| 17 | dimension_key | text | 否 | — |
| 18 | placement | text | 是 | — |
| 19 | target_id | text | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | target_text | text | 是 | — |
| 21 | target_match_type | text | 是 | — |
| 22 | target_bid | numeric | 是 | — |
| 23 | target_type | text | 是 | — |
| 24 | target_status | text | 是 | — |
| 25 | advertised_product_id | text | 是 | — |
| 26 | advertised_product_name | text | 是 | — |
| 27 | advertised_product_parent_id | text | 是 | — |
| 28 | advertised_product_brand | text | 是 | — |
| 29 | advertised_product_category | text | 是 | — |
| 3 | manager_account | text | 是 | — |
| 30 | advertised_product_subcategory | text | 是 | — |
| 31 | advertised_product_group | text | 是 | — |
| 32 | advertised_product_sku | text | 是 | — |
| 33 | advertised_product_marketplace | text | 是 | — |
| 34 | purchased_product_id | text | 是 | — |
| 35 | purchased_product_name | text | 是 | — |
| 36 | purchased_product_marketplace | text | 是 | — |
| 37 | impressions | bigint | 是 | — |
| 38 | viewable_impressions | bigint | 是 | — |
| 39 | clicks | bigint | 是 | — |
| 4 | ad_product | text | 否 | ''::text |
| 40 | spend | numeric | 是 | — |
| 41 | purchases | bigint | 是 | — |
| 42 | sales | numeric | 是 | — |
| 43 | units | bigint | 是 | — |
| 44 | promoted_purchases | bigint | 是 | — |
| 45 | promoted_sales | numeric | 是 | — |
| 46 | promoted_units | bigint | 是 | — |
| 47 | halo_purchases | bigint | 是 | — |
| 48 | halo_sales | numeric | 是 | — |
| 49 | halo_units | bigint | 是 | — |
| 5 | portfolio_id | text | 是 | — |
| 50 | new_to_brand_purchases | bigint | 是 | — |
| 51 | new_to_brand_sales | numeric | 是 | — |
| 52 | new_to_brand_units | bigint | 是 | — |
| 53 | long_term_sales | numeric | 是 | — |
| 54 | detail_page_views | bigint | 是 | — |
| 55 | ctr_pct | numeric | 是 | — |
| 56 | vctr_pct | numeric | 是 | — |
| 57 | cpc | numeric | 是 | — |
| 58 | cvr_pct | numeric | 是 | — |
| 59 | cpa | numeric | 是 | — |
| 6 | portfolio_name | text | 是 | — |
| 60 | acos_pct | numeric | 是 | — |
| 61 | roas | numeric | 是 | — |
| 62 | promoted_cpa | numeric | 是 | — |
| 63 | promoted_cvr_pct | numeric | 是 | — |
| 64 | promoted_acos_pct | numeric | 是 | — |
| 65 | promoted_roas | numeric | 是 | — |
| 66 | new_to_brand_cpa | numeric | 是 | — |
| 67 | new_to_brand_cvr_pct | numeric | 是 | — |
| 68 | new_to_brand_acos_pct | numeric | 是 | — |
| 69 | new_to_brand_roas | numeric | 是 | — |
| 7 | campaign_id | text | 否 | — |
| 70 | long_term_roas | numeric | 是 | — |
| 71 | cost_per_detail_page_view | numeric | 是 | — |
| 72 | detail_page_view_rate_pct | numeric | 是 | — |
| 73 | row_hash | character | 否 | — |
| 74 | batch_id | bigint | 是 | — |
| 75 | source_file_name | text | 是 | — |
| 76 | source_file_hash | character | 是 | — |
| 77 | first_imported_at | timestamp with time zone | 否 | now() |
| 78 | updated_at | timestamp with time zone | 否 | now() |
| 8 | campaign_name | text | 是 | — |
| 9 | campaign_state | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, data_level, grain_level, campaign_id, ad_group_id, stat_date, dimension_key（ad_daily_2026_09_pkey）
- 索引：ad_daily_2026_09_account_id_advertised_product_id_idx（CREATE INDEX ad_daily_2026_09_account_id_advertised_product_id_idx ON core.ad_daily_2026_09 USING btree (account_id, advertised_product_id)）
- 索引：ad_daily_2026_09_account_id_campaign_id_stat_date_idx（CREATE INDEX ad_daily_2026_09_account_id_campaign_id_stat_date_idx ON core.ad_daily_2026_09 USING btree (account_id, campaign_id, stat_date)）
- 索引：ad_daily_2026_09_account_id_data_level_stat_date_campaign_i_idx（CREATE INDEX ad_daily_2026_09_account_id_data_level_stat_date_campaign_i_idx ON core.ad_daily_2026_09 USING btree (account_id, data_level, stat_date, campaign_id)）

#### core.ad_daily_2026_10（表）

> 大小 40 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | global_campaign_id | text | 是 | — |
| 11 | ad_group_id | text | 否 | ''::text |
| 12 | ad_group_name | text | 是 | — |
| 13 | stat_date | date | 否 | — |
| 14 | budget_currency | text | 是 | — |
| 15 | data_level | text | 否 | — |
| 16 | grain_level | text | 否 | — |
| 17 | dimension_key | text | 否 | — |
| 18 | placement | text | 是 | — |
| 19 | target_id | text | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | target_text | text | 是 | — |
| 21 | target_match_type | text | 是 | — |
| 22 | target_bid | numeric | 是 | — |
| 23 | target_type | text | 是 | — |
| 24 | target_status | text | 是 | — |
| 25 | advertised_product_id | text | 是 | — |
| 26 | advertised_product_name | text | 是 | — |
| 27 | advertised_product_parent_id | text | 是 | — |
| 28 | advertised_product_brand | text | 是 | — |
| 29 | advertised_product_category | text | 是 | — |
| 3 | manager_account | text | 是 | — |
| 30 | advertised_product_subcategory | text | 是 | — |
| 31 | advertised_product_group | text | 是 | — |
| 32 | advertised_product_sku | text | 是 | — |
| 33 | advertised_product_marketplace | text | 是 | — |
| 34 | purchased_product_id | text | 是 | — |
| 35 | purchased_product_name | text | 是 | — |
| 36 | purchased_product_marketplace | text | 是 | — |
| 37 | impressions | bigint | 是 | — |
| 38 | viewable_impressions | bigint | 是 | — |
| 39 | clicks | bigint | 是 | — |
| 4 | ad_product | text | 否 | ''::text |
| 40 | spend | numeric | 是 | — |
| 41 | purchases | bigint | 是 | — |
| 42 | sales | numeric | 是 | — |
| 43 | units | bigint | 是 | — |
| 44 | promoted_purchases | bigint | 是 | — |
| 45 | promoted_sales | numeric | 是 | — |
| 46 | promoted_units | bigint | 是 | — |
| 47 | halo_purchases | bigint | 是 | — |
| 48 | halo_sales | numeric | 是 | — |
| 49 | halo_units | bigint | 是 | — |
| 5 | portfolio_id | text | 是 | — |
| 50 | new_to_brand_purchases | bigint | 是 | — |
| 51 | new_to_brand_sales | numeric | 是 | — |
| 52 | new_to_brand_units | bigint | 是 | — |
| 53 | long_term_sales | numeric | 是 | — |
| 54 | detail_page_views | bigint | 是 | — |
| 55 | ctr_pct | numeric | 是 | — |
| 56 | vctr_pct | numeric | 是 | — |
| 57 | cpc | numeric | 是 | — |
| 58 | cvr_pct | numeric | 是 | — |
| 59 | cpa | numeric | 是 | — |
| 6 | portfolio_name | text | 是 | — |
| 60 | acos_pct | numeric | 是 | — |
| 61 | roas | numeric | 是 | — |
| 62 | promoted_cpa | numeric | 是 | — |
| 63 | promoted_cvr_pct | numeric | 是 | — |
| 64 | promoted_acos_pct | numeric | 是 | — |
| 65 | promoted_roas | numeric | 是 | — |
| 66 | new_to_brand_cpa | numeric | 是 | — |
| 67 | new_to_brand_cvr_pct | numeric | 是 | — |
| 68 | new_to_brand_acos_pct | numeric | 是 | — |
| 69 | new_to_brand_roas | numeric | 是 | — |
| 7 | campaign_id | text | 否 | — |
| 70 | long_term_roas | numeric | 是 | — |
| 71 | cost_per_detail_page_view | numeric | 是 | — |
| 72 | detail_page_view_rate_pct | numeric | 是 | — |
| 73 | row_hash | character | 否 | — |
| 74 | batch_id | bigint | 是 | — |
| 75 | source_file_name | text | 是 | — |
| 76 | source_file_hash | character | 是 | — |
| 77 | first_imported_at | timestamp with time zone | 否 | now() |
| 78 | updated_at | timestamp with time zone | 否 | now() |
| 8 | campaign_name | text | 是 | — |
| 9 | campaign_state | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, data_level, grain_level, campaign_id, ad_group_id, stat_date, dimension_key（ad_daily_2026_10_pkey）
- 索引：ad_daily_2026_10_account_id_advertised_product_id_idx（CREATE INDEX ad_daily_2026_10_account_id_advertised_product_id_idx ON core.ad_daily_2026_10 USING btree (account_id, advertised_product_id)）
- 索引：ad_daily_2026_10_account_id_campaign_id_stat_date_idx（CREATE INDEX ad_daily_2026_10_account_id_campaign_id_stat_date_idx ON core.ad_daily_2026_10 USING btree (account_id, campaign_id, stat_date)）
- 索引：ad_daily_2026_10_account_id_data_level_stat_date_campaign_i_idx（CREATE INDEX ad_daily_2026_10_account_id_data_level_stat_date_campaign_i_idx ON core.ad_daily_2026_10 USING btree (account_id, data_level, stat_date, campaign_id)）

#### core.ad_daily_2026_11（表）

> 大小 40 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | global_campaign_id | text | 是 | — |
| 11 | ad_group_id | text | 否 | ''::text |
| 12 | ad_group_name | text | 是 | — |
| 13 | stat_date | date | 否 | — |
| 14 | budget_currency | text | 是 | — |
| 15 | data_level | text | 否 | — |
| 16 | grain_level | text | 否 | — |
| 17 | dimension_key | text | 否 | — |
| 18 | placement | text | 是 | — |
| 19 | target_id | text | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | target_text | text | 是 | — |
| 21 | target_match_type | text | 是 | — |
| 22 | target_bid | numeric | 是 | — |
| 23 | target_type | text | 是 | — |
| 24 | target_status | text | 是 | — |
| 25 | advertised_product_id | text | 是 | — |
| 26 | advertised_product_name | text | 是 | — |
| 27 | advertised_product_parent_id | text | 是 | — |
| 28 | advertised_product_brand | text | 是 | — |
| 29 | advertised_product_category | text | 是 | — |
| 3 | manager_account | text | 是 | — |
| 30 | advertised_product_subcategory | text | 是 | — |
| 31 | advertised_product_group | text | 是 | — |
| 32 | advertised_product_sku | text | 是 | — |
| 33 | advertised_product_marketplace | text | 是 | — |
| 34 | purchased_product_id | text | 是 | — |
| 35 | purchased_product_name | text | 是 | — |
| 36 | purchased_product_marketplace | text | 是 | — |
| 37 | impressions | bigint | 是 | — |
| 38 | viewable_impressions | bigint | 是 | — |
| 39 | clicks | bigint | 是 | — |
| 4 | ad_product | text | 否 | ''::text |
| 40 | spend | numeric | 是 | — |
| 41 | purchases | bigint | 是 | — |
| 42 | sales | numeric | 是 | — |
| 43 | units | bigint | 是 | — |
| 44 | promoted_purchases | bigint | 是 | — |
| 45 | promoted_sales | numeric | 是 | — |
| 46 | promoted_units | bigint | 是 | — |
| 47 | halo_purchases | bigint | 是 | — |
| 48 | halo_sales | numeric | 是 | — |
| 49 | halo_units | bigint | 是 | — |
| 5 | portfolio_id | text | 是 | — |
| 50 | new_to_brand_purchases | bigint | 是 | — |
| 51 | new_to_brand_sales | numeric | 是 | — |
| 52 | new_to_brand_units | bigint | 是 | — |
| 53 | long_term_sales | numeric | 是 | — |
| 54 | detail_page_views | bigint | 是 | — |
| 55 | ctr_pct | numeric | 是 | — |
| 56 | vctr_pct | numeric | 是 | — |
| 57 | cpc | numeric | 是 | — |
| 58 | cvr_pct | numeric | 是 | — |
| 59 | cpa | numeric | 是 | — |
| 6 | portfolio_name | text | 是 | — |
| 60 | acos_pct | numeric | 是 | — |
| 61 | roas | numeric | 是 | — |
| 62 | promoted_cpa | numeric | 是 | — |
| 63 | promoted_cvr_pct | numeric | 是 | — |
| 64 | promoted_acos_pct | numeric | 是 | — |
| 65 | promoted_roas | numeric | 是 | — |
| 66 | new_to_brand_cpa | numeric | 是 | — |
| 67 | new_to_brand_cvr_pct | numeric | 是 | — |
| 68 | new_to_brand_acos_pct | numeric | 是 | — |
| 69 | new_to_brand_roas | numeric | 是 | — |
| 7 | campaign_id | text | 否 | — |
| 70 | long_term_roas | numeric | 是 | — |
| 71 | cost_per_detail_page_view | numeric | 是 | — |
| 72 | detail_page_view_rate_pct | numeric | 是 | — |
| 73 | row_hash | character | 否 | — |
| 74 | batch_id | bigint | 是 | — |
| 75 | source_file_name | text | 是 | — |
| 76 | source_file_hash | character | 是 | — |
| 77 | first_imported_at | timestamp with time zone | 否 | now() |
| 78 | updated_at | timestamp with time zone | 否 | now() |
| 8 | campaign_name | text | 是 | — |
| 9 | campaign_state | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, data_level, grain_level, campaign_id, ad_group_id, stat_date, dimension_key（ad_daily_2026_11_pkey）
- 索引：ad_daily_2026_11_account_id_advertised_product_id_idx（CREATE INDEX ad_daily_2026_11_account_id_advertised_product_id_idx ON core.ad_daily_2026_11 USING btree (account_id, advertised_product_id)）
- 索引：ad_daily_2026_11_account_id_campaign_id_stat_date_idx（CREATE INDEX ad_daily_2026_11_account_id_campaign_id_stat_date_idx ON core.ad_daily_2026_11 USING btree (account_id, campaign_id, stat_date)）
- 索引：ad_daily_2026_11_account_id_data_level_stat_date_campaign_i_idx（CREATE INDEX ad_daily_2026_11_account_id_data_level_stat_date_campaign_i_idx ON core.ad_daily_2026_11 USING btree (account_id, data_level, stat_date, campaign_id)）

#### core.ad_daily_default（表）

> 大小 40 kB，估算行数 0。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | global_campaign_id | text | 是 | — |
| 11 | ad_group_id | text | 否 | ''::text |
| 12 | ad_group_name | text | 是 | — |
| 13 | stat_date | date | 否 | — |
| 14 | budget_currency | text | 是 | — |
| 15 | data_level | text | 否 | — |
| 16 | grain_level | text | 否 | — |
| 17 | dimension_key | text | 否 | — |
| 18 | placement | text | 是 | — |
| 19 | target_id | text | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | target_text | text | 是 | — |
| 21 | target_match_type | text | 是 | — |
| 22 | target_bid | numeric | 是 | — |
| 23 | target_type | text | 是 | — |
| 24 | target_status | text | 是 | — |
| 25 | advertised_product_id | text | 是 | — |
| 26 | advertised_product_name | text | 是 | — |
| 27 | advertised_product_parent_id | text | 是 | — |
| 28 | advertised_product_brand | text | 是 | — |
| 29 | advertised_product_category | text | 是 | — |
| 3 | manager_account | text | 是 | — |
| 30 | advertised_product_subcategory | text | 是 | — |
| 31 | advertised_product_group | text | 是 | — |
| 32 | advertised_product_sku | text | 是 | — |
| 33 | advertised_product_marketplace | text | 是 | — |
| 34 | purchased_product_id | text | 是 | — |
| 35 | purchased_product_name | text | 是 | — |
| 36 | purchased_product_marketplace | text | 是 | — |
| 37 | impressions | bigint | 是 | — |
| 38 | viewable_impressions | bigint | 是 | — |
| 39 | clicks | bigint | 是 | — |
| 4 | ad_product | text | 否 | ''::text |
| 40 | spend | numeric | 是 | — |
| 41 | purchases | bigint | 是 | — |
| 42 | sales | numeric | 是 | — |
| 43 | units | bigint | 是 | — |
| 44 | promoted_purchases | bigint | 是 | — |
| 45 | promoted_sales | numeric | 是 | — |
| 46 | promoted_units | bigint | 是 | — |
| 47 | halo_purchases | bigint | 是 | — |
| 48 | halo_sales | numeric | 是 | — |
| 49 | halo_units | bigint | 是 | — |
| 5 | portfolio_id | text | 是 | — |
| 50 | new_to_brand_purchases | bigint | 是 | — |
| 51 | new_to_brand_sales | numeric | 是 | — |
| 52 | new_to_brand_units | bigint | 是 | — |
| 53 | long_term_sales | numeric | 是 | — |
| 54 | detail_page_views | bigint | 是 | — |
| 55 | ctr_pct | numeric | 是 | — |
| 56 | vctr_pct | numeric | 是 | — |
| 57 | cpc | numeric | 是 | — |
| 58 | cvr_pct | numeric | 是 | — |
| 59 | cpa | numeric | 是 | — |
| 6 | portfolio_name | text | 是 | — |
| 60 | acos_pct | numeric | 是 | — |
| 61 | roas | numeric | 是 | — |
| 62 | promoted_cpa | numeric | 是 | — |
| 63 | promoted_cvr_pct | numeric | 是 | — |
| 64 | promoted_acos_pct | numeric | 是 | — |
| 65 | promoted_roas | numeric | 是 | — |
| 66 | new_to_brand_cpa | numeric | 是 | — |
| 67 | new_to_brand_cvr_pct | numeric | 是 | — |
| 68 | new_to_brand_acos_pct | numeric | 是 | — |
| 69 | new_to_brand_roas | numeric | 是 | — |
| 7 | campaign_id | text | 否 | — |
| 70 | long_term_roas | numeric | 是 | — |
| 71 | cost_per_detail_page_view | numeric | 是 | — |
| 72 | detail_page_view_rate_pct | numeric | 是 | — |
| 73 | row_hash | character | 否 | — |
| 74 | batch_id | bigint | 是 | — |
| 75 | source_file_name | text | 是 | — |
| 76 | source_file_hash | character | 是 | — |
| 77 | first_imported_at | timestamp with time zone | 否 | now() |
| 78 | updated_at | timestamp with time zone | 否 | now() |
| 8 | campaign_name | text | 是 | — |
| 9 | campaign_state | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, data_level, grain_level, campaign_id, ad_group_id, stat_date, dimension_key（ad_daily_default_pkey）
- 索引：ad_daily_default_account_id_advertised_product_id_idx（CREATE INDEX ad_daily_default_account_id_advertised_product_id_idx ON core.ad_daily_default USING btree (account_id, advertised_product_id)）
- 索引：ad_daily_default_account_id_campaign_id_stat_date_idx（CREATE INDEX ad_daily_default_account_id_campaign_id_stat_date_idx ON core.ad_daily_default USING btree (account_id, campaign_id, stat_date)）
- 索引：ad_daily_default_account_id_data_level_stat_date_campaign_i_idx（CREATE INDEX ad_daily_default_account_id_data_level_stat_date_campaign_i_idx ON core.ad_daily_default USING btree (account_id, data_level, stat_date, campaign_id)）

#### core.business_report_parent_asin_period（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 是 | — |
| 10 | mobile_app_session_pct | numeric | 是 | — |
| 11 | browser_session_pct | numeric | 是 | — |
| 12 | browser_session_b2b_pct | numeric | 是 | — |
| 13 | ordered_product_units | bigint | 是 | — |
| 14 | ordered_product_units_b2b | bigint | 是 | — |
| 15 | unit_session_pct | numeric | 是 | — |
| 16 | unit_session_b2b_pct | numeric | 是 | — |
| 17 | ordered_product_sales | numeric | 是 | — |
| 18 | ordered_product_sales_b2b | numeric | 是 | — |
| 19 | total_order_items | bigint | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | total_order_items_b2b | bigint | 是 | — |
| 21 | currency_code | text | 是 | — |
| 22 | source_batch_id | bigint | 是 | — |
| 23 | created_at | timestamp with time zone | 是 | — |
| 24 | updated_at | timestamp with time zone | 是 | — |
| 3 | report_start_date | date | 是 | — |
| 4 | report_end_date | date | 是 | — |
| 5 | parent_asin | text | 是 | — |
| 6 | title | text | 是 | — |
| 7 | sessions_total | bigint | 是 | — |
| 8 | sessions_b2b | bigint | 是 | — |
| 9 | mobile_app_conversion_rate_b2b_pct | numeric | 是 | — |

#### core.import_batches（表）

> 大小 400 kB，估算行数 349。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | batch_id | bigint | 否 | — |
| 10 | imported_at | timestamp with time zone | 否 | now() |
| 11 | source_row_count | integer | 否 | 0 |
| 12 | valid_row_count | integer | 否 | 0 |
| 13 | failed_row_count | integer | 否 | 0 |
| 14 | import_status | text | 否 | — |
| 15 | error_message | text | 是 | — |
| 16 | metadata | jsonb | 否 | '{}'::jsonb |
| 17 | account_id | text | 是 | — |
| 18 | account_name | text | 是 | — |
| 19 | source_kind | text | 是 | — |
| 2 | file_name | text | 否 | — |
| 20 | source_url | text | 是 | — |
| 21 | data_level | text | 是 | — |
| 22 | target_table | text | 是 | — |
| 23 | inserted_row_count | integer | 是 | 0 |
| 24 | updated_row_count | integer | 是 | 0 |
| 25 | skipped_row_count | integer | 是 | 0 |
| 26 | schema_version | text | 是 | 'v2.0'::text |
| 3 | file_hash | character | 否 | — |
| 4 | source_path | text | 否 | — |
| 5 | report_type | text | 是 | — |
| 6 | report_start_date | date | 是 | — |
| 7 | report_end_date | date | 是 | — |
| 8 | exported_at | timestamp with time zone | 是 | — |
| 9 | export_time_source | text | 是 | — |

约束与索引：

- PRIMARY KEY：batch_id（import_batches_pkey）
- UNIQUE：file_hash（import_batches_file_hash_key）
- 索引：idx_batches_acct（CREATE INDEX idx_batches_acct ON core.import_batches USING btree (account_id, imported_at DESC)）
- 索引：import_batches_file_hash_key（CREATE UNIQUE INDEX import_batches_file_hash_key ON core.import_batches USING btree (file_hash)）

#### core.report_advertised_product_daily（表）

> 大小 173 MB，估算行数 198,450。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | campaign_name | text | 是 | — |
| 11 | ad_group_name | text | 是 | — |
| 12 | budget_currency | text | 是 | — |
| 13 | advertised_product_name | text | 是 | — |
| 14 | advertised_product_parent_id | text | 是 | — |
| 15 | advertised_product_brand | text | 是 | — |
| 16 | advertised_product_category | text | 是 | — |
| 17 | advertised_product_subcategory | text | 是 | — |
| 18 | advertised_product_group | text | 是 | — |
| 19 | advertised_product_sku | text | 是 | — |
| 2 | ad_product | text | 否 | — |
| 20 | impressions | bigint | 是 | — |
| 21 | clicks | bigint | 是 | — |
| 22 | spend | numeric | 是 | — |
| 23 | purchases | bigint | 是 | — |
| 24 | sales | numeric | 是 | — |
| 25 | units | bigint | 是 | — |
| 26 | promoted_purchases | bigint | 是 | — |
| 27 | promoted_sales | numeric | 是 | — |
| 28 | promoted_units | bigint | 是 | — |
| 29 | halo_purchases | bigint | 是 | — |
| 3 | campaign_id | text | 否 | — |
| 30 | halo_sales | numeric | 是 | — |
| 31 | halo_units | bigint | 是 | — |
| 32 | new_to_brand_purchases | bigint | 是 | — |
| 33 | new_to_brand_sales | numeric | 是 | — |
| 34 | new_to_brand_units | bigint | 是 | — |
| 35 | detail_page_views | bigint | 是 | — |
| 36 | ctr_pct | numeric | 是 | — |
| 37 | cpc | numeric | 是 | — |
| 38 | cvr_pct | numeric | 是 | — |
| 39 | cpa | numeric | 是 | — |
| 4 | ad_group_id | text | 否 | — |
| 40 | acos_pct | numeric | 是 | — |
| 41 | roas | numeric | 是 | — |
| 42 | promoted_cpa | numeric | 是 | — |
| 43 | promoted_cvr_pct | numeric | 是 | — |
| 44 | promoted_roas | numeric | 是 | — |
| 45 | new_to_brand_cpa | numeric | 是 | — |
| 46 | new_to_brand_cvr_pct | numeric | 是 | — |
| 47 | new_to_brand_roas | numeric | 是 | — |
| 48 | cost_per_detail_page_view | numeric | 是 | — |
| 49 | detail_page_view_rate_pct | numeric | 是 | — |
| 5 | advertised_product_id | text | 否 | — |
| 50 | source_file_name | text | 否 | — |
| 51 | source_file_hash | character | 否 | — |
| 52 | row_hash | character | 否 | — |
| 53 | batch_id | bigint | 否 | — |
| 54 | first_imported_at | timestamp with time zone | 是 | — |
| 55 | loaded_at | timestamp with time zone | 是 | — |
| 56 | advertised_product_marketplace | text | 是 | — |
| 57 | click_cvr_pct | numeric | 是 | — |
| 6 | stat_date | date | 否 | — |
| 7 | account_name | text | 是 | — |
| 8 | portfolio_id | text | 是 | — |
| 9 | portfolio_name | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, ad_group_id, advertised_product_id, stat_date（report_advertised_product_daily_pkey）
- 索引：idx_report_advertised_product_daily_account_id_stat_date（CREATE INDEX idx_report_advertised_product_daily_account_id_stat_date ON core.report_advertised_product_daily USING btree (account_id, stat_date)）
- 索引：idx_report_advertised_product_daily_campaign_id_ad_group_id（CREATE INDEX idx_report_advertised_product_daily_campaign_id_ad_group_id ON core.report_advertised_product_daily USING btree (campaign_id, ad_group_id)）

#### core.report_business_child_asin_daily（表）

> 大小 207 MB，估算行数 342,859。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | session_pct_b2b | numeric | 是 | — |
| 11 | page_views_total | bigint | 是 | — |
| 12 | page_views_b2b | bigint | 是 | — |
| 13 | page_view_pct_total | numeric | 是 | — |
| 14 | page_view_pct_b2b | numeric | 是 | — |
| 15 | featured_offer_pct | numeric | 是 | — |
| 16 | featured_offer_b2b_pct | numeric | 是 | — |
| 17 | ordered_product_units | bigint | 是 | — |
| 18 | ordered_product_units_b2b | bigint | 是 | — |
| 19 | unit_session_pct | numeric | 是 | — |
| 2 | account_name | text | 否 | — |
| 20 | unit_session_b2b_pct | numeric | 是 | — |
| 21 | ordered_product_sales | numeric | 是 | — |
| 22 | ordered_product_sales_b2b | numeric | 是 | — |
| 23 | total_order_items | bigint | 是 | — |
| 24 | total_order_items_b2b | bigint | 是 | — |
| 25 | currency_code | text | 否 | 'USD'::text |
| 26 | source_batch_id | bigint | 是 | — |
| 27 | source_file_name | text | 是 | — |
| 28 | source_file_hash | character | 是 | — |
| 29 | created_at | timestamp with time zone | 否 | now() |
| 3 | stat_date | date | 否 | — |
| 30 | updated_at | timestamp with time zone | 否 | now() |
| 4 | child_asin | text | 否 | — |
| 5 | parent_asin | text | 否 | — |
| 6 | title | text | 否 | — |
| 7 | sessions_total | bigint | 是 | — |
| 8 | sessions_b2b | bigint | 是 | — |
| 9 | conversion_rate_total_pct | numeric | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, stat_date, child_asin（report_business_child_asin_daily_pkey）
- 索引：idx_brc_account_date（CREATE INDEX idx_brc_account_date ON core.report_business_child_asin_daily USING btree (account_id, stat_date)）
- 索引：idx_brc_batch（CREATE INDEX idx_brc_batch ON core.report_business_child_asin_daily USING btree (source_batch_id)）
- 索引：idx_brc_child（CREATE INDEX idx_brc_child ON core.report_business_child_asin_daily USING btree (child_asin)）
- 索引：idx_brc_date（CREATE INDEX idx_brc_date ON core.report_business_child_asin_daily USING btree (stat_date)）
- 索引：idx_brc_parent（CREATE INDEX idx_brc_parent ON core.report_business_child_asin_daily USING btree (parent_asin)）
- 索引：idx_brc_parent_date（CREATE INDEX idx_brc_parent_date ON core.report_business_child_asin_daily USING btree (account_id, stat_date, parent_asin)）

#### core.report_business_parent_asin_period（表）

> 大小 1368 kB，估算行数 2,449。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | mobile_app_session_pct | numeric | 是 | — |
| 11 | browser_session_pct | numeric | 是 | — |
| 12 | browser_session_b2b_pct | numeric | 是 | — |
| 13 | ordered_product_units | bigint | 是 | — |
| 14 | ordered_product_units_b2b | bigint | 是 | — |
| 15 | unit_session_pct | numeric | 是 | — |
| 16 | unit_session_b2b_pct | numeric | 是 | — |
| 17 | ordered_product_sales | numeric | 是 | — |
| 18 | ordered_product_sales_b2b | numeric | 是 | — |
| 19 | total_order_items | bigint | 是 | — |
| 2 | account_name | text | 否 | — |
| 20 | total_order_items_b2b | bigint | 是 | — |
| 21 | currency_code | text | 否 | 'USD'::text |
| 22 | source_batch_id | bigint | 是 | — |
| 23 | created_at | timestamp with time zone | 否 | now() |
| 24 | updated_at | timestamp with time zone | 否 | now() |
| 3 | report_start_date | date | 否 | — |
| 4 | report_end_date | date | 否 | — |
| 5 | parent_asin | text | 否 | — |
| 6 | title | text | 否 | — |
| 7 | sessions_total | bigint | 是 | — |
| 8 | sessions_b2b | bigint | 是 | — |
| 9 | mobile_app_conversion_rate_b2b_pct | numeric | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, report_start_date, report_end_date, parent_asin（report_business_parent_asin_period_pkey）
- 索引：idx_brp_account_period（CREATE INDEX idx_brp_account_period ON core.report_business_parent_asin_period USING btree (account_id, report_start_date, report_end_date)）
- 索引：idx_brp_asin（CREATE INDEX idx_brp_asin ON core.report_business_parent_asin_period USING btree (parent_asin)）
- 索引：idx_brp_batch（CREATE INDEX idx_brp_batch ON core.report_business_parent_asin_period USING btree (source_batch_id)）
- 索引：idx_brp_period（CREATE INDEX idx_brp_period ON core.report_business_parent_asin_period USING btree (report_start_date, report_end_date)）

#### core.report_campaign_daily（表）

> 大小 7272 kB，估算行数 10,158。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | clicks | bigint | 是 | — |
| 11 | spend | numeric | 是 | — |
| 12 | purchases | bigint | 是 | — |
| 13 | sales | numeric | 是 | — |
| 14 | new_to_brand_purchases | bigint | 是 | — |
| 15 | long_term_sales | numeric | 是 | — |
| 16 | ctr_pct | numeric | 是 | — |
| 17 | vctr_pct | numeric | 是 | — |
| 18 | cpc | numeric | 是 | — |
| 19 | cvr_pct | numeric | 是 | — |
| 2 | ad_product | text | 否 | — |
| 20 | cpa | numeric | 是 | — |
| 21 | acos_pct | numeric | 是 | — |
| 22 | roas | numeric | 是 | — |
| 23 | new_to_brand_cpa | numeric | 是 | — |
| 24 | long_term_roas | numeric | 是 | — |
| 25 | source_file_name | text | 否 | — |
| 26 | source_file_hash | character | 否 | — |
| 27 | row_hash | character | 否 | — |
| 28 | batch_id | bigint | 否 | — |
| 29 | first_imported_at | timestamp with time zone | 是 | — |
| 3 | campaign_id | text | 否 | — |
| 30 | loaded_at | timestamp with time zone | 是 | — |
| 31 | portfolio_id | text | 是 | — |
| 32 | portfolio_name | text | 是 | — |
| 33 | campaign_state | text | 是 | — |
| 34 | units | bigint | 是 | — |
| 35 | new_to_brand_sales | numeric | 是 | — |
| 36 | click_purchase_rate_pct | numeric | 是 | — |
| 37 | click_cvr_pct | numeric | 是 | — |
| 4 | stat_date | date | 否 | — |
| 5 | account_name | text | 是 | — |
| 6 | campaign_name | text | 是 | — |
| 7 | budget_currency | text | 是 | — |
| 8 | impressions | bigint | 是 | — |
| 9 | viewable_impressions | bigint | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, stat_date（report_campaign_daily_pkey）
- 索引：idx_report_campaign_daily_account_id_stat_date（CREATE INDEX idx_report_campaign_daily_account_id_stat_date ON core.report_campaign_daily USING btree (account_id, stat_date)）
- 索引：idx_report_campaign_daily_campaign_id（CREATE INDEX idx_report_campaign_daily_campaign_id ON core.report_campaign_daily USING btree (campaign_id)）

#### core.report_placement_daily（表）

> 大小 27 MB，估算行数 32,840。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | campaign_name | text | 是 | — |
| 11 | ad_group_name | text | 是 | — |
| 12 | budget_currency | text | 是 | — |
| 13 | impressions | bigint | 是 | — |
| 14 | clicks | bigint | 是 | — |
| 15 | spend | numeric | 是 | — |
| 16 | purchases | bigint | 是 | — |
| 17 | sales | numeric | 是 | — |
| 18 | units | bigint | 是 | — |
| 19 | promoted_purchases | bigint | 是 | — |
| 2 | ad_product | text | 否 | — |
| 20 | promoted_sales | numeric | 是 | — |
| 21 | promoted_units | bigint | 是 | — |
| 22 | halo_purchases | bigint | 是 | — |
| 23 | halo_sales | numeric | 是 | — |
| 24 | halo_units | bigint | 是 | — |
| 25 | new_to_brand_purchases | bigint | 是 | — |
| 26 | new_to_brand_sales | numeric | 是 | — |
| 27 | new_to_brand_units | bigint | 是 | — |
| 28 | detail_page_views | bigint | 是 | — |
| 29 | ctr_pct | numeric | 是 | — |
| 3 | campaign_id | text | 否 | — |
| 30 | cpc | numeric | 是 | — |
| 31 | cvr_pct | numeric | 是 | — |
| 32 | cpa | numeric | 是 | — |
| 33 | acos_pct | numeric | 是 | — |
| 34 | roas | numeric | 是 | — |
| 35 | promoted_cpa | numeric | 是 | — |
| 36 | promoted_cvr_pct | numeric | 是 | — |
| 37 | promoted_roas | numeric | 是 | — |
| 38 | new_to_brand_cpa | numeric | 是 | — |
| 39 | new_to_brand_cvr_pct | numeric | 是 | — |
| 4 | ad_group_id | text | 否 | — |
| 40 | new_to_brand_roas | numeric | 是 | — |
| 41 | cost_per_detail_page_view | numeric | 是 | — |
| 42 | detail_page_view_rate_pct | numeric | 是 | — |
| 43 | source_file_name | text | 否 | — |
| 44 | source_file_hash | character | 否 | — |
| 45 | row_hash | character | 否 | — |
| 46 | batch_id | bigint | 否 | — |
| 47 | first_imported_at | timestamp with time zone | 是 | — |
| 48 | loaded_at | timestamp with time zone | 是 | — |
| 49 | click_cvr_pct | numeric | 是 | — |
| 5 | placement | text | 否 | — |
| 6 | stat_date | date | 否 | — |
| 7 | account_name | text | 是 | — |
| 8 | portfolio_id | text | 是 | — |
| 9 | portfolio_name | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, ad_group_id, placement, stat_date（report_placement_daily_pkey）
- 索引：idx_report_placement_daily_account_id_stat_date（CREATE INDEX idx_report_placement_daily_account_id_stat_date ON core.report_placement_daily USING btree (account_id, stat_date)）
- 索引：idx_report_placement_daily_campaign_id_ad_group_id（CREATE INDEX idx_report_placement_daily_campaign_id_ad_group_id ON core.report_placement_daily USING btree (campaign_id, ad_group_id)）

#### core.report_purchased_product_daily（表）

> 大小 103 MB，估算行数 106,305。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | campaign_name | text | 是 | — |
| 11 | ad_group_name | text | 是 | — |
| 12 | budget_currency | text | 是 | — |
| 13 | purchased_product_name | text | 是 | — |
| 14 | purchased_product_marketplace | text | 是 | — |
| 15 | purchases | bigint | 是 | — |
| 16 | sales | numeric | 是 | — |
| 17 | units | bigint | 是 | — |
| 18 | halo_purchases | bigint | 是 | — |
| 19 | halo_sales | numeric | 是 | — |
| 2 | ad_product | text | 否 | — |
| 20 | halo_units | bigint | 是 | — |
| 21 | new_to_brand_purchases | bigint | 是 | — |
| 22 | new_to_brand_sales | numeric | 是 | — |
| 23 | new_to_brand_units | bigint | 是 | — |
| 24 | source_file_name | text | 否 | — |
| 25 | source_file_hash | character | 否 | — |
| 26 | row_hash | character | 否 | — |
| 27 | batch_id | bigint | 否 | — |
| 28 | first_imported_at | timestamp with time zone | 是 | — |
| 29 | loaded_at | timestamp with time zone | 是 | — |
| 3 | campaign_id | text | 否 | — |
| 30 | purchased_product_parent_id | text | 是 | — |
| 31 | purchased_product_brand | text | 是 | — |
| 32 | purchased_product_category | text | 是 | — |
| 33 | purchased_product_subcategory | text | 是 | — |
| 34 | purchased_product_group | text | 是 | — |
| 35 | advertised_product_id | text | 否 | — |
| 36 | advertised_product_name | text | 是 | — |
| 37 | advertised_product_parent_id | text | 是 | — |
| 38 | advertised_product_marketplace | text | 是 | — |
| 39 | advertised_product_sku | text | 是 | — |
| 4 | ad_group_id | text | 否 | — |
| 5 | purchased_product_id | text | 否 | — |
| 6 | stat_date | date | 否 | — |
| 7 | account_name | text | 是 | — |
| 8 | portfolio_id | text | 是 | — |
| 9 | portfolio_name | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, ad_group_id, advertised_product_id, purchased_product_id, stat_date（report_purchased_product_daily_pkey）
- 索引：idx_report_purchased_product_daily_account_id_stat_date（CREATE INDEX idx_report_purchased_product_daily_account_id_stat_date ON core.report_purchased_product_daily USING btree (account_id, stat_date)）
- 索引：idx_report_purchased_product_daily_campaign_id_ad_group_id（CREATE INDEX idx_report_purchased_product_daily_campaign_id_ad_group_id ON core.report_purchased_product_daily USING btree (campaign_id, ad_group_id)）
- 索引：idx_report_purchased_product_daily_purchased_product_id（CREATE INDEX idx_report_purchased_product_daily_purchased_product_id ON core.report_purchased_product_daily USING btree (purchased_product_id)）

#### core.report_search_term_daily（表）

> 大小 362 MB，估算行数 402,879。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | ad_product | text | 否 | — |
| 10 | campaign_name | text | 是 | — |
| 11 | ad_group_name | text | 是 | — |
| 12 | budget_currency | text | 是 | — |
| 13 | impressions | bigint | 是 | — |
| 14 | clicks | bigint | 是 | — |
| 15 | spend | numeric | 是 | — |
| 16 | purchases | bigint | 是 | — |
| 17 | sales | numeric | 是 | — |
| 18 | units | bigint | 是 | — |
| 19 | promoted_purchases | bigint | 是 | — |
| 2 | account_id | text | 否 | — |
| 20 | promoted_sales | numeric | 是 | — |
| 21 | promoted_units | bigint | 是 | — |
| 22 | halo_purchases | bigint | 是 | — |
| 23 | halo_sales | numeric | 是 | — |
| 24 | halo_units | bigint | 是 | — |
| 25 | new_to_brand_purchases | bigint | 是 | — |
| 26 | new_to_brand_sales | numeric | 是 | — |
| 27 | new_to_brand_units | bigint | 是 | — |
| 28 | detail_page_views | bigint | 是 | — |
| 29 | ctr_pct | numeric | 是 | — |
| 3 | campaign_id | text | 否 | — |
| 30 | cpc | numeric | 是 | — |
| 31 | cvr_pct | numeric | 是 | — |
| 32 | cpa | numeric | 是 | — |
| 33 | acos_pct | numeric | 是 | — |
| 34 | roas | numeric | 是 | — |
| 35 | source_file_name | text | 否 | — |
| 36 | source_file_hash | character | 否 | — |
| 37 | row_hash | character | 否 | — |
| 38 | batch_id | bigint | 否 | — |
| 39 | first_imported_at | timestamp with time zone | 是 | — |
| 4 | ad_group_id | text | 否 | — |
| 40 | loaded_at | timestamp with time zone | 是 | — |
| 41 | target_id | text | 否 | — |
| 42 | target_text | text | 是 | — |
| 43 | target_match_type | text | 是 | — |
| 44 | promoted_cpa | numeric | 是 | — |
| 45 | promoted_cvr_pct | numeric | 是 | — |
| 46 | promoted_roas | numeric | 是 | — |
| 47 | detail_page_view_rate_pct | numeric | 是 | — |
| 48 | click_cvr_pct | numeric | 是 | — |
| 5 | search_term | text | 否 | — |
| 6 | stat_date | date | 否 | — |
| 7 | account_name | text | 是 | — |
| 8 | portfolio_id | text | 是 | — |
| 9 | portfolio_name | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, ad_group_id, target_id, search_term, stat_date（report_search_term_daily_pkey）
- 索引：idx_report_search_term_daily_account_id_stat_date（CREATE INDEX idx_report_search_term_daily_account_id_stat_date ON core.report_search_term_daily USING btree (account_id, stat_date)）
- 索引：idx_report_search_term_daily_campaign_id_ad_group_id（CREATE INDEX idx_report_search_term_daily_campaign_id_ad_group_id ON core.report_search_term_daily USING btree (campaign_id, ad_group_id)）
- 索引：idx_report_search_term_daily_search_term（CREATE INDEX idx_report_search_term_daily_search_term ON core.report_search_term_daily USING btree (search_term)）

#### core.report_targeting_daily（表）

> 大小 173 MB，估算行数 198,672。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | campaign_name | text | 是 | — |
| 11 | ad_group_name | text | 是 | — |
| 12 | budget_currency | text | 是 | — |
| 13 | target_text | text | 是 | — |
| 14 | target_match_type | text | 是 | — |
| 15 | target_bid | numeric | 是 | — |
| 16 | target_type | text | 是 | — |
| 17 | target_status | text | 是 | — |
| 18 | impressions | bigint | 是 | — |
| 19 | clicks | bigint | 是 | — |
| 2 | ad_product | text | 否 | — |
| 20 | spend | numeric | 是 | — |
| 21 | purchases | bigint | 是 | — |
| 22 | sales | numeric | 是 | — |
| 23 | units | bigint | 是 | — |
| 24 | promoted_purchases | bigint | 是 | — |
| 25 | promoted_sales | numeric | 是 | — |
| 26 | promoted_units | bigint | 是 | — |
| 27 | halo_purchases | bigint | 是 | — |
| 28 | halo_sales | numeric | 是 | — |
| 29 | halo_units | bigint | 是 | — |
| 3 | campaign_id | text | 否 | — |
| 30 | new_to_brand_purchases | bigint | 是 | — |
| 31 | new_to_brand_sales | numeric | 是 | — |
| 32 | new_to_brand_units | bigint | 是 | — |
| 33 | detail_page_views | bigint | 是 | — |
| 34 | ctr_pct | numeric | 是 | — |
| 35 | cpc | numeric | 是 | — |
| 36 | cvr_pct | numeric | 是 | — |
| 37 | cpa | numeric | 是 | — |
| 38 | acos_pct | numeric | 是 | — |
| 39 | roas | numeric | 是 | — |
| 4 | ad_group_id | text | 否 | — |
| 40 | promoted_cpa | numeric | 是 | — |
| 41 | promoted_cvr_pct | numeric | 是 | — |
| 42 | promoted_roas | numeric | 是 | — |
| 43 | new_to_brand_cpa | numeric | 是 | — |
| 44 | new_to_brand_cvr_pct | numeric | 是 | — |
| 45 | new_to_brand_roas | numeric | 是 | — |
| 46 | cost_per_detail_page_view | numeric | 是 | — |
| 47 | detail_page_view_rate_pct | numeric | 是 | — |
| 48 | source_file_name | text | 否 | — |
| 49 | source_file_hash | character | 否 | — |
| 5 | target_id | text | 否 | — |
| 50 | row_hash | character | 否 | — |
| 51 | batch_id | bigint | 否 | — |
| 52 | first_imported_at | timestamp with time zone | 是 | — |
| 53 | loaded_at | timestamp with time zone | 是 | — |
| 54 | campaign_state | text | 是 | — |
| 55 | ad_group_state | text | 是 | — |
| 56 | click_cvr_pct | numeric | 是 | — |
| 6 | stat_date | date | 否 | — |
| 7 | account_name | text | 是 | — |
| 8 | portfolio_id | text | 是 | — |
| 9 | portfolio_name | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, ad_group_id, target_id, stat_date（report_targeting_daily_pkey）
- 索引：idx_report_targeting_daily_account_id_stat_date（CREATE INDEX idx_report_targeting_daily_account_id_stat_date ON core.report_targeting_daily USING btree (account_id, stat_date)）
- 索引：idx_report_targeting_daily_campaign_id_ad_group_id（CREATE INDEX idx_report_targeting_daily_campaign_id_ad_group_id ON core.report_targeting_daily USING btree (campaign_id, ad_group_id)）
- 索引：idx_report_targeting_daily_target_id（CREATE INDEX idx_report_targeting_daily_target_id ON core.report_targeting_daily USING btree (target_id)）

#### core.search_query_performance_monthly（表）

> 大小 29 MB，估算行数 50,999。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | sqp_monthly_id | bigint | 否 | — |
| 10 | brand_impressions | bigint | 是 | — |
| 11 | brand_impression_share_pct | numeric | 是 | — |
| 12 | clicks_total | bigint | 是 | — |
| 13 | click_rate_pct | numeric | 是 | — |
| 14 | brand_clicks | bigint | 是 | — |
| 15 | brand_click_share_pct | numeric | 是 | — |
| 16 | click_median_price | numeric | 是 | — |
| 17 | brand_click_median_price | numeric | 是 | — |
| 18 | click_same_day_delivery | bigint | 是 | — |
| 19 | click_one_day_delivery | bigint | 是 | — |
| 2 | marketplace | text | 否 | — |
| 20 | click_two_day_delivery | bigint | 是 | — |
| 21 | cart_adds_total | bigint | 是 | — |
| 22 | cart_add_rate_pct | numeric | 是 | — |
| 23 | brand_cart_adds | bigint | 是 | — |
| 24 | brand_cart_add_share_pct | numeric | 是 | — |
| 25 | cart_add_median_price | numeric | 是 | — |
| 26 | brand_cart_add_median_price | numeric | 是 | — |
| 27 | cart_add_same_day_delivery | bigint | 是 | — |
| 28 | cart_add_one_day_delivery | bigint | 是 | — |
| 29 | cart_add_two_day_delivery | bigint | 是 | — |
| 3 | brand_name | text | 否 | — |
| 30 | purchases_total | bigint | 是 | — |
| 31 | purchase_rate_pct | numeric | 是 | — |
| 32 | brand_purchases | bigint | 是 | — |
| 33 | brand_purchase_share_pct | numeric | 是 | — |
| 34 | purchase_median_price | numeric | 是 | — |
| 35 | brand_purchase_median_price | numeric | 是 | — |
| 36 | purchase_same_day_delivery | bigint | 是 | — |
| 37 | purchase_one_day_delivery | bigint | 是 | — |
| 38 | purchase_two_day_delivery | bigint | 是 | — |
| 39 | source_batch_id | bigint | 是 | — |
| 4 | report_scope | text | 否 | 'month'::text |
| 40 | source_file_name | text | 否 | — |
| 41 | source_file_hash | character | 否 | — |
| 42 | imported_at | timestamp with time zone | 否 | now() |
| 43 | updated_at | timestamp with time zone | 否 | now() |
| 5 | report_date | date | 否 | — |
| 6 | search_query | text | 否 | — |
| 7 | search_query_score | integer | 是 | — |
| 8 | search_query_volume | bigint | 是 | — |
| 9 | impressions_total | bigint | 是 | — |

约束与索引：

- PRIMARY KEY：sqp_monthly_id（search_query_performance_monthly_pkey）
- UNIQUE：marketplace, brand_name, report_date, search_query（search_query_performance_monthly_uk）
- 索引：search_query_performance_monthly_brand_date_idx（CREATE INDEX search_query_performance_monthly_brand_date_idx ON core.search_query_performance_monthly USING btree (marketplace, brand_name, report_date DESC)）
- 索引：search_query_performance_monthly_date_idx（CREATE INDEX search_query_performance_monthly_date_idx ON core.search_query_performance_monthly USING btree (report_date DESC)）
- 索引：search_query_performance_monthly_uk（CREATE UNIQUE INDEX search_query_performance_monthly_uk ON core.search_query_performance_monthly USING btree (marketplace, brand_name, report_date, search_query)）

#### core.search_query_performance_weekly（表）

> 大小 45 MB，估算行数 78,000。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | sqp_weekly_id | bigint | 否 | — |
| 10 | impressions_total | bigint | 是 | — |
| 11 | brand_impressions | bigint | 是 | — |
| 12 | brand_impression_share_pct | numeric | 是 | — |
| 13 | clicks_total | bigint | 是 | — |
| 14 | click_rate_pct | numeric | 是 | — |
| 15 | brand_clicks | bigint | 是 | — |
| 16 | brand_click_share_pct | numeric | 是 | — |
| 17 | click_median_price | numeric | 是 | — |
| 18 | brand_click_median_price | numeric | 是 | — |
| 19 | click_same_day_delivery | bigint | 是 | — |
| 2 | marketplace | text | 否 | — |
| 20 | click_one_day_delivery | bigint | 是 | — |
| 21 | click_two_day_delivery | bigint | 是 | — |
| 22 | cart_adds_total | bigint | 是 | — |
| 23 | cart_add_rate_pct | numeric | 是 | — |
| 24 | brand_cart_adds | bigint | 是 | — |
| 25 | brand_cart_add_share_pct | numeric | 是 | — |
| 26 | cart_add_median_price | numeric | 是 | — |
| 27 | brand_cart_add_median_price | numeric | 是 | — |
| 28 | cart_add_same_day_delivery | bigint | 是 | — |
| 29 | cart_add_one_day_delivery | bigint | 是 | — |
| 3 | brand_name | text | 否 | — |
| 30 | cart_add_two_day_delivery | bigint | 是 | — |
| 31 | purchases_total | bigint | 是 | — |
| 32 | purchase_rate_pct | numeric | 是 | — |
| 33 | brand_purchases | bigint | 是 | — |
| 34 | brand_purchase_share_pct | numeric | 是 | — |
| 35 | purchase_median_price | numeric | 是 | — |
| 36 | brand_purchase_median_price | numeric | 是 | — |
| 37 | purchase_same_day_delivery | bigint | 是 | — |
| 38 | purchase_one_day_delivery | bigint | 是 | — |
| 39 | purchase_two_day_delivery | bigint | 是 | — |
| 4 | report_scope | text | 否 | 'week'::text |
| 40 | source_batch_id | bigint | 是 | — |
| 41 | source_file_name | text | 否 | — |
| 42 | source_file_hash | character | 否 | — |
| 43 | imported_at | timestamp with time zone | 否 | now() |
| 44 | updated_at | timestamp with time zone | 否 | now() |
| 5 | week_start_date | date | 否 | — |
| 6 | week_end_date | date | 否 | — |
| 7 | search_query | text | 否 | — |
| 8 | search_query_score | integer | 是 | — |
| 9 | search_query_volume | bigint | 是 | — |

约束与索引：

- PRIMARY KEY：sqp_weekly_id（search_query_performance_weekly_pkey）
- UNIQUE：marketplace, brand_name, week_start_date, week_end_date, search_query（search_query_performance_weekly_uk）
- 索引：search_query_performance_weekly_brand_end_idx（CREATE INDEX search_query_performance_weekly_brand_end_idx ON core.search_query_performance_weekly USING btree (marketplace, brand_name, week_end_date DESC)）
- 索引：search_query_performance_weekly_end_idx（CREATE INDEX search_query_performance_weekly_end_idx ON core.search_query_performance_weekly USING btree (week_end_date DESC)）
- 索引：search_query_performance_weekly_uk（CREATE UNIQUE INDEX search_query_performance_weekly_uk ON core.search_query_performance_weekly USING btree (marketplace, brand_name, week_start_date, week_end_date, search_query)）

#### core.search_term_daily（表）

> 大小 70 MB，估算行数 102,761。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 否 | — |
| 10 | search_term | text | 否 | — |
| 11 | stat_date | date | 否 | — |
| 12 | budget_currency | text | 是 | — |
| 13 | impressions | bigint | 是 | — |
| 14 | clicks | bigint | 是 | — |
| 15 | spend | numeric | 是 | — |
| 16 | purchases | bigint | 是 | — |
| 17 | sales | numeric | 是 | — |
| 18 | units | bigint | 是 | — |
| 19 | promoted_purchases | bigint | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | promoted_sales | numeric | 是 | — |
| 21 | promoted_units | bigint | 是 | — |
| 22 | halo_purchases | bigint | 是 | — |
| 23 | halo_sales | numeric | 是 | — |
| 24 | halo_units | bigint | 是 | — |
| 25 | new_to_brand_purchases | bigint | 是 | — |
| 26 | new_to_brand_sales | numeric | 是 | — |
| 27 | new_to_brand_units | bigint | 是 | — |
| 28 | detail_page_views | bigint | 是 | — |
| 29 | ctr_pct | numeric | 是 | — |
| 3 | ad_product | text | 否 | ''::text |
| 30 | cpc | numeric | 是 | — |
| 31 | cvr_pct | numeric | 是 | — |
| 32 | cpa | numeric | 是 | — |
| 33 | acos_pct | numeric | 是 | — |
| 34 | roas | numeric | 是 | — |
| 35 | row_hash | character | 否 | — |
| 36 | batch_id | bigint | 是 | — |
| 37 | source_file_name | text | 是 | — |
| 38 | source_file_hash | character | 是 | — |
| 39 | first_imported_at | timestamp with time zone | 否 | now() |
| 4 | portfolio_id | text | 是 | — |
| 40 | updated_at | timestamp with time zone | 否 | now() |
| 5 | portfolio_name | text | 是 | — |
| 6 | campaign_id | text | 否 | — |
| 7 | campaign_name | text | 是 | — |
| 8 | ad_group_id | text | 否 | ''::text |
| 9 | ad_group_name | text | 是 | — |

约束与索引：

- PRIMARY KEY：account_id, ad_product, campaign_id, ad_group_id, search_term, stat_date（search_term_daily_pkey）
- 索引：idx_st_daily_main（CREATE INDEX idx_st_daily_main ON core.search_term_daily USING btree (account_id, stat_date, campaign_id)）

#### core.search_term_target_period（表）

> 大小 5835 MB，估算行数 4,455,019。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | period_fact_id | bigint | 否 | — |
| 10 | campaign_start_raw | text | 是 | — |
| 11 | bidding_strategy | text | 是 | — |
| 12 | campaign_rule_amount | numeric | 是 | — |
| 13 | campaign_cost_type | text | 是 | — |
| 14 | budget_currency | text | 是 | — |
| 15 | delivery_id | text | 是 | — |
| 16 | delivery_name | text | 是 | — |
| 17 | delivery_start_raw | text | 是 | — |
| 18 | delivery_end_raw | text | 是 | — |
| 19 | delivery_budget | numeric | 是 | — |
| 2 | account_id | text | 是 | — |
| 20 | ad_group_id | text | 是 | — |
| 21 | ad_group_name | text | 是 | — |
| 22 | ad_id | text | 是 | — |
| 23 | ad_name | text | 是 | — |
| 24 | search_term | text | 是 | — |
| 25 | target_id | text | 是 | — |
| 26 | target_bid | numeric | 是 | — |
| 27 | target_type | text | 是 | — |
| 28 | target_state | text | 是 | — |
| 29 | target_text | text | 是 | — |
| 3 | account_name | text | 是 | — |
| 30 | target_match_type | text | 是 | — |
| 31 | placement | text | 是 | — |
| 32 | raw_date_range | text | 否 | — |
| 33 | period_start | date | 否 | — |
| 34 | period_end | date | 否 | — |
| 35 | cpm | numeric | 是 | — |
| 36 | cpc | numeric | 是 | — |
| 37 | impressions | bigint | 是 | — |
| 38 | viewable_impressions | bigint | 是 | — |
| 39 | clicks | bigint | 是 | — |
| 4 | campaign_id | text | 是 | — |
| 40 | ctr_pct | numeric | 是 | — |
| 41 | vctr_pct | numeric | 是 | — |
| 42 | spend | numeric | 是 | — |
| 43 | purchases | bigint | 是 | — |
| 44 | new_to_brand_purchases | bigint | 是 | — |
| 45 | cost_per_purchase | numeric | 是 | — |
| 46 | cost_per_new_to_brand_purchase | numeric | 是 | — |
| 47 | sales | numeric | 是 | — |
| 48 | long_term_sales | numeric | 是 | — |
| 49 | roas | numeric | 是 | — |
| 5 | campaign_name | text | 是 | — |
| 50 | long_term_roas | numeric | 是 | — |
| 51 | source_row_number | integer | 否 | — |
| 52 | row_business_hash | character | 否 | — |
| 53 | row_content_hash | character | 否 | — |
| 54 | source_batch_id | bigint | 否 | — |
| 55 | source_file_name | text | 否 | — |
| 56 | source_file_hash | character | 否 | — |
| 57 | imported_at | timestamp with time zone | 否 | now() |
| 6 | global_campaign_id | text | 是 | — |
| 7 | campaign_budget_amount | numeric | 是 | — |
| 8 | campaign_budget_type | text | 是 | — |
| 9 | campaign_state | text | 是 | — |

约束与索引：

- PRIMARY KEY：period_fact_id（search_term_target_period_pkey）
- UNIQUE：source_batch_id, row_content_hash（search_term_target_period_batch_content_uk）
- 索引：search_term_target_period_batch_content_uk（CREATE UNIQUE INDEX search_term_target_period_batch_content_uk ON core.search_term_target_period USING btree (source_batch_id, row_content_hash)）
- 索引：sttp_business_hash_idx（CREATE INDEX sttp_business_hash_idx ON core.search_term_target_period USING btree (row_business_hash)）
- 索引：sttp_campaign_idx（CREATE INDEX sttp_campaign_idx ON core.search_term_target_period USING btree (account_id, campaign_id, period_start)）
- 索引：sttp_period_idx（CREATE INDEX sttp_period_idx ON core.search_term_target_period USING btree (period_start, period_end)）
- 索引：sttp_search_term_idx（CREATE INDEX sttp_search_term_idx ON core.search_term_target_period USING btree (search_term)）
- 索引：sttp_source_file_hash_idx（CREATE INDEX sttp_source_file_hash_idx ON core.search_term_target_period USING btree (source_file_hash)）
- 索引：sttp_target_idx（CREATE INDEX sttp_target_idx ON core.search_term_target_period USING btree (target_id, target_match_type)）

#### core.v_business_parent_from_child_daily（视图）

> 视图（无物理存储，列如下）。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 是 | — |
| 10 | ordered_product_units | bigint | 是 | — |
| 11 | ordered_product_units_b2b | bigint | 是 | — |
| 12 | ordered_product_sales | numeric | 是 | — |
| 13 | ordered_product_sales_b2b | numeric | 是 | — |
| 14 | total_order_items | bigint | 是 | — |
| 15 | total_order_items_b2b | bigint | 是 | — |
| 2 | account_name | text | 是 | — |
| 3 | report_start_date | date | 是 | — |
| 4 | report_end_date | date | 是 | — |
| 5 | parent_asin | text | 是 | — |
| 6 | sample_title | text | 是 | — |
| 7 | child_count | integer | 是 | — |
| 8 | sessions_total | bigint | 是 | — |
| 9 | sessions_b2b | bigint | 是 | — |

#### stg.load_tmp（表）

> 大小 42 MB，估算行数 102,761。

| # | 字段 | 类型 | 可空 | 默认值 |
|---|------|------|------|--------|
| 1 | account_id | text | 是 | — |
| 10 | search_term | text | 是 | — |
| 11 | stat_date | text | 是 | — |
| 12 | budget_currency | text | 是 | — |
| 13 | impressions | text | 是 | — |
| 14 | clicks | text | 是 | — |
| 15 | spend | text | 是 | — |
| 16 | purchases | text | 是 | — |
| 17 | sales | text | 是 | — |
| 18 | units | text | 是 | — |
| 19 | promoted_purchases | text | 是 | — |
| 2 | account_name | text | 是 | — |
| 20 | promoted_sales | text | 是 | — |
| 21 | promoted_units | text | 是 | — |
| 22 | halo_purchases | text | 是 | — |
| 23 | halo_sales | text | 是 | — |
| 24 | halo_units | text | 是 | — |
| 25 | new_to_brand_purchases | text | 是 | — |
| 26 | new_to_brand_sales | text | 是 | — |
| 27 | new_to_brand_units | text | 是 | — |
| 28 | detail_page_views | text | 是 | — |
| 29 | ctr_pct | text | 是 | — |
| 3 | ad_product | text | 是 | — |
| 30 | cpc | text | 是 | — |
| 31 | cvr_pct | text | 是 | — |
| 32 | cpa | text | 是 | — |
| 33 | acos_pct | text | 是 | — |
| 34 | roas | text | 是 | — |
| 35 | row_hash | text | 是 | — |
| 36 | batch_id | text | 是 | — |
| 37 | source_file_name | text | 是 | — |
| 38 | source_file_hash | text | 是 | — |
| 4 | portfolio_id | text | 是 | — |
| 5 | portfolio_name | text | 是 | — |
| 6 | campaign_id | text | 是 | — |
| 7 | campaign_name | text | 是 | — |
| 8 | ad_group_id | text | 是 | — |
| 9 | ad_group_name | text | 是 | — |

## 关联

- [[阿里云RDS-amazon_ads-库表结构]]（旧实例，已归档）
- [[亚马逊TIB与广告报告数据沉淀方案]]
- [[pgAdmin连接阿里云RDS-PostgreSQL操作指南]]

## 来源

- 阿里云 RDS 实例 `amazon_ads_v2` 现场元数据查询（2026-09-21，psql 直连 information_schema / pg_catalog 导出）
- amazon-ads-console/backend/.env（RDS_DATABASE_URL）
