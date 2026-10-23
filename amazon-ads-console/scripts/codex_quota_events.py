"""Notification-first quota reads with bounded polling and serialized publication.

Notifications are hints, never trusted quota or identity. Every hint is verified
by account/rateLimits/read on the isolated reader. No model calls are made.
"""
import asyncio
import contextlib
import hashlib
import json
import os
from pathlib import Path
import signal
import tempfile
import time

FALLBACK_SECONDS = 60
PUBLISH_SECONDS = 30
MIN_READ_SECONDS = 5
DEBOUNCE_SECONDS = 1
CHANNEL = 'codex_usage_changed'
WATCH_COMMAND = ('CPO_ENV_FILE=/opt/agent/cpo/shared/backend.env '
                 '/opt/agent/cpo/current/.venv/bin/python '
                 '/opt/agent/cpo/current/amazon-ads-console/scripts/watch_codex_usage.py')


async def stop_process(process):
    if process.returncode is None:
        with contextlib.suppress(ProcessLookupError):
            process.terminate()
    try:
        await asyncio.wait_for(process.wait(), 5)
    except asyncio.TimeoutError:
        with contextlib.suppress(ProcessLookupError):
            process.kill()
        await process.wait()


class Reader:
    def __init__(self, config, changed):
        self.config, self.changed = config, changed
        self.pending = {}
        self.serial = 0
        self.fingerprint = None

    async def open(self):
        self.temp = tempfile.TemporaryDirectory(prefix='codex-quota-reader-')
        env = {**os.environ, 'CODEX_HOME': self.config['codexHome'],
               'CODEX_SQLITE_HOME': self.temp.name}
        try:
            self.process = await asyncio.create_subprocess_exec(
                self.config['codexExecutable'], 'app-server', '--stdio', env=env,
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL, limit=1024*1024)
            self.pump = asyncio.create_task(self.receive())
            await self.request('initialize', {'clientInfo': {
                'name': 'codex_relay_quota', 'version': '0.4.0'}}, timeout=15)
            await self.send({'method': 'initialized', 'params': {}})
        except BaseException:
            await self.close()
            raise

    async def send(self, value):
        self.process.stdin.write((json.dumps(value)+'\n').encode())
        await self.process.stdin.drain()

    async def request(self, method, params, timeout=30):
        self.serial += 1
        serial = self.serial
        future = asyncio.get_running_loop().create_future()
        self.pending[serial] = future
        try:
            await self.send({'id': serial, 'method': method, 'params': params})
            return await asyncio.wait_for(future, timeout)
        finally:
            self.pending.pop(serial, None)

    async def receive(self):
        try:
            while True:
                line = await self.process.stdout.readline()
                if not line:
                    raise RuntimeError('reader disconnected')
                message = json.loads(line)
                serial = message.get('id')
                if serial in self.pending:
                    future = self.pending[serial]
                    if not future.done():
                        if 'error' in message:
                            future.set_exception(RuntimeError('quota read rejected'))
                        else:
                            future.set_result(message.get('result'))
                elif message.get('method') == 'account/rateLimits/updated':
                    # A read can itself emit the same notification. Deduplicate it
                    # so the fallback never becomes a self-sustaining read loop.
                    params = message.get('params') or {}
                    fingerprint = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()
                    if fingerprint != self.fingerprint:
                        self.fingerprint = fingerprint
                        self.changed('official-notification')
                elif message.get('method') == 'account/updated':
                    self.changed('account-notification')
        except (Exception, asyncio.CancelledError):
            for future in list(self.pending.values()):
                if not future.done():
                    future.set_exception(RuntimeError('reader disconnected'))

    async def close(self):
        if hasattr(self, 'pump'):
            self.pump.cancel()
            await asyncio.gather(self.pump, return_exceptions=True)
        if hasattr(self, 'process'):
            await stop_process(self.process)
        if hasattr(self, 'temp'):
            self.temp.cleanup()


class LocalSignals:
    """Read only new token-count records; never export or persist chat text."""
    def __init__(self, home):
        self.root = Path(home).expanduser()/'sessions'
        self.positions = {}
        self.initialized = False

    def poll(self):
        changed, positions = False, {}
        files = sorted((p for p in self.root.rglob('*.jsonl') if not p.is_symlink()),
                       key=lambda p: p.stat().st_mtime, reverse=True)[:512]
        for path in files:
            stat = path.stat()
            old = self.positions.get(path)
            # First pass establishes a baseline instead of replaying history.
            if not self.initialized:
                positions[path] = (stat.st_ino, stat.st_size, b'')
                continue
            offset, partial = (old[1], old[2]) if old and old[0] == stat.st_ino and old[1] <= stat.st_size else (0, b'')
            if offset == stat.st_size:
                positions[path] = (stat.st_ino, offset, partial)
                continue
            # Bound reads after a gap; only the tail is needed to trigger a full
            # accounting scan. Token values still come from the existing scanner.
            start = max(offset, stat.st_size-1024*1024)
            with path.open('rb') as stream:
                stream.seek(start)
                data = (partial if start == offset else b'')+stream.read(1024*1024)
                end = stream.tell()
            lines = data.split(b'\n')
            if start > offset:
                lines = lines[1:]
            for line in lines[:-1]:
                if b'"token_count"' not in line:
                    continue
                try:
                    value = json.loads(line)
                    changed |= value.get('type') == 'event_msg' and (value.get('payload') or {}).get('type') == 'token_count'
                except (ValueError, TypeError, AttributeError):
                    pass
            tail = lines[-1] if lines else b''
            positions[path] = (stat.st_ino, end, tail if len(tail) < 1024*1024 else b'')
        self.initialized, self.positions = True, positions
        return changed


class Monitor:
    def __init__(self, config, sanitize, unavailable, publish):
        self.config, self.sanitize = config, sanitize
        self.unavailable, self.publish = unavailable, publish
        self.wake, self.dirty = asyncio.Event(), asyncio.Event()
        self.reasons = set()
        self.latest = None
        self.reader_connected = self.device_connected = False
        self.catchup_until = 0
        self.last_read = 0
        self.trigger_name = 'startup'
        self.read_count = self.event_count = 0

    def trigger(self, reason):
        self.reasons.add(reason)
        self.wake.set()
        if reason in ('local-usage', 'device-usage'):
            self.catchup_until = time.monotonic()+60
            self.event_count += 1

    async def reader_loop(self):
        backoff = 2
        while True:
            reader = Reader(self.config, self.trigger)
            try:
                await reader.open()
                self.reader_connected = True
                self.trigger('reader-connected')
                while True:
                    await self.wake.wait()
                    await asyncio.sleep(max(DEBOUNCE_SECONDS, self.last_read+MIN_READ_SECONDS-time.monotonic()))
                    reasons = self.reasons.copy()
                    self.reasons.clear(); self.wake.clear()
                    result = await reader.request('account/rateLimits/read', {})
                    # Full identity validation is repeated for every read, including
                    # account-change events. Event payloads cannot rebind the source.
                    self.latest = self.sanitize(result, self.config['expectedAccountDigest'])
                    self.last_read = time.monotonic()
                    self.trigger_name = ','.join(sorted(reasons))[:160]
                    self.read_count += 1
                    self.dirty.set()
                    backoff = 2
            except asyncio.CancelledError:
                raise
            except Exception:
                self.latest = self.unavailable()
                self.dirty.set()
            finally:
                self.reader_connected = False
                await reader.close()
            await asyncio.sleep(backoff)
            backoff = min(backoff*2, 30)

    async def device_loop(self):
        backoff = 2
        while True:
            process = None
            try:
                process = await asyncio.create_subprocess_exec(
                    'ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                    '-o', 'ConnectTimeout=8', '-o', 'ServerAliveInterval=15',
                    '-o', 'ServerAliveCountMax=2', self.config['sshHost'], WATCH_COMMAND,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=4096)
                while True:
                    line = await asyncio.wait_for(process.stdout.readline(), 45)
                    if not line:
                        raise RuntimeError('usage notification channel disconnected')
                    message = json.loads(line)
                    event = message.get('event')
                    if event not in ('ready', 'alive', 'usage-changed'):
                        continue
                    self.device_connected = True
                    backoff = 2
                    if event == 'ready':
                        self.trigger('device-reconnected')
                    elif event == 'usage-changed':
                        self.trigger('device-usage')
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
            finally:
                self.device_connected = False
                if process:
                    await stop_process(process)
            await asyncio.sleep(backoff)
            backoff = min(backoff*2, 30)

    async def timer_loop(self):
        last_fallback, last_publish, last_followup = time.monotonic(), time.monotonic(), 0
        home = (self.config.get('hostUsage') or {}).get('codexHome')
        logs = LocalSignals(home) if home else None
        while True:
            await asyncio.sleep(2)
            now = time.monotonic()
            if logs:
                try:
                    if await asyncio.to_thread(logs.poll):
                        self.trigger('local-usage')
                except Exception:
                    pass  # The timed scan remains available; never log file contents.
            if now-last_fallback >= FALLBACK_SECONDS:
                self.trigger('fallback'); last_fallback = now
            elif now < self.catchup_until and now-last_followup >= 15:
                self.trigger('usage-followup'); last_followup = now
            if now-last_publish >= PUBLISH_SECONDS:
                self.dirty.set(); last_publish = now

    def sample(self):
        return {**self.latest, 'collection': {
            'mode': 'notifications-first', 'fallbackSeconds': FALLBACK_SECONDS,
            'publishSeconds': PUBLISH_SECONDS, 'readerConnected': self.reader_connected,
            'deviceNotificationsConnected': self.device_connected,
            'trigger': self.trigger_name, 'reads': self.read_count, 'usageEvents': self.event_count}}

    async def publisher_loop(self):
        while True:
            await self.dirty.wait()
            self.dirty.clear()
            if self.latest is None:
                continue
            try:
                await asyncio.to_thread(self.publish, self.config, self.sample())
            except Exception:
                # Latest state is retried on the next periodic tick. Never refresh
                # quota capture time after upload errors or while reusing a sample.
                pass

    async def run(self):
        tasks = [asyncio.create_task(fn()) for fn in (
            self.reader_loop, self.device_loop, self.timer_loop, self.publisher_loop)]
        try:
            await asyncio.gather(*tasks)
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)


async def monitor(config, sanitize, unavailable, publish):
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for name in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(name, stop.set)
    task = asyncio.create_task(Monitor(config, sanitize, unavailable, publish).run())
    stopping = asyncio.create_task(stop.wait())
    try:
        done, _ = await asyncio.wait((task, stopping), return_when=asyncio.FIRST_COMPLETED)
        if task in done:
            await task
    finally:
        task.cancel(); stopping.cancel()
        await asyncio.gather(task, stopping, return_exceptions=True)
        for name in (signal.SIGTERM, signal.SIGINT):
            loop.remove_signal_handler(name)
