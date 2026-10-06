-- ============================================================================
-- Amazon Ads V2 核心结构 —— 在「新的空 RDS」上建立
-- 依据：《Amazon_Ads_V2数据库最优结构设计_基于实际导出数据_2026-09-12.md》
--
-- 与设计文档的一处差异（已确认档：空库无需共存）：
--   文档建议先建 ad_daily_v2 等带 _v2 后缀的表，是为与旧库共存预留。
--   本库为全新空库（0 张业务表），不存在旧表冲突，因此直接使用正式名。
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS core;

-- ----------------------------------------------------------------------------
-- 1. core.ad_daily —— 统一日级事实表（campaign/placement/targeting/
--    advertised_product/purchased_product/product_cpo 六种 data_level 共表）
--    按月 RANGE 分区，账户过滤走索引（设计文档 §18）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS core.ad_daily CASCADE;
CREATE TABLE core.ad_daily (
  -- 维度
  account_id              text NOT NULL,
  account_name            text,
  manager_account         text,
  ad_product              text NOT NULL DEFAULT '',

  portfolio_id            text,
  portfolio_name          text,

  campaign_id             text NOT NULL,
  campaign_name           text,
  campaign_state          text,
  global_campaign_id      text,

  ad_group_id             text NOT NULL DEFAULT '',
  ad_group_name           text,

  stat_date               date NOT NULL,
  budget_currency         text,

  -- 粒度控制
  data_level              text NOT NULL,
  grain_level             text NOT NULL,
  dimension_key           text NOT NULL,

  -- Placement 专用
  placement               text,

  -- Targeting 专用
  target_id               text,
  target_text             text,
  target_match_type       text,
  target_bid              numeric(18,4),
  target_type             text,
  target_status           text,

  -- 推广商品专用
  advertised_product_id           text,
  advertised_product_name         text,
  advertised_product_parent_id    text,
  advertised_product_brand        text,
  advertised_product_category     text,
  advertised_product_subcategory  text,
  advertised_product_group        text,
  advertised_product_sku          text,
  advertised_product_marketplace  text,

  -- 达成转化商品专用
  purchased_product_id            text,
  purchased_product_name          text,
  purchased_product_marketplace   text,

  -- 原始指标
  impressions             bigint,
  viewable_impressions    bigint,
  clicks                  bigint,
  spend                   numeric(18,4),
  purchases               bigint,
  sales                   numeric(18,4),
  units                   bigint,
  promoted_purchases      bigint,
  promoted_sales          numeric(18,4),
  promoted_units          bigint,
  halo_purchases          bigint,
  halo_sales              numeric(18,4),
  halo_units              bigint,
  new_to_brand_purchases  bigint,
  new_to_brand_sales      numeric(18,4),
  new_to_brand_units      bigint,
  long_term_sales         numeric(18,4),
  detail_page_views       bigint,

  -- 高频派生指标（导入阶段一次算好，查询直接读）
  ctr_pct                 numeric(12,6),
  vctr_pct                numeric(12,6),
  cpc                     numeric(18,6),
  cvr_pct                 numeric(12,6),
  cpa                     numeric(18,6),
  acos_pct                numeric(12,6),
  roas                    numeric(18,6),
  promoted_cpa            numeric(18,6),
  promoted_cvr_pct        numeric(12,6),
  promoted_acos_pct       numeric(12,6),
  promoted_roas           numeric(18,6),
  new_to_brand_cpa        numeric(18,6),
  new_to_brand_cvr_pct    numeric(12,6),
  new_to_brand_acos_pct   numeric(12,6),
  new_to_brand_roas       numeric(18,6),
  long_term_roas          numeric(18,6),
  cost_per_detail_page_view     numeric(18,6),
  detail_page_view_rate_pct     numeric(12,6),

  -- 技术字段
  row_hash                char(64)    NOT NULL,
  batch_id                bigint,
  source_file_name        text,
  source_file_hash        char(64),
  first_imported_at       timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),

  -- 业务唯一键（设计文档 §8）：可空字段统一规范为 '' 避免 NULL 唯一语义踩坑
  PRIMARY KEY (account_id, ad_product, data_level, grain_level,
               campaign_id, ad_group_id, stat_date, dimension_key)
) PARTITION BY RANGE (stat_date);

-- 主索引与辅助索引（设计文档 §18.2）
CREATE INDEX idx_ad_daily_main   ON core.ad_daily (account_id, data_level, stat_date, campaign_id);
CREATE INDEX idx_ad_daily_camp   ON core.ad_daily (account_id, campaign_id, stat_date);
CREATE INDEX idx_ad_daily_prod   ON core.ad_daily (account_id, advertised_product_id);

-- 按月分区 + DEFAULT 兜底
CREATE TABLE core.ad_daily_default PARTITION OF core.ad_daily DEFAULT;
CREATE TABLE core.ad_daily_2026_08 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE core.ad_daily_2026_09 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE core.ad_daily_2026_10 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE core.ad_daily_2026_11 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

-- 自动建月分区（导入前调用，避免落入 DEFAULT 分区）
CREATE OR REPLACE FUNCTION core.ensure_ad_daily_partition(p_date date)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
  v_start date := date_trunc('month', p_date)::date;
  v_end   date := (date_trunc('month', p_date) + interval '1 month')::date;
  v_name  text := 'ad_daily_' || to_char(v_start, 'YYYY_MM');
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                 WHERE n.nspname='core' AND c.relname=v_name) THEN
    EXECUTE format('CREATE TABLE core.%I PARTITION OF core.ad_daily FOR VALUES FROM (%L) TO (%L)',
                   v_name, v_start, v_end);
  END IF;
END $$;

-- ----------------------------------------------------------------------------
-- 2. core.search_term_daily —— 搜索词独立事实表（设计文档 §10）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS core.search_term_daily CASCADE;
CREATE TABLE core.search_term_daily (
  account_id              text NOT NULL,
  account_name            text,
  ad_product              text NOT NULL DEFAULT '',
  portfolio_id            text,
  portfolio_name          text,
  campaign_id             text NOT NULL,
  campaign_name           text,
  ad_group_id             text NOT NULL DEFAULT '',
  ad_group_name           text,
  search_term             text NOT NULL,
  stat_date               date NOT NULL,
  budget_currency         text,

  impressions             bigint,
  clicks                  bigint,
  spend                   numeric(18,4),
  purchases               bigint,
  sales                   numeric(18,4),
  units                   bigint,
  promoted_purchases      bigint,
  promoted_sales          numeric(18,4),
  promoted_units          bigint,
  halo_purchases          bigint,
  halo_sales              numeric(18,4),
  halo_units              bigint,
  new_to_brand_purchases  bigint,
  new_to_brand_sales      numeric(18,4),
  new_to_brand_units      bigint,
  detail_page_views       bigint,

  ctr_pct                 numeric(12,6),
  cpc                     numeric(18,6),
  cvr_pct                 numeric(12,6),
  cpa                     numeric(18,6),
  acos_pct                numeric(12,6),
  roas                    numeric(18,6),

  row_hash                char(64) NOT NULL,
  batch_id                bigint,
  source_file_name        text,
  source_file_hash        char(64),
  first_imported_at       timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, ad_product, campaign_id, ad_group_id, search_term, stat_date)
);
CREATE INDEX idx_st_daily_main ON core.search_term_daily (account_id, stat_date, campaign_id);

-- ----------------------------------------------------------------------------
-- 3. core.ad_hourly —— 分时事实表（设计文档 §11，含归因控制字段）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS core.ad_hourly CASCADE;
CREATE TABLE core.ad_hourly (
  account_id              text NOT NULL,
  account_name            text,
  ad_product              text NOT NULL DEFAULT '',
  campaign_id             text NOT NULL,
  campaign_name           text,
  stat_date               date NOT NULL,
  hour                    smallint NOT NULL,
  hourly_type             text NOT NULL,
  placement               text NOT NULL DEFAULT '',

  impressions             bigint,
  clicks                  bigint,
  spend                   numeric(18,4),
  purchases               bigint,
  sales                   numeric(18,4),
  units                   bigint,

  ctr_pct                 numeric(12,6),
  cpc                     numeric(18,6),
  cvr_pct                 numeric(12,6),
  acos_pct                numeric(12,6),
  roas                    numeric(18,6),

  attribution_window_days smallint,
  mature_after            date,
  attribution_status      text DEFAULT 'unknown',

  row_hash                char(64) NOT NULL,
  batch_id                bigint,
  source_file_name        text,
  source_file_hash        char(64),
  first_imported_at       timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, ad_product, campaign_id, stat_date, hour, hourly_type, placement)
);

-- ----------------------------------------------------------------------------
-- 4. core.ad_entity_current —— 当前配置表（设计文档 §12）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS core.ad_entity_current CASCADE;
CREATE TABLE core.ad_entity_current (
  account_id          text NOT NULL,
  account_name        text,
  ad_product          text NOT NULL DEFAULT '',
  entity_type         text NOT NULL,
  entity_key          text NOT NULL,

  portfolio_id        text,
  portfolio_name      text,
  campaign_id         text,
  campaign_name       text,
  ad_group_id         text,
  ad_group_name       text,
  ad_id               text,
  keyword_id          text,
  target_id           text,

  state               text,
  campaign_state      text,
  ad_group_state      text,
  start_date          date,
  end_date            date,

  budget              numeric(18,4),
  budget_type         text,
  targeting_type      text,
  bidding_strategy    text,
  default_bid         numeric(18,4),
  bid                 numeric(18,4),
  keyword_text        text,
  match_type          text,
  target_expression   text,
  placement           text,
  bid_adjustment_pct  numeric(12,4),
  sku                 text,
  asin                text,
  is_negative         boolean,
  is_draft            boolean,
  cost_type           text,
  optimization_goal   text,

  extra               jsonb,
  source_file_name    text,
  source_file_hash    char(64),
  snapshot_date       date,
  first_seen_at       timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (account_id, ad_product, entity_type, entity_key)
);
CREATE INDEX idx_entity_main ON core.ad_entity_current (account_id, ad_product, entity_type, campaign_id);
CREATE INDEX idx_entity_ag   ON core.ad_entity_current (campaign_id, ad_group_id);

-- ----------------------------------------------------------------------------
-- 5. core.ad_change_log —— 调整历史表（设计文档 §13）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS core.ad_change_log CASCADE;
CREATE TABLE core.ad_change_log (
  change_id           bigserial PRIMARY KEY,
  account_id          text NOT NULL,
  account_name        text,
  ad_product          text NOT NULL DEFAULT '',
  campaign_id         text,
  campaign_name       text,
  ad_group_id         text,
  ad_group_name       text,
  changed_at          timestamptz,
  detected_at         timestamptz NOT NULL DEFAULT now(),
  change_level        text,
  change_type         text,
  object_id           text,
  object_name         text,
  placement           text,
  previous_value      text,
  new_value           text,
  reason              text,
  operator_name       text,
  notes               text,
  change_source       text NOT NULL,
  source_file_name    text,
  source_file_hash    char(64),
  event_hash          char(64) NOT NULL UNIQUE,
  imported_at         timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_change_main ON core.ad_change_log (account_id, changed_at, campaign_id);

-- ----------------------------------------------------------------------------
-- 6. core.import_batches —— 导入管理/审计表（设计文档 §15）
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS core.import_batches CASCADE;
CREATE TABLE core.import_batches (
  batch_id            bigserial PRIMARY KEY,
  account_id          text,
  account_name        text,
  source_kind         text,
  source_path         text,
  source_url          text,
  file_name           text,
  file_hash           char(64) NOT NULL UNIQUE,
  report_type         text,
  data_level          text,
  target_table        text,
  report_start_date   date,
  report_end_date     date,
  exported_at         timestamptz,
  imported_at         timestamptz NOT NULL DEFAULT now(),
  source_row_count    integer,
  valid_row_count     integer,
  inserted_row_count  integer,
  updated_row_count   integer,
  skipped_row_count   integer,
  failed_row_count    integer,
  import_status       text NOT NULL DEFAULT 'pending',
  error_message       text,
  schema_version      text DEFAULT 'v2.0',
  metadata            jsonb
);
CREATE INDEX idx_batches_main ON core.import_batches (account_id, imported_at DESC);
