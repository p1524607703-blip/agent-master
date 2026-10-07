"""Local-only Redis watchdog: credentials never enter journald or stdout."""
import json
import os
import socket
import sys
import time
from datetime import datetime
from pathlib import Path


def emit(health, error_class='', failed_checks=0, request_errors=0):
    priority = '4' if health == 'degraded' else '6'
    fields = {
        'PRIORITY': priority, 'SYSLOG_IDENTIFIER': 'cpo-redis-watchdog',
        'MESSAGE': 'CPO Redis request errors observed; requests fall back to PostgreSQL' if health == 'degraded' and request_errors
                   else 'CPO Redis unavailable; requests fall back to PostgreSQL' if health == 'degraded'
                   else 'CPO Redis recovered' if health == 'recovered' else 'CPO Redis healthy',
        'CPO_COMPONENT': 'redis', 'CPO_HEALTH': health,
        'CPO_ERROR_CLASS': error_class, 'CPO_FAILED_CHECKS': str(failed_checks),
        'CPO_REQUEST_CACHE_ERRORS': str(request_errors),
    }
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as journal:
            journal.connect('/run/systemd/journal/socket')
            journal.send('\n'.join(f'{key}={value}' for key, value in fields.items()).encode())
    except OSError:
        print(json.dumps(fields))


def read_trace_errors(trace_file, old, now, max_bytes=1024 * 1024):
    """Consume only new complete JSONL records; cap IO and survive rotation.

    The cursor lives in the same state file as health, so one request error is
    never replayed each minute. On first discovery, consider only recent traces.
    """
    try:
        with trace_file.open('rb') as stream:
            stat = os.fstat(stream.fileno())
            identity = {'device': stat.st_dev, 'inode': stat.st_ino}
            cursor = old.get('trace_cursor') or {}
            same_file = all(cursor.get(key) == value for key, value in identity.items())
            offset = int(cursor.get('offset', 0)) if same_file else 0
            if offset > stat.st_size:
                offset = 0  # Supports a manually truncated file as well as rename/create.
            skipped = max(0, stat.st_size - offset - max_bytes)
            offset += skipped
            stream.seek(offset)
            data = stream.read(max_bytes)
    except OSError:
        return 0, old.get('trace_cursor'), 0
    if skipped:
        # Start after the first partial record in the bounded tail.
        boundary = data.find(b'\n')
        if boundary < 0:
            return 0, {**identity, 'offset': offset}, skipped
        offset += boundary + 1
        data = data[boundary + 1:]
    boundary = data.rfind(b'\n')
    if boundary < 0:
        return 0, {**identity, 'offset': offset}, skipped
    complete = data[:boundary + 1]
    errors = 0
    for line in complete.splitlines():
        try:
            record = json.loads(line)
            if record.get('event') != 'request_complete':
                continue
            if not cursor:
                timestamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00')).timestamp()
                if timestamp < now - 120:
                    continue
            errors += max(0, int(record.get('l2_error', 0)))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return errors, {**identity, 'offset': offset + len(complete)}, skipped


def update_state(state_file, healthy, error_class='', now=None, trace_file=None):
    now = time.time() if now is None else now
    try:
        old = json.loads(state_file.read_text())
    except (OSError, ValueError):
        old = {}
    request_errors, trace_cursor, skipped = read_trace_errors(trace_file, old, now) if trace_file else (0, old.get('trace_cursor'), 0)
    ping_healthy = healthy
    healthy = healthy and request_errors == 0
    if ping_healthy and request_errors:
        error_class = 'RedisRequestError'
    failed_checks = 0 if healthy else int(old.get('failed_checks', 0)) + 1
    state = {'healthy': healthy, 'checked_at': now, 'failed_checks': failed_checks,
             'last_warning_at': old.get('last_warning_at', 0), 'ping_healthy': ping_healthy,
             'request_cache_errors': request_errors, 'trace_cursor': trace_cursor,
             'trace_skipped_bytes': skipped}
    event = None
    if not healthy and (old.get('healthy') is not False or now - state['last_warning_at'] >= 900):
        event = 'degraded'
        state['last_warning_at'] = now
    elif healthy and old.get('healthy') is False:
        event = 'recovered'
    elif healthy and not old:
        event = 'healthy'
    state_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = state_file.with_suffix('.tmp')
    temp.write_text(json.dumps(state))
    temp.chmod(0o600)
    temp.replace(state_file)
    if event:
        emit(event, error_class, failed_checks, request_errors)
    return state, event


def main():
    state_file = Path(os.getenv('CPO_WATCHDOG_STATE', '/opt/agent/cpo/shared/watchdog/redis-state.json'))
    healthy = False
    error_class = ''
    try:
        from dotenv import load_dotenv
        load_dotenv(os.getenv('CPO_ENV_FILE', '.env'), override=False)
        import redis
        client = redis.Redis.from_url(os.getenv('CPO_REDIS_URL', 'redis://127.0.0.1:6379/0'),
                                     socket_connect_timeout=1, socket_timeout=1)
        healthy = bool(client.ping())
    except Exception as error:
        error_class = type(error).__name__
    trace_file = Path(os.getenv('CPO_TRACE_LOG', '/opt/agent/cpo/shared/traces/requests.jsonl'))
    update_state(state_file, healthy, error_class, trace_file=trace_file)
    # Degraded is an observed state, not a failed timer unit. Recovery still runs.


if __name__ == '__main__':
    main()
