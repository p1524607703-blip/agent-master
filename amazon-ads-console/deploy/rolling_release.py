"""Git-pinned blue/green CPO activation. No live-cache deletion or forced drain.

Run activate/retire as root under deploy.lock; serve runs as the ubuntu user.
Traffic is switched only after candidate readiness and scoped cache warming.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

BASE = Path('/opt/agent/cpo')
STATE = BASE / 'shared/rolling.json'
UPSTREAM = Path('/etc/nginx/conf.d/cpo-active.conf')
INTERNAL = Path('/etc/nginx/conf.d/cpo-internal.conf')
FRONTEND = Path('/var/www/cpo-console')
SNIPPETS = [Path('/etc/nginx/snippets/' + x) for x in ('cpo-api-proxy.conf', 'codex-model-proxy.conf')]
SYSTEMD = Path('/etc/systemd/system')
UNIT = SYSTEMD / 'cpo-console.service'
SLOTS = {'blue': 8001, 'green': 8002}


def run(*cmd, timeout=30, check=True):
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if check and result.returncode:
        # Commands/env/response bodies can contain private data; log only the executable.
        raise RuntimeError('Host operation failed: ' + Path(cmd[0]).name)
    return result


def write(path, content, mode=0o644):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.rolling-tmp')
    temp.write_text(content)
    temp.chmod(mode)
    temp.replace(path)


def save_state(value):
    write(STATE, json.dumps(value, indent=2) + '\n', 0o600)
    user = pwd.getpwnam('ubuntu')
    os.chown(STATE, user.pw_uid, user.pw_gid)


def active_state():
    return json.loads(STATE.read_text()) if STATE.exists() else None


def unit_name(slot):
    assert slot in SLOTS
    return 'cpo-console-' + slot + '.service'


def upstream(port):
    assert port in (8000, 8001, 8002)
    return f'upstream cpo_active {{ server 127.0.0.1:{port}; }}\n'


def proxy_snippet(text):
    count = len(re.findall(r'proxy_pass\s+http://(?:127\.0\.0\.1:8000|cpo_active)\s*;', text))
    if count != 1:
        raise ValueError('Unknown CPO proxy configuration; refuse replacement')
    return re.sub(r'proxy_pass\s+http://(?:127\.0\.0\.1:8000|cpo_active)\s*;', 'proxy_pass http://cpo_active;', text)


def connections(port):
    # Include established/handshake/closing sockets; ignore the listener and TIME_WAIT.
    output = run('ss', '-Htn', 'state', 'all', f'( sport = :{port} )').stdout.decode()
    return sum(1 for line in output.splitlines() if line.split()[0] not in {'LISTEN', 'TIME-WAIT', 'CLOSE'})


def idle(port, *, samples=3, pause=time.sleep):
    for sample in range(samples):
        if connections(port):
            return False
        if sample + 1 < samples:
            pause(1)
    return True


def ready(port, commit, attempts=60, *, pause=time.sleep):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for attempt in range(attempts):
        try:
            with opener.open(f'http://127.0.0.1:{port}/api/ping', timeout=3) as response:
                value = json.load(response)
                actual = response.headers.get('X-CPO-Release')
            if value != {'ok': True} or actual != commit:
                raise ValueError('Readiness release mismatch')
            try:
                opener.open(f'http://127.0.0.1:{port}/api/auth/me', timeout=3)
                raise ValueError('Anonymous authentication bypass')
            except urllib.error.HTTPError as error:
                if error.code == 401:
                    return
        except (OSError, ValueError):
            pass
        if attempt + 1 < attempts:
            pause(1)
    raise RuntimeError('Candidate readiness failed')


def slot_unit(release, port, engine):
    return f'''[Unit]
Description=CPO Console API slot {release.name}
After=network.target postgresql.service
Requires=postgresql.service
[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory={release}/amazon-ads-console/backend
ExecStart={release}/.venv/bin/python {engine} serve {release} --port {port}
Environment=PYTHONUNBUFFERED=1
Environment=CPO_RELEASE_COMMIT={release.name}
Environment=CPO_CACHE_NAMESPACE={release.name}
Environment=CPO_TRACE_LOG=/opt/agent/cpo/shared/traces/requests.jsonl
Restart=on-failure
RestartSec=5
TimeoutStopSec=infinity
NoNewPrivileges=true
PrivateTmp=true
UMask=0077
[Install]
WantedBy=multi-user.target
'''


def marker(slot):
    # Stopping this compatibility unit never propagates a stop to its dependency.
    return f'''[Unit]
Description=CPO Console active-slot aggregate (check slot readiness as well)
Requires={unit_name(slot)}
BindsTo={unit_name(slot)}
After={unit_name(slot)}
[Service]
Type=oneshot
ExecStart=/usr/bin/true
RemainAfterExit=yes
[Install]
WantedBy=multi-user.target
'''


def internal_proxy():
    return '''# Stable loopback compatibility entry; backend workers use 8001/8002.
server {
 listen 127.0.0.1:8000;
 server_name localhost;
 location /api/ {
  proxy_pass http://cpo_active;
  proxy_http_version 1.1;
  proxy_set_header Connection "";
  proxy_set_header Host $host;
  proxy_set_header Authorization $http_authorization;
  proxy_set_header X-Request-ID $http_x_request_id;
  proxy_buffering off;
  proxy_read_timeout 300s;
  proxy_send_timeout 300s;
  client_max_body_size 120m;
  access_log off;
 }
 location / { return 404; }
}
'''


def reload_nginx():
    run('nginx', '-t')
    run('systemctl', 'reload', 'nginx')


def link(path, target):
    temp = path.with_name(path.name + '.rolling-tmp')
    if temp.is_symlink():
        temp.unlink()
    temp.symlink_to(target)
    temp.replace(path)


def retirement_timer(engine):
    write(SYSTEMD / 'cpo-retire.service', f'''[Unit]
Description=Retire idle CPO release without interrupting streams
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 {engine} retire
''')
    write(SYSTEMD / 'cpo-retire.timer', '''[Unit]
Description=Check draining CPO release
[Timer]
OnBootSec=30s
OnUnitActiveSec=15s
[Install]
WantedBy=timers.target
''')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'cpo-retire.timer')


def retire():
    state = active_state()
    if not state:
        return
    if (json.loads((BASE / 'current/release.json').read_text())['commit'] != state['commit']
            or (state['slot'] != 'legacy' and UPSTREAM.read_text() != upstream(state['port']))):
        raise RuntimeError('Release pointers disagree; inspect rolling-backups before retiring')
    if not state.get('draining'):
        ensure_marker(state['slot'])
        return
    old = state['draining']
    if old['port'] == state['port'] or old['commit'] == state['commit']:
        raise RuntimeError('Refuse retirement of active release')
    if not idle(old['port']):
        return  # Never SIGKILL a long/active stream; next activation refuses slot reuse.
    run('systemctl', 'stop', old['unit'], timeout=25)
    if old['unit'] != 'cpo-console.service':
        run('systemctl', 'disable', old['unit'])
    if old['unit'] == 'cpo-console.service':
        # Install stable internal routing only after the legacy listener has exited.
        write(INTERNAL, internal_proxy())
        try:
            reload_nginx()
        except Exception:
            INTERNAL.unlink(missing_ok=True)
            reload_nginx()
            run('systemctl', 'start', old['unit'])
            raise
    state['draining'] = None
    save_state(state)
    ensure_marker(state['slot'])


def ensure_marker(slot):
    if slot == 'legacy':
        run('systemctl', 'start', 'cpo-console')
        return
    value = marker(slot)
    if not UNIT.exists() or UNIT.read_text() != value:
        write(UNIT, value)
        run('systemctl', 'daemon-reload')
    run('systemctl', 'start', 'cpo-console')


def public_ready(url, commit, *, seconds=30, clock=time.monotonic, pause=time.sleep):
    # nginx reload is asynchronous: old workers may briefly accept a new request.
    # Wait for *both* versions and the auth boundary to converge before committing.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = clock() + seconds
    mismatch = 'unknown'
    while True:
        try:
            for suffix in ('/version.json', '/api/ping'):
                with opener.open(url.rstrip('/') + suffix, timeout=3) as response:
                    value = json.load(response)
                    actual = value.get('commit') if suffix == '/version.json' else response.headers.get('X-CPO-Release')
                if actual != commit:
                    mismatch = suffix
                    raise ValueError('Release not converged')
            try:
                response = opener.open(url.rstrip('/') + '/api/auth/me', timeout=3)
                response.close()
                mismatch = 'authentication'
            except urllib.error.HTTPError as error:
                error.close()
                if error.code == 401:
                    return
                mismatch = 'authentication_status'
        except (OSError, ValueError):
            pass
        if clock() >= deadline:
            raise RuntimeError('Public readiness did not converge: ' + mismatch)
        pause(min(.5, max(0, deadline - clock())))


@contextmanager
def locked():
    with (BASE / 'deploy.lock').open('a') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
        else:
            yield True


def activate(release, engine):
    # Parent deploy.sh already holds deploy.lock throughout this function.
    old = active_state()
    if old and old.get('draining'):
        retire()
        old = active_state()
        if old.get('draining'):
            raise RuntimeError('Previous release still draining; refusing slot reuse')
    if old and old['commit'] == release.name:
        ready(old['port'], release.name, attempts=3)
        return
    if old and (old['commit'] != json.loads((BASE / 'current/release.json').read_text())['commit']
                or (old['slot'] != 'legacy' and UPSTREAM.read_text() != upstream(old['port']))):
        raise RuntimeError('Active slot and release pointer disagree')
    slot = 'green' if old and old['slot'] == 'blue' else 'blue'
    port = SLOTS[slot]
    selected = unit_name(slot)
    if run('systemctl', 'is-active', '--quiet', selected, check=False).returncode == 0:
        raise RuntimeError('Candidate slot is occupied')
    if connections(port):
        raise RuntimeError('Candidate port is occupied')
    # Preserve exact nginx files and links. No config is reloaded until all files exist.
    paths = [UPSTREAM, INTERNAL, *SNIPPETS, UNIT]
    originals = {p: p.read_bytes() if p.exists() else None for p in paths}
    links = {p: os.readlink(p) for p in [BASE / 'current', FRONTEND]}
    previous = old or {'slot': 'legacy', 'port': 8000, 'unit': 'cpo-console.service',
                       'commit': json.loads((BASE / 'current/release.json').read_text())['commit']}
    candidate = {'slot': slot, 'port': port, 'unit': selected, 'commit': release.name,
                 'engine': str(engine), 'draining': previous}
    switched = False
    try:
        write(SYSTEMD / 'cpo-console.service.d/cpo-drain.conf', '[Service]\nTimeoutStopSec=infinity\n')
        if not old or old.get('slot') == 'legacy':
            pinned = UNIT.read_text().replace(str(BASE / 'current') + '/', str(BASE / 'releases' / previous['commit']) + '/')
            write(UNIT, pinned)
        write(SYSTEMD / selected, slot_unit(release, port, engine))
        run('systemctl', 'daemon-reload')
        run('systemctl', 'start', selected)
        ready(port, release.name)
        env = ['env', 'CPO_CACHE_NAMESPACE=' + release.name, 'CPO_RELEASE_COMMIT=' + release.name]
        if 'def namespace(' not in (release / 'amazon-ads-console/backend/app/services/build_cache.py').read_text():
            env += ['CPO_REDIS_ENABLED=false']  # Old rollback app cannot share incompatible snapshots.
        run('runuser', '-u', 'ubuntu', '--', *env, str(release / '.venv/bin/python'),
            str(engine.parent / 'cache_release.py'), str(release), 'prewarm', timeout=240)
        ready(port, release.name, attempts=3)
        retirement_timer(engine)
        run('systemctl', 'enable', selected)
        # Capture durable private recovery evidence before the cutover.
        audit = BASE / 'shared/rolling-backups' / (str(time.time_ns()) + '-' + release.name)
        audit.mkdir(parents=True, mode=0o700)
        for i, (path, data) in enumerate(originals.items()):
            if data is not None:
                write(audit / str(i), data.decode(), 0o600)
        write(audit / 'manifest.json', json.dumps({'paths': [str(p) for p in paths],
            'present': [v is not None for v in originals.values()], 'links': {str(p): t for p,t in links.items()},
            'previous': previous, 'candidate': candidate}), 0o600)
        write(audit / 'phase.json', json.dumps({'phase': 'SWITCHING', 'commit': release.name}), 0o600)
        write(UPSTREAM, upstream(port))
        for snippet in SNIPPETS:
            write(snippet, proxy_snippet(snippet.read_text()).replace('access_log off;', 'access_log /var/log/nginx/cpo_api_access.log cpo_api;'))
        reload_nginx()
        switched = True
        link(BASE / 'current', release)
        link(FRONTEND, release / 'amazon-ads-console/frontend/dist')
        public = json.loads((release / 'release.json').read_text())['public_url']
        public_ready(public, release.name)
        # Commit only after both the public frontend/backend and auth boundary pass.
        save_state(candidate)
        write(audit / 'phase.json', json.dumps({'phase': 'COMMITTED', 'commit': release.name}), 0o600)
    except Exception:
        for path, data in originals.items():
            if data is None:
                path.unlink(missing_ok=True)
            else:
                write(path, data.decode())
        for path, target in links.items():
            link(path, target)
        reload_nginx()
        run('systemctl', 'daemon-reload')
        if old:
            save_state(old)
            run('systemctl', 'start', 'cpo-console')
        else:
            STATE.unlink(missing_ok=True)
        run('systemctl', 'disable', selected, check=False)
        # A candidate that already received traffic drains too. Never kill it on rollback.
        if idle(port):
            run('systemctl', 'stop', selected, timeout=25)
        elif switched:
            recovery = dict(old or previous)
            recovery['draining'] = {'slot': slot, 'port': port, 'unit': selected,
                                    'commit': release.name}
            save_state(recovery)
            retirement_timer(engine)
        raise

    # Retirement is post-commit maintenance. Failure must not roll back a healthy
    # release after an old process has exited; the timer retries it conservatively.
    try:
        retire()
        retirement = bool(active_state().get('draining'))
    except Exception as error:
        retirement = True
        print(json.dumps({'retirement_pending': True, 'error_class': type(error).__name__}))
    print(json.dumps({'healthy': True, 'slot': slot, 'commit': release.name,
                      'draining': retirement}))


def serve(release, port):
    os.environ['CPO_RELEASE_COMMIT'] = release.name
    os.environ['CPO_CACHE_NAMESPACE'] = release.name
    backend = release / 'amazon-ads-console/backend'
    os.chdir(backend)
    sys.path.insert(0, str(backend))
    if 'def namespace(' not in (backend / 'app/services/build_cache.py').read_text():
        os.environ['CPO_REDIS_ENABLED'] = 'false'
    from dotenv import load_dotenv
    load_dotenv(backend / '.env', override=False)
    # Fixed launch identity wins over shared environment/defaults.
    os.environ['CPO_RELEASE_COMMIT'] = release.name
    os.environ['CPO_CACHE_NAMESPACE'] = release.name
    import run_rds  # Configures DSNs; never runs its legacy hard-coded port launcher.
    from app.main import app
    # Older rollback apps expose no version in ping. The engine supplies readiness metadata.
    for route in app.routes:
        if getattr(route, 'path', None) == '/api/ping':
            app.routes.remove(route)
            break
    @app.get('/api/ping')
    def ping():
        from fastapi.responses import JSONResponse
        return JSONResponse({'ok': True}, headers={'X-CPO-Release': release.name})
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=port, access_log=False, proxy_headers=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('activate', 'retire', 'serve'))
    parser.add_argument('release', nargs='?', type=Path)
    parser.add_argument('--port', type=int, choices=tuple(SLOTS.values()))
    args = parser.parse_args()
    if args.action == 'serve':
        serve(args.release, args.port)
    elif args.action == 'activate':
        release = args.release.resolve()
        if release.parent != BASE / 'releases' or not re.fullmatch('[0-9a-f]{40}', release.name):
            raise ValueError('Expected a pinned release path')
        activate(release, Path(__file__).resolve())
    else:
        with locked() as acquired:
            if acquired:
                retire()


if __name__ == '__main__':
    main()
