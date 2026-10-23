#!/usr/bin/env python3
"""Hardware-bound loopback Responses connector. Python 3.9+, no pip packages.

Never opens or changes Codex/Codex++ authentication, settings or process state.
"""
import argparse
import base64
import getpass
import hashlib
import hmac
import http.client
import http.server
import json
import os
import plistlib
from pathlib import Path
import secrets
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse

ROOT = Path(__file__).resolve().parent
WINDOWS = sys.platform == 'win32'
PRIVATE = Path(os.environ['LOCALAPPDATA']) / 'CodexDeviceRelay' / 'bound' if WINDOWS else Path.home() / 'Library/Application Support/CodexDeviceRelay/bound'
CONFIG = PRIVATE / 'connector.json'
PORT = 58961
MAX_BODY = 16 * 1024 * 1024


def private_dir():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    if WINDOWS:
        user = subprocess.check_output(['whoami', '/user', '/fo', 'csv', '/nh'], text=True).strip().split(',')[-1].strip('"')
        subprocess.run(['icacls', str(PRIVATE), '/inheritance:r', '/grant:r', user + ':(OI)(CI)F', 'SYSTEM:(OI)(CI)F'], check=True, stdout=subprocess.DEVNULL)
    else:
        PRIVATE.chmod(0o700)


def save(path, value):
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(str(path), flags, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as stream:
        stream.write(value)


def load():
    return json.loads(CONFIG.read_text(encoding='utf-8'))


def signer(config, action, message=b''):
    payload = {'name': config['keyName'], 'action': action, 'message': base64.b64encode(message).decode()}
    if config.get('handle'):
        payload['handle'] = config['handle']
    if WINDOWS:
        command = ['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'windows-key.ps1')]
    elif sys.platform == 'darwin':
        command = [str(ROOT / 'macos-key')]
    else:
        raise RuntimeError('Only Windows TPM and Mac Secure Enclave are supported')
    proc = subprocess.run(command, input=json.dumps(payload), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
    if proc.returncode:
        raise RuntimeError('Hardware key unavailable. No software fallback; check TPM/Secure Enclave and enrollment.')
    return json.loads(proc.stdout)


def base(config):
    url = urllib.parse.urlsplit(config['baseUrl'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment or not url.path.endswith('/v1'):
        raise ValueError('A trusted HTTPS Base URL ending in /v1 is required')
    return url


def proof(config, method, path, body):
    timestamp, nonce = str(int(time.time())), secrets.token_urlsafe(24)
    message = ('cpo-device-v1\n' + hashlib.sha256(config['apiKey'].encode()).hexdigest() + '\n' + method
               + '\n' + path + '\n' + timestamp + '\n' + nonce + '\n' + hashlib.sha256(body).hexdigest()).encode()
    value = signer(config, 'sign', message)
    if value['publicKey'] != config['publicKey']:
        raise RuntimeError('Hardware key changed')
    return {'Authorization': 'Bearer ' + config['apiKey'], 'X-CPO-Time': timestamp,
            'X-CPO-Nonce': nonce, 'X-CPO-Proof': value['signature'], 'Content-Type': 'application/json'}


def open_upstream(config, method, path, body):
    url = base(config)
    conn = http.client.HTTPSConnection(url.hostname, url.port or 443, timeout=300)
    try:
        conn.request(method, path, body=body if method != 'GET' else None, headers=proof(config, method, path, body))
        return conn, conn.getresponse()
    except BaseException:
        conn.close()
        raise


def enroll(config):
    path = base(config).path[:-3] + '/device-enrollment'
    body = json.dumps({'publicKey': config['publicKey'], 'provider': config['provider']}, separators=(',', ':')).encode()
    conn, response = open_upstream(config, 'POST', path, body)
    try:
        raw = response.read(8192)
        if response.status != 200:
            raise RuntimeError('Enrollment rejected (HTTP %d); contact administrator. Existing Codex was not changed.' % response.status)
        return json.loads(raw)
    finally:
        conn.close()


class LocalServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = False
    request_queue_size = 32


class Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *args):
        pass

    def error(self, status, message):
        raw = json.dumps({'error': {'message': message, 'type': 'device_connector'}}).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(raw)
        self.close_connection = True

    def do_GET(self):
        self.forward()

    def do_POST(self):
        self.forward()

    def forward(self):
        config = self.server.config
        if self.headers.get('Host') != '127.0.0.1:%d' % self.server.server_port or self.headers.get('Origin'):
            return self.error(403, 'Only local Codex clients are allowed')
        auth = self.headers.get('Authorization', '')
        if not hmac.compare_digest(auth.encode(), ('Bearer ' + config['localKey']).encode()):
            return self.error(401, 'Invalid local connector key')
        valid = (self.command == 'GET' and self.path == '/v1/models') or (self.command == 'POST' and self.path in ('/v1/responses', '/v1/responses/compact'))
        if not valid:
            return self.error(404, 'Unsupported local endpoint')
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.error(400, 'Invalid request length')
        if self.headers.get('Transfer-Encoding') or length < 0 or length > MAX_BODY or len(self.headers.get_all('Content-Length', [])) > 1:
            return self.error(413, 'Invalid or oversized device request')
        if self.command == 'GET' and length:
            return self.error(400, 'Unexpected request body')
        if not self.server.slots.acquire(blocking=False):
            return self.error(429, 'Local connector is busy')
        conn = None
        headers_sent = False
        try:
            body = self.rfile.read(length)
            if len(body) != length:
                return self.error(400, 'Incomplete request body')
            path = base(config).path + self.path[len('/v1'):]
            conn, response = open_upstream(config, self.command, path, body)
            self.send_response(response.status)
            for name in ('Content-Type', 'Retry-After', 'X-Request-ID'):
                if response.getheader(name):
                    self.send_header(name, response.getheader(name))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Connection', 'close')
            self.end_headers()
            headers_sent = True
            self.close_connection = True
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
            # Never log request text, keys, signing handles or subprocess output.
            if not headers_sent:
                self.error(502, 'Device connection failed; check enrollment and hardware key')
        finally:
            if conn:
                conn.close()
            self.server.slots.release()


def setup():
    private_dir()
    if CONFIG.exists():
        config = load()
    else:
        config = {'baseUrl': input('HTTPS Base URL: ').strip().rstrip('/'), 'apiKey': getpass.getpass('Device Key (hidden): ').strip(),
                  'localKey': 'sk-local-' + secrets.token_urlsafe(32), 'keyName': 'CodexRelay-' + secrets.token_hex(16)}
        base(config)
        if not 32 <= len(config['apiKey']) <= 256:
            raise RuntimeError('Invalid device Key')
        value = signer(config, 'create')
        config.update(value)
        save(CONFIG, json.dumps(config))
    receipt = enroll(config)
    print('Fingerprint: ' + receipt['fingerprint'])
    print('Enrollment: ' + receipt['state'] + ' (administrator must compare this fingerprint)')
    save(PRIVATE / 'provider.txt', 'New NON-CURRENT provider, pure API, Responses\nBase URL: http://127.0.0.1:%d/v1\nKey: %s\nUse the model assigned by your administrator. Launch ONLY via Codex multi-instance.\n' % (PORT, config['localKey']))
    print('Private provider fields saved to: ' + str(PRIVATE / 'provider.txt'))
    print('Original Codex windows, login files and providers were not changed.')
    enable_startup()


def enable_startup():
    script = PRIVATE / 'device_connector.py'
    if script.resolve() != Path(__file__).resolve():
        return
    if WINDOWS:
        pythonw = Path(sys.executable).with_name('pythonw.exe')
        if not pythonw.exists():
            raise RuntimeError('A full Python installation including pythonw.exe is required')
        startup = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Startup/CodexBoundConnector.cmd'
        save(startup, '@echo off\r\nstart "" "%s" "%s" serve\r\n' % (pythonw, script))
        subprocess.Popen([str(pythonw), str(script), 'serve'], close_fds=True)
    else:
        agent = Path.home() / 'Library/LaunchAgents/com.codex-device-relay.bound.plist'
        agent.parent.mkdir(parents=True, exist_ok=True)
        payload = {'Label': 'com.codex-device-relay.bound', 'ProgramArguments': [sys.executable, str(script), 'serve'],
                   'RunAtLoad': True, 'KeepAlive': False}
        save(agent, plistlib.dumps(payload).decode())
        # Do not unload or restart anything, including another connector already running.
        subprocess.run(['launchctl', 'bootstrap', 'gui/%d' % os.getuid(), str(agent)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def install():
    manifest = ROOT / 'SHA256SUMS.json'
    if manifest.exists():
        for name, digest in json.loads(manifest.read_text(encoding='utf-8')).items():
            if Path(name).name != name or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                raise RuntimeError('Package integrity check failed')
    private_dir()
    for name in ('device_connector.py', 'windows-key.ps1', 'macos-key', '使用说明.md'):
        source = ROOT / name
        dest = PRIVATE / name
        if source.exists() and source.resolve() != dest.resolve():
            shutil.copyfile(source, dest)
            if not WINDOWS:
                dest.chmod(0o700 if name == 'macos-key' else 0o600)
    if WINDOWS or sys.platform == 'darwin':
        subprocess.run([sys.executable, str(PRIVATE / 'device_connector.py'), 'setup'], check=True)
    else:
        raise RuntimeError('Unsupported operating system')


def serve():
    config = load()
    base(config)
    # Missing hardware handle on a copied installation fails before opening a port.
    signer(config, 'sign', b'connector-start')
    with LocalServer(('127.0.0.1', PORT), Handler) as server:
        server.config = config
        server.slots = threading.BoundedSemaphore(8)
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'setup', 'serve'])
    args = parser.parse_args()
    if args.action == 'install':
        install()
    elif args.action == 'setup':
        setup()
    else:
        serve()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        print('Device connector could not start or enroll. Check HTTPS, hardware key and administrator approval. Original Codex was not changed.', file=sys.stderr)
        sys.exit(1)
