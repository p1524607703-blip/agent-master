-- 005_business_child_asin_daily.sql
-- Seller Central 业务报告「按子商品」日级事实。Parent ASIN 仅是当日关系快照。

BEGIN;

CREATE TABLE IF NOT EXISTS core.report_business_child_asin_daily (
    account_id TEXT NOT NULL,
    account_name TEXT NOT NULL,
    stat_date DATE NOT NULL,
    child_asin TEXT NOT NULL,
    parent_asin TEXT NOT NULL,
    title TEXT NOT NULL,
    sessions_total BIGINT,
    sessions_b2b BIGINT,
    conversion_rate_total_pct NUMERIC(12,6),
    session_pct_b2b NUMERIC(12,6),
    page_views_total BIGINT,
    page_views_b2b BIGINT,
    page_view_pct_total NUMERIC(12,6),
    page_view_pct_b2b NUMERIC(12,6),
    featured_offer_pct NUMERIC(12,6),
    featured_offer_b2b_pct NUMERIC(12,6),
    ordered_product_units BIGINT,
    ordered_product_units_b2b BIGINT,
    unit_session_pct NUMERIC(12,6),
    unit_session_b2b_pct NUMERIC(12,6),
    ordered_product_sales NUMERIC(18,6),
    ordered_product_sales_b2b NUMERIC(18,6),
    total_order_items BIGINT,
    total_order_items_b2b BIGINT,
    currency_code TEXT NOT NULL DEFAULT 'USD',
    source_batch_id BIGINT,
    source_file_name TEXT,
    source_file_hash CHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (account_id, stat_date, child_asin)
);

CREATE INDEX IF NOT EXISTS idx_brc_account_date ON core.report_business_child_asin_daily (account_id, stat_date);
CREATE INDEX IF NOT EXISTS idx_brc_date ON core.report_business_child_asin_daily (stat_date);
CREATE INDEX IF NOT EXISTS idx_brc_child ON core.report_business_child_asin_daily (child_asin);
CREATE INDEX IF NOT EXISTS idx_brc_parent ON core.report_business_child_asin_daily (parent_asin);
CREATE INDEX IF NOT EXISTS idx_brc_parent_date ON core.report_business_child_asin_daily (account_id, stat_date, parent_asin);
CREATE INDEX IF NOT EXISTS idx_brc_batch ON core.report_business_child_asin_daily (source_batch_id);

COMMENT ON TABLE core.report_business_child_asin_daily IS
'业务报告按子商品日级事实；主键=账户+日期+Child ASIN；Parent ASIN为当日父子关系快照。';

CREATE OR REPLACE VIEW core.v_business_parent_from_child_daily AS
SELECT
    account_id,
    max(account_name) AS account_name,
    stat_date AS report_start_date,
    stat_date AS report_end_date,
    parent_asin,
    max(title) AS sample_title,
    count(DISTINCT child_asin)::int AS child_count,
    sum(COALESCE(sessions_total,0))::bigint AS sessions_total,
    sum(COALESCE(sessions_b2b,0))::bigint AS sessions_b2b,
    sum(COALESCE(ordered_product_units,0))::bigint AS ordered_product_units,
    sum(COALESCE(ordered_product_units_b2b,0))::bigint AS ordered_product_units_b2b,
    sum(COALESCE(ordered_product_sales,0))::numeric(20,6) AS ordered_product_sales,
    sum(COALESCE(ordered_product_sales_b2b,0))::numeric(20,6) AS ordered_product_sales_b2b,
    sum(COALESCE(total_order_items,0))::bigint AS total_order_items,
    sum(COALESCE(total_order_items_b2b,0))::bigint AS total_order_items_b2b
FROM core.report_business_child_asin_daily
GROUP BY account_id, stat_date, parent_asin;

COMMIT;
