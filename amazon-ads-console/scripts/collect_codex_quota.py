#!/usr/bin/env python3
"""Read official quota without model calls and send sanitized snapshots through existing SSH."""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
from datetime import datetime, timezone


def atomic(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream)
    os.chmod(temp, 0o600)
    temp.replace(path)


def clean_window(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('invalid official window')
    used, minutes, reset = (value.get(k) for k in ('usedPercent', 'windowDurationMins', 'resetsAt'))
    if isinstance(used, bool) or not isinstance(used, (int, float)) or not 0 <= used <= 100:
        raise ValueError('invalid official percentage')
    if type(minutes) is not int or minutes <= 0 or type(reset) is not int or reset <= 0:
        raise ValueError('invalid official period')
    return {'usedPercent': used, 'windowDurationMins': minutes, 'resetsAt': reset}


def sanitize(result, expected_digest):
    identity = result.get('accountId')
    if not isinstance(identity, str) or hashlib.sha256(identity.encode()).hexdigest() != expected_digest:
        raise ValueError('source account identity mismatch')
    limits = (result.get('rateLimitsByLimitId') or {}).get('codex') or result.get('rateLimits') or {}
    primary, secondary = clean_window(limits.get('primary')), clean_window(limits.get('secondary'))
    if not primary and not secondary:
        raise ValueError('official quota unavailable')
    plan = limits.get('planType')
    return {'schemaVersion': 1, 'status': 'available',
            'capturedAt': datetime.now(timezone.utc).isoformat(),
            'primary': primary, 'secondary': secondary,
            'planType': plan if isinstance(plan, str) and len(plan) <= 32 else None}


async def read_limits(config):
    env = os.environ.copy()
    env['CODEX_HOME'] = config['codexHome']
    with tempfile.TemporaryDirectory(prefix='codex-quota-reader-') as tmp:
        # Do not open or migrate the running source's session database.
        env['CODEX_SQLITE_HOME'] = tmp
        process = await asyncio.create_subprocess_exec(config['codexExecutable'], 'app-server', '--stdio',
            env=env, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL)
        async def send(value):
            process.stdin.write((json.dumps(value)+'\n').encode())
            await process.stdin.drain()
        async def reply(request_id):
            while True:
                line = await process.stdout.readline()
                if not line:
                    raise RuntimeError('quota reader exited')
                if len(line) > 1024*1024:
                    raise ValueError('quota reply too large')
                value = json.loads(line)
                if value.get('id') == request_id:
                    if 'error' in value:
                        raise RuntimeError('official quota request rejected')
                    return value['result']
        try:
            await send({'id': 1, 'method': 'initialize', 'params': {'clientInfo': {'name': 'codex_relay_quota', 'version': '0.3.0'}}})
            await asyncio.wait_for(reply(1), 15)
            await send({'method': 'initialized', 'params': {}})
            await send({'id': 2, 'method': 'account/rateLimits/read', 'params': {}})
            result = await asyncio.wait_for(reply(2), 30)
            return sanitize(result, config['expectedAccountDigest'])
        finally:
            if process.returncode is None:
                process.terminate()
            try:
                await asyncio.wait_for(process.wait(), 5)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()


REMOTE_WRITER = '''import json,os,sys
from pathlib import Path
v=json.load(sys.stdin);p=Path(v['destination'])
assert p.is_absolute() and str(p).startswith('/opt/agent/cpo/shared/') and '..' not in p.parts
p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
t=p.with_suffix('.tmp');fd=os.open(t,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f:json.dump(v['snapshot'],f)
os.chmod(t,0o600);t.replace(p)
'''


def publish(config, value):
    """Publish a verified sample. Reusing it must never change capturedAt."""
    atomic(config['localSnapshot'], value)
    payload = json.dumps({'destination': config['remoteSnapshot'], 'snapshot': value})
    subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8',
        config['sshHost'], 'python3 -c '+shlex.quote(REMOTE_WRITER)], input=payload, text=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20, check=True)
    if config.get('hostUsage'):
        from collect_codex_host_usage import collect_host
        host_config = config['hostUsage']
        try:
            host = collect_host(host_config, value)
        except Exception:
            host = {'schemaVersion':1,'status':'unavailable','capturedAt':datetime.now(timezone.utc).isoformat(),
                    'userId':host_config['userId'],'deviceId':host_config['deviceId']}
        atomic(host_config['localSnapshot'], host)
        subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',
            config['sshHost'],'python3 -c '+shlex.quote(REMOTE_WRITER)],
            input=json.dumps({'destination':host_config['remoteSnapshot'],'snapshot':host}),text=True,
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=True)
        evidence_path = Path(host_config['localSnapshot']).with_suffix('.evidence.json')
        if evidence_path.exists() and evidence_path.stat().st_size<=8*1024*1024 and not evidence_path.stat().st_mode & 0o077:
            subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',
                config['sshHost'],'python3 -c '+shlex.quote(REMOTE_WRITER)],
                input=json.dumps({'destination':str(Path(host_config['remoteSnapshot']).with_suffix('.evidence.json')),
                                  'snapshot':json.loads(evidence_path.read_text())}),text=True,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=True)
    if config.get('reconcileAttribution') is True:
        # Fixed server entrypoint, using only code from the active published release.
        command = ('CPO_ENV_FILE=/opt/agent/cpo/shared/backend.env '
                   '/opt/agent/cpo/current/.venv/bin/python '
                   '/opt/agent/cpo/current/amazon-ads-console/scripts/reconcile_codex_attribution.py')
        subprocess.run(['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8',
            config['sshHost'],command], stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30,check=True)
    return value


def collect(config):
    try:
        value = asyncio.run(read_limits(config))
    except Exception:
        value = unavailable()
    return publish(config, value)


def unavailable():
    return {'schemaVersion': 1, 'status': 'unavailable',
            'capturedAt': datetime.now(timezone.utc).isoformat(), 'primary': None, 'secondary': None}


# The persistent scheduler is separate so --once remains a bounded diagnostic.
async def serve(config):
    from codex_quota_events import monitor
    await monitor(config, sanitize, unavailable, publish)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    path = Path(args.config)
    if path.stat().st_mode & 0o077:
        raise RuntimeError('collector configuration must be private')
    config = json.loads(path.read_text())
    if args.once:
        value = collect(config)
        print(json.dumps({'status': value['status'], 'capturedAt': value['capturedAt']}))
        return
    import fcntl
    with open(path.with_suffix('.lock'), 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        asyncio.run(serve(config))


if __name__ == '__main__':
    main()
