#!/usr/bin/env python3
"""共用的 RDS 连接助手。

默认连 **amazon_ads_v2**（真正有数据、且 amazon_ads_admin 是 owner 的那个库）。
用环境变量 DBNAME 可切换，例如 DBNAME=amazon_ads。
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

ENV_PATH = Path("/Users/panjinlong/Documents/agent-master/amazon-ads-console/backend/.env")
DEFAULT_DB = "amazon_ads_v2"


def pg_env(dbname: str | None = None) -> dict:
    values = dict(l.split('=', 1) for l in ENV_PATH.read_text().splitlines()
                  if '=' in l and not l.startswith('#'))
    url = values.get('RDS_DATABASE_URL') or values['DATABASE_URL']
    url = url.strip().strip('"').strip("'")
    u = urlsplit(url)
    query = parse_qs(u.query)
    env = dict(os.environ)
    env.update(
        PGHOST=u.hostname,
        PGPORT=str(u.port or 5432),
        PGUSER=unquote(u.username),
        PGDATABASE=dbname or os.environ.get("DBNAME") or DEFAULT_DB,
        PGPASSWORD=unquote(u.password or ""),
        PGSSLMODE=query.get('sslmode', ['disable'])[-1],  # 2026-09-30：迁腾讯云后走 SSH 隧道，库层不再套 TLS
        PGCONNECT_TIMEOUT="15",
    )
    env.pop('PGSSLROOTCERT', None)
    if query.get('sslrootcert'):
        env['PGSSLROOTCERT'] = query['sslrootcert'][-1]
    return env


def psql(sql: str, *, tuples_only: bool = True, timeout: int = 1800, dbname: str | None = None) -> str:
    cmd = ["psql", "-w", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-A", "-F", "|"]
    if tuples_only:
        cmd.append("-t")
    cmd += ["-c", sql]
    r = subprocess.run(cmd, env=pg_env(dbname), capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"psql failed:\n{r.stderr[:2000]}")
    return r.stdout


def psql_file(path: str | Path, timeout: int = 900, dbname: str | None = None) -> str:
    r = subprocess.run(
        ["psql", "-w", "-X", "-q", "-v", "ON_ERROR_STOP=1", "-f", str(path)],
        env=pg_env(dbname), capture_output=True, text=True, timeout=timeout,
    )
    if r.returncode != 0:
        raise RuntimeError(f"psql -f failed:\n{r.stderr[:2000]}")
    return r.stdout + r.stderr


if __name__ == "__main__":
    print(psql("select current_user, current_database(), version()"))
