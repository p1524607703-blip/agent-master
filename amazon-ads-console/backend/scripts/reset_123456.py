#!/usr/bin/env python3
"""把 IAM 里「超级管理员 + 管理层 + 运营层」三类账号的密码统一重置为 123456。

与 seed_rds_iam.py 同样的护栏：只允许 RDS 主机，避免误写本地库。
注意：app.core.passwords.hash_password 强制 >=12 位，123456 只有 6 位会被拒，
所以这里用同款 PBKDF2 算法（pbkdf2_sha256$600000$salt$digest）直接生成兼容哈希，
登录校验 verify_password 不校验长度，因此 123456 可正常登录。

用法：
  python3 scripts/reset_123456.py            # 先 dry-run 列出目标账号
  python3 scripts/reset_123456.py --apply    # 真正改密
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

ENV_PATH = BACKEND_ROOT / ".env"
ALLOWED_HOSTS = ("127.0.0.1", "localhost")   # 2026-09-30：迁腾讯云后经本机 SSH 隧道访问（旧 .pg.rds.aliyuncs.com 已停用）

# 三类角色：超级管理员 / 管理层 / 运营层
TARGET_ROLES = ("super_admin", "management", "operator")
NEW_PLAIN = "123456"
ITERATIONS = 600_000
SALT_BYTES = 16
DKLEN = 32


def load_dsn() -> dict:
    if not ENV_PATH.is_file():
        raise SystemExit(f"找不到 {ENV_PATH}")
    raw = ""
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        if line.startswith("DATABASE_URL="):
            raw = line.split("=", 1)[1].strip()
            break
    if not raw:
        raise SystemExit("backend/.env 里没有 DATABASE_URL")
    p = urlsplit(raw)
    if p.hostname not in ALLOWED_HOSTS:
        raise SystemExit(f"拒绝执行：host={p.hostname} 不是 RDS 主机（本脚本只允许 RDS）")
    q = parse_qs(p.query)
    return {
        "host": p.hostname,
        "port": str(p.port or 5432),
        "user": unquote(p.username or ""),
        "password": unquote(p.password or ""),
        "dbname": p.path.lstrip("/"),
        "sslmode": (q.get("sslmode") or ["verify-full"])[-1],
        "sslrootcert": (q.get("sslrootcert") or [""])[-1],
    }


def psql(dsn: dict, sql: str) -> tuple[int, str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = dsn["password"]
    env["PGSSLMODE"] = dsn["sslmode"]
    if dsn["sslrootcert"]:
        env["PGSSLROOTCERT"] = dsn["sslrootcert"]
    env["PGCONNECT_TIMEOUT"] = "10"
    proc = subprocess.run(
        ["psql", "-w", "-h", dsn["host"], "-p", dsn["port"], "-U", dsn["user"],
         "-d", dsn["dbname"], "-X", "-q", "-t", "-A", "-F", "|", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=env, capture_output=True, text=True, timeout=60,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def make_hash(password: str) -> str:
    """同款 PBKDF2 哈希，跳过 app.core.passwords 的 12 位强制限制。"""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS, dklen=DKLEN)
    s = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
    d = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"pbkdf2_sha256${ITERATIONS}${s}${d}"


def role_cn(code: str) -> str:
    return {"super_admin": "超级管理员", "management": "管理层", "operator": "运营层"}.get(code, code)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正改密；不传则只列出目标账号")
    args = ap.parse_args()

    dsn = load_dsn()
    print(f"目标库：{dsn['user']}@{dsn['host']}:{dsn['port']}/{dsn['dbname']}")

    code, out, err = psql(
        dsn,
        f"SELECT username, display_name, role_code, operator_code, status "
        f"FROM iam.users WHERE role_code IN ('super_admin','management','operator') "
        f"ORDER BY CASE role_code WHEN 'super_admin' THEN 1 WHEN 'management' THEN 2 ELSE 3 END, username;",
    )
    if code != 0:
        print(f"查询失败：{err}")
        return 2

    rows = [r for r in out.splitlines() if r]
    if not rows:
        print("未找到任何目标角色账号。")
        return 0

    print()
    print(f"{'用户名':<10} {'显示名':<18} {'角色':<12} {'运营组':<6} {'状态'}")
    print("-" * 64)
    for r in rows:
        username, disp, role, op, status = (r.split("|") + ["", "", "", "", ""])[:5]
        print(f"{username:<10} {disp:<18} {role_cn(role):<12} {(op or '-'):<6} {status}")
    print(f"\n共 {len(rows)} 个账号（超级管理员 + 管理层 + 运营层）")

    if not args.apply:
        print("\n[DRY-RUN] 未改密。确认无误后加 --apply 执行。")
        return 0

    new_hash = make_hash(NEW_PLAIN)
    code, out, err = psql(
        dsn,
        f"UPDATE iam.users SET password_hash = '{new_hash}', updated_at = now() "
        f"WHERE role_code IN ('super_admin','management','operator');",
    )
    if code != 0:
        print(f"改密失败：{err}")
        return 3

    print(f"\n✅ 已将以上 {len(rows)} 个账号密码统一重置为：{NEW_PLAIN}")
    print("⚠️ 123456 为弱密码，请尽快在正式环境轮换。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
