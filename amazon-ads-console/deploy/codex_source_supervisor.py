#!/usr/bin/env python3
"""Supervise only the existing local Codex++ source and device-key gateway."""
import argparse
import fcntl
import http.client
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / 'services.json'


def atomic(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    os.chmod(temp, 0o600)
    temp.replace(path)


def command_line(pid):
    try:
        result = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'stat=,command='],
                                capture_output=True, text=True, timeout=4)
    except (OSError,subprocess.TimeoutExpired):
        return ''  # Uncertain identity must never authorize a process termination.
    value = result.stdout.strip()
    if not value or value.split()[0].startswith('Z'):
        return ''
    return value.split(None, 1)[1] if len(value.split(None, 1)) == 2 else ''


def matches(pid, role, config):
    value = command_line(pid)
    if role == 'source':
        return value.startswith(config['sourceExecutable'] + ' ') and \
            '--codex-plus-multi-worker ' + config['sourceOptions'] in value
    scripts = [config['gatewayScript'], config.get('adoptedGatewayScript', '')]
    return any(script and script in value for script in scripts) and \
        '--config ' + config['gatewayConfig'] in value


def owner(role, config):
    port = config['sourcePort'] if role == 'source' else config['gatewayPort']
    result = subprocess.run(['/usr/sbin/lsof', '-nP', '-t', '-iTCP:%d' % port, '-sTCP:LISTEN'],
                            capture_output=True, text=True, timeout=5)
    for value in set(result.stdout.split()):
        if value.isdigit() and matches(int(value), role, config):
            return int(value)
    return None


def probe_owner(role, config):
    try:
        return owner(role,config),True
    except (OSError,subprocess.TimeoutExpired):
        return None,False


def write_status(path, value, logger):
    try:
        atomic(path,value)
        return True
    except OSError as exc:
        # A full disk/status write failure must not take a healthy source down.
        logger.warning('status_write_failed errno=%s',exc.errno)
        return False


def process_exists(pid):
    if not pid:
        return False
    try:
        os.kill(pid,0)
        return True
    except OSError:
        return False


def http_check(role, config):
    port = config['sourcePort'] if role == 'source' else config['gatewayPort']
    connection = http.client.HTTPConnection('127.0.0.1', port, timeout=3)
    try:
        if role == 'source':
            connection.request('POST', '/backend/status', '{}', {'Content-Type': 'application/json'})
        else:
            secret = json.loads(Path(config['gatewayConfig']).read_text())['deviceKeys']['local-test']
            connection.request('GET', '/v1/models', headers={'Authorization': 'Bearer ' + secret})
        response = connection.getresponse()
        body = response.read(65536)
        if response.status != 200:
            return False, 'http_%d' % response.status
        data = json.loads(body)
        if not isinstance(data, dict):
            return False, 'invalid_local_reply'
        if role == 'gateway' and not any(m.get('id') == config['model'] for m in data.get('data', [])):
            return False, 'model_catalog_mismatch'
        return True, 'local_http_ok'
    except (OSError, http.client.HTTPException, ValueError, KeyError):
        return False, 'unavailable_or_invalid_local_reply'
    finally:
        connection.close()


def terminate(pid, role, config):
    if not pid or not matches(pid, role, config):
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if not matches(pid, role, config):
            return
        time.sleep(0.25)
    if matches(pid, role, config):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def validate_source_isolation(config, env):
    # Only this service's worker may be launched; never fall back to the main home.
    options_path = Path(config['sourceOptions']).expanduser().resolve()
    instance = options_path.parent
    main_home = Path.home().resolve()
    expected = {
        'CODEX_HOME': instance / 'codex-home',
        'CODEX_SQLITE_HOME': instance / 'sqlite-home',
        'HOME': instance / 'worker-home',
        'CODEX_PLUS_STATE_DIR': instance / 'worker-home' / '.codex-session-delete',
    }
    for key, target in expected.items():
        actual = Path(env.get(key, '')).expanduser().resolve()
        if not env.get(key) or actual != target.resolve():
            raise ValueError('Source worker isolation mismatch: ' + key)
        if actual in (main_home, main_home / '.codex', main_home / '.codex-session-delete'):
            raise ValueError('Source worker overlaps main authentication directory')
    options = json.loads(options_path.read_text())
    if Path(options.get('stateDir', '')).expanduser().resolve() != expected['CODEX_PLUS_STATE_DIR'].resolve():
        raise ValueError('Source worker state directory mismatch')
    return True


def launch(role, config):
    env = os.environ.copy()
    for key in ('NO_PROXY', 'no_proxy'):
        values = [v for v in env.get(key, '').split(',') if v]
        env[key] = ','.join(dict.fromkeys(values + ['127.0.0.1', 'localhost', '::1']))
    if role == 'source':
        # Reuse the vendor-generated multi-instance launch environment verbatim.
        # This is local to this isolated child; no shell or launchd global environment changes.
        env.update(json.loads(Path(config['sourceEnvironment']).read_text()))
        validate_source_isolation(config, env)
        command = [config['sourceExecutable'], '--codex-plus-multi-worker', config['sourceOptions']]
        result = Path(config['sourceOptions']).with_name('launch-result.json')
        if result.exists():
            result.unlink()
    else:
        command = [config['python'], config['gatewayScript'], '--config', config['gatewayConfig'],
                   '--log-file', str(ROOT / 'gateway-requests.log')]
    log_path = ROOT / (role + '-child.log')
    if log_path.exists() and log_path.stat().st_size > 2000000:
        log_path.replace(log_path.with_suffix('.previous.log'))
    with log_path.open('ab') as output:
        child = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL,
                                 stdout=output, stderr=output, start_new_session=True)
    if role == 'source':
        manifest = Path(config['sourceOptions']).with_name('instance.json')
        data = json.loads(manifest.read_text())
        data.update(pid=child.pid, status='starting', running=False, startedAtMs=int(time.time() * 1000))
        atomic(manifest, data)
    return child


def serve(role):
    os.umask(0o077)
    config = json.loads(CONFIG.read_text())
    lock = (ROOT / (role + '.lock')).open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 0
    logger = logging.getLogger(role)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(ROOT / (role + '-events.log'), maxBytes=2000000,
                                  backupCount=3, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
    logger.addHandler(handler)
    status_path = ROOT / (role + '-status.json')
    try:
        previous = json.loads(status_path.read_text())
    except (OSError, ValueError):
        previous = {}
    restarts = previous.get('restartTimes', [])
    starts = previous.get('startCount', 0)
    stop = [False]
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.__setitem__(0, True))
    child = None
    managed_pid = None
    generation = None
    state = None
    failures = 0
    warmup_until = 0
    next_start = 0
    try:
        while not stop[0]:
            if child:
                child.poll()
            now = time.time()
            paused = (ROOT / (role + '.paused')).exists()
            pid,probe_available = probe_owner(role, config)
            healthy, reason = http_check(role, config) if pid else (False, 'expected_process_not_listening')
            if not probe_available:
                current,reason = 'probe_unavailable','process_probe_unavailable'
            elif paused:
                terminate(pid or managed_pid, role, config)
                managed_pid = None
                if child:
                    child.poll()
                current = 'paused'
            elif healthy:
                managed_pid = pid
                failures = 0
                warmup_until = 0
                current = 'healthy'
                if generation != pid:
                    logger.info('adopted_or_recovered pid=%s', pid)
                    generation = pid
            elif now < warmup_until:
                current = 'starting'
            else:
                failures += 1
                current = 'degraded'
                restarts = [t for t in restarts if now - t < 600]
                if len(restarts) >= 5:
                    current = 'recovery_backoff'
                elif failures >= (6 if pid or process_exists(managed_pid) else 2) and now >= next_start:
                    logger.warning('local_health_failed reason=%s; recovery_attempt', reason)
                    terminate(pid or managed_pid, role, config)
                    if child:
                        child.poll()
                    child = launch(role, config)
                    managed_pid = child.pid
                    restarts.append(now)
                    starts += 1
                    failures = 0
                    warmup_until = now + (100 if role == 'source' else 12)
                    next_start = now + 15
                    current = 'starting'
                    logger.info('started pid=%s attempt_count=%s', child.pid, len(restarts))
            if current != state:
                logger.info('state=%s reason=%s', current, reason)
                state = current
            write_status(status_path, {'role': role, 'state': state, 'pid': managed_pid,
                   'supervisorPid': os.getpid(), 'checkedAt': now, 'startCount': starts,
                   'restartTimes': restarts, 'reason': reason, 'localHealthy': healthy and not paused,
                   'upstreamModelProbed': False},logger)
            for _ in range(10):
                if stop[0]:
                    break
                time.sleep(0.5)
    except Exception as exc:
        # Exception class only: child errors must never dump credentials or settings.
        logger.error('supervisor_error class=%s', type(exc).__name__)
        return 1
    finally:
        final_pid,_ = probe_owner(role,config)
        terminate(final_pid or managed_pid, role, config)
        if child:
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        logger.info('supervisor_stopped')
        lock.close()
    return 0


def model_probe():
    config = json.loads(CONFIG.read_text())
    secret = json.loads(Path(config['gatewayConfig']).read_text())['deviceKeys']['local-test']
    connection = http.client.HTTPConnection('127.0.0.1', config['gatewayPort'], timeout=45)
    body = {'model': config['model'], 'stream': True, 'store': False,
            'instructions': 'Return exactly service-health-ok.',
            'input': [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'Confirm service recovery.'}]}]}
    result = {'checkedAt': time.time(), 'httpStatus': None, 'completed': False, 'expectedReply': False}
    try:
        connection.request('POST', '/v1/responses', json.dumps(body),
                           {'Authorization': 'Bearer ' + secret, 'Content-Type': 'application/json'})
        response = connection.getresponse()
        result['httpStatus'] = response.status
        text = ''
        for line in response.read().decode().splitlines():
            if not line.startswith('data: '):
                continue
            try:
                event = json.loads(line[6:])
            except ValueError:
                continue
            if event.get('type') == 'response.output_text.delta':
                text += event.get('delta', '')
            if event.get('type') == 'response.completed':
                result['completed'] = True
        result['expectedReply'] = text.strip() == 'service-health-ok'
    except (OSError, http.client.HTTPException):
        result['transportFailed'] = True
    finally:
        connection.close()
    atomic(ROOT / 'last-model-probe.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('serve', 'status', 'pause', 'resume', 'probe', 'check-isolation'))
    parser.add_argument('role', choices=('source', 'gateway', 'all'), nargs='?', default='all')
    args = parser.parse_args()
    os.umask(0o077)
    if args.command == 'check-isolation':
        config = json.loads(CONFIG.read_text())
        env = json.loads(Path(config['sourceEnvironment']).read_text())
        validate_source_isolation(config, env)
        print(json.dumps({'isolated': True, 'mainAuthenticationModified': False, 'sourceRestarted': False}))
        return 0
    if args.command == 'serve':
        if args.role == 'all':
            parser.error('serve requires a single role')
        return serve(args.role)
    if args.command == 'probe':
        result = model_probe()
        print(json.dumps(result))
        return 0 if result['httpStatus'] == 200 and result['completed'] and result['expectedReply'] else 1
    roles = ('source', 'gateway') if args.role == 'all' else (args.role,)
    results = {}
    for role in roles:
        flag = ROOT / (role + '.paused')
        if args.command == 'pause':
            flag.touch(mode=0o600)
        elif args.command == 'resume':
            flag.unlink(missing_ok=True)
        status = ROOT / (role + '-status.json')
        results[role] = json.loads(status.read_text()) if status.exists() else {'state': 'not_started'}
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
