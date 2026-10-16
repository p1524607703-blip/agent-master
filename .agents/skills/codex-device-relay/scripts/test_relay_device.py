"""Contract tests with local HTTP fixtures; no real model or credential is used."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.util
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest

spec = importlib.util.spec_from_file_location('relay_device', Path(__file__).with_name('relay_device.py'))
relay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay)


@contextmanager
def service(mode='ok', redirect=None):
    state = {'modelCalls': 0, 'requests': 0, 'key': secrets.token_urlsafe(32)}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, code, payload, content_type='application/json'):
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            state['requests'] += 1
            if self.headers.get('Authorization') != 'Bearer ' + state['key']:
                self.reply(401, {})
            elif mode == 'redirect':
                self.send_response(302)
                self.send_header('Location', redirect)
                self.end_headers()
            else:
                self.reply(200, {'data': [{'id': 'gpt-6.1-sol'}]})

        def do_POST(self):
            state['modelCalls'] += 1
            if self.headers.get('Authorization') != 'Bearer ' + state['key']:
                self.reply(401, {})
                return
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            marker = payload['input'][0]['content'][0]['text'].removeprefix('Return exactly ')
            event = {'type': 'response.output_text.delta', 'delta': marker}
            raw = ('data: ' + json.dumps(event) + '\n\n').encode()
            if mode == 'ok':
                raw += b'data: {"type":"response.completed","response":{"status":"completed"}}\n\n'
            elif mode == 'done-only':
                raw += b'data: [DONE]\n\n'
            self.reply(200, raw, 'text/event-stream')

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield 'http://127.0.0.1:' + str(server.server_port) + '/v1', state
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


class Contracts(unittest.TestCase):
    def test_catalogue_does_not_call_model(self):
        with service() as (url, state):
            result = relay.probe(url, state['key'], 'gpt-6.1-sol')
            self.assertTrue(result['passed'])
            self.assertEqual(len(result['checks']), 3)
            self.assertEqual(state['modelCalls'], 0)
            self.assertFalse(result['localToolVerified'])

    def test_complete_stream_matches_exact_marker_once(self):
        with service() as (url, state):
            result = relay.probe(url, state['key'], 'gpt-6.1-sol', True)
            self.assertTrue(result['checks'][-1]['passed'])
            self.assertEqual(state['modelCalls'], 1)
            self.assertNotIn(state['key'], json.dumps(result))

    def test_incomplete_stream_rejected_without_retry(self):
        for mode in ('truncated', 'done-only'):
            with self.subTest(mode=mode), service(mode) as (url, state):
                with self.assertRaisesRegex(relay.CheckError, 'response.completed'):
                    relay.probe(url, state['key'], 'gpt-6.1-sol', True)
                self.assertEqual(state['modelCalls'], 1)

    def test_wrong_key_and_unpublished_model_never_call_model(self):
        with service() as (url, state):
            with self.assertRaisesRegex(relay.CheckError, '401'):
                relay.probe(url, secrets.token_urlsafe(32), 'gpt-6.1-sol', True)
            with self.assertRaisesRegex(relay.CheckError, '尚未发布'):
                relay.probe(url, state['key'], 'unpublished', True)
            self.assertEqual(state['modelCalls'], 0)

    def test_redirect_never_forwards_credential(self):
        with service() as (destination, target):
            with service('redirect', destination + '/models') as (url, state):
                with self.assertRaisesRegex(relay.CheckError, '302'):
                    relay.probe(url, state['key'], 'gpt-6.1-sol')
            self.assertEqual(target['requests'], 0)

    def test_nonlocal_http_and_embedded_credentials_rejected(self):
        for url in ('http://100.64.0.2:6160/v1', 'https://user:secret@relay.example/v1',
                    'https://relay.example/v1?key=secret', 'https://relay.example/v1/responses'):
            with self.subTest(url=url), self.assertRaises(relay.CheckError):
                relay.base_url(url)

    def test_cli_receipt_has_no_key_and_keeps_distinct_verifications(self):
        with tempfile.TemporaryDirectory() as temp, service() as (url, state):
            root = Path(temp)
            keyfile = root / 'private.key'
            keyfile.write_text(state['key'])
            keyfile.chmod(0o600)
            receipt = root / 'receipt.json'
            args = [sys.executable, str(Path(__file__).with_name('relay_device.py')), 'probe',
                    '--base-url', url, '--device-id', 'test-device', '--key-file', str(keyfile),
                    '--receipt', str(receipt), '--live']
            proc = subprocess.run(args, text=True, capture_output=True)
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            stored = receipt.read_text()
            self.assertNotIn(state['key'], proc.stdout + proc.stderr + stored)
            self.assertFalse(json.loads(stored)['desktopInstanceVerified'])
            self.assertFalse(json.loads(stored)['localToolVerified'])
            before = state['requests'], state['modelCalls']
            duplicate = subprocess.run(args, text=True, capture_output=True)
            self.assertEqual(duplicate.returncode, 1)
            self.assertEqual((state['requests'], state['modelCalls']), before)
            self.assertEqual(receipt.read_text(), stored)

    @unittest.skipIf(os.name == 'nt', 'POSIX permission contract')
    def test_world_readable_key_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            key = Path(temp) / 'key'
            key.write_text(secrets.token_urlsafe(32))
            key.chmod(0o644)
            with self.assertRaisesRegex(relay.CheckError, '600'):
                relay.load_key(str(key))


if __name__ == '__main__':
    unittest.main()
