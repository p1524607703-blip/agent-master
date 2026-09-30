"""数据仓库（amazon_ads_v2）查询通道。

注意：这里连的是**数据仓库**，不是应用库。
  - 应用库 amazon_ads（iam.* 身份与角色）由 app/services/auth.py 用 asyncpg 直连
  - 数据仓库 amazon_ads_v2（core.report_*_daily）由本模块用 psql 子进程访问
两组 PG 环境变量由 run_rds.py 分别导出：PG* / RDS_PG*，本模块只读 RDS_PG*。
"""
import json
import os
import subprocess
from typing import Any, Optional

_PREFIX = "RDS_PG"


def _pg_setting(name: str) -> str:
    key = f"{_PREFIX}{name}"
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"{key} is not configured; start the backend with run_rds.py")
    return value


def _run(sql: str) -> str:
    env = os.environ.copy()
    for key in ('PASSWORD', 'SSLMODE', 'SSLROOTCERT'):
        value = env.get(f'RDS_PG{key}')
        if value is not None:
            env[f'PG{key}'] = value
        else:
            env.pop(f'PG{key}', None)
    proc = subprocess.run(
        ['psql', '-h', _pg_setting('HOST'), '-p', _pg_setting('PORT'),
         '-U', _pg_setting('USER'), '-d', _pg_setting('DATABASE'),
         '-X', '-q', '-t', '-A', '-v', 'ON_ERROR_STOP=1', '-c', sql],
        env=env, capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() if proc.stderr else 'RDS query failed')
    return proc.stdout.strip()


def query_rows(sql: str) -> list[dict[str, Any]]:
    body = sql.strip().rstrip(';')
    wrapped = "SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json)::text FROM (" + body + ") q;"
    out = _run(wrapped)
    return json.loads(out or '[]')


def query_one(sql: str) -> Optional[dict[str, Any]]:
    rows = query_rows(sql)
    return rows[0] if rows else None



def mutate_rows(sql: str) -> list[dict[str, Any]]:
    """Execute INSERT/UPDATE/DELETE ... RETURNING and return JSON rows.

    Data-modifying CTE must remain top-level in PostgreSQL, so this intentionally
    does not reuse query_rows(), which nests the SQL inside a subquery.
    """
    body = sql.strip().rstrip(';')
    wrapped = "WITH mutation AS (" + body + ") SELECT COALESCE(json_agg(row_to_json(mutation)), '[]'::json)::text FROM mutation;"
    out = _run(wrapped)
    return json.loads(out or '[]')


def mutate_one(sql: str) -> Optional[dict[str, Any]]:
    rows = mutate_rows(sql)
    return rows[0] if rows else None

def ping() -> bool:
    return _run('SELECT 1;') == '1'
