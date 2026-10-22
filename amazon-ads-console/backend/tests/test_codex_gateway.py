"""Actual HTTP tests against a disposable local relay and a gated fake model source."""
import concurrent.futures
from contextlib import contextmanager
import importlib.util
import json
from pathlib import Path
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import unittest
import httpx

path = Path(__file__).resolve().parents[2] / 'deploy/codex_gateway.py'
spec = importlib.util.spec_from_file_location('codex_gateway', path)
gateway = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gateway)


class GatewayTests(unittest.TestCase):
    @contextmanager
    def fixture(self, *, limit=2, queued=4, timeout=2, upstream_status=200, externally_managed=False):
        release = threading.Event()
        count_lock = threading.Lock()
        state = {'active': 0, 'maximum': 0, 'calls': 0, 'credentialForwarded': False}
        class Model(BaseHTTPRequestHandler):
            def log_message(self, *_): pass
            def do_POST(self):
                self.rfile.read(int(self.headers['content-length']))
                with count_lock:
                    state['active'] += 1; state['calls'] += 1
                    state['maximum'] = max(state['maximum'], state['active'])
                    state['credentialForwarded'] |= bool(self.headers.get('Authorization'))
                try:
                    release.wait(5)
                    body = b'{"error":{"code":"upstream_fixture_limit"}}' if upstream_status == 429 else b'{"status":"completed"}'
                    self.send_response(upstream_status)
                    self.send_header('Content-Type','application/json')
                    self.send_header('Content-Length',str(len(body)))
                    if upstream_status == 429: self.send_header('Retry-After','7')
                    self.end_headers(); self.wfile.write(body)
                finally:
                    with count_lock: state['active'] -= 1
        source = ThreadingHTTPServer(('127.0.0.1',0), Model)
        relay = gateway.Gateway({'listenHost':'127.0.0.1','listenPort':0,
            'upstreamHost':'127.0.0.1','upstreamPort':source.server_port,
            'maxConcurrent':limit,'maxQueued':queued,'maxConnections':16,
            'queueWaitSeconds':timeout,'deviceKeys':{'fixture':'fixture-private-key'},'verifiedModels':['fixture'],
            'externallyManagedDevices':['fixture'] if externally_managed else [],
            **({'maxConnections':None} if externally_managed else {})})
        threads = [threading.Thread(target=s.serve_forever,daemon=True) for s in (source,relay)]
        for t in threads: t.start()
        def call():
            with httpx.Client(trust_env=False,timeout=6) as client:
                return client.post(f'http://127.0.0.1:{relay.server_port}/v1/responses',
                    headers={'Authorization':'Bearer fixture-private-key'},json={'model':'fixture','input':'hi'})
        try: yield relay, release, state, call
        finally:
            release.set()
            for s in (relay,source): s.shutdown(); s.server_close()
            for t in threads: t.join(2)

    def wait_for(self, predicate):
        deadline = time.monotonic()+3
        while time.monotonic()<deadline:
            if predicate(): return
            time.sleep(.005)
        self.fail('Fixture did not reach the expected state')

    def test_four_windows_queue_and_all_finish_with_bounded_concurrency(self):
        with self.fixture() as (relay, release, state, call), concurrent.futures.ThreadPoolExecutor(4) as pool:
            jobs = [pool.submit(call) for _ in range(4)]
            self.wait_for(lambda: relay.capacity.snapshot() == (2,2))
            time.sleep(.15)
            self.assertFalse(any(job.done() for job in jobs))
            release.set()
            self.assertEqual([job.result().status_code for job in jobs],[200]*4)
            self.assertEqual(state['maximum'],2)
            self.assertEqual(state['calls'],4)
            self.assertFalse(state['credentialForwarded'])
            self.assertEqual(relay.capacity.snapshot(),(0,0))

    def test_queue_full_is_explicit_and_does_not_reach_model(self):
        with self.fixture(limit=1,queued=1) as (relay, release, state, call), concurrent.futures.ThreadPoolExecutor(2) as pool:
            jobs=[pool.submit(call) for _ in range(2)]
            self.wait_for(lambda: relay.capacity.snapshot()==(1,1))
            result=call()
            self.assertEqual(result.status_code,429)
            self.assertEqual(result.json()['error']['code'],'relay_queue_full')
            self.assertEqual(result.headers['retry-after'],'2')
            self.assertEqual(result.headers['x-relay-limit-origin'],'local')
            self.assertEqual(state['calls'],1)
            release.set()
            self.assertEqual([job.result().status_code for job in jobs],[200,200])

    def test_queue_timeout_cleans_up_without_running_an_expired_job(self):
        with self.fixture(limit=1,timeout=.08) as (relay, release, state, call), concurrent.futures.ThreadPoolExecutor(1) as pool:
            first=pool.submit(call)
            self.wait_for(lambda: state['calls']==1)
            result=call()
            self.assertEqual(result.status_code,429)
            self.assertEqual(result.json()['error']['code'],'relay_queue_timeout')
            self.assertEqual(relay.capacity.snapshot(),(1,0))
            release.set(); self.assertEqual(first.result().status_code,200)
            self.assertEqual(call().status_code,200)
            self.assertEqual(state['calls'],2)

    def test_real_upstream_limit_remains_an_upstream_limit(self):
        with self.fixture(upstream_status=429) as (_, release, state, call):
            release.set(); result=call()
            self.assertEqual(result.status_code,429)
            self.assertEqual(result.headers['retry-after'],'7')
            self.assertEqual(result.headers['x-relay-limit-origin'],'upstream')
            self.assertEqual(result.json()['error']['code'],'upstream_fixture_limit')
            self.assertEqual(state['calls'],1)

    def test_console_owned_admission_has_no_second_hidden_capacity_limit(self):
        with self.fixture(limit=1,queued=1,externally_managed=True) as (relay,release,state,call), concurrent.futures.ThreadPoolExecutor(3) as pool:
            jobs=[pool.submit(call) for _ in range(3)]
            self.wait_for(lambda:state['active']==3)
            self.assertEqual(relay.capacity.snapshot(),(0,0))
            release.set()
            self.assertEqual([job.result().status_code for job in jobs],[200]*3)
            self.assertEqual(state['maximum'],3)

    def test_fifo_prevents_new_requests_jumping_existing_waiters(self):
        admission=gateway.Admission(1,4)
        self.assertEqual(admission.acquire(1),'accepted')
        order=[]
        def work(number):
            self.assertEqual(admission.acquire(2),'accepted')
            order.append(number); admission.release()
        threads=[]
        for number in range(3):
            t=threading.Thread(target=work,args=(number,)); t.start(); threads.append(t)
            self.wait_for(lambda: admission.snapshot()[1]==number+1)
        admission.release()
        for t in threads: t.join(3)
        self.assertEqual(order,[0,1,2])
        self.assertEqual(admission.snapshot(),(0,0))


if __name__=='__main__': unittest.main()
