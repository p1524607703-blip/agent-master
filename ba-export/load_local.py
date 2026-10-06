#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 1: 把紫鸟下载目录里【已经下好】的 BA Week CSV 灌进 RDS, 成功后即删本地文件。
只匹配: *搜索目录绩效*Week_*.csv / *搜索查询绩效*Week_*.csv (严格排除 Month/Quarter 与其它报表)。
幂等: ba_to_rds.py 内部 ON CONFLICT DO NOTHING, 重跑不重复。
"""
import os, sys, subprocess, glob, datetime
from urllib.parse import urlsplit, unquote

DL = "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号"
LOADER = "/Users/panjinlong/Documents/agent-master/ba-export/ba_to_rds.py"
ENV_PATH = "/Users/panjinlong/Documents/agent-master/amazon-ads-console/backend/.env"

# 连接改为从 backend/.env 的 RDS_DATABASE_URL 读（数据仓库 amazon_ads_v2）。
# 2026-09-21：原为硬编码 PGPASSWORD='Root_1234' + 旧库 121.41.134.56（该机已整机退役），
#            且旧默认库名 amazon_ads 是 RBAC 库、根本没有 core.* 表。
def _init_env():
    """把 .env 里的 RDS_DATABASE_URL 拆成 PG* 环境变量，供 ba_to_rds.py 子进程继承。"""
    if not os.path.isfile(ENV_PATH):
        raise SystemExit(f'找不到 {ENV_PATH}')
    url = None
    for line in open(ENV_PATH, encoding='utf-8'):
        if line.startswith('RDS_DATABASE_URL='):
            url = line.split('=', 1)[1].strip()
            break
    if not url:
        raise SystemExit('backend/.env 里没有 RDS_DATABASE_URL')
    p = urlsplit(url)
    os.environ.setdefault('PGHOST', p.hostname or '')
    os.environ.setdefault('PGPORT', str(p.port or 5432))
    os.environ.setdefault('PGUSER', unquote(p.username or ''))
    os.environ.setdefault('PGPASSWORD', unquote(p.password or ''))
    os.environ.setdefault('PGDB', (p.path or '/').lstrip('/'))
    os.environ.setdefault('PGSSLMODE', 'verify-full')
    os.environ.setdefault('PGSSLROOTCERT', os.path.expanduser('~/.postgresql/root.crt'))


_init_env()
PGPASSWORD = os.environ.get('PGPASSWORD', '')  # 由 _init_env 注入，不再硬编码
BA_BRAND = os.environ.get('BA_BRAND', 'WHITIN')
BA_BATCH_ID = os.environ.get('BA_BATCH_ID', 'DRAIN_' + datetime.date.today().isoformat())

PATTERNS = ['*搜索目录绩效*Week_*.csv', '*搜索查询绩效*Week_*.csv']

def collect():
    files = set()
    for p in PATTERNS:
        files |= set(glob.glob(os.path.join(DL, p)))
        files |= set(glob.glob(os.path.join(DL, '搜索绩效查询', p)))
    return sorted(files)

def main():
    files = collect()
    print(f'找到 {len(files)} 个 BA Week CSV (batch={BA_BATCH_ID})')
    ok = fail = 0
    for f in files:
        env = os.environ.copy()
        env['PGPASSWORD'] = PGPASSWORD
        env['BA_BRAND'] = BA_BRAND
        env['BA_BATCH_ID'] = BA_BATCH_ID
        r = subprocess.run([sys.executable, LOADER, f], env=env,
                           capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
            print('  OK  ', r.stdout.strip().replace('\n', ' | '))
            os.remove(f)
            print('       DELETED', os.path.basename(f))
        else:
            fail += 1
            print('  FAIL', os.path.basename(f))
            print('       ', r.stderr.strip()[:400].replace('\n', ' '))
    print(f'=== Phase1 完成: 成功 {ok} / 失败 {fail} ===')

if __name__ == '__main__':
    main()
