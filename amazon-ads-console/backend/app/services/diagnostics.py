"""Management-only historical request lookup, with bounded local log reads."""
from __future__ import annotations

import gzip
import json
import os
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.observability import release_metadata
from app.services.build_cache import build_cache
from app.services.cache import cache

RETENTION_DAYS = 30
MAX_SCAN_BYTES = 64 * 1024 * 1024
MAX_SCAN_LINES = 100_000
SAFE_FIELDS = {
    'schema_version', 'event', 'timestamp', 'request_id', 'user_id', 'username',
    'role', 'operator_group', 'target_operator', 'date', 'period', 'period_start', 'period_end',
    'endpoint', 'method', 'revision', 'l1_hit', 'l1_miss', 'l1_stale',
    'l2_hit', 'l2_miss', 'l2_error', 'lock_acquired', 'lock_wait_ms',
    'lock_timeout', 'psql_calls', 'db_wall_ms', 'build_ms', 'total_ms',
    'status_code', 'pid', 'release', 'commit', 'exception_type', 'stack',
    'performance_class', 'performance_reason', 'quality', 'response_bytes', 'build',
}


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if parsed.tzinfo is None:
        raise ValueError('时间必须包含时区，例如 2026-10-06T21:00:00-04:00')
    return parsed.astimezone(timezone.utc)


def _trace_path() -> Path | None:
    value = os.environ.get('CPO_TRACE_LOG')
    return Path(value) if value else None


def diagnostic_status() -> dict[str, Any]:
    path = _trace_path()
    metadata = release_metadata()
    redis_stats = build_cache.stats()
    # Avoid revealing the Redis hostname or credentials in the management UI.
    redis_stats.pop('url', None)
    return {
        'release': {'release_version': metadata['release'], 'git_commit': metadata['commit']},
        'cache': {'memory': cache.stats(), 'redis': redis_stats},
        'trace': {'available': bool(path and path.is_file()), 'retention_days': RETENTION_DAYS},
    }


def request_traces(*, request_id: str | None = None, user_id: str | None = None,
                   username: str | None = None, endpoint: str | None = None,
                   since: str | None = None, until: str | None = None,
                   limit: int = 100) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    start = _timestamp(since) if since else now - timedelta(days=RETENTION_DAYS if request_id else 1)
    end = _timestamp(until) if until else now + timedelta(minutes=5)
    if start > end:
        raise ValueError('开始时间不能晚于结束时间')
    path = _trace_path()
    result: dict[str, Any] = {
        'items': [], 'available': bool(path and path.is_file()),
        'retention_days': RETENTION_DAYS, 'scan_truncated': False,
    }
    if not result['available'] or path is None:
        return result
    # The user can only filter records; they can never choose a filesystem path.
    candidates = [path] + sorted(
        (p for p in path.parent.glob(path.name + '.*') if p.is_file() and not p.is_symlink()),
        key=lambda p: p.stat().st_mtime, reverse=True,
    )
    records: list[dict[str, Any]] = []
    scanned_bytes = scanned_lines = 0
    for candidate in candidates[:40]:
        matches: deque[dict[str, Any]] = deque(maxlen=limit)
        try:
            opener = gzip.open if candidate.suffix == '.gz' else open
            with opener(candidate, 'rb') as stream:
                if candidate.suffix != '.gz':
                    size = candidate.stat().st_size
                    budget = max(0, MAX_SCAN_BYTES - scanned_bytes)
                    if size > budget:
                        stream.seek(size - budget)
                        stream.readline()
                        result['scan_truncated'] = True
                while True:
                    line = stream.readline(65537)
                    if not line:
                        break
                    scanned_bytes += len(line)
                    scanned_lines += 1
                    if scanned_bytes > MAX_SCAN_BYTES or scanned_lines > MAX_SCAN_LINES:
                        result['scan_truncated'] = True
                        break
                    if len(line) > 65536:
                        continue
                    try:
                        record = json.loads(line)
                        if not isinstance(record, dict) or record.get('event') != 'request_complete':
                            continue
                        when = _timestamp(record['timestamp'])
                        if not start <= when <= end:
                            continue
                        if request_id and record.get('request_id') != request_id:
                            continue
                        if user_id and str(record.get('user_id')) != user_id and record.get('username') != user_id:
                            continue
                        if username and record.get('username') != username:
                            continue
                        if endpoint and endpoint not in str(record.get('endpoint', '')):
                            continue
                        matches.append({key: value for key, value in record.items() if key in SAFE_FIELDS})
                    except (ValueError, KeyError, TypeError):
                        continue
        except (OSError, EOFError):
            continue
        records.extend(matches)
        if scanned_bytes >= MAX_SCAN_BYTES or scanned_lines >= MAX_SCAN_LINES:
            break
    records.sort(key=lambda r: r['timestamp'], reverse=True)
    result['items'] = records[:limit]
    if result['scan_truncated']:
        result['message'] = '日志较多，本次检索达到扫描上限；请使用服务器日志核查更早记录。'
    return result
