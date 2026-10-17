-- Run explicitly with the approved database administrator channel.
-- Source confirmation records are operational data and are loaded separately.
SELECT pg_advisory_xact_lock(hashtext('cpo_identity_v2_20261017'));
CREATE TABLE IF NOT EXISTS ops_products.cpo_fix_backup_20261017(kind text NOT NULL,identity_key text NOT NULL,payload jsonb NOT NULL,saved_at timestamptz NOT NULL DEFAULT now(),PRIMARY KEY(kind,identity_key));
INSERT INTO ops_products.cpo_fix_backup_20261017(kind,identity_key,payload)
SELECT 'view_definition',viewname,jsonb_build_object('definition',definition) FROM pg_views WHERE schemaname='ops_products' AND viewname IN ('child_asin_mapping','product_mapping','product_ownership','product_roster') ON CONFLICT DO NOTHING;
INSERT INTO ops_products.cpo_fix_backup_20261017(kind,identity_key,payload)
SELECT 'child',account_scope||'|'||child_asin,to_jsonb(m) FROM ops_products.child_asin_mapping m ON CONFLICT DO NOTHING;
INSERT INTO ops_products.cpo_fix_backup_20261017(kind,identity_key,payload)
SELECT 'parent',parent_asin,to_jsonb(m) FROM ops_products.product_mapping m ON CONFLICT DO NOTHING;
INSERT INTO ops_products.cpo_fix_backup_20261017(kind,identity_key,payload)
SELECT 'ownership',concat_ws('|',brand,product_code,parent_asin),to_jsonb(m) FROM ops_products.product_ownership m ON CONFLICT DO NOTHING;
INSERT INTO ops_products.cpo_fix_backup_20261017(kind,identity_key,payload)
SELECT 'roster',roster_id::text,to_jsonb(m) FROM ops_products.product_roster m ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS ops_products.confirmed_sku_registry(
 child_asin text PRIMARY KEY CHECK(child_asin ~ '^B[A-Z0-9]{9}$'),source_sku text NOT NULL,operator_group text NOT NULL CHECK(operator_group ~ '^[A-Z]{2}[0-9]+$'),source_product_code text NOT NULL,canonical_product_code text NOT NULL,source_row integer NOT NULL,source_file_hash text NOT NULL,source_file text NOT NULL,source_sheet text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS ops_products.child_identity_overrides(LIKE ops_product_ref.child_asin_mapping INCLUDING DEFAULTS,PRIMARY KEY(account_scope,child_asin));
CREATE TABLE IF NOT EXISTS ops_products.parent_identity_overrides(LIKE ops_product_ref.product_mapping INCLUDING DEFAULTS,PRIMARY KEY(parent_asin));
CREATE TABLE IF NOT EXISTS ops_products.ownership_additions(LIKE ops_product_ref.product_ownership INCLUDING DEFAULTS,PRIMARY KEY(brand,product_code,parent_asin));
CREATE TABLE IF NOT EXISTS ops_products.roster_additions(LIKE ops_product_ref.product_roster INCLUDING DEFAULTS,PRIMARY KEY(roster_id));
GRANT SELECT ON ops_products.confirmed_sku_registry,ops_products.child_identity_overrides,ops_products.parent_identity_overrides,ops_products.ownership_additions,ops_products.roster_additions TO ads_readonly;
SELECT kind,count(*) rows FROM ops_products.cpo_fix_backup_20261017 GROUP BY kind ORDER BY kind;

-- The source SKU registry does not supply these optional catalog attributes.
ALTER TABLE ops_products.roster_additions ALTER COLUMN category DROP NOT NULL,ALTER COLUMN size_range DROP NOT NULL,ALTER COLUMN factory DROP NOT NULL,ALTER COLUMN in_stock DROP NOT NULL,ALTER COLUMN row_hash DROP NOT NULL;
CREATE OR REPLACE VIEW ops_products.child_asin_mapping AS
SELECT * FROM ops_products.child_identity_overrides
UNION ALL SELECT b.* FROM ops_product_ref.child_asin_mapping b
WHERE NOT EXISTS(SELECT 1 FROM ops_products.child_identity_overrides o WHERE o.account_scope=b.account_scope AND o.child_asin=b.child_asin);
CREATE OR REPLACE VIEW ops_products.product_mapping AS
SELECT * FROM ops_products.parent_identity_overrides
UNION ALL SELECT b.* FROM ops_product_ref.product_mapping b
WHERE NOT EXISTS(SELECT 1 FROM ops_products.parent_identity_overrides o WHERE o.parent_asin=b.parent_asin);
CREATE OR REPLACE VIEW ops_products.product_ownership AS
SELECT * FROM ops_products.ownership_additions
UNION ALL SELECT b.* FROM ops_product_ref.product_ownership b
WHERE NOT EXISTS(SELECT 1 FROM ops_products.ownership_additions o WHERE o.brand=b.brand AND o.product_code=b.product_code AND o.parent_asin=b.parent_asin);
CREATE OR REPLACE VIEW ops_products.product_roster AS
SELECT * FROM ops_products.roster_additions
UNION ALL SELECT b.* FROM ops_product_ref.product_roster b
WHERE NOT EXISTS(SELECT 1 FROM ops_products.roster_additions o WHERE o.brand=b.brand AND o.product_code=b.product_code AND o.parent_asin=b.parent_asin AND o.owner_group=b.owner_group);
