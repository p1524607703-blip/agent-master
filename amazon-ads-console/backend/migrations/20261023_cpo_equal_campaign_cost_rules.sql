-- Schema only. Actual campaign targets require separately recorded approval.
BEGIN;
SET LOCAL lock_timeout='3s';
SET LOCAL statement_timeout='15s';
ALTER TABLE ops_products.cpo_campaign_cost_rules
 ADD COLUMN IF NOT EXISTS rule_config jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE ops_products.cpo_campaign_cost_rules
 DROP CONSTRAINT IF EXISTS cpo_campaign_cost_rules_allocation_mode_check;
ALTER TABLE ops_products.cpo_campaign_cost_rules
 ADD CONSTRAINT cpo_campaign_cost_rules_allocation_mode_check
 CHECK (allocation_mode IN ('campaign_owner','multi_owner_equal'));
ALTER TABLE ops_products.cpo_campaign_cost_rules
 DROP CONSTRAINT IF EXISTS cpo_campaign_cost_rules_rule_config_check;
ALTER TABLE ops_products.cpo_campaign_cost_rules
 ADD CONSTRAINT cpo_campaign_cost_rules_rule_config_check
 CHECK (jsonb_typeof(rule_config)='object' AND
   (allocation_mode='campaign_owner' OR
     (jsonb_typeof(rule_config->'targets')='array' AND
      jsonb_array_length(rule_config->'targets') BETWEEN 2 AND 20) IS TRUE));
COMMENT ON COLUMN ops_products.cpo_campaign_cost_rules.rule_config IS
 'Approved name-mode SB accounting targets. Equal mode requires unique same-group maintained targets, weight=1; application validates exact name, scope, dates and source pool. Does not change ASIN identities or business orders.';
COMMIT;
