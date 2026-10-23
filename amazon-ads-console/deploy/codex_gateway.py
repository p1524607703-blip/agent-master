#!/usr/bin/env python3
"""Authenticated local entry for the isolated Codex++ Responses helper."""
import argparse
from collections import deque
import hmac
import http.client
import json
import logging
import re
import uuid
from logging.handlers import RotatingFileHandler
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

MAX_BODY = 16 * 1024 * 1024
REQUEST_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z')


def safe_request_id(value):
    return value if isinstance(value, str) and REQUEST_ID.fullmatch(value) else None


FORWARD_HEADERS = (
    'user-agent', 'session-id', 'thread-id', 'x-opencode-session',
    'x-codex-beta-features', 'openai-beta', 'x-codex-client-version',
)


class Admission:
    """Bounded FIFO admission; queued calls never occupy a model slot."""
    def __init__(self, limit, queued):
        self.limit, self.queued = limit, queued
        self.active = 0
        self.waiters = deque()
        self.condition = threading.Condition()

    def acquire(self, timeout):
        deadline = time.monotonic() + timeout
        with self.condition:
            if self.active < self.limit and not self.waiters:
                self.active += 1
                return 'accepted'
            if len(self.waiters) >= self.queued:
                return 'queue_full'
            ticket = object()
            self.waiters.append(ticket)
            while True:
                if self.waiters[0] is ticket and self.active < self.limit:
                    self.waiters.popleft()
                    self.active += 1
                    self.condition.notify_all()
                    return 'accepted'
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.waiters.remove(ticket)
                    self.condition.notify_all()
                    return 'queue_timeout'
                self.condition.wait(remaining)

    def release(self):
        with self.condition:
            self.active -= 1
            self.condition.notify_all()

    def snapshot(self):
        with self.condition:
            return self.active, len(self.waiters)


class Gateway(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, settings):
        self.settings = settings
        self.capacity = Admission(settings.get('maxConcurrent', 6), settings.get('maxQueued', 24))
        maximum = settings.get('maxConnections', 32)
        self.connections = threading.BoundedSemaphore(maximum) if maximum is not None else None
        super().__init__((settings['listenHost'], settings['listenPort']), Handler)

    def process_request(self, request, address):
        if self.connections is not None and not self.connections.acquire(blocking=False):
            try:
                request.sendall(b'HTTP/1.1 503 Service Unavailable\r\nContent-Length: 0\r\nRetry-After: 2\r\nConnection: close\r\n\r\n')
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            if self.connections is not None:
                self.connections.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            if self.connections is not None:
                self.connections.release()


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def setup(self):
        super().setup()
        self.connection.settimeout(45)

    def log_message(self, fmt, *args):
        # Log neither URLs with queries, headers, credentials nor request bodies.
        pass

    def reply(self, status, value, extra=None):
        data = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        for name, value in (extra or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)
        self.close_connection = True

    def authorized_device(self):
        value = self.headers.get('Authorization', '')
        if not value.startswith('Bearer '):
            return None
        supplied = value[7:].encode()
        for device, token in self.server.settings['deviceKeys'].items():
            if hmac.compare_digest(supplied, token.encode()):
                return device
        return None

    def dispatch(self):
        device = self.authorized_device()
        if device is None:
            self.reply(401, {'error': {'message': 'Invalid device credential'}})
            return
        path = urlsplit(self.path).path
        if self.command == 'GET' and path == '/v1/models':
            # Publish only models which have passed the local Responses probe.
            self.reply(200, {'object': 'list', 'data': [
                {'id': m, 'object': 'model', 'owned_by': 'local-codex-account'}
                for m in self.server.settings['verifiedModels']
            ]})
            return
        if self.command != 'POST' or path not in ('/v1/responses', '/v1/responses/compact'):
            self.reply(404, {'error': {'message': 'Model route not allowed'}})
            return
        if self.headers.get('Transfer-Encoding'):
            self.reply(400, {'error': {'message': 'Content-Length is required'}})
            return
        try:
            length = int(self.headers.get('Content-Length', '-1'))
        except ValueError:
            length = -1
        if length < 0 or length > MAX_BODY:
            self.reply(413 if length > MAX_BODY else 411, {'error': {'message': 'Invalid request size'}})
            return
        body = self.rfile.read(length)
        if len(body) != length:
            self.reply(400, {'error': {'message': 'Incomplete request body'}})
            return
        try:
            request = json.loads(body)
        except (ValueError, UnicodeDecodeError):
            self.reply(400, {'error': {'message': 'Expected JSON request'}})
            return
        if not isinstance(request, dict) or request.get('model') not in self.server.settings['verifiedModels']:
            self.reply(400, {'error': {'message': 'Model has not been enabled'}})
            return
        request_id = safe_request_id(self.headers.get('X-Request-ID')) or uuid.uuid4().hex
        queued_at = time.monotonic()
        # The console authenticates individual devices and owns their admission leases.
        # This exception is selected by the private credential, never a caller header.
        externally_managed = device in self.server.settings.get('externallyManagedDevices', [])
        admission = 'accepted' if externally_managed else self.server.capacity.acquire(
            timeout=self.server.settings.get('queueWaitSeconds', 120))
        waited = time.monotonic() - queued_at
        if admission != 'accepted':
            active, queued = self.server.capacity.snapshot()
            logging.warning('device=%s route=%s status=429 origin=local reason=%s wait=%.2f active=%s queued=%s',
                            device, path, admission, waited, active, queued)
            self.reply(429, {'error': {'message': 'Relay queue is busy; retry after a short delay',
                                     'type': 'rate_limit_error', 'code': 'relay_' + admission}},
                       {'Retry-After': '2', 'X-Relay-Limit-Origin': 'local'})
            return
        start = time.monotonic()
        status = 502
        response_started = False
        connection = None
        error_type = None
        outcome = 'upstream_headers_error'
        stage = 'headers'
        headers_ms = first_byte_ms = None
        upstream_request_id = None
        try:
            connection = http.client.HTTPConnection(
                self.server.settings['upstreamHost'], self.server.settings['upstreamPort'], timeout=180)
            headers = {'Content-Type': 'application/json', 'Accept-Encoding': 'identity', 'X-Request-ID':request_id}
            for name in FORWARD_HEADERS:
                if self.headers.get(name):
                    headers[name] = self.headers[name]
            # The device key never goes to Codex++ or to the account's upstream.
            connection.request('POST', path, body=body, headers=headers)
            upstream = connection.getresponse()
            status = upstream.status
            headers_ms = (time.monotonic()-start)*1000
            upstream_request_id = safe_request_id(upstream.getheader('X-Request-ID'))
            self.send_response(status)
            self.send_header('Content-Type', upstream.getheader('Content-Type', 'application/json'))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Request-ID', request_id)
            if upstream_request_id:
                self.send_header('X-Upstream-Request-ID', upstream_request_id)
            if status == 429:
                self.send_header('X-Relay-Limit-Origin', 'upstream')
            self.send_header('X-Accel-Buffering', 'no')
            self.send_header('Transfer-Encoding', 'chunked')
            self.send_header('Connection', 'close')
            if upstream.getheader('Retry-After'):
                self.send_header('Retry-After', upstream.getheader('Retry-After'))
            self.end_headers()
            response_started = True
            self.close_connection = True
            while True:
                stage = 'upstream_read'
                data = upstream.read1(65536)
                if not data:
                    break
                if first_byte_ms is None:
                    first_byte_ms = (time.monotonic()-start)*1000
                stage = 'downstream_write'
                self.wfile.write(('%x\r\n' % len(data)).encode() + data + b'\r\n')
                self.wfile.flush()
            stage = 'downstream_write'
            self.wfile.write(b'0\r\n\r\n')
            self.wfile.flush()
            outcome = 'transport_complete'
        except (BrokenPipeError, ConnectionResetError) as exc:
            error_type = type(exc).__name__
            status = 499 if stage == 'downstream_write' else 502
            outcome = 'downstream_disconnected' if status == 499 else 'upstream_transport_error'
        except (OSError, http.client.HTTPException) as exc:
            error_type = type(exc).__name__
            status = 502
            outcome = 'upstream_headers_error' if not response_started else 'transport_error'
            if not response_started:
                self.reply(502, {'error': {'message': 'Codex++ upstream unavailable'}})
        finally:
            if connection:
                connection.close()
            if not externally_managed:
                self.server.capacity.release()
            logging.info('request_id=%s upstream_request_id=%s device=%s route=%s status=%s headers_sent=%s outcome=%s stage=%s error_type=%s origin=upstream wait=%.2f headers_ms=%s first_byte_ms=%s elapsed=%.2f',
                         request_id, upstream_request_id, device, path, status, response_started, outcome, stage, error_type,
                         waited, round(headers_ms,3) if headers_ms is not None else None,
                         round(first_byte_ms,3) if first_byte_ms is not None else None, time.monotonic()-start)

    def do_GET(self):
        self.dispatch()

    def do_POST(self):
        self.dispatch()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', required=True)
    parser.add_argument('--log-file')
    args = parser.parse_args()
    settings = json.loads(Path(args.config).read_text())
    for name, default, maximum in [('maxConcurrent', 6, 32), ('maxQueued', 24, 128),
                                    ('maxConnections', 32, 192), ('queueWaitSeconds', 120, 240)]:
        value = settings.get(name, default)
        if name == 'maxConnections' and value is None:
            continue
        if type(value) is not int or value < 1 or value > maximum:
            raise ValueError('Invalid relay capacity setting: ' + name)
    external = settings.get('externallyManagedDevices', [])
    if not isinstance(external, list) or any(not isinstance(name, str) or name not in settings['deviceKeys'] for name in external):
        raise ValueError('External admission requires registered private credentials')
    if settings.get('maxConnections', 32) is not None and settings.get('maxConnections', 32) < settings.get('maxConcurrent', 6) + settings.get('maxQueued', 24) + 2:
        raise ValueError('Reserve two connections for local health checks')
    # Initial acceptance is strictly local; LAN publication is a separate step.
    if settings['listenHost'] != '127.0.0.1':
        raise ValueError('This trial gateway must listen on loopback only')
    handlers = [RotatingFileHandler(args.log_file, maxBytes=2000000, backupCount=3, encoding='utf-8')] if args.log_file else None
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=handlers)
    with Gateway(settings) as server:
        logging.info('ready host=%s port=%s upstream=%s', settings['listenHost'], settings['listenPort'], settings['upstreamPort'])
        server.serve_forever(poll_interval=0.5)


if __name__ == '__main__':
    main()
