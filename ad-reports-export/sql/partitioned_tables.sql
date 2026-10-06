-- 按 account_id LIST 分区的 5 事实表 + 5 快照表
-- 生成器: gen_partitioned_ddl.py (列定义导入 loader, 防漂移)

DROP TABLE IF EXISTS core.subscribed_campaign_daily CASCADE;
CREATE TABLE core.subscribed_campaign_daily (
  account_id text, account_name text, manager_account text, ad_product text, campaign_id text, campaign_name text, global_campaign_id text, budget_currency text, stat_date date, impressions numeric, viewable_impressions numeric, clicks numeric, ctr_pct numeric, vctr_pct numeric, cost numeric, purchases numeric, new_to_brand_purchases numeric, cost_per_purchase numeric, new_to_brand_cost_per_purchase numeric, sales numeric, long_term_sales numeric, roas numeric, long_term_roas numeric, source_file_name text, source_file_hash text,
  PRIMARY KEY (account_id, campaign_id, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_campaign_daily_p_chuanpeng PARTITION OF core.subscribed_campaign_daily FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_campaign_daily_p_oudesi PARTITION OF core.subscribed_campaign_daily FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_campaign_daily_p_jieboli PARTITION OF core.subscribed_campaign_daily FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_campaign_daily_p_ams PARTITION OF core.subscribed_campaign_daily FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_campaign_daily_p_default PARTITION OF core.subscribed_campaign_daily DEFAULT;

DROP TABLE IF EXISTS core.subscribed_placement_daily CASCADE;
CREATE TABLE core.subscribed_placement_daily (
  budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, placement text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric, source_file_name text, source_file_hash text,
  PRIMARY KEY (account_id, campaign_id, ad_group_id, placement, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_placement_daily_p_chuanpeng PARTITION OF core.subscribed_placement_daily FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_placement_daily_p_oudesi PARTITION OF core.subscribed_placement_daily FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_placement_daily_p_jieboli PARTITION OF core.subscribed_placement_daily FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_placement_daily_p_ams PARTITION OF core.subscribed_placement_daily FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_placement_daily_p_default PARTITION OF core.subscribed_placement_daily DEFAULT;

DROP TABLE IF EXISTS core.subscribed_search_term_daily CASCADE;
CREATE TABLE core.subscribed_search_term_daily (
  budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, search_term text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric, source_file_name text, source_file_hash text,
  PRIMARY KEY (account_id, campaign_id, ad_group_id, search_term, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_search_term_daily_p_chuanpeng PARTITION OF core.subscribed_search_term_daily FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_search_term_daily_p_oudesi PARTITION OF core.subscribed_search_term_daily FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_search_term_daily_p_jieboli PARTITION OF core.subscribed_search_term_daily FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_search_term_daily_p_ams PARTITION OF core.subscribed_search_term_daily FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_search_term_daily_p_default PARTITION OF core.subscribed_search_term_daily DEFAULT;

DROP TABLE IF EXISTS core.subscribed_product_daily CASCADE;
CREATE TABLE core.subscribed_product_daily (
  budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, advertised_product_id text, advertised_product_name text, advertised_product_parent_id text, advertised_product_brand text, advertised_product_category text, advertised_product_subcategory text, advertised_product_group text, advertised_product_sku text, advertised_product_marketplace text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric, source_file_name text, source_file_hash text,
  PRIMARY KEY (account_id, campaign_id, ad_group_id, advertised_product_id, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_product_daily_p_chuanpeng PARTITION OF core.subscribed_product_daily FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_product_daily_p_oudesi PARTITION OF core.subscribed_product_daily FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_product_daily_p_jieboli PARTITION OF core.subscribed_product_daily FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_product_daily_p_ams PARTITION OF core.subscribed_product_daily FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_product_daily_p_default PARTITION OF core.subscribed_product_daily DEFAULT;

DROP TABLE IF EXISTS core.subscribed_product_cpo_daily CASCADE;
CREATE TABLE core.subscribed_product_cpo_daily (
  budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, advertised_product_id text, advertised_product_name text, advertised_product_parent_id text, advertised_product_brand text, advertised_product_category text, advertised_product_subcategory text, advertised_product_group text, advertised_product_sku text, advertised_product_marketplace text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric, source_file_name text, source_file_hash text,
  PRIMARY KEY (account_id, campaign_id, ad_group_id, advertised_product_id, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_product_cpo_daily_p_chuanpeng PARTITION OF core.subscribed_product_cpo_daily FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_product_cpo_daily_p_oudesi PARTITION OF core.subscribed_product_cpo_daily FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_product_cpo_daily_p_jieboli PARTITION OF core.subscribed_product_cpo_daily FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_product_cpo_daily_p_ams PARTITION OF core.subscribed_product_cpo_daily FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_product_cpo_daily_p_default PARTITION OF core.subscribed_product_cpo_daily DEFAULT;

DROP TABLE IF EXISTS core.subscribed_campaign_daily_snapshot CASCADE;
CREATE TABLE core.subscribed_campaign_daily_snapshot (
  snapshot_date date, run_id text, account_id text, account_name text, manager_account text, ad_product text, campaign_id text, campaign_name text, global_campaign_id text, budget_currency text, stat_date date, impressions numeric, viewable_impressions numeric, clicks numeric, ctr_pct numeric, vctr_pct numeric, cost numeric, purchases numeric, new_to_brand_purchases numeric, cost_per_purchase numeric, new_to_brand_cost_per_purchase numeric, sales numeric, long_term_sales numeric, roas numeric, long_term_roas numeric,
  PRIMARY KEY (snapshot_date, account_id, campaign_id, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_campaign_daily_snapshot_p_chuanpeng PARTITION OF core.subscribed_campaign_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_campaign_daily_snapshot_p_oudesi PARTITION OF core.subscribed_campaign_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_campaign_daily_snapshot_p_jieboli PARTITION OF core.subscribed_campaign_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_campaign_daily_snapshot_p_ams PARTITION OF core.subscribed_campaign_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_campaign_daily_snapshot_p_default PARTITION OF core.subscribed_campaign_daily_snapshot DEFAULT;

DROP TABLE IF EXISTS core.subscribed_product_daily_snapshot CASCADE;
CREATE TABLE core.subscribed_product_daily_snapshot (
  snapshot_date date, run_id text, budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, advertised_product_id text, advertised_product_name text, advertised_product_parent_id text, advertised_product_brand text, advertised_product_category text, advertised_product_subcategory text, advertised_product_group text, advertised_product_sku text, advertised_product_marketplace text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric,
  PRIMARY KEY (snapshot_date, account_id, campaign_id, ad_group_id, advertised_product_id, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_product_daily_snapshot_p_chuanpeng PARTITION OF core.subscribed_product_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_product_daily_snapshot_p_oudesi PARTITION OF core.subscribed_product_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_product_daily_snapshot_p_jieboli PARTITION OF core.subscribed_product_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_product_daily_snapshot_p_ams PARTITION OF core.subscribed_product_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_product_daily_snapshot_p_default PARTITION OF core.subscribed_product_daily_snapshot DEFAULT;

DROP TABLE IF EXISTS core.subscribed_search_term_daily_snapshot CASCADE;
CREATE TABLE core.subscribed_search_term_daily_snapshot (
  snapshot_date date, run_id text, budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, search_term text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric,
  PRIMARY KEY (snapshot_date, account_id, campaign_id, ad_group_id, search_term, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_search_term_daily_snapshot_p_chuanpeng PARTITION OF core.subscribed_search_term_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_search_term_daily_snapshot_p_oudesi PARTITION OF core.subscribed_search_term_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_search_term_daily_snapshot_p_jieboli PARTITION OF core.subscribed_search_term_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_search_term_daily_snapshot_p_ams PARTITION OF core.subscribed_search_term_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_search_term_daily_snapshot_p_default PARTITION OF core.subscribed_search_term_daily_snapshot DEFAULT;

DROP TABLE IF EXISTS core.subscribed_placement_daily_snapshot CASCADE;
CREATE TABLE core.subscribed_placement_daily_snapshot (
  snapshot_date date, run_id text, budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, placement text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric,
  PRIMARY KEY (snapshot_date, account_id, campaign_id, ad_group_id, placement, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_placement_daily_snapshot_p_chuanpeng PARTITION OF core.subscribed_placement_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_placement_daily_snapshot_p_oudesi PARTITION OF core.subscribed_placement_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_placement_daily_snapshot_p_jieboli PARTITION OF core.subscribed_placement_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_placement_daily_snapshot_p_ams PARTITION OF core.subscribed_placement_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_placement_daily_snapshot_p_default PARTITION OF core.subscribed_placement_daily_snapshot DEFAULT;

DROP TABLE IF EXISTS core.subscribed_product_cpo_daily_snapshot CASCADE;
CREATE TABLE core.subscribed_product_cpo_daily_snapshot (
  snapshot_date date, run_id text, budget_currency text, account_id text, account_name text, portfolio_id text, portfolio_name text, campaign_id text, campaign_name text, ad_group_id text, ad_group_name text, advertised_product_id text, advertised_product_name text, advertised_product_parent_id text, advertised_product_brand text, advertised_product_category text, advertised_product_subcategory text, advertised_product_group text, advertised_product_sku text, advertised_product_marketplace text, stat_date date, impressions numeric, clicks numeric, ctr_pct numeric, cost numeric, purchases numeric, sales numeric, units numeric, cost_per_purchase numeric, purchase_rate_pct numeric, roas numeric, promoted_purchases numeric, promoted_sales numeric, promoted_units numeric, promoted_cost_per_purchase numeric, promoted_purchase_rate_pct numeric, promoted_roas numeric, halo_purchases numeric, halo_sales numeric, halo_units numeric, new_to_brand_purchases numeric, new_to_brand_sales numeric, new_to_brand_units numeric, new_to_brand_cost_per_purchase numeric, new_to_brand_purchase_rate_pct numeric, new_to_brand_roas numeric, detail_page_views numeric, cost_per_detail_page_view numeric, detail_page_view_rate_pct numeric,
  PRIMARY KEY (snapshot_date, account_id, campaign_id, ad_group_id, advertised_product_id, stat_date)
) PARTITION BY LIST (account_id);
CREATE TABLE core.subscribed_product_cpo_daily_snapshot_p_chuanpeng PARTITION OF core.subscribed_product_cpo_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh');
CREATE TABLE core.subscribed_product_cpo_daily_snapshot_p_oudesi PARTITION OF core.subscribed_product_cpo_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919');
CREATE TABLE core.subscribed_product_cpo_daily_snapshot_p_jieboli PARTITION OF core.subscribed_product_cpo_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh');
CREATE TABLE core.subscribed_product_cpo_daily_snapshot_p_ams PARTITION OF core.subscribed_product_cpo_daily_snapshot FOR VALUES IN ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz');
CREATE TABLE core.subscribed_product_cpo_daily_snapshot_p_default PARTITION OF core.subscribed_product_cpo_daily_snapshot DEFAULT;
