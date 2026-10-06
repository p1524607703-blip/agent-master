-- 003_report_tables.sql
-- 按「一份报告一张表」重建广告事实层。由 _build_report_tables.py 生成，可重复执行（先 DROP）。
-- 原则：只保留实测有值的列，不保留死列；主键=业务自然键；batch_id 建真外键。

BEGIN;

-- ===== 广告活动报告（campaign）源行数 2,397 / 业务列 20 =====
DROP TABLE IF EXISTS core.report_campaign_daily;
CREATE TABLE core.report_campaign_daily AS
SELECT
    b.account_id,
    b.ad_product,
    b.campaign_id,
    b.stat_date,
    b.account_name,
    b.campaign_name,
    b.budget_currency,
    b.impressions,
    b.viewable_impressions,
    b.clicks,
    b.spend,
    b.purchases,
    b.sales,
    b.new_to_brand_purchases,
    b.long_term_sales,
    b.ctr_pct,
    b.vctr_pct,
    b.cpc,
    b.cvr_pct,
    b.cpa,
    b.acos_pct,
    b.roas,
    b.new_to_brand_cpa,
    b.long_term_roas,
    ib.file_name AS source_file_name,
    ib.file_hash AS source_file_hash,
    b.row_hash,
    b.batch_id,
    b.first_imported_at,
    NOW() AS loaded_at
FROM   core.ad_daily b
LEFT   JOIN core.import_batches ib ON ib.batch_id = b.batch_id
WHERE  b.data_level = 'campaign';

ALTER TABLE core.report_campaign_daily ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE core.report_campaign_daily ALTER COLUMN ad_product SET NOT NULL;
ALTER TABLE core.report_campaign_daily ALTER COLUMN campaign_id SET NOT NULL;
ALTER TABLE core.report_campaign_daily ALTER COLUMN stat_date SET NOT NULL;
ALTER TABLE core.report_campaign_daily ALTER COLUMN row_hash SET NOT NULL;
ALTER TABLE core.report_campaign_daily ALTER COLUMN batch_id SET NOT NULL;
ALTER TABLE core.report_campaign_daily ALTER COLUMN source_file_name SET NOT NULL;
ALTER TABLE core.report_campaign_daily ALTER COLUMN source_file_hash SET NOT NULL;
ALTER TABLE core.report_campaign_daily ADD PRIMARY KEY (account_id, ad_product, campaign_id, stat_date);
ALTER TABLE core.report_campaign_daily ADD CONSTRAINT fk_report_campaign_daily_batch FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);
CREATE INDEX idx_report_campaign_daily_account_id_stat_date ON core.report_campaign_daily (account_id, stat_date);
CREATE INDEX idx_report_campaign_daily_campaign_id ON core.report_campaign_daily (campaign_id);
COMMENT ON TABLE core.report_campaign_daily IS '广告活动报告日粒度事实表（campaign）。来自 ODS core.ad_daily，只保留本报告有值的列。';

-- ===== 广告位报告（placement）源行数 6,829 / 业务列 36 =====
DROP TABLE IF EXISTS core.report_placement_daily;
CREATE TABLE core.report_placement_daily AS
SELECT
    b.account_id,
    b.ad_product,
    b.campaign_id,
    COALESCE(b.ad_group_id, '') AS ad_group_id,
    b.placement,
    b.stat_date,
    b.account_name,
    b.portfolio_id,
    b.portfolio_name,
    b.campaign_name,
    b.ad_group_name,
    b.budget_currency,
    b.impressions,
    b.clicks,
    b.spend,
    b.purchases,
    b.sales,
    b.units,
    b.promoted_purchases,
    b.promoted_sales,
    b.promoted_units,
    b.halo_purchases,
    b.halo_sales,
    b.halo_units,
    b.new_to_brand_purchases,
    b.new_to_brand_sales,
    b.new_to_brand_units,
    b.detail_page_views,
    b.ctr_pct,
    b.cpc,
    b.cvr_pct,
    b.cpa,
    b.acos_pct,
    b.roas,
    b.promoted_cpa,
    b.promoted_cvr_pct,
    b.promoted_roas,
    b.new_to_brand_cpa,
    b.new_to_brand_cvr_pct,
    b.new_to_brand_roas,
    b.cost_per_detail_page_view,
    b.detail_page_view_rate_pct,
    ib.file_name AS source_file_name,
    ib.file_hash AS source_file_hash,
    b.row_hash,
    b.batch_id,
    b.first_imported_at,
    NOW() AS loaded_at
FROM   core.ad_daily b
LEFT   JOIN core.import_batches ib ON ib.batch_id = b.batch_id
WHERE  b.data_level = 'placement';

ALTER TABLE core.report_placement_daily ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN ad_product SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN campaign_id SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN ad_group_id SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN placement SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN stat_date SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN row_hash SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN batch_id SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN source_file_name SET NOT NULL;
ALTER TABLE core.report_placement_daily ALTER COLUMN source_file_hash SET NOT NULL;
ALTER TABLE core.report_placement_daily ADD PRIMARY KEY (account_id, ad_product, campaign_id, ad_group_id, placement, stat_date);
ALTER TABLE core.report_placement_daily ADD CONSTRAINT fk_report_placement_daily_batch FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);
CREATE INDEX idx_report_placement_daily_account_id_stat_date ON core.report_placement_daily (account_id, stat_date);
CREATE INDEX idx_report_placement_daily_campaign_id_ad_group_id ON core.report_placement_daily (campaign_id, ad_group_id);
COMMENT ON TABLE core.report_placement_daily IS '广告位报告日粒度事实表（placement）。来自 ODS core.ad_daily，只保留本报告有值的列。';

-- ===== 投放报告（targeting）源行数 62,021 / 业务列 41 =====
DROP TABLE IF EXISTS core.report_targeting_daily;
CREATE TABLE core.report_targeting_daily AS
SELECT
    b.account_id,
    b.ad_product,
    b.campaign_id,
    COALESCE(b.ad_group_id, '') AS ad_group_id,
    COALESCE(b.target_id, '') AS target_id,
    b.stat_date,
    b.account_name,
    b.portfolio_id,
    b.portfolio_name,
    b.campaign_name,
    b.ad_group_name,
    b.budget_currency,
    b.target_text,
    b.target_match_type,
    b.target_bid,
    b.target_type,
    b.target_status,
    b.impressions,
    b.clicks,
    b.spend,
    b.purchases,
    b.sales,
    b.units,
    b.promoted_purchases,
    b.promoted_sales,
    b.promoted_units,
    b.halo_purchases,
    b.halo_sales,
    b.halo_units,
    b.new_to_brand_purchases,
    b.new_to_brand_sales,
    b.new_to_brand_units,
    b.detail_page_views,
    b.ctr_pct,
    b.cpc,
    b.cvr_pct,
    b.cpa,
    b.acos_pct,
    b.roas,
    b.promoted_cpa,
    b.promoted_cvr_pct,
    b.promoted_roas,
    b.new_to_brand_cpa,
    b.new_to_brand_cvr_pct,
    b.new_to_brand_roas,
    b.cost_per_detail_page_view,
    b.detail_page_view_rate_pct,
    ib.file_name AS source_file_name,
    ib.file_hash AS source_file_hash,
    b.row_hash,
    b.batch_id,
    b.first_imported_at,
    NOW() AS loaded_at
FROM   core.ad_daily b
LEFT   JOIN core.import_batches ib ON ib.batch_id = b.batch_id
WHERE  b.data_level = 'targeting';

ALTER TABLE core.report_targeting_daily ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN ad_product SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN campaign_id SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN ad_group_id SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN target_id SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN stat_date SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN row_hash SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN batch_id SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN source_file_name SET NOT NULL;
ALTER TABLE core.report_targeting_daily ALTER COLUMN source_file_hash SET NOT NULL;
ALTER TABLE core.report_targeting_daily ADD PRIMARY KEY (account_id, ad_product, campaign_id, ad_group_id, target_id, stat_date);
ALTER TABLE core.report_targeting_daily ADD CONSTRAINT fk_report_targeting_daily_batch FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);
CREATE INDEX idx_report_targeting_daily_account_id_stat_date ON core.report_targeting_daily (account_id, stat_date);
CREATE INDEX idx_report_targeting_daily_campaign_id_ad_group_id ON core.report_targeting_daily (campaign_id, ad_group_id);
CREATE INDEX idx_report_targeting_daily_target_id ON core.report_targeting_daily (target_id);
COMMENT ON TABLE core.report_targeting_daily IS '投放报告日粒度事实表（targeting）。来自 ODS core.ad_daily，只保留本报告有值的列。';

-- ===== 推广的商品报告（advertised_product）源行数 2,457 / 业务列 43 =====
DROP TABLE IF EXISTS core.report_advertised_product_daily;
CREATE TABLE core.report_advertised_product_daily AS
SELECT
    b.account_id,
    b.ad_product,
    b.campaign_id,
    COALESCE(b.ad_group_id, '') AS ad_group_id,
    COALESCE(b.advertised_product_id, '') AS advertised_product_id,
    b.stat_date,
    b.account_name,
    b.portfolio_id,
    b.portfolio_name,
    b.campaign_name,
    b.ad_group_name,
    b.budget_currency,
    b.advertised_product_name,
    b.advertised_product_parent_id,
    b.advertised_product_brand,
    b.advertised_product_category,
    b.advertised_product_subcategory,
    b.advertised_product_group,
    b.advertised_product_sku,
    b.impressions,
    b.clicks,
    b.spend,
    b.purchases,
    b.sales,
    b.units,
    b.promoted_purchases,
    b.promoted_sales,
    b.promoted_units,
    b.halo_purchases,
    b.halo_sales,
    b.halo_units,
    b.new_to_brand_purchases,
    b.new_to_brand_sales,
    b.new_to_brand_units,
    b.detail_page_views,
    b.ctr_pct,
    b.cpc,
    b.cvr_pct,
    b.cpa,
    b.acos_pct,
    b.roas,
    b.promoted_cpa,
    b.promoted_cvr_pct,
    b.promoted_roas,
    b.new_to_brand_cpa,
    b.new_to_brand_cvr_pct,
    b.new_to_brand_roas,
    b.cost_per_detail_page_view,
    b.detail_page_view_rate_pct,
    ib.file_name AS source_file_name,
    ib.file_hash AS source_file_hash,
    b.row_hash,
    b.batch_id,
    b.first_imported_at,
    NOW() AS loaded_at
FROM   core.ad_daily b
LEFT   JOIN core.import_batches ib ON ib.batch_id = b.batch_id
WHERE  b.data_level = 'advertised_product';

ALTER TABLE core.report_advertised_product_daily ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN ad_product SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN campaign_id SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN ad_group_id SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN advertised_product_id SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN stat_date SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN row_hash SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN batch_id SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN source_file_name SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ALTER COLUMN source_file_hash SET NOT NULL;
ALTER TABLE core.report_advertised_product_daily ADD PRIMARY KEY (account_id, ad_product, campaign_id, ad_group_id, advertised_product_id, stat_date);
ALTER TABLE core.report_advertised_product_daily ADD CONSTRAINT fk_report_advertised_product_daily_batch FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);
CREATE INDEX idx_report_advertised_product_daily_account_id_stat_date ON core.report_advertised_product_daily (account_id, stat_date);
CREATE INDEX idx_report_advertised_product_daily_campaign_id_ad_group_id ON core.report_advertised_product_daily (campaign_id, ad_group_id);
COMMENT ON TABLE core.report_advertised_product_daily IS '推广的商品报告日粒度事实表（advertised_product）。来自 ODS core.ad_daily，只保留本报告有值的列。';

-- ===== 达成转化的商品报告（purchased_product）源行数 16,097 / 业务列 17 =====
DROP TABLE IF EXISTS core.report_purchased_product_daily;
CREATE TABLE core.report_purchased_product_daily AS
SELECT
    b.account_id,
    b.ad_product,
    b.campaign_id,
    COALESCE(b.ad_group_id, '') AS ad_group_id,
    COALESCE(b.purchased_product_id, '') AS purchased_product_id,
    b.stat_date,
    b.account_name,
    b.portfolio_id,
    b.portfolio_name,
    b.campaign_name,
    b.ad_group_name,
    b.budget_currency,
    b.purchased_product_name,
    b.purchased_product_marketplace,
    b.purchases,
    b.sales,
    b.units,
    b.halo_purchases,
    b.halo_sales,
    b.halo_units,
    b.new_to_brand_purchases,
    b.new_to_brand_sales,
    b.new_to_brand_units,
    ib.file_name AS source_file_name,
    ib.file_hash AS source_file_hash,
    b.row_hash,
    b.batch_id,
    b.first_imported_at,
    NOW() AS loaded_at
FROM   core.ad_daily b
LEFT   JOIN core.import_batches ib ON ib.batch_id = b.batch_id
WHERE  b.data_level = 'purchased_product';

ALTER TABLE core.report_purchased_product_daily ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN ad_product SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN campaign_id SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN ad_group_id SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN purchased_product_id SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN stat_date SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN row_hash SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN batch_id SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN source_file_name SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ALTER COLUMN source_file_hash SET NOT NULL;
ALTER TABLE core.report_purchased_product_daily ADD PRIMARY KEY (account_id, ad_product, campaign_id, ad_group_id, purchased_product_id, stat_date);
ALTER TABLE core.report_purchased_product_daily ADD CONSTRAINT fk_report_purchased_product_daily_batch FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);
CREATE INDEX idx_report_purchased_product_daily_account_id_stat_date ON core.report_purchased_product_daily (account_id, stat_date);
CREATE INDEX idx_report_purchased_product_daily_campaign_id_ad_group_id ON core.report_purchased_product_daily (campaign_id, ad_group_id);
CREATE INDEX idx_report_purchased_product_daily_purchased_product_id ON core.report_purchased_product_daily (purchased_product_id);
COMMENT ON TABLE core.report_purchased_product_daily IS '达成转化的商品报告日粒度事实表（purchased_product）。来自 ODS core.ad_daily，只保留本报告有值的列。';

-- ===== 搜索词报告（search_term）源行数 102,761 / 业务列 28 =====
-- 搜索词报表源 CSV 无「广告产品」列，ad_product 原为空串；
-- 这里从广告活动报告（6 份报表中唯一带该列的）按 (account_id, campaign_id) 回填。
DROP TABLE IF EXISTS core.report_search_term_daily;
CREATE TABLE core.report_search_term_daily AS
SELECT
    COALESCE(cm.ad_product, '') AS ad_product,
    s.account_id,
    s.campaign_id,
    s.ad_group_id,
    s.search_term,
    s.stat_date,
    s.account_name,
    s.portfolio_id,
    s.portfolio_name,
    s.campaign_name,
    s.ad_group_name,
    s.budget_currency,
    s.impressions,
    s.clicks,
    s.spend,
    s.purchases,
    s.sales,
    s.units,
    s.promoted_purchases,
    s.promoted_sales,
    s.promoted_units,
    s.halo_purchases,
    s.halo_sales,
    s.halo_units,
    s.new_to_brand_purchases,
    s.new_to_brand_sales,
    s.new_to_brand_units,
    s.detail_page_views,
    s.ctr_pct,
    s.cpc,
    s.cvr_pct,
    s.cpa,
    s.acos_pct,
    s.roas,
    ib.file_name AS source_file_name,
    ib.file_hash AS source_file_hash,
    s.row_hash,
    s.batch_id,
    s.first_imported_at,
    NOW() AS loaded_at
FROM   core.search_term_daily s
LEFT   JOIN (SELECT DISTINCT account_id, campaign_id, ad_product
           FROM core.ad_daily WHERE data_level='campaign' AND ad_product <> '') cm
       ON cm.account_id = s.account_id AND cm.campaign_id = s.campaign_id
LEFT   JOIN core.import_batches ib ON ib.batch_id = s.batch_id;

ALTER TABLE core.report_search_term_daily ALTER COLUMN account_id SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN ad_product SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN campaign_id SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN ad_group_id SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN search_term SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN stat_date SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN row_hash SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN batch_id SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN source_file_name SET NOT NULL;
ALTER TABLE core.report_search_term_daily ALTER COLUMN source_file_hash SET NOT NULL;
ALTER TABLE core.report_search_term_daily ADD PRIMARY KEY (account_id, ad_product, campaign_id, ad_group_id, search_term, stat_date);
ALTER TABLE core.report_search_term_daily ADD CONSTRAINT fk_report_search_term_daily_batch FOREIGN KEY (batch_id) REFERENCES core.import_batches(batch_id);
CREATE INDEX idx_report_search_term_daily_account_id_stat_date ON core.report_search_term_daily (account_id, stat_date);
CREATE INDEX idx_report_search_term_daily_campaign_id_ad_group_id ON core.report_search_term_daily (campaign_id, ad_group_id);
CREATE INDEX idx_report_search_term_daily_search_term ON core.report_search_term_daily (search_term);
COMMENT ON TABLE core.report_search_term_daily IS '搜索词报告日粒度事实表（search_term）。ad_product 由活动报告回填。';

COMMIT;

-- ===== 汇总 =====
-- core.report_campaign_daily                   预期   2,397 行 / 20 个业务列
-- core.report_placement_daily                  预期   6,829 行 / 36 个业务列
-- core.report_targeting_daily                  预期  62,021 行 / 41 个业务列
-- core.report_advertised_product_daily         预期   2,457 行 / 43 个业务列
-- core.report_purchased_product_daily          预期  16,097 行 / 17 个业务列
-- core.report_search_term_daily                预期 102,761 行 / 28 个业务列