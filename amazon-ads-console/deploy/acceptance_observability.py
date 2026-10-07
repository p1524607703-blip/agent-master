"""Production acceptance through HTTPS; does not import or mutate business facts.

Run on Agent-server from a prepared release. The existing account password is
provided only through CPO_ACCEPTANCE_PASSWORD; tokens never enter output files.
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url', default='https://193.112.27.91:80')
    parser.add_argument('--date', default='2026-10-04')
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    import run_rds
    from app.services.build_cache import RedisBuildCache, build_cache
    from app.services.operator_cpo import OPERATOR_NAMES
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    sessions = []
    evidence = {'checks': [], 'requests': []}

    def request(path, token=None, payload=None):
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(args.base_url.rstrip('/') + '/api' + path,
                                     data=json.dumps(payload).encode() if payload is not None else None,
                                     headers=headers)
        start = time.perf_counter()
        try:
            response = opener.open(req, timeout=120)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            data = json.load(response)
            request_id = response.headers.get('X-Request-ID')
            assert request_id and len(response.headers.get_all('X-Request-ID')) == 1
            evidence['requests'].append({'path': path, 'status': response.code,
                'request_id': request_id, 'wall_ms': round((time.perf_counter()-start)*1000, 2)})
            return response.code, data, request_id

    def login(username):
        password = os.environ.get('CPO_ACCEPTANCE_PASSWORD')
        assert password, 'CPO_ACCEPTANCE_PASSWORD is required for existing account acceptance'
        status, data, _ = request('/auth/login', payload={'username': username, 'password': password})
        assert status == 200, 'Existing account login failed: ' + username
        token = data['accessToken']
        sessions.append(token)
        return token

    try:
        status, data, rid = request('/ping')
        assert status == 200 and data == {'ok': True}
        assert request('/diagnostics/status')[0] == 401
        assert request('/operators/XM')[0] == 401
        boss, xm, aj = (login(name) for name in ('boss', 'op_xm1', 'op_aj1'))
        date_query = '?date=' + urllib.parse.quote(args.date) + '&period=daily'
        assert request('/operators/AJ'+date_query, xm)[0] == 403
        assert request('/operators/XM'+date_query, aj)[0] == 403
        assert request('/diagnostics/requests', xm)[0] == 403
        assert request('/operator-cpo'+date_query, xm)[0] == 403
        status, own, _ = request('/operators/XM'+date_query, xm)
        assert status == 200
        assert all(p.get('operatorName') == OPERATOR_NAMES['XM'] for p in own.get('products', []))
        assert 'businessMappingConflictOrders' not in own
        status, own, _ = request('/my-cpo'+date_query, xm)
        assert status == 200 and own['me']['group'] == 'XM'
        assert all(str(p.get('group', '')).startswith('XM') for p in own.get('products', []))
        for secret_scope in ('unmappedAdSpend', 'unmappedAd', 'businessMappingConflictOrders', 'businessOutOfScopeOrders'):
            assert secret_scope not in own
        status, summary, summary_rid = request('/operator-cpo'+date_query, boss)
        assert status == 200 and summary.get('operators')
        assert request('/operator-cpo'+date_query, boss)[0] == 200
        status, diagnostics, _ = request('/diagnostics/status', boss)
        assert status == 200 and diagnostics['trace']['available']
        time.sleep(0.2)
        status, records, _ = request('/diagnostics/requests?request_id='+summary_rid, boss)
        assert status == 200 and len(records['items']) == 1
        record = records['items'][0]
        assert record['request_id'] == summary_rid and record['role'] == 'management'
        assert record['revision'] is not None and record['commit'] != 'unknown'
        assert record['release'].startswith('cpo-v')
        evidence['sample_request'] = record
        evidence['release'] = diagnostics['release']
        log = subprocess.check_output(['sudo', '-n', 'cat', '/var/log/nginx/cpo_api_access.log'], text=True)
        assert any(json.loads(line).get('request_id') == summary_rid for line in log.splitlines())
        journal = subprocess.check_output(['journalctl', '-u', 'cpo-console', '--since', '10 minutes ago',
                                          '--grep', summary_rid, '-o', 'cat'], text=True)
        assert summary_rid in journal
        evidence['checks'].extend(['anonymous ping 200', 'anonymous protected API 401',
            'cross-group and diagnostics denied 403', 'own-group products isolated',
            'management summary 200', 'HTTPS/Nginx/FastAPI/trace file ID correlation',
            'release and revision recorded'])

        # Exercise new single-flight behavior with an isolated ephemeral Redis key.
        client = build_cache._get_client()
        key = 'cpo:acceptance:' + str(time.time_ns())
        tested_cache = RedisBuildCache(client=client)
        calls = 0
        gate = threading.Barrier(6)
        guard = threading.Lock()
        def loader():
            nonlocal calls
            with guard:
                calls += 1
            time.sleep(0.15)
            return {'accepted': True}
        def build(_):
            gate.wait(timeout=5)
            return tested_cache._get_or_set_key(key, 10, loader)
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                values = list(pool.map(build, range(6)))
            assert calls == 1 and all(value == {'accepted': True} for value in values)
            evidence['checks'].append('real Redis 6 concurrent requests -> 1 loader')
        finally:
            client.delete(key)
        print(json.dumps({'passed': True, **evidence}, ensure_ascii=False))
    finally:
        for token in sessions:
            try:
                request('/auth/logout', token, payload={})
            except Exception:
                pass


if __name__ == '__main__':
    main()
