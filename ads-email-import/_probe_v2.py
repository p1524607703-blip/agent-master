import subprocess, os, sys
from pathlib import Path
from urllib.parse import urlsplit
line = [l for l in open('/Users/panjinlong/Documents/agent-master/amazon-ads-console/backend/.env') if l.startswith('DATABASE_URL=')][0]
u = urlsplit(line.strip().split('=',1)[1])
DB = os.environ.get('DBNAME', 'amazon_ads_v2')
env = dict(os.environ)
env.update(PGHOST=u.hostname, PGPORT='5432', PGUSER=u.username.split(':')[0],
           PGDATABASE=DB, PGPASSWORD=u.password or '',
           PGSSLMODE='verify-full',
           PGSSLROOTCERT=str(Path.home()/'.postgresql'/'root.crt'), PGCONNECT_TIMEOUT='15')
def q(sql, title='', timeout=180):
    r = subprocess.run(['psql','-w','-X','-q','-t','-A','-F','|','-c',sql], env=env, capture_output=True, text=True, timeout=timeout)
    if title: print(f"### {title}")
    print(r.stdout.strip() or r.stderr.strip()[:400]); print()
