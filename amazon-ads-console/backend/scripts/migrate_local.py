import asyncio
import os
from pathlib import Path
from urllib.parse import urlparse

import asyncpg

BACKEND_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = BACKEND_ROOT / 'migrations'
DEFAULT_DATABASE_URL = 'postgresql+asyncpg://adsight_dev@127.0.0.1:55432/adsight_local'
ALLOWED_HOSTS = {'127.0.0.1', 'localhost', '::1'}
ALLOWED_PORT = 55432


def local_dsn() -> str:
    raw = os.environ.get('DATABASE_URL', DEFAULT_DATABASE_URL)
    parsed = urlparse(raw)
    if parsed.hostname not in ALLOWED_HOSTS or parsed.port != ALLOWED_PORT:
        raise RuntimeError('Refusing non-local database: RBAC local migration only allows localhost:55432')
    if raw.startswith('postgresql+asyncpg://'):
        return raw.replace('postgresql+asyncpg://', 'postgresql://', 1)
    return raw


async def main() -> None:
    conn = await asyncpg.connect(local_dsn())
    try:
        await conn.execute('CREATE SCHEMA IF NOT EXISTS iam')
        await conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS iam.schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            '''
        )
        for path in sorted(MIGRATIONS_DIR.glob('*.sql')):
            version = path.name
            applied = await conn.fetchval(
                'SELECT 1 FROM iam.schema_migrations WHERE version = $1', version
            )
            if applied:
                print('SKIP {}'.format(version))
                continue
            sql = path.read_text(encoding='utf-8')
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    'INSERT INTO iam.schema_migrations(version) VALUES($1)', version
                )
            print('APPLIED {}'.format(version))
    finally:
        await conn.close()


if __name__ == '__main__':
    asyncio.run(main())
