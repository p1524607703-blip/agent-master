"""Safely validate the new RDS password and configure backend/.env."""
from __future__ import annotations

import getpass
import os
from pathlib import Path
import subprocess
import tempfile
from urllib.parse import quote

HOST = "pgm-bp1p3g11alay2d21vo.pg.rds.aliyuncs.com"
PORT = "5432"
DATABASE = "amazon_ads"
USER = "amazon_ads_admin"
SSLMODE = "verify-full"
SSLROOTCERT = Path.home() / ".postgresql" / "root.crt"
ENV_PATH = Path(__file__).resolve().parent / ".env"


def _error_category(stderr: str) -> str:
    text = stderr.lower()
    if "password authentication failed" in text or "no password supplied" in text:
        return "credentials_invalid"
    if "server does not support ssl" in text:
        return "ssl_not_enabled"
    if any(term in text for term in ("root certificate file", "certificate verify failed", "server certificate", "ssl error")):
        return "ssl_certificate"
    if any(term in text for term in ("could not translate host name", "could not connect to server", "connection timed out", "timeout expired")):
        return "network_or_dns"
    return "other"


def _test_password(password: str) -> tuple[bool, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    env["PGSSLMODE"] = SSLMODE
    env["PGSSLROOTCERT"] = str(SSLROOTCERT)
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
    encoded_root = quote(str(SSLROOTCERT), safe="/")
    return (
        f"postgresql+asyncpg://{encoded_user}:{encoded_password}@{HOST}:{PORT}/{encoded_db}"
        f"?sslmode={SSLMODE}&sslrootcert={encoded_root}"
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
    if not SSLROOTCERT.is_file():
        print("error_category=ssl_certificate")
        return 2

    for attempt in range(1, 3):
        password = getpass.getpass(f"RDS password attempt {attempt}/2: ")
        if not password:
            print("error_category=credentials_invalid")
            continue
        try:
            ok, category = _test_password(password)
        except subprocess.TimeoutExpired:
            ok, category = False, "network_or_dns"
        if ok:
            _write_env(password)
            print(f"host={HOST}")
            print(f"port={PORT}")
            print(f"user={USER}")
            print(f"database={DATABASE}")
            print("password_present=True")
            print(f"sslmode={SSLMODE}")
            print("config_written=True")
            return 0
        print(f"error_category={category}")
        if category in {"ssl_not_enabled", "ssl_certificate", "network_or_dns"}:
            return 3

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
