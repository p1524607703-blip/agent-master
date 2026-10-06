import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import asyncpg

from app.core.config import settings
from app.core.passwords import verify_password


def _database_dsn() -> str:
    raw = settings.database_url
    if raw.startswith('postgresql+asyncpg://'):
        return raw.replace('postgresql+asyncpg://', 'postgresql://', 1)
    if raw.startswith('postgresql://'):
        return raw
    raise RuntimeError('Unsupported database URL for auth sessions')


async def _connect():
    return await asyncpg.connect(_database_dsn())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _public_user(row: Any) -> Dict[str, Any]:
    return {
        'userId': row['user_id'],
        'username': row['username'],
        'displayName': row['display_name'],
        'roleCode': row['role_code'],
        'operatorCode': row['operator_code'],
    }


async def create_session(username: str, password: str) -> Optional[Tuple[str, datetime, Dict[str, Any]]]:
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            '''
            SELECT user_id, username, password_hash, display_name, role_code, operator_code
            FROM iam.users
            WHERE LOWER(username) = LOWER($1) AND status = 'active'
            LIMIT 1
            ''',
            username.strip(),
        )
        if row is None or not verify_password(password, row['password_hash']):
            return None

        token = secrets.token_urlsafe(48)
        token_hash = _hash_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=settings.auth_session_hours)
        await conn.execute(
            '''
            INSERT INTO iam.user_sessions (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            ''',
            row['user_id'], token_hash, expires_at,
        )
        return token, expires_at, _public_user(row)
    finally:
        await conn.close()


async def resolve_session(token: str) -> Optional[Dict[str, Any]]:
    token_hash = _hash_token(token)
    conn = await _connect()
    try:
        row = await conn.fetchrow(
            '''
            SELECT u.user_id, u.username, u.display_name, u.role_code, u.operator_code, s.session_id
            FROM iam.user_sessions s
            JOIN iam.users u ON u.user_id = s.user_id
            WHERE s.token_hash = $1
              AND s.revoked_at IS NULL
              AND s.expires_at > NOW()
              AND u.status = 'active'
            LIMIT 1
            ''',
            token_hash,
        )
        if row is None:
            return None
        await conn.execute(
            'UPDATE iam.user_sessions SET last_seen_at = NOW() WHERE session_id = $1',
            row['session_id'],
        )
        return _public_user(row)
    finally:
        await conn.close()


async def revoke_session(token: str) -> bool:
    token_hash = _hash_token(token)
    conn = await _connect()
    try:
        result = await conn.execute(
            '''
            UPDATE iam.user_sessions
            SET revoked_at = COALESCE(revoked_at, NOW()), last_seen_at = NOW()
            WHERE token_hash = $1 AND revoked_at IS NULL
            ''',
            token_hash,
        )
        return result != 'UPDATE 0'
    finally:
        await conn.close()
