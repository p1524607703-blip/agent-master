\o sql/create_snapshot_extra.sql
WITH facts(t) AS (VALUES
  ('subscribed_search_term_daily'),
  ('subscribed_placement_daily'),
  ('subscribed_product_cpo_daily')
),
pkcols AS (
  SELECT i.indrelid::regclass::text AS tname, a.attname
  FROM pg_index i
  JOIN pg_attribute a ON a.attrelid=i.indrelid AND a.attnum=ANY(i.indkey)
  WHERE i.indisprimary
)
SELECT
  'CREATE TABLE core.' || f.t || '_snapshot (' || E'\n'
  || '  snapshot_date date NOT NULL,' || E'\n'
  || '  run_id uuid NOT NULL,' || E'\n'
  || string_agg(
       '  ' || c.column_name || ' ' ||
       CASE c.data_type
         WHEN 'character' THEN 'char('||c.character_maximum_length||')'
         WHEN 'character varying' THEN 'varchar('||c.character_maximum_length||')'
         WHEN 'timestamp with time zone' THEN 'timestamptz'
         WHEN 'numeric' THEN 'numeric('||c.numeric_precision||','||c.numeric_scale||')'
         WHEN 'ARRAY' THEN 'text'
         ELSE c.data_type END ||
       CASE WHEN pk.attname IS NOT NULL THEN ' NOT NULL' ELSE '' END,
       ',' || E'\n')
  || E'\n  PRIMARY KEY (snapshot_date, ' || string_agg(pk.attname, ', ') || ')' || E'\n);'
  || E'\n'
FROM facts f
JOIN information_schema.columns c
  ON c.table_schema='core' AND c.table_name=f.t
LEFT JOIN pkcols pk
  ON pk.tname='core.'||f.t AND pk.attname=c.column_name
WHERE c.column_name NOT IN ('source_file_name','source_file_hash','imported_at')
GROUP BY f.t
ORDER BY f.t;
\o
