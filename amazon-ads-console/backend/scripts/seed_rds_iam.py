#!/usr/bin/env python3
"""把 IAM 账号种进 RDS 应用库 amazon_ads 的 iam.users。

与 scripts/seed_local_iam.py 的区别：
  - 那个只允许 localhost:55432（本地开发库）；本脚本只允许 RDS 主机，两者护栏方向相反
  - 账号按业务真实存在的运营组前缀生成（从 report_campaign_daily 里实测得来）

用法：
  python3 scripts/seed_rds_iam.py                # 生成随机临时密码并打印一次
  ADSIGHT_SEED_PASSWORD='...' python3 scripts/seed_rds_iam.py   # 指定固定密码（>=12 位）
"""
from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.passwords import hash_password  # noqa: E402

ENV_PATH = BACKEND_ROOT / ".env"
ALLOWED_HOSTS = ("127.0.0.1", "localhost")   # 2026-09-30：迁腾讯云后经本机 SSH 隧道访问，避免误写本地库

# (username, display_name, role_code, operator_code)
SEED_USERS = [
    ("admin",        "系统管理员",       "super_admin", None),
    ("boss",         "管理层（老板）",   "management",  None),
    ("op_zj1",       "运营-ZJ1 刘子娟",  "operator",    "ZJ1"),
    ("op_aj1",       "运营-AJ1 爱菊",    "operator",    "AJ1"),
    ("op_yt1",       "运营-YT1 林雅婷",  "operator",    "YT1"),
    ("op_xm1",       "运营-XM1",         "operator",    "XM1"),
    ("op_xm2",       "运营-XM2",         "operator",    "XM2"),
    ("op_dd1",       "运营-DD1 谢丹丹",  "operator",    "DD1"),
    ("op_aj2",       "运营-AJ2 爱菊",    "operator",    "AJ2"),
    ("op_ys1",       "运营-YS1",         "operator",    "YS1"),
]


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
         "-d", dsn["dbname"], "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env=env, capture_output=True, text=True, timeout=60,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def main() -> int:
    dsn = load_dsn()
    print(f"目标库：{dsn['user']}@{dsn['host']}:{dsn['port']}/{dsn['dbname']}")

    code, out, err = psql(dsn, "SELECT count(*) FROM iam.roles;")
    if code != 0:
        print(f"连不上或 iam 未初始化：{err}")
        return 2
    if int(out) < 3:
        print(f"iam.roles 只有 {out} 行，请先跑 migrations 001/002")
        return 3

    password = os.environ.get("ADSIGHT_SEED_PASSWORD") or ("Ads-" + secrets.token_urlsafe(9))
    if len(password) < 12:
        print(f"密码不足 12 位（当前 {len(password)}）")
        return 4
    pwd_hash = hash_password(password)

    created, skipped = [], []
    for username, display_name, role_code, operator_code in SEED_USERS:
        op = "NULL" if operator_code is None else "'" + operator_code.replace("'", "''") + "'"
        sel = f"SELECT count(*) FROM iam.users WHERE lower(username)=lower('{username}');"
        code, out, err = psql(dsn, sel)
        if code != 0:
            print(f"查询失败：{err}")
            return 5
        if int(out) > 0:
            skipped.append(username)
            continue
        ins = (
            "INSERT INTO iam.users (username, email, password_hash, display_name, role_code, operator_code, status) "
            f"VALUES ('{username}', NULL, '{pwd_hash}', '{display_name}', '{role_code}', {op}, 'active');"
        )
        code, _, err = psql(dsn, ins)
        if code != 0:
            print(f"插入 {username} 失败：{err}")
            return 6
        created.append((username, role_code, operator_code))

    print()
    if created:
        print(f"新建 {len(created)} 个账号：")
        for u, r, o in created:
            print(f"  {u:<10} role={r:<12} operator_code={o or '-'}")
    if skipped:
        print(f"已存在跳过 {len(skipped)} 个：{', '.join(skipped)}")

    code, out, err = psql(dsn, "SELECT count(*), count(*) FILTER (WHERE status='active') FROM iam.users;")
    print(f"\niam.users 现有 {out.split('|')[0]} 行（active {out.split('|')[1] if '|' in out else '?'}）")

    print()
    print("=" * 64)
    print(f"  临时统一密码（所有种子账号共用，请尽快轮换）：{password}")
    print("=" * 64)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
