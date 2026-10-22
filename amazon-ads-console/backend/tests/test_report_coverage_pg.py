"""Real stdlib/psql path against an isolated, synthetic temporary PostgreSQL."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pytest

from app.services.report_coverage_sql import LOCK_NAME, TABLES

ROOT=Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def warehouse():
    if not all(shutil.which(name) for name in ("initdb","pg_ctl","psql")) or os.getuid()==0:
        pytest.skip("Temporary PostgreSQL binaries and non-root user required")
    with tempfile.TemporaryDirectory(prefix="cpo-coverage-pg-") as directory:
        directory=Path(directory);data=directory/"data";socket=directory/"socket";socket.mkdir()
        subprocess.run(["initdb","-D",str(data),"-A","trust","--no-locale","-E","UTF8"],capture_output=True,check=True)
        # No TCP listener or shared database: a unique private Unix socket only.
        subprocess.run(["pg_ctl","-D",str(data),"-l",str(directory/"postgres.log"),"-o",f"-k {socket} -c listen_addresses=''","-w","start"],capture_output=True,check=True)
        dsn=f"postgresql:///postgres?host={socket}"
        def sql(statement):
            return subprocess.run(["psql","--dbname",dsn,"-XqAt","-v","ON_ERROR_STOP=1"],input=statement,text=True,capture_output=True,check=True).stdout.strip()
        try:
            sql("CREATE SCHEMA core; CREATE TABLE core.import_batches(batch_id bigint,target_table text,import_status text,valid_row_count bigint);")
            sql("CREATE ROLE ads_readonly; CREATE ROLE amazon_ads_admin;")
            sql((ROOT/"migrations/20261022_report_coverage_snapshots.sql").read_text())
            for table in TABLES:
                constraint="" if table==TABLES[-1] else "NOT NULL"
                sql(f"CREATE TABLE {table}(account_id text,account_name text,stat_date date,source_file_name text {constraint});"
                    f"INSERT INTO {table} VALUES ('a','test-a','2026-09-01','f1'),('a','test-a','2026-10-19','f2'),('b','test-b','2026-10-20','f3');"
                    f"INSERT INTO core.import_batches VALUES(7,'{table}','success',999999);")
            sql(f"UPDATE {TABLES[-1]} SET source_file_name=NULL WHERE account_id='b';")
            yield dsn,sql
        finally:
            subprocess.run(["pg_ctl","-D",str(data),"-m","immediate","-w","stop"],capture_output=True,check=True)


def cli(dsn,*args):
    # -S excludes site-packages: exactly the dependency-free deployment path.
    run=subprocess.run([sys.executable,"-S",str(ROOT/"scripts/refresh_report_coverage.py"),"--dsn",dsn,*args],capture_output=True,text=True,timeout=20)
    return run.returncode,json.loads(run.stdout)


def test_real_bootstrap_exact_counts_revisions_nullable_lineage_and_unchanged_skip(warehouse):
    dsn,sql=warehouse
    for role in ("ads_readonly","amazon_ads_admin"):
        assert sql(f"SELECT has_table_privilege('{role}','core.report_coverage_snapshots','SELECT');")=="t"
        for privilege in ("INSERT","UPDATE","DELETE","TRUNCATE"):
            assert sql(f"SELECT has_table_privilege('{role}','core.report_coverage_snapshots','{privilege}');")=="f"
    code,result=cli(dsn)
    assert code==0 and result["status"]=="READY" and len(result["refreshed"])==6
    snapshots=json.loads(sql("SELECT json_agg(row_to_json(s)) FROM core.report_coverage_snapshots s;"))
    assert len(snapshots)==6
    for row in snapshots:
        assert row["source_revision_at_refresh"]==7
        assert sum(account["rows"] for account in row["payload"])==3
        assert row["payload"][0]["min_date"]=="2026-09-01"
        assert row["payload"][0]["max_date"]=="2026-10-19"
        expected=2 if row["table_name"]==TABLES[-1] else 3
        assert sum(account["lineage_rows"] for account in row["payload"])==expected
    before=sql("SELECT json_agg(snapshot_at ORDER BY table_name) FROM core.report_coverage_snapshots;")
    code,result=cli(dsn)
    assert code==0 and result["status"]=="UNCHANGED" and result["refreshed"]==[]
    assert before==sql("SELECT json_agg(snapshot_at ORDER BY table_name) FROM core.report_coverage_snapshots;")


def test_real_changed_revision_refreshes_only_changed_table_and_forced_bootstrap(warehouse):
    dsn,sql=warehouse;table=TABLES[0]
    sql(f"INSERT INTO {table} VALUES('a','test-a','2026-10-21','f4'); INSERT INTO core.import_batches VALUES(8,'{table}','success',888888);")
    code,result=cli(dsn)
    assert code==0 and result["refreshed"]==[table] and len(result["skipped"])==5
    assert sql(f"SELECT sum((a->>'rows')::bigint) FROM core.report_coverage_snapshots s,LATERAL jsonb_array_elements(s.payload) a WHERE s.table_name='{table}';")=="4"
    code,result=cli(dsn,"--force","--table",table)
    assert code==0 and result["refreshed"]==[table]


def test_real_scan_timeout_preserves_payload_then_backs_off_and_recovers(warehouse):
    dsn,sql=warehouse;table=TABLES[2];backup=table+"_test_original"
    original=sql(f"SELECT payload FROM core.report_coverage_snapshots WHERE table_name='{table}';")
    sql(f"ALTER TABLE {table} RENAME TO {backup.split('.')[1]};"
        "CREATE FUNCTION core.coverage_test_delay(text) RETURNS text LANGUAGE plpgsql AS $$ BEGIN PERFORM pg_sleep(2); RETURN $1; END $$;"
        f"CREATE VIEW {table} AS SELECT account_id,account_name,stat_date,core.coverage_test_delay(source_file_name) AS source_file_name FROM {backup};")
    try:
        code,result=cli(dsn,"--force","--table",table,"--statement-timeout-seconds","1")
        assert code==1 and result["failed"]==[table]
        assert sql(f"SELECT refresh_state||':'||error_code FROM core.report_coverage_snapshots WHERE table_name='{table}';")=="FAILED:QUERY_TIMEOUT"
        assert original==sql(f"SELECT payload FROM core.report_coverage_snapshots WHERE table_name='{table}';")
        code,result=cli(dsn,"--table",table)
        assert code==0 and result["status"]=="UNCHANGED" and result["skipped"]==[table]
    finally:
        sql(f"DROP VIEW {table}; ALTER TABLE {backup} RENAME TO {table.split('.')[1]}; DROP FUNCTION core.coverage_test_delay(text);")
    code,result=cli(dsn,"--force","--table",table)
    assert code==0 and result["refreshed"]==[table]


def test_real_distributed_lock_skips_competing_worker(warehouse):
    dsn,sql=warehouse
    lock=subprocess.Popen(["psql","--dbname",dsn,"-XqAt"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        lock.stdin.write(f"SELECT pg_advisory_lock(hashtext('{LOCK_NAME}'));\n\\echo acquired\n");lock.stdin.flush()
        while lock.stdout.readline().strip()!="acquired": pass
        code,result=cli(dsn,"--force")
        assert code==0 and result["status"]=="BUSY" and result["refreshed"]==[]
    finally:
        lock.stdin.close();lock.wait(timeout=5)
