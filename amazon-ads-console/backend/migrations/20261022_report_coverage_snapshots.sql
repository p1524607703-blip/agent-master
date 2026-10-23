-- Apply to amazon_ads_v2 (the warehouse), using the migration owner.
-- The HTTP runtime only needs SELECT; the scheduled maintenance user needs
-- SELECT/INSERT/UPDATE on this table plus SELECT on the six source fact tables.
BEGIN;
CREATE TABLE IF NOT EXISTS core.report_coverage_snapshots (
    table_name text PRIMARY KEY CHECK (table_name IN (
        'core.report_campaign_daily','core.report_placement_daily',
        'core.report_targeting_daily','core.report_advertised_product_daily',
        'core.report_purchased_product_daily','core.report_search_term_daily'
    )),
    snapshot_version integer NOT NULL DEFAULT 1,
    source_revision_at_refresh bigint NOT NULL DEFAULT 0,
    payload jsonb CHECK (payload IS NULL OR jsonb_typeof(payload)='array'),
    snapshot_at timestamptz,
    refresh_state text NOT NULL CHECK (refresh_state IN ('PENDING','REFRESHING','READY','FAILED')),
    refresh_started_at timestamptz,
    refresh_finished_at timestamptz,
    error_code text CHECK (error_code IN ('QUERY_TIMEOUT','REFRESH_FAILED')),
    CHECK ((payload IS NULL) = (snapshot_at IS NULL))
);
COMMENT ON TABLE core.report_coverage_snapshots IS
    'Exact current fact coverage, refreshed outside HTTP requests. Import counts are never fact counts.';
-- Environments may provide one or both existing HTTP query roles. Snapshot
-- maintenance runs as the migration owner; neither API role needs write access.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ads_readonly') THEN
        GRANT SELECT ON core.report_coverage_snapshots TO ads_readonly;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='amazon_ads_admin') THEN
        GRANT SELECT ON core.report_coverage_snapshots TO amazon_ads_admin;
    END IF;
END $$;
COMMIT;
