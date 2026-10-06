-- ============================================================================
-- Amazon Ads V2 核心结构 —— 目标库 amazon_ads_v2
-- 依据：《Amazon_Ads_V2数据库最优结构设计_基于实际导出数据_2026-09-12.md》
--
-- 命名说明：设计文档建议先建 *_v2 后缀表是为与旧库共存；本库本身已叫 _v2，
-- 且 core.ad_daily / core.search_term_daily 均不存在（无命名冲突），故直接用正式名。
--
-- ⚠️ 本脚本**不会** DROP core.import_batches —— 该表已有 14 条历史批次记录，
--    采用 ALTER TABLE 就地扩列，保留历史。
-- ============================================================================

CREATE SCHEMA IF NOT EXISTS core;

-- ----------------------------------------------------------------------------
-- 1. core.ad_daily —— 统一日级事实表（六种 data_level 共表），按月 RANGE 分区
-- ----------------------------------------------------------------------------
DROP TABLE IF EXISTS core.ad_daily CASCADE;
CREATE TABLE core.ad_daily (
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

  data_level              text NOT NULL,
  grain_level             text NOT NULL,
  dimension_key           text NOT NULL,

  placement               text,

  target_id               text,
  target_text             text,
  target_match_type       text,
  target_bid              numeric(18,4),
  target_type             text,
  target_status           text,

  advertised_product_id           text,
  advertised_product_name         text,
  advertised_product_parent_id    text,
  advertised_product_brand        text,
  advertised_product_category     text,
  advertised_product_subcategory  text,
  advertised_product_group        text,
  advertised_product_sku          text,
  advertised_product_marketplace  text,

  purchased_product_id            text,
  purchased_product_name          text,
  purchased_product_marketplace   text,

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

  row_hash                char(64)    NOT NULL,
  batch_id                bigint,
  source_file_name        text,
  source_file_hash        char(64),
  first_imported_at       timestamptz NOT NULL DEFAULT now(),
  updated_at              timestamptz NOT NULL DEFAULT now(),

  PRIMARY KEY (account_id, ad_product, data_level, grain_level,
               campaign_id, ad_group_id, stat_date, dimension_key)
) PARTITION BY RANGE (stat_date);

CREATE INDEX idx_ad_daily_main ON core.ad_daily (account_id, data_level, stat_date, campaign_id);
CREATE INDEX idx_ad_daily_camp ON core.ad_daily (account_id, campaign_id, stat_date);
CREATE INDEX idx_ad_daily_prod ON core.ad_daily (account_id, advertised_product_id);

CREATE TABLE core.ad_daily_default PARTITION OF core.ad_daily DEFAULT;
CREATE TABLE core.ad_daily_2026_08 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE core.ad_daily_2026_09 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE core.ad_daily_2026_10 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE core.ad_daily_2026_11 PARTITION OF core.ad_daily
  FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');

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
--    注：本库已存在 core.search_term_target_period（月期间粒度、历史回填用），
--        两者口径不同，见 README 说明，暂不合并。
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
-- 3/4/5. ad_hourly / ad_entity_current / ad_change_log
--   按设计文档 P1「先创建空表」，但当前数据源尚未接通：
--     ad_hourly        ← 需要分时(Hourly)报告，暂无导出
--     ad_entity_current← 需要「广告详细数据.xlsx」Bulk 快照，暂无导出
--     ad_change_log    ← 需要变更历史，已有独立仓库 ziniao-ad-change-history
--   因此暂不创建，避免出现长期空表。数据源就绪时再补。
-- ----------------------------------------------------------------------------

-- ----------------------------------------------------------------------------
-- 6. core.import_batches —— 就地扩列（保留已有 14 条历史批次）
-- ----------------------------------------------------------------------------
ALTER TABLE core.import_batches
  ADD COLUMN IF NOT EXISTS account_id          text,
  ADD COLUMN IF NOT EXISTS account_name        text,
  ADD COLUMN IF NOT EXISTS source_kind         text,
  ADD COLUMN IF NOT EXISTS source_url          text,
  ADD COLUMN IF NOT EXISTS data_level          text,
  ADD COLUMN IF NOT EXISTS target_table        text,
  ADD COLUMN IF NOT EXISTS inserted_row_count  integer DEFAULT 0,
  ADD COLUMN IF NOT EXISTS updated_row_count   integer DEFAULT 0,
  ADD COLUMN IF NOT EXISTS skipped_row_count   integer DEFAULT 0,
  ADD COLUMN IF NOT EXISTS schema_version      text DEFAULT 'v2.0';

CREATE INDEX IF NOT EXISTS idx_batches_acct ON core.import_batches (account_id, imported_at DESC);
