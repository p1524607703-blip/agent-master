-- Restore the exact pre-change view definitions; confirmation evidence is retained.
DO $restore$ DECLARE r record; BEGIN FOR r IN SELECT identity_key,payload->>'definition' definition FROM ops_products.cpo_fix_backup_20261017 WHERE kind='view_definition' LOOP EXECUTE format('CREATE OR REPLACE VIEW ops_products.%I AS %s',r.identity_key,r.definition); END LOOP; END $restore$;
