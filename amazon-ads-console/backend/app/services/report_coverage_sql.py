"""Standard-library-only SQL contract shared by HTTP readers and maintenance."""

SNAPSHOT_TABLE = "core.report_coverage_snapshots"
SNAPSHOT_VERSION = 1
LOCK_NAME = "cpo_report_coverage_refresh_v1"
REPORT_SPECS = (
    ("广告活动", "core.report_campaign_daily", "spend"),
    ("广告位", "core.report_placement_daily", "spend"),
    ("投放", "core.report_targeting_daily", "spend"),
    ("推广的商品", "core.report_advertised_product_daily", "spend"),
    ("达成转化的商品", "core.report_purchased_product_daily", None),
    ("搜索词", "core.report_search_term_daily", "spend"),
)
TABLES = tuple(spec[1] for spec in REPORT_SPECS)


def exact_coverage_sql(table: str, source_name_not_null: bool) -> str:
    if table not in TABLES:
        raise ValueError("Unsupported report table")
    lineage = "count(*)::bigint" if source_name_not_null else "count(source_file_name)::bigint"
    return f"""
        WITH coverage AS (
            SELECT account_id,min(stat_date)::text AS min_date,max(stat_date)::text AS max_date,
                   count(*)::bigint AS rows,{lineage} AS lineage_rows
            FROM {table} GROUP BY account_id
        )
        SELECT coverage.*,latest.account_name FROM coverage
        LEFT JOIN LATERAL (
            SELECT account_name FROM {table} r WHERE r.account_id=coverage.account_id
            ORDER BY stat_date DESC, account_name LIMIT 1
        ) latest ON true ORDER BY coverage.account_id
    """


def maintenance_sql(tables=TABLES, *, force=False, statement_timeout_ms=300000, cooldown_seconds=900) -> str:
    """Build a single locked psql session; no runtime or third-party dependency.

    State writes commit around a bounded REPEATABLE READ transaction per table.
    Failed scans roll back and retain the old payload. All identifiers come from
    the fixed allowlist; limits are integers, never user SQL.
    """
    if not tables or not set(tables).issubset(TABLES):
        raise ValueError("Unsupported report table")
    if not 1000 <= statement_timeout_ms <= 600000 or not 60 <= cooldown_seconds <= 86400:
        raise ValueError("Invalid maintenance limits")
    script = [f"""
\\set ON_ERROR_STOP on
SET application_name='cpo-report-coverage-refresh';
SET statement_timeout='30s';
SET lock_timeout='2s';
SET max_parallel_workers_per_gather=0;
SET client_connection_check_interval='1s';
SELECT pg_try_advisory_lock(hashtext('{LOCK_NAME}')) AS coverage_locked \\gset
\\if :coverage_locked
CREATE TEMP TABLE coverage_run(table_name text PRIMARY KEY,outcome text);
"""]
    for table in dict.fromkeys(tables):
        script.append(f"""
SELECT ({'true' if force else 'false'} OR s.table_name IS NULL OR (
    (s.snapshot_version<>{SNAPSHOT_VERSION} OR s.snapshot_at IS NULL OR s.refresh_state<>'READY'
     OR s.source_revision_at_refresh<>r.revision)
    AND NOT (s.refresh_state IN ('FAILED','REFRESHING') AND
         COALESCE(s.refresh_finished_at,s.refresh_started_at)>
         clock_timestamp()-interval '{cooldown_seconds} seconds')
)) AS coverage_needed
FROM (SELECT COALESCE(max(batch_id),0)::bigint AS revision FROM core.import_batches
      WHERE target_table='{table}' AND import_status='success') r
LEFT JOIN {SNAPSHOT_TABLE} s ON s.table_name='{table}' \\gset
\\if :coverage_needed
INSERT INTO {SNAPSHOT_TABLE}(table_name,refresh_state,refresh_started_at)
VALUES('{table}','REFRESHING',clock_timestamp())
ON CONFLICT(table_name) DO UPDATE SET refresh_state='REFRESHING',
  refresh_started_at=clock_timestamp(),refresh_finished_at=NULL,error_code=NULL;
BEGIN ISOLATION LEVEL REPEATABLE READ;
SET LOCAL statement_timeout={statement_timeout_ms};
SELECT COALESCE((SELECT attnotnull FROM pg_catalog.pg_attribute
  WHERE attrelid='{table}'::regclass AND attname='source_file_name' AND NOT attisdropped),false)
  AS coverage_not_null \\gset
\\set ON_ERROR_STOP off
\\if :coverage_not_null
""")
        for i, constrained in enumerate((True, False)):
            if i:
                script.append("\\else\n")
            exact = exact_coverage_sql(table, constrained)
            script.append(f"""
UPDATE {SNAPSHOT_TABLE} SET
  payload=(SELECT COALESCE(jsonb_agg(row_to_json(q)),'[]'::jsonb) FROM ({exact}) q),
  source_revision_at_refresh=(SELECT COALESCE(max(batch_id),0)::bigint FROM core.import_batches
      WHERE target_table='{table}' AND import_status='success'),
  snapshot_version={SNAPSHOT_VERSION},snapshot_at=transaction_timestamp(),
  refresh_finished_at=clock_timestamp(),refresh_state='READY',error_code=NULL
WHERE table_name='{table}';
""")
        script.append(f"""
\\endif
\\if :ERROR
\\set coverage_error :SQLSTATE
ROLLBACK;
\\set ON_ERROR_STOP on
UPDATE {SNAPSHOT_TABLE} SET refresh_state='FAILED',refresh_finished_at=clock_timestamp(),
  error_code=CASE WHEN :'coverage_error'='57014' THEN 'QUERY_TIMEOUT' ELSE 'REFRESH_FAILED' END
WHERE table_name='{table}';
INSERT INTO coverage_run VALUES('{table}','FAILED');
\\else
\\set ON_ERROR_STOP on
COMMIT;
INSERT INTO coverage_run VALUES('{table}','READY');
\\endif
\\else
INSERT INTO coverage_run VALUES('{table}','SKIPPED');
\\endif
""")
    script.append(f"""
SELECT json_build_object('status',CASE WHEN bool_or(outcome='FAILED') THEN 'FAILED'
  WHEN bool_or(outcome='READY') THEN 'READY' ELSE 'UNCHANGED' END,
  'refreshed',COALESCE(json_agg(table_name) FILTER(WHERE outcome='READY'),'[]'::json),
  'failed',COALESCE(json_agg(table_name) FILTER(WHERE outcome='FAILED'),'[]'::json),
  'skipped',COALESCE(json_agg(table_name) FILTER(WHERE outcome='SKIPPED'),'[]'::json),
  'snapshot_count',(SELECT count(*) FROM {SNAPSHOT_TABLE} WHERE snapshot_at IS NOT NULL),
  'snapshots',(SELECT COALESCE(json_agg(row_to_json(summary)),'[]'::json) FROM (
      SELECT table_name,snapshot_version,source_revision_at_refresh,snapshot_at,refresh_state,
             CASE WHEN payload IS NULL THEN NULL ELSE jsonb_array_length(payload) END AS accounts,
             CASE WHEN payload IS NULL THEN NULL ELSE COALESCE(
               (SELECT sum((a->>'rows')::bigint) FROM jsonb_array_elements(payload) a),0) END AS rows
      FROM {SNAPSHOT_TABLE} ORDER BY table_name
  ) summary)) FROM coverage_run;
SELECT pg_advisory_unlock(hashtext('{LOCK_NAME}')) AS coverage_unlocked \\gset
\\else
SELECT '{{"status":"BUSY","refreshed":[],"failed":[],"skipped":[]}}'::json;
\\endif
""")
    return "\n".join(script)
