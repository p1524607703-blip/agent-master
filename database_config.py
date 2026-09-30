"""Shared database defaults for standalone report importers."""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit


def configure_warehouse_env():
    path = Path(__file__).resolve().parent / 'amazon-ads-console' / 'backend' / '.env'
    values = dict(line.split('=', 1) for line in path.read_text().splitlines()
                  if '=' in line and not line.startswith('#')) if path.exists() else {}
    raw = os.environ.get('RDS_DATABASE_URL') or values.get('RDS_DATABASE_URL')
    if not raw:
        raise RuntimeError('RDS_DATABASE_URL is required for report imports')
    parsed = urlsplit(raw.strip().strip('"').strip("'"))
    query = parse_qs(parsed.query)
    defaults = {'PGHOST': parsed.hostname, 'PGPORT': str(parsed.port or 15432),
                'PGUSER': unquote(parsed.username or ''), 'PGPASSWORD': unquote(parsed.password or ''),
                'PGDB': parsed.path.lstrip('/'), 'PGSSLMODE': query.get('sslmode', ['disable'])[-1]}
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    if query.get('sslrootcert'):
        os.environ.setdefault('PGSSLROOTCERT', query['sslrootcert'][-1])
    else:
        # 2026-09-30 起走本机 SSH 隧道连接腾讯云 PostgreSQL，外层已加密，
        # 旧阿里云 CA（~/.postgresql/root.crt）不再适用，避免残留变量干扰。
        os.environ.pop('PGSSLROOTCERT', None)
