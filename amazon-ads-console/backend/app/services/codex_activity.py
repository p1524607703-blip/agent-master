"""Server-observed request activity. Heartbeats never imply model usage."""
import fcntl
import json
import os
from datetime import datetime, timezone

RECENT_SECONDS = 300
# Open leases are released by the OS on process exit, including an abrupt restart.
_leases = {}


def begin(path, device_id):
    stream = os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w')
    try:
        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        json.dump({'schemaVersion': 1, 'deviceId': str(device_id),
                   'startedAt': datetime.now(timezone.utc).isoformat()}, stream)
        stream.flush()
        _leases[str(path)] = stream
    except BaseException:
        stream.close()
        raise


def release(path):
    stream = _leases.pop(str(path), None)
    if stream:
        stream.close()


def timestamp(value):
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError('timezone required')
    return value


def observe(directory):
    """Read shared request journals; only an OS-held lease proves work is in flight."""
    sources = {}
    try:
        for path in directory.glob('*.json'):
            try:
                with path.open() as stream:
                    try:
                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        locked = False
                    except BlockingIOError:
                        locked = True
                    record = json.load(stream)
                at = timestamp(record.get('finishedAt') or record['startedAt'])
                source = sources.setdefault(record['deviceId'], {'activeRequests': 0, 'lastActivityAt': at})
                source['activeRequests'] += int(locked and not record.get('finishedAt'))
                source['lastActivityAt'] = max(source['lastActivityAt'], at)
            except FileNotFoundError:
                continue  # The existing journal collector can prune a finished request.
        return sources, True
    except (OSError, ValueError, KeyError, TypeError):
        return {}, False


def present(now, last_request=None, observed=None, *, revoked=False, available=True):
    observed = observed or {}
    active = observed.get('activeRequests', 0)
    times = []
    try:
        for value in (last_request, observed.get('lastActivityAt')):
            if value is not None:
                at = timestamp(value)
                if (at - now).total_seconds() > 30:
                    raise ValueError('future activity')
                times.append(at)
    except (ValueError, TypeError):
        available = False
    last = max(times) if times else None
    if revoked:
        state = 'revoked'
    elif not available:
        state = 'unknown'
    elif active:
        state = 'active'
    elif last and (now - last).total_seconds() <= RECENT_SECONDS:
        state = 'recent'
    else:
        state = 'idle'
    return {'activityStatus': state, 'activeRequests': active if available and not revoked else 0,
            'lastActivityAt': last, 'online': state in ('active', 'recent')}
