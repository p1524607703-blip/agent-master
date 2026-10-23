#!/usr/bin/env python3
"""Create a disposable Unix-socket-only PostgreSQL cluster; never load the production .env."""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pg-bin',required=True)
    parser.add_argument('--live-key-file',help='Explicit opt-in: one real model request with this private upstream key file')
    parser.add_argument('--live-base-url',default='')
    parser.add_argument('--receipt-file',help='Private output receipt for the explicit real-model test')
    args=parser.parse_args()
    if args.live_key_file and (not args.live_base_url or not args.receipt_file):
        parser.error('--live-key-file requires --live-base-url and --receipt-file')
    backend=Path(__file__).resolve().parents[1]
    pg=Path(args.pg_bin)
    with tempfile.TemporaryDirectory(prefix='cpo-xt-',dir='/tmp') as temporary:
        root=Path(temporary); data=root/'data'; socket=root/'socket'; socket.mkdir(mode=0o700)
        subprocess.run([str(pg/'initdb'),'-D',str(data),'-A','trust','-U','codex_test','--no-locale'],check=True,stdout=subprocess.DEVNULL)
        subprocess.run([str(pg/'pg_ctl'),'-D',str(data),'-l',str(root/'postgres.log'),'-o',f"-k {socket} -c listen_addresses='' -p 56389",'-w','start'],check=True,stdout=subprocess.DEVNULL)
        try:
            dsn=f'postgresql://codex_test@/postgres?host={socket}&port=56389'
            seed="""CREATE SCHEMA iam; CREATE TABLE iam.users(user_id bigint primary key,username text,display_name text,role_code text,status text);
INSERT INTO iam.users VALUES (1,'fixture_ai','Synthetic AI','ai','active');
CREATE SCHEMA codex_ops; CREATE VIEW codex_ops.personnel_roster AS SELECT *, 'ai'::text group_code,'AI test'::text group_name,'TEST'::text person_code FROM iam.users;"""
            subprocess.run([str(pg/'psql'),dsn,'-v','ON_ERROR_STOP=1','-q','-c',seed],check=True)
            subprocess.run([str(pg/'psql'),dsn,'-v','ON_ERROR_STOP=1','-q','-f',str(backend/'migrations/20261018_codex_device_telemetry.sql')],check=True)
            env_file=root/'isolated.env'
            env_file.write_text('DATABASE_URL='+dsn+'\nOPERATOR_WARMUP_ENABLED=false\n')
            env_file.chmod(0o600)
            env=os.environ.copy()
            for key in ['DATABASE_URL','RDS_DATABASE_URL','CPO_ENV_FILE','CODEX_TELEMETRY_ENABLED']:
                env.pop(key,None)
            env.update(CPO_ENV_FILE=str(env_file),CODEX_ISOLATED_DB_TEST='1')
            targets=['tests.test_codex_devices','tests.test_codex_telemetry','tests.test_codex_windows_handoff',
                     'tests.test_codex_compat','tests.test_codex_concurrent','tests.test_codex_gateway','tests.test_codex_control']
            if args.live_key_file:
                env.update(CODEX_LIVE_KEY_FILE=str(Path(args.live_key_file).resolve()),
                    CODEX_LIVE_BASE_URL=args.live_base_url,CODEX_LIVE_RECEIPT=str(Path(args.receipt_file).resolve()))
                targets=['tests.test_codex_telemetry.LiveProxyTests.test_live_model_accounting']
            result=subprocess.run([sys.executable,'-m','unittest',*targets,'-v'],cwd=backend,env=env)
            if result.returncode:raise SystemExit(result.returncode)
            print(json.dumps({'isolatedPostgres':True,'tcpListener':False,'realModelsInvoked':bool(args.live_key_file),'productionDatabaseTouched':False,'tests':'passed'}))
        finally:
            subprocess.run([str(pg/'pg_ctl'),'-D',str(data),'-m','fast','-w','stop'],check=True,stdout=subprocess.DEVNULL)


if __name__=='__main__':main()
