import asyncio
import os
import secrets
import sys
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.passwords import hash_password  # noqa: E402

DEFAULT_DATABASE_URL = 'postgresql+asyncpg://adsight_dev@127.0.0.1:55432/adsight_local'
ALLOWED_HOSTS = {'127.0.0.1', 'localhost', '::1'}
ALLOWED_PORT = 55432

SEED_USERS = (
    ('admin', '开发管理员', 'super_admin', None, 'ADSIGHT_SEED_ADMIN_PASSWORD'),
    ('management_demo', '管理层示例', 'management', None, 'ADSIGHT_SEED_MANAGEMENT_PASSWORD'),
    ('operator_zj', '运营示例-ZJ', 'operator', 'ZJ', 'ADSIGHT_SEED_OPERATOR_PASSWORD'),
)


def local_dsn() -> str:
    raw = os.environ.get('DATABASE_URL', DEFAULT_DATABASE_URL)
    parsed = urlparse(raw)
    if parsed.hostname not in ALLOWED_HOSTS or parsed.port != ALLOWED_PORT:
        raise RuntimeError('Refusing non-local database: RBAC local seed only allows localhost:55432')
    if raw.startswith('postgresql+asyncpg://'):
        return raw.replace('postgresql+asyncpg://', 'postgresql://', 1)
    return raw


def seed_password(env_name: str) -> tuple:
    configured = os.environ.get(env_name)
    if configured:
        return configured, False
    return secrets.token_urlsafe(18), True


async def main() -> None:
    conn = await asyncpg.connect(local_dsn())
    generated = []
    try:
        for username, display_name, role_code, operator_code, env_name in SEED_USERS:
            existing = await conn.fetchval(
                'SELECT user_id FROM iam.users WHERE lower(username) = lower($1)', username
            )
            if existing:
                print('SKIP {} (already exists)'.format(username))
                continue
            password, was_generated = seed_password(env_name)
            password_hash = hash_password(password)
            await conn.execute(
                '''
                INSERT INTO iam.users
                    (username, email, password_hash, display_name, role_code, operator_code, status)
                VALUES ($1, NULL, $2, $3, $4, $5, 'active')
                ''',
                username, password_hash, display_name, role_code, operator_code
            )
            print('CREATED {} role={}'.format(username, role_code))
            if was_generated:
                generated.append((username, password))
        if generated:
            print()
            print('Temporary local development passwords (shown once; not stored as plaintext):')
            for username, password in generated:
                print('{}={}'.format(username, password))
            print('Set ADSIGHT_SEED_*_PASSWORD environment variables before seeding a fresh database if fixed dev passwords are preferred.')
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
