CREATE TABLE IF NOT EXISTS ops_products.full_funnel_visibility_policy (
 account_name text PRIMARY KEY CHECK(account_name<>''),
 brand_name text NOT NULL CHECK(brand_name<>''),
 access_scope text NOT NULL CHECK(access_scope IN ('all_operators','operator_groups')),
 allowed_groups text[] NOT NULL DEFAULT '{}',
 display_order smallint NOT NULL DEFAULT 0 CHECK(display_order>=0),
 is_active boolean NOT NULL DEFAULT true,
 confirmation_source text NOT NULL,
 evidence jsonb NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK(array_position(allowed_groups,NULL) IS NULL),
 CHECK(cardinality(allowed_groups)=0 OR array_to_string(allowed_groups,',') ~ '^[A-Z]{2}(,[A-Z]{2})*$'),
 CHECK((access_scope='all_operators' AND cardinality(allowed_groups)=0) OR (access_scope='operator_groups' AND cardinality(allowed_groups)>0))
);
COMMENT ON TABLE ops_products.full_funnel_visibility_policy IS 'Full-Funnel disclosure visibility by source account and brand. Management sees all; operator access must be evaluated from authenticated session on every response. Does not allocate expenses.';
GRANT SELECT ON ops_products.full_funnel_visibility_policy TO ads_readonly;