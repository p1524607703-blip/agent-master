"""Local dev launcher: two DSNs — 应用库用于 auth，数据仓库用于业务查询。

应用库 amazon_ads：iam.* 身份与角色、会话
数据仓库 amazon_ads_v2：core.report_*_daily 广告活动事实表

PostgreSQL 不支持跨库 JOIN，因此导出两组 PG* 环境变量：
  PG*      → 应用库（auth）
  RDS_PG*  → 数据仓库（业务读，rds_query.py 只读这一组）
"""
import os
from urllib.parse import parse_qs, unquote, urlsplit

import uvicorn

from app.core.config import settings


def _configure_pg_env(database_url: str, prefix: str = "PG") -> None:
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgresql", "postgresql+asyncpg"}:
        raise RuntimeError("DATABASE_URL must use PostgreSQL")

    database = parsed.path.lstrip("/")
    if not parsed.hostname or not parsed.username or not database:
        raise RuntimeError("DATABASE_URL must include host, user, and database")

    os.environ[f"{prefix}HOST"] = parsed.hostname
    os.environ[f"{prefix}PORT"] = str(parsed.port or 5432)
    os.environ[f"{prefix}USER"] = unquote(parsed.username)
    os.environ[f"{prefix}DATABASE"] = unquote(database)

    if parsed.password is not None:
        os.environ[f"{prefix}PASSWORD"] = unquote(parsed.password)
    else:
        os.environ.pop(f"{prefix}PASSWORD", None)

    query = parse_qs(parsed.query)
    if query.get("sslmode"):
        os.environ[f"{prefix}SSLMODE"] = query["sslmode"][-1]
    else:
        os.environ.pop(f"{prefix}SSLMODE", None)
    if query.get("sslrootcert"):
        os.environ[f"{prefix}SSLROOTCERT"] = query["sslrootcert"][-1]
    else:
        os.environ.pop(f"{prefix}SSLROOTCERT", None)


_configure_pg_env(settings.database_url, "PG")
_configure_pg_env(settings.data_database_url, "RDS_PG")


if __name__ == "__main__":
    print(f"[auth] app  db = {os.environ['PGUSER']}@{os.environ['PGHOST']}:{os.environ['PGPORT']}/{os.environ['PGDATABASE']}")
    print(f"[data] data db = {os.environ['RDS_PGUSER']}@{os.environ['RDS_PGHOST']}:{os.environ['RDS_PGPORT']}/{os.environ['RDS_PGDATABASE']}")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, access_log=False, proxy_headers=False)
