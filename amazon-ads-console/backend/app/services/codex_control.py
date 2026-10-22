"""Persistent, process-safe admission settings for the unified device entry."""
import asyncio
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import time
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from app.core.config import settings

QUEUE_LIMIT = 24
QUEUE_SECONDS = 120


def directory():
    root = Path(settings.codex_event_spool_dir).expanduser() / 'control'
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    (root / 'leases').mkdir(exist_ok=True, mode=0o700)
    return root


def default_policy():
    return {'schemaVersion': 1, 'revision': 0, 'globalMaxConcurrent': 6, 'devices': {},
            'updatedAt': None, 'updatedBy': None}


def valid_limit(value):
    return value is None or (type(value) is int and 1 <= value <= 100000)


@contextmanager
def locked():
    root = directory()
    with os.fdopen(os.open(root / 'policy.lock', os.O_RDWR | os.O_CREAT, 0o600), 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield root


def read_policy(root):
    path = root / 'policy.json'
    if not path.exists():
        return default_policy()
    try:
        if path.stat().st_size > 8 * 1024 * 1024 or path.stat().st_mode & 0o077:
            raise ValueError('Invalid private policy file')
        value = json.loads(path.read_text())
        assert value['schemaVersion'] == 1 and type(value['revision']) is int and value['revision'] >= 0
        assert valid_limit(value['globalMaxConcurrent']) and isinstance(value['devices'], dict)
        for key, item in value['devices'].items():
            uuid.UUID(key)
            assert type(item['enabled']) is bool and valid_limit(item['maxConcurrent'])
        return value
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        raise HTTPException(503, 'Device control settings are unavailable') from None


def device_policy(policy, device_id):
    return policy['devices'].get(str(device_id), {'enabled': True, 'maxConcurrent': None})


def require_device_enabled(device_id):
    with locked() as root:
        enabled = device_policy(read_policy(root), device_id)['enabled']
    if not enabled:
        raise HTTPException(403, {'code': 'device_disabled', 'message': 'This device is disabled by its administrator'})


def update(*, revision, actor, device_ids=None, enabled=None, device_limit=False, max_concurrent=None):
    with locked() as root:
        value = read_policy(root)
        if value['revision'] != revision:
            raise HTTPException(409, 'Settings changed; refresh before saving again')
        if device_ids is None:
            value['globalMaxConcurrent'] = max_concurrent
        else:
            for device_id in device_ids:
                item = dict(device_policy(value, device_id))
                if enabled is not None:
                    item['enabled'] = enabled
                if device_limit:
                    item['maxConcurrent'] = max_concurrent
                value['devices'][str(device_id)] = item
        value.update(revision=revision + 1, updatedAt=datetime.now(timezone.utc).isoformat(), updatedBy=actor)
        temp = root / ('policy.' + uuid.uuid4().hex + '.tmp')
        with os.fdopen(os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
            json.dump(value, stream, separators=(',', ':'))
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, root / 'policy.json')
        return value


def live_leases(root):
    result = []
    for path in (root / 'leases').glob('*.json'):
        try:
            with path.open() as stream:
                try:
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    result.append(json.load(stream))
                else:
                    path.unlink(missing_ok=True)  # A crashed process cannot retain a slot.
        except FileNotFoundError:
            continue
        except (OSError, ValueError, KeyError, TypeError):
            raise HTTPException(503, 'Device request admission is unavailable') from None
    return result


def snapshot():
    with locked() as root:
        policy = read_policy(root)
        leases = live_leases(root)
    counts = {}
    for lease in leases:
        count = counts.setdefault(lease['deviceId'], {'activeRequests': 0, 'queuedRequests': 0})
        count['activeRequests' if lease['state'] == 'active' else 'queuedRequests'] += 1
    return policy, counts


class Lease:
    def __init__(self, root, device_id):
        self.path = root / 'leases' / (uuid.uuid4().hex + '.json')
        self.stream = os.fdopen(os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o600), 'w+')
        try:
            fcntl.flock(self.stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.record = {'id': self.path.stem, 'deviceId': str(device_id), 'ticket': time.time_ns(), 'state': 'queued'}
            self.write()
        except BaseException:
            self.stream.close()
            self.path.unlink(missing_ok=True)
            raise

    def write(self):
        self.stream.seek(0); self.stream.truncate()
        json.dump(self.record, self.stream); self.stream.flush()

    def close(self):
        if self.stream.closed:
            return
        with locked():
            self.stream.close()
            self.path.unlink(missing_ok=True)


def busy(code):
    return HTTPException(429, {'code': code, 'message': 'Device request queue is busy; retry later'},
                         headers={'Retry-After': '2', 'X-Relay-Limit-Origin': 'control'})


async def acquire(device_id):
    lease = None
    deadline = time.monotonic() + QUEUE_SECONDS
    try:
        with locked() as root:
            lease = Lease(root, device_id)
        while True:
            with locked() as root:
                policy = read_policy(root)
                if not device_policy(policy, device_id)['enabled']:
                    raise HTTPException(403, {'code': 'device_disabled', 'message': 'This device is disabled by its administrator'})
                leases = live_leases(root)
                active = [r for r in leases if r['state'] == 'active']
                queued = sorted((r for r in leases if r['state'] == 'queued'), key=lambda r: (r['ticket'], r['id']))
                total_limit = policy['globalMaxConcurrent']
                if total_limit is None or len(active) < total_limit:
                    # Skip a waiting device whose own slots are full; other devices can still run.
                    for waiter in queued:
                        item = device_policy(policy, waiter['deviceId'])
                        device_limit = item['maxConcurrent']
                        occupied = sum(r['deviceId'] == waiter['deviceId'] for r in active)
                        if item['enabled'] and (device_limit is None or occupied < device_limit):
                            if waiter['id'] == lease.record['id']:
                                lease.record['state'] = 'active'; lease.write()
                                return lease
                            break
                if len(queued) > QUEUE_LIMIT:
                    raise busy('relay_queue_full')
            if time.monotonic() >= deadline:
                raise busy('relay_queue_timeout')
            await asyncio.sleep(.1)
    except BaseException:
        if lease:
            lease.close()
        raise


class ControlledStream:
    def __init__(self, stream, lease):
        self.stream, self.lease = stream, lease

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return await self.stream.__anext__()
        except BaseException:
            self.lease.close()
            raise

    async def aclose(self):
        try:
            await self.stream.aclose()
        finally:
            self.lease.close()
