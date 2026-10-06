-- Brand Analytics 周度报表 (川鹏2号 / WHITIN, US)
-- scp = 搜索目录绩效 (Search Catalog Performance, 按 ASIN)
-- sqp = 搜索查询绩效 (Search Query Performance, 按 搜索查询)
-- 列名采用 Amazon 原始英文语义 (与已存在的 core.search_query_performance_monthly 风格一致)

CREATE SCHEMA IF NOT EXISTS core;

-- ============ SCP 周表 ============
DROP TABLE IF EXISTS core.search_catalog_performance_weekly CASCADE;
CREATE TABLE core.search_catalog_performance_weekly (
  scp_weekly_id            bigserial PRIMARY KEY,
  marketplace              text        NOT NULL DEFAULT 'US',
  brand_name               text        NOT NULL,
  week_start_date          date        NOT NULL,
  week_end_date            date        NOT NULL,
  asin_title               text,
  asin                     text        NOT NULL,
  category                 text,
  impressions              bigint,
  impressions_rating_median numeric(8,2),
  impressions_median_price numeric(14,4),
  impressions_same_day_delivery  bigint,
  impressions_one_day_delivery   bigint,
  impressions_two_day_delivery    bigint,
  clicks                   bigint,
  click_through_rate_pct   numeric(12,6),
  click_median_price       numeric(14,4),
  clicks_same_day_delivery  bigint,
  clicks_one_day_delivery   bigint,
  clicks_two_day_delivery   bigint,
  cart_adds                bigint,
  cart_add_median_price    numeric(14,4),
  cart_adds_same_day_delivery  bigint,
  cart_adds_one_day_delivery   bigint,
  cart_adds_two_day_delivery    bigint,
  purchases                bigint,
  search_attributed_sales  numeric(16,4),
  conversion_rate_pct      numeric(12,6),
  purchase_rating_median   numeric(8,2),
  purchase_median_price    numeric(14,4),
  purchases_same_day_delivery  bigint,
  purchases_one_day_delivery   bigint,
  purchases_two_day_delivery    bigint,
  report_date              date,
  source_batch_id          bigint,
  source_file_name         text        NOT NULL,
  source_file_hash         char(64)    NOT NULL,
  imported_at              timestamptz NOT NULL DEFAULT now(),
  UNIQUE (marketplace, asin, week_start_date, week_end_date)
);

CREATE INDEX IF NOT EXISTS idx_scp_weekly_asin        ON core.search_catalog_performance_weekly (asin);
CREATE INDEX IF NOT EXISTS idx_scp_weekly_week       ON core.search_catalog_performance_weekly (week_start_date, week_end_date);

-- ============ SQP 周表 ============
DROP TABLE IF EXISTS core.search_query_performance_weekly CASCADE;
CREATE TABLE core.search_query_performance_weekly (
  sqp_weekly_id            bigserial PRIMARY KEY,
  marketplace              text        NOT NULL DEFAULT 'US',
  brand_name               text        NOT NULL,
  week_start_date          date        NOT NULL,
  week_end_date            date        NOT NULL,
  search_query             text        NOT NULL,
  search_query_score       integer,
  search_query_volume      bigint,
  impressions_total        bigint,
  brand_impressions        bigint,
  brand_impression_share_pct numeric(12,6),
  clicks_total             bigint,
  click_rate_pct           numeric(12,6),
  brand_clicks             bigint,
  brand_click_share_pct    numeric(12,6),
  click_median_price       numeric(14,4),
  brand_click_median_price numeric(14,4),
  cart_adds_total          bigint,
  cart_add_rate_pct        numeric(12,6),
  brand_cart_adds          bigint,
  brand_cart_add_share_pct numeric(12,6),
  cart_add_median_price    numeric(14,4),
  brand_cart_add_median_price numeric(14,4),
  purchases_total          bigint,
  purchase_rate_pct        numeric(12,6),
  brand_purchases          bigint,
  brand_purchase_share_pct numeric(12,6),
  purchase_median_price    numeric(14,4),
  brand_purchase_median_price numeric(14,4),
  impressions_same_day_delivery  bigint,
  impressions_one_day_delivery   bigint,
  impressions_two_day_delivery    bigint,
  clicks_same_day_delivery  bigint,
  clicks_one_day_delivery   bigint,
  clicks_two_day_delivery   bigint,
  cart_adds_same_day_delivery  bigint,
  cart_adds_one_day_delivery   bigint,
  cart_adds_two_day_delivery    bigint,
  purchases_same_day_delivery  bigint,
  purchases_one_day_delivery   bigint,
  purchases_two_day_delivery    bigint,
  source_batch_id          bigint,
  source_file_name         text        NOT NULL,
  source_file_hash         char(64)    NOT NULL,
  imported_at              timestamptz NOT NULL DEFAULT now(),
  UNIQUE (marketplace, search_query, week_start_date, week_end_date)
);

CREATE INDEX IF NOT EXISTS idx_sqp_weekly_query       ON core.search_query_performance_weekly (search_query);
CREATE INDEX IF NOT EXISTS idx_sqp_weekly_week       ON core.search_query_performance_weekly (week_start_date, week_end_date);
