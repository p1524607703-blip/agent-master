"""映射表体检：列出 app.* 与 core.* 里所有与归属/映射相关的表及其规模。

只读。用法：backend/.venv/bin/python _mapping_audit.py [sql]
不带参数时输出总览；带参数时执行该 SQL（走应用库，前缀 RDS: 走数据仓库）。
"""
import os
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.core.config import settings


def configure_pg_env(database_url: str, prefix: str) -> None:
    parsed = urlsplit(database_url)
    database = parsed.path.lstrip("/")
    os.environ[f"{prefix}HOST"] = parsed.hostname
    os.environ[f"{prefix}PORT"] = str(parsed.port or 5432)
    os.environ[f"{prefix}USER"] = unquote(parsed.username)
    os.environ[f"{prefix}DATABASE"] = unquote(database)
    if parsed.password is not None:
        os.environ[f"{prefix}PASSWORD"] = unquote(parsed.password)
    query = parse_qs(parsed.query)
    if query.get("sslmode"):
        os.environ[f"{prefix}SSLMODE"] = query["sslmode"][-1]
    if query.get("sslrootcert"):
        os.environ[f"{prefix}SSLROOTCERT"] = query["sslrootcert"][-1]


configure_pg_env(settings.database_url, "PG")
configure_pg_env(settings.data_database_url, "RDS_PG")


def run(sql: str, prefix: str = "PG", timeout: int = 60) -> str:
    proc = subprocess.run(
        ["psql", "-h", os.environ[f"{prefix}HOST"], "-p", os.environ[f"{prefix}PORT"],
         "-U", os.environ[f"{prefix}USER"], "-d", os.environ[f"{prefix}DATABASE"],
         "-X", "-q", "-t", "-A", "-F", "\t", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "psql failed")
    return proc.stdout.strip()


OVERVIEW = r"""
SELECT n.nspname || '.' || c.relname AS tab,
       c.relkind,
       (SELECT COALESCE(n_live_tup, 0) FROM pg_stat_user_tables s
         WHERE s.relid = c.oid) AS approx_rows
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r','v','m')
  AND n.nspname IN ('app','core','iam','public')
  AND c.relname ~ '(map|mapping|roster|asin|sku|product|operator|归属|映射)'
ORDER BY 1;
"""

if __name__ == "__main__":
    if len(sys.argv) > 1:
        prefix = "RDS_PG" if sys.argv[1].startswith("RDS:") else "PG"
        sql = sys.argv[1][4:] if prefix == "RDS_PG" else sys.argv[1]
        print(run(sql, prefix))
    else:
        print("=== 应用库 amazon_ads ===")
        print(run(OVERVIEW, "PG"))
        print("\n=== 数据仓库 amazon_ads_v2 ===")
        print(run(OVERVIEW, "RDS_PG"))
