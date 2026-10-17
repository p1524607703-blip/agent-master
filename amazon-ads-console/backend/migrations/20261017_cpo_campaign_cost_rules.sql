CREATE TABLE IF NOT EXISTS ops_products.cpo_campaign_cost_rules (
 rule_id bigserial PRIMARY KEY,
 account_name text NOT NULL CHECK(account_name<>''),
 campaign_id text NOT NULL CHECK(campaign_id<>''),
 ad_product text NOT NULL CHECK(ad_product='Sponsored Brands'),
 expected_campaign_name text NOT NULL CHECK(expected_campaign_name<>''),
 business_account text NOT NULL CHECK(business_account<>''),
 operator_group text NOT NULL CHECK(operator_group ~ '^[A-Z]{2}[0-9]+$'),
 product_code text NOT NULL CHECK(product_code<>''),
 parent_asin text NOT NULL CHECK(parent_asin ~ '^B[A-Z0-9]{9}$'),
 allowed_source_products text[] NOT NULL CHECK(cardinality(allowed_source_products)>0),
 allocation_mode text NOT NULL DEFAULT 'campaign_owner' CHECK(allocation_mode='campaign_owner'),
 valid_from date NOT NULL,
 valid_to date,
 confirmation_source text NOT NULL CHECK(confirmation_source<>''),
 evidence jsonb NOT NULL,
 active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(valid_to IS NULL OR valid_to>=valid_from),
 UNIQUE(account_name,campaign_id,ad_product,valid_from)
);
COMMENT ON TABLE ops_products.cpo_campaign_cost_rules IS 'Confirmed campaign accounting owner; never changes advertised/purchased ASIN identity or business units. Date, account, ad-product and source-pool guarded.';
GRANT SELECT ON ops_products.cpo_campaign_cost_rules TO ads_readonly;
