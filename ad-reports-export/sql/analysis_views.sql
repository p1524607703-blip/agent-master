-- 订阅报告分析视图: 把"能存"变成"能看 / 能研究"
-- 1) v_import_freshness   —— 运营监控: 每次加载后各报告是否新鲜、行数是否正常
-- 2) v_attribution_drift_* —— 归因稳定性研究: 同一实体跨快照的 metrics 漂移(= Amazon 重归因幅度)
-- 注意: 漂移视图只在存在 >=2 个不同 snapshot_date 时才有非零结果;
--       当前每日定时任务(北京 10:30)每机器日写 1 份快照, 跑满 2 天即开始显现。

CREATE SCHEMA IF NOT EXISTS core;

-- ============ 1. 导入新鲜度监控 ============
-- 每个 (账户, 报告类型) 取最近一次加载, 标注 fresh/stale (exported_at < 今天-2 视为陈旧)
DROP VIEW IF EXISTS core.v_import_freshness CASCADE;
CREATE VIEW core.v_import_freshness AS
SELECT ib.account_id, ib.report_type, ib.exported_at, ib.loaded_row_count,
       ib.dropped_dup_rows, ib.status, ib.imported_at, ib.run_id,
       CASE WHEN ib.exported_at >= (current_date - interval '2 day') THEN 'fresh'
            ELSE 'stale' END AS freshness
FROM core.import_batch ib
JOIN (
  SELECT account_id, report_type, max(imported_at) AS mi
  FROM core.import_batch GROUP BY account_id, report_type
) l ON l.account_id = ib.account_id AND l.report_type = ib.report_type AND l.mi = ib.imported_at;

-- ============ 2a. 归因漂移 —— campaign 层级(核心) ============
-- 同一 (campaign_id, stat_date) 跨最早/最晚快照的 sales / roas / purchases 之差
DROP VIEW IF EXISTS core.v_attribution_drift_campaign CASCADE;
CREATE VIEW core.v_attribution_drift_campaign AS
WITH snaps AS (
  SELECT campaign_id, stat_date, min(snapshot_date) AS first_sd, max(snapshot_date) AS last_sd
  FROM core.subscribed_campaign_daily_snapshot GROUP BY campaign_id, stat_date
),
f AS (
  SELECT s.campaign_id, s.stat_date, s.sales, s.roas, s.purchases, s.cost
  FROM core.subscribed_campaign_daily_snapshot s
  JOIN snaps n ON n.campaign_id=s.campaign_id AND n.stat_date=s.stat_date AND s.snapshot_date=n.first_sd
),
l AS (
  SELECT s.campaign_id, s.stat_date, s.sales, s.roas, s.purchases, s.cost
  FROM core.subscribed_campaign_daily_snapshot s
  JOIN snaps n ON n.campaign_id=s.campaign_id AND n.stat_date=s.stat_date AND s.snapshot_date=n.last_sd
)
SELECT f.campaign_id, f.stat_date, snaps.first_sd, snaps.last_sd,
       f.sales  AS sales_first,  l.sales  AS sales_last,
       (l.sales - f.sales) AS sales_delta,
       CASE WHEN f.sales > 0 THEN round((l.sales - f.sales) / f.sales * 100, 2) ELSE NULL END AS sales_drift_pct,
       f.roas   AS roas_first,   l.roas   AS roas_last,
       round((l.roas - f.roas)::numeric, 4) AS roas_delta,
       f.purchases AS purchases_first, l.purchases AS purchases_last,
       (l.purchases - f.purchases) AS purchases_delta
FROM snaps JOIN f USING (campaign_id, stat_date) JOIN l USING (campaign_id, stat_date)
WHERE f.sales <> l.sales OR f.roas <> l.roas OR f.purchases <> l.purchases;  -- 仅显示有漂移

-- ============ 2b. 归因漂移 —— search_term 层级(PPC 最相关) ============
DROP VIEW IF EXISTS core.v_attribution_drift_search_term CASCADE;
CREATE VIEW core.v_attribution_drift_search_term AS
WITH snaps AS (
  SELECT campaign_id, ad_group_id, search_term, stat_date,
         min(snapshot_date) AS first_sd, max(snapshot_date) AS last_sd
  FROM core.subscribed_search_term_daily_snapshot
  GROUP BY campaign_id, ad_group_id, search_term, stat_date
),
f AS (
  SELECT s.campaign_id, s.ad_group_id, s.search_term, s.stat_date, s.sales, s.roas, s.purchases
  FROM core.subscribed_search_term_daily_snapshot s
  JOIN snaps n ON n.campaign_id=s.campaign_id AND n.ad_group_id=s.ad_group_id
     AND n.search_term=s.search_term AND n.stat_date=s.stat_date AND s.snapshot_date=n.first_sd
),
l AS (
  SELECT s.campaign_id, s.ad_group_id, s.search_term, s.stat_date, s.sales, s.roas, s.purchases
  FROM core.subscribed_search_term_daily_snapshot s
  JOIN snaps n ON n.campaign_id=s.campaign_id AND n.ad_group_id=s.ad_group_id
     AND n.search_term=s.search_term AND n.stat_date=s.stat_date AND s.snapshot_date=n.last_sd
)
SELECT f.campaign_id, f.ad_group_id, f.search_term, f.stat_date, snaps.first_sd, snaps.last_sd,
       f.sales AS sales_first, l.sales AS sales_last,
       (l.sales - f.sales) AS sales_delta,
       CASE WHEN f.sales > 0 THEN round((l.sales - f.sales) / f.sales * 100, 2) ELSE NULL END AS sales_drift_pct,
       f.roas AS roas_first, l.roas AS roas_last,
       round((l.roas - f.roas)::numeric, 4) AS roas_delta,
       (l.purchases - f.purchases) AS purchases_delta
FROM snaps JOIN f USING (campaign_id, ad_group_id, search_term, stat_date)
JOIN l USING (campaign_id, ad_group_id, search_term, stat_date)
WHERE f.sales <> l.sales OR f.roas <> l.roas OR f.purchases <> l.purchases;

-- ============ 2c. 归因漂移 —— product 层级(产品线广告单/自然单研究) ============
DROP VIEW IF EXISTS core.v_attribution_drift_product CASCADE;
CREATE VIEW core.v_attribution_drift_product AS
WITH snaps AS (
  SELECT campaign_id, ad_group_id, advertised_product_id, stat_date,
         min(snapshot_date) AS first_sd, max(snapshot_date) AS last_sd
  FROM core.subscribed_product_daily_snapshot
  GROUP BY campaign_id, ad_group_id, advertised_product_id, stat_date
),
f AS (
  SELECT s.campaign_id, s.ad_group_id, s.advertised_product_id, s.stat_date, s.sales, s.roas, s.purchases
  FROM core.subscribed_product_daily_snapshot s
  JOIN snaps n ON n.campaign_id=s.campaign_id AND n.ad_group_id=s.ad_group_id
     AND n.advertised_product_id=s.advertised_product_id AND n.stat_date=s.stat_date AND s.snapshot_date=n.first_sd
),
l AS (
  SELECT s.campaign_id, s.ad_group_id, s.advertised_product_id, s.stat_date, s.sales, s.roas, s.purchases
  FROM core.subscribed_product_daily_snapshot s
  JOIN snaps n ON n.campaign_id=s.campaign_id AND n.ad_group_id=s.ad_group_id
     AND n.advertised_product_id=s.advertised_product_id AND n.stat_date=s.stat_date AND s.snapshot_date=n.last_sd
)
SELECT f.campaign_id, f.ad_group_id, f.advertised_product_id, f.stat_date, snaps.first_sd, snaps.last_sd,
       f.sales AS sales_first, l.sales AS sales_last,
       (l.sales - f.sales) AS sales_delta,
       CASE WHEN f.sales > 0 THEN round((l.sales - f.sales) / f.sales * 100, 2) ELSE NULL END AS sales_drift_pct,
       f.roas AS roas_first, l.roas AS roas_last,
       round((l.roas - f.roas)::numeric, 4) AS roas_delta,
       (l.purchases - f.purchases) AS purchases_delta
FROM snaps JOIN f USING (campaign_id, ad_group_id, advertised_product_id, stat_date)
JOIN l USING (campaign_id, ad_group_id, advertised_product_id, stat_date)
WHERE f.sales <> l.sales OR f.roas <> l.roas OR f.purchases <> l.purchases;
