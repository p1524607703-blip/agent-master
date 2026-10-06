"""Safely validate the database password and configure backend/.env.

2026-09-30：数据库已从阿里云 RDS 全量迁至腾讯云服务器自建 PostgreSQL。
连接经本机常驻 SSH 隧道访问：

    本机 127.0.0.1:15432  →  SSH Agent-server  →  服务器 127.0.0.1:5432

因此 host/port 是隧道入口，数据库层不再套 TLS（外层 SSH 已加密），
旧阿里云 CA（~/.postgresql/root.crt）与 sslmode=verify-full 组合已作废。
"""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote

HOST = "127.0.0.1"
PORT = "15432"          # 本机 SSH 隧道端口；服务器侧数据库仍是 5432
DATABASE = "amazon_ads"
USER = "amazon_ads_admin"
SSLMODE = "disable"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def _error_category(stderr: str) -> str:
    text = stderr.lower()
    if "password authentication failed" in text or "no password supplied" in text:
        return "credentials_invalid"
    if "server does not support ssl" in text:
        return "ssl_not_enabled"
    if any(term in text for term in ("root certificate file", "certificate verify failed", "server certificate", "ssl error")):
        return "ssl_certificate"
    if any(term in text for term in (
        "could not translate host name", "could not connect to server",
        "connection timed out", "timeout expired", "connection refused",
    )):
        # 2026-09-30 起最常见的原因是本机 SSH 隧道没起来
        return "tunnel_or_network"
    return "other"


def _test_password(password: str) -> tuple[bool, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    env["PGSSLMODE"] = SSLMODE
    env["PGCONNECT_TIMEOUT"] = "8"
    proc = subprocess.run(
        [
            "psql", "-w", "-h", HOST, "-p", PORT,
            "-U", USER, "-d", DATABASE, "-X", "-q",
            "-t", "-A", "-c", "SELECT 1;",
        ],
        env=env, capture_output=True, text=True, timeout=20,
    )
    if proc.returncode == 0 and proc.stdout.strip() == "1":
        return True, "none"
    return False, _error_category(proc.stderr or "")


def _database_url(password: str) -> str:
    encoded_user = quote(USER, safe="")
    encoded_password = quote(password, safe="")
    encoded_db = quote(DATABASE, safe="")
    return (
        f"postgresql+asyncpg://{encoded_user}:{encoded_password}@{HOST}:{PORT}/{encoded_db}"
        f"?sslmode={SSLMODE}"
    )


def _write_env(password: str) -> None:
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = "DATABASE_URL=" + _database_url(password) + "\n"
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=ENV_PATH.parent,
            prefix=".env.", delete=False,
        ) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        os.chmod(temp_path, 0o600)
        os.replace(temp_path, ENV_PATH)
        os.chmod(ENV_PATH, 0o600)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def main() -> int:
    # 隧道体检：数据库只监听服务器本地，这里连的其实是本机隧道的入口
    tunnel = subprocess.run(
        ["/usr/sbin/lsof", "-nP", "-iTCP:" + PORT, "-sTCP:LISTEN"],
        capture_output=True, text=True,
    )
    if tunnel.returncode != 0:
        print("error_category=tunnel_or_network")
        print(f"hint=本机 {PORT} 未监听，先执行："
              "launchctl kickstart -k gui/$(id -u)/com.panjinlong.agent-server-db-tunnel")
        return 3

    for attempt in range(1, 3):
        password = getpass.getpass(f"database password attempt {attempt}/2: ")
        if not password:
            print("error_category=credentials_invalid")
            continue
        try:
            ok, category = _test_password(password)
        except subprocess.TimeoutExpired:
            ok, category = False, "tunnel_or_network"
        if ok:
            _write_env(password)
            print(f"host={HOST}")
            print(f"port={PORT}")
            print(f"user={USER}")
            print(f"database={DATABASE}")
            print("password_present=True")
            print(f"sslmode={SSLMODE}")
            print("tunnel=ok")
            print("config_written=True")
            return 0
        print(f"error_category={category}")
        if category in {"ssl_not_enabled", "ssl_certificate", "tunnel_or_network"}:
            return 3

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
