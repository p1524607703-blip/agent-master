"""应用库（amazon_ads）查询通道。

分工：
  - 应用库 amazon_ads：iam.*（身份与角色/会话）、app.*（主数据，如 product_roster）
  - 数据仓库 amazon_ads_v2：core.report_*_daily（广告活动事实）

两库在同一个 PostgreSQL 实例上但**不能跨库 JOIN**，所以走两条独立连接。
环境变量由 run_rds.py 导出：PG*（本模块用）/ RDS_PG*（rds_query.py 用）。
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any, Optional

_PREFIX = "PG"


def _setting(name: str) -> str:
    key = f"{_PREFIX}{name}"
    value = os.environ.get(key)
    if not value:
        raise RuntimeError(f"{key} is not configured; start the backend with run_rds.py")
    return value


def _run(sql: str) -> str:
    proc = subprocess.run(
        ["psql", "-h", _setting("HOST"), "-p", _setting("PORT"),
         "-U", _setting("USER"), "-d", _setting("DATABASE"),
         "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() if proc.stderr else "app db query failed")
    return proc.stdout.strip()


def query_rows(sql: str) -> list[dict[str, Any]]:
    body = sql.strip().rstrip(";")
    out = _run("SELECT COALESCE(json_agg(row_to_json(q)), '[]'::json)::text FROM (" + body + ") q;")
    return json.loads(out or "[]")


def query_one(sql: str) -> Optional[dict[str, Any]]:
    rows = query_rows(sql)
    return rows[0] if rows else None


def ping() -> bool:
    return _run("SELECT 1;") == "1"
