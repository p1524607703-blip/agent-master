#!/usr/bin/env python3
"""Install reproducible CPO host configuration with backups and validation.

Run this file from a Git-verified release as root. It never switches application
code or alters databases. Backups live outside all nginx include directories.
"""
import argparse
import json
import os
import pwd
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / 'deploy/infra'
PROJECT = ASSETS.parent.parent
BACKUP_PATTERN = re.compile(r'(?:\.bak|\.backup|\.old)(?:\.|$)|~$')


def without_legacy_format(text):
    # Previous manual edits defined an unsafe request_uri/referer log format in
    # nginx.conf. The replacement is a single JSON format in conf.d.
    return re.sub(r'^[ \t]*log_format[ \t]+cpo_api\b[^;]*;[ \t]*\n?', '', text,
                  flags=re.MULTILINE)


def configuration_plan(server_name, certificate_dir):
    if not re.fullmatch(r'[A-Za-z0-9.-]+', server_name):
        raise ValueError('server_name must be a DNS hostname or IP address')
    if not re.fullmatch(r'/[A-Za-z0-9_./-]+', certificate_dir):
        raise ValueError('Invalid certificate directory')
    assets = {
        '/etc/nginx/conf.d/cpo-observability.conf': 'cpo-observability.conf',
        '/etc/nginx/snippets/cpo-response-headers.conf': 'cpo-response-headers.conf',
        '/etc/nginx/snippets/cpo-api-proxy.conf': 'cpo-api-proxy.conf',
        '/etc/nginx/sites-available/default': 'cpo-site.conf',
        '/etc/systemd/journald.conf.d/cpo.conf': 'journald-cpo.conf',
        '/etc/logrotate.d/nginx': 'logrotate-nginx',
        '/etc/logrotate.d/cpo-traces': 'logrotate-cpo-traces',
        '/etc/systemd/system/cpo-redis-watchdog.service': 'cpo-redis-watchdog.service',
        '/etc/systemd/system/cpo-redis-watchdog.timer': 'cpo-redis-watchdog.timer',
        '/etc/systemd/system/cpo-logrotate.service': 'cpo-logrotate.service',
        '/etc/systemd/system/cpo-logrotate.timer': 'cpo-logrotate.timer',
    }
    plan = {path: (ASSETS / asset).read_text() for path, asset in assets.items()}
    plan['/etc/nginx/sites-available/default'] = plan['/etc/nginx/sites-available/default'].replace(
        '{{SERVER_NAME}}', server_name).replace('{{CERTIFICATE_DIR}}', certificate_dir)
    plan['/opt/agent/cpo/tooling/redis_watchdog.py'] = (PROJECT / 'deploy/redis_watchdog.py').read_text()
    plan['/etc/systemd/system/cpo-console.service.d/cpo-observability.conf'] = (
        '[Service]\nEnvironment=CPO_TRACE_LOG=/opt/agent/cpo/shared/traces/requests.jsonl\n')
    return plan


def run(*command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(json.dumps({'check': list(command[:2]), 'status': 'OK' if result.returncode == 0 else 'FAILED'}))
    if result.returncode:
        print(result.stdout[-4000:], file=sys.stderr)
        raise subprocess.CalledProcessError(result.returncode, command)


def snapshot(path, backup, manifest):
    key = str(path)
    if key in manifest:
        return
    if path.is_symlink():
        manifest[key] = {'type': 'symlink', 'target': os.readlink(path)}
    elif path.exists():
        destination = backup / 'files' / path.relative_to('/')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        manifest[key] = {'type': 'file', 'backup': str(destination)}
    else:
        manifest[key] = {'type': 'absent'}


def restore(manifest):
    for name, entry in manifest.items():
        path = Path(name)
        if path.exists() or path.is_symlink():
            path.unlink()
        if entry['type'] == 'symlink':
            path.symlink_to(entry['target'])
        elif entry['type'] == 'file':
            shutil.copy2(entry['backup'], path)


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.cpo-tmp')
    temp.write_text(text)
    temp.chmod(0o644)
    temp.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Apply; otherwise print the plan only')
    parser.add_argument('--server-name', default='193.112.27.91')
    parser.add_argument('--certificate-dir', default='/etc/letsencrypt/live/193.112.27.91')
    args = parser.parse_args()
    plan = configuration_plan(args.server_name, args.certificate_dir)
    nginx_main = Path('/etc/nginx/nginx.conf')
    if nginx_main.exists():
        plan[str(nginx_main)] = without_legacy_format(nginx_main.read_text())
    quarantine = [path for path in Path('/etc/nginx/sites-enabled').glob('*')
                  if BACKUP_PATTERN.search(path.name)]
    changed = {Path(name): text for name, text in plan.items()
               if not Path(name).is_file() or Path(name).read_text() != text}
    enabled = Path('/etc/nginx/sites-enabled/default')
    symlink_changed = not enabled.is_symlink() or os.readlink(enabled) != '/etc/nginx/sites-available/default'
    print(json.dumps({'changed_files': [str(path) for path in changed],
                      'quarantine': [str(path) for path in quarantine],
                      'repair_default_symlink': symlink_changed, 'apply': args.apply}))
    if not args.apply:
        return
    if os.geteuid() != 0:
        parser.error('--apply requires root')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid.uuid4().hex[:8]
    backup = Path('/var/backups/cpo-infra') / stamp
    backup.mkdir(parents=True, mode=0o700)
    manifest = {}
    timers = ('cpo-redis-watchdog.timer', 'cpo-logrotate.timer')
    timer_states = {timer: {
        'active': subprocess.run(['systemctl', 'is-active', '--quiet', timer]).returncode == 0,
        'enabled': subprocess.run(['systemctl', 'is-enabled', '--quiet', timer]).returncode == 0,
    } for timer in timers}
    for path in (*changed, *quarantine, *((enabled,) if symlink_changed else ())):
        snapshot(path, backup, manifest)
    (backup / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    nginx_changed = any(str(path).startswith('/etc/nginx/') for path in changed) or bool(quarantine) or symlink_changed
    journal_changed = any(str(path).startswith('/etc/systemd/journald') for path in changed)
    try:
        for path, text in changed.items():
            atomic_write(path, text)
        for path in quarantine:
            destination = backup / 'quarantined' / path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), destination)
        if symlink_changed:
            enabled.parent.mkdir(parents=True, exist_ok=True)
            if enabled.exists() or enabled.is_symlink():
                enabled.unlink()
            enabled.symlink_to('/etc/nginx/sites-available/default')
        account = pwd.getpwnam('ubuntu')
        for name in ('traces', 'watchdog'):
            directory = Path('/opt/agent/cpo/shared') / name
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            directory.chmod(0o700)
            os.chown(directory, account.pw_uid, account.pw_gid)
        # No reload is attempted unless both the complete nginx configuration and
        # all logrotate rules validate. Duplicate log globs are rejected here.
        run('nginx', '-t')
        run('logrotate', '--debug', '/etc/logrotate.conf')
        run('systemd-analyze', 'verify', '/etc/systemd/system/cpo-redis-watchdog.service',
            '/etc/systemd/system/cpo-redis-watchdog.timer', '/etc/systemd/system/cpo-logrotate.service',
            '/etc/systemd/system/cpo-logrotate.timer')
        run('systemctl', 'daemon-reload')
        if journal_changed:
            run('systemctl', 'restart', 'systemd-journald')
            run('journalctl', '--flush')
            run('journalctl', '--vacuum-size=2G', '--vacuum-time=30days')
        if nginx_changed:
            run('systemctl', 'reload', 'nginx')
        run('systemctl', 'enable', '--now', 'cpo-redis-watchdog.timer', 'cpo-logrotate.timer')
        run('systemctl', 'start', 'cpo-redis-watchdog.service')
    except Exception:
        for timer, state in timer_states.items():
            if not state['active']:
                subprocess.run(['systemctl', 'stop', timer])
            if not state['enabled']:
                subprocess.run(['systemctl', 'disable', timer])
        restore(manifest)
        run('systemctl', 'daemon-reload')
        if journal_changed:
            run('systemctl', 'restart', 'systemd-journald')
        # Restore the previously loaded nginx configuration only if valid; if
        # the original disk configuration was broken, retain the running workers.
        if subprocess.run(['nginx', '-t']).returncode == 0:
            run('systemctl', 'reload', 'nginx')
        print(json.dumps({'status': 'FAILED_RESTORED', 'backup': str(backup)}), file=sys.stderr)
        raise
    print(json.dumps({'status': 'OK', 'backup': str(backup), 'changed_files': len(changed),
                      'quarantined_backups': len(quarantine), 'nginx_reloaded': nginx_changed}))


if __name__ == '__main__':
    main()
