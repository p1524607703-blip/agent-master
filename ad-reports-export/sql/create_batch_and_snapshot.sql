-- 川鹏2号 订阅报告「滚动 30 天」三层架构补全
-- 第 3 层(Daily 事实表 version-overwrite)已由 create_subscribed_reports.sql 落地。
-- 本文件补第 2 层 import_batch(加载血缘) 与第 4 层 snapshot_history(归因稳定性研究)。
-- 配合 subscribed_reports_to_rds.py 使用: 每次加载生成 1 个 run_id 串联本批所有文件。

CREATE SCHEMA IF NOT EXISTS core;

-- ============ 1. import_batch: 每次加载(run)的每个文件一行 ============
-- 记录血缘: 源文件 / hash / 原始行数 / 去重后行数 / 数据窗口末位 / 状态
DROP TABLE IF EXISTS core.import_batch CASCADE;
CREATE TABLE core.import_batch (
  batch_id          bigserial   PRIMARY KEY,
  run_id            uuid        NOT NULL,
  account_id        text        NOT NULL,
  report_type       text        NOT NULL,
  source_file_name  text        NOT NULL,
  source_file_hash  char(64)    NOT NULL,
  file_row_count    integer     NOT NULL,   -- CSV 原始数据行(去重前)
  loaded_row_count  integer     NOT NULL,   -- 实际 upsert 行(去重后)
  dropped_dup_rows  integer     NOT NULL DEFAULT 0,
  exported_at       date,                    -- 报告数据窗口末位 = max(stat_date)
  imported_at       timestamptz NOT NULL DEFAULT now(),
  status            text        NOT NULL DEFAULT 'ok'
);
CREATE INDEX IF NOT EXISTS idx_import_batch_run  ON core.import_batch (run_id);
CREATE INDEX IF NOT EXISTS idx_import_batch_key  ON core.import_batch (account_id, report_type, exported_at);

-- ============ 2. campaign_daily 历史快照(归因漂移研究) ============
-- 每次导入把当前事实表整表状态存档; 同一 (campaign_id, stat_date) 跨多个 snapshot_date
-- 的 metrics 之差 = Amazon 在 7/14 天窗口内的重归因幅度。
DROP TABLE IF EXISTS core.subscribed_campaign_daily_snapshot CASCADE;
CREATE TABLE core.subscribed_campaign_daily_snapshot (
  snapshot_date       date        NOT NULL,
  run_id              uuid        NOT NULL,
  account_id          text        NOT NULL,
  account_name        text,
  manager_account     text,
  ad_product          text,
  campaign_id         text        NOT NULL,
  campaign_name       text,
  global_campaign_id  text,
  budget_currency     text,
  stat_date           date        NOT NULL,
  impressions         bigint,
  viewable_impressions bigint,
  clicks              bigint,
  ctr_pct             numeric(10,4),
  vctr_pct            numeric(10,4),
  cost                numeric(18,4),
  purchases           bigint,
  new_to_brand_purchases bigint,
  cost_per_purchase   numeric(18,4),
  new_to_brand_cost_per_purchase numeric(18,4),
  sales               numeric(18,4),
  long_term_sales     numeric(18,4),
  roas                numeric(10,4),
  long_term_roas      numeric(10,4),
  report_type         text        NOT NULL DEFAULT 'campaign',
  PRIMARY KEY (snapshot_date, account_id, campaign_id, stat_date)
);
CREATE INDEX IF NOT EXISTS idx_camp_snap_cmp ON core.subscribed_campaign_daily_snapshot (campaign_id, stat_date, snapshot_date);

-- ============ 3. product_daily 历史快照(同样用于归因研究) ============
DROP TABLE IF EXISTS core.subscribed_product_daily_snapshot CASCADE;
CREATE TABLE core.subscribed_product_daily_snapshot (
  snapshot_date       date NOT NULL,
  run_id              uuid NOT NULL,
  budget_currency     text,
  account_id          text NOT NULL,
  account_name        text,
  portfolio_id        text,
  portfolio_name      text,
  campaign_id         text NOT NULL,
  campaign_name       text,
  ad_group_id         text NOT NULL,
  ad_group_name       text,
  advertised_product_id text NOT NULL,
  advertised_product_name text,
  advertised_product_parent_id text,
  advertised_product_brand text,
  advertised_product_category text,
  advertised_product_subcategory text,
  advertised_product_group text,
  advertised_product_sku text,
  advertised_product_marketplace text,
  stat_date           date NOT NULL,
  impressions         bigint,
  clicks              bigint,
  ctr_pct             numeric(10,4),
  cost                numeric(18,4),
  purchases           bigint,
  sales               numeric(18,4),
  units               bigint,
  cost_per_purchase   numeric(18,4),
  purchase_rate_pct   numeric(10,4),
  roas                numeric(10,4),
  promoted_purchases  bigint,
  promoted_sales      numeric(18,4),
  promoted_units      bigint,
  promoted_cost_per_purchase numeric(18,4),
  promoted_purchase_rate_pct numeric(10,4),
  promoted_roas       numeric(10,4),
  halo_purchases      bigint,
  halo_sales          numeric(18,4),
  halo_units          bigint,
  new_to_brand_purchases bigint,
  new_to_brand_sales  numeric(18,4),
  new_to_brand_units  bigint,
  new_to_brand_cost_per_purchase numeric(18,4),
  new_to_brand_purchase_rate_pct numeric(10,4),
  new_to_brand_roas   numeric(10,4),
  detail_page_views   bigint,
  cost_per_detail_page_view numeric(18,4),
  detail_page_view_rate_pct numeric(10,4),
  report_type         text NOT NULL DEFAULT 'product',
  PRIMARY KEY (snapshot_date, account_id, campaign_id, ad_group_id, advertised_product_id, stat_date)
);
CREATE INDEX IF NOT EXISTS idx_prod_snap_cmp ON core.subscribed_product_daily_snapshot (advertised_product_id, stat_date, snapshot_date);
