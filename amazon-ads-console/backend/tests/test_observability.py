import asyncio
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import observability as trace
from app.core.config import settings
from app.services.cache import MemoryTTLCache
from app.services import rds_query


class ObservabilityTests(unittest.TestCase):
    def setUp(self):
        self.records = []
        self.app = FastAPI()
        self.app.add_middleware(trace.RequestDiagnosticsMiddleware)
        self.writer = patch.object(trace, 'emit_diagnostic', side_effect=lambda value: self.records.append(dict(value)))
        self.writer.start()

    def tearDown(self):
        self.writer.stop()

    def test_threadpool_context_and_l1_revision_survive_hit(self):
        cache = MemoryTTLCache()
        loader = Mock()
        def load():
            loader()
            trace.update_context(revision='582', date='2026-10-04', period_start='2026-10-04', period_end='2026-10-04')
            trace.increment('psql_calls', 2)
            trace.increment('db_wall_ms', 12.5)
            trace.increment('build_ms', 8)
            return {'final_cpo': True, 'summary': {'missingBusinessProducts': 0}, 'sourceCompleteness': {'completeDays': 1}}
        @self.app.get('/snapshot')
        def snapshot():
            trace.update_context(username='xm', role='operator', operator_group='XM')
            return cache.get_or_set('test', load, 60)
        with TestClient(self.app) as client:
            self.assertEqual(client.get('/snapshot').status_code, 200)
            self.assertEqual(client.get('/snapshot').status_code, 200)
        cold, hot = self.records
        self.assertEqual(cold['psql_calls'], 2)
        self.assertEqual(cold['db_wall_ms'], 12.5)
        self.assertEqual(hot['l1_hit'], 1)
        self.assertEqual(hot['psql_calls'], 0)
        self.assertEqual(hot['revision'], '582')
        self.assertTrue(hot['quality']['final_cpo'])
        self.assertEqual(hot['username'], 'xm')
        self.assertEqual(hot['endpoint'], '/snapshot')
        self.assertIsNone(trace.request_context.get())
        loader.assert_called_once()

    def test_request_id_requires_valid_header_and_trusted_peer(self):
        @self.app.get('/hello')
        def hello():
            return {'ok': True}
        with patch.dict(os.environ, {'CPO_TRUSTED_PROXY_CIDRS': '127.0.0.0/8'}):
            with TestClient(self.app, client=('127.0.0.1', 1234)) as client:
                response = client.get('/hello?token=secret-query&date=2026-10-04', headers={'X-Request-ID': 'nginx-123'})
                self.assertEqual(response.headers['X-Request-ID'], 'nginx-123')
                response = client.get('/hello', headers={'X-Request-ID': 'invalid space'})
                self.assertEqual(len(response.headers['X-Request-ID']), 32)
            with TestClient(self.app, client=('203.0.113.7', 1234)) as client:
                self.assertNotEqual(client.get('/hello', headers={'X-Request-ID': 'forged-123'}).headers['X-Request-ID'], 'forged-123')
        self.assertNotIn('secret-query', json.dumps(self.records))
        self.assertEqual(self.records[0]['date'], '2026-10-04')

    def test_exception_returns_id_and_safe_stack(self):
        @self.app.get('/explode/{token}')
        def explode(token: str):
            raise RuntimeError('SQL SELECT password super-secret')
        with TestClient(self.app, raise_server_exceptions=False) as client:
            response = client.get('/explode/private-token')
        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json(), {'detail': 'Internal server error'})
        self.assertEqual(response.headers['X-Request-ID'], self.records[0]['request_id'])
        self.assertEqual(self.records[0]['exception_type'], 'RuntimeError')
        self.assertTrue(any(frame['function'] == 'explode' for frame in self.records[0]['stack']))
        encoded = json.dumps(self.records)
        self.assertNotIn('private-token', encoded)
        self.assertNotIn('super-secret', encoded)
        self.assertEqual(self.records[0]['endpoint'], '/explode/{token}')

    def test_concurrent_async_requests_keep_identity_separate(self):
        @self.app.get('/concurrent/{name}')
        async def concurrent(name: str):
            trace.update_context(username=name)
            await asyncio.sleep(0.01)
            trace.increment('psql_calls', 1 if name == 'xm' else 3)
            return {'username': trace.request_context.get()['username']}
        async def exercise():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='http://test') as client:
                responses = await asyncio.gather(client.get('/concurrent/xm'), client.get('/concurrent/aj'))
                self.assertEqual([item.json()['username'] for item in responses], ['xm', 'aj'])
        asyncio.run(exercise())
        by_user = {record['username']: record for record in self.records}
        self.assertEqual(by_user['xm']['psql_calls'], 1)
        self.assertEqual(by_user['aj']['psql_calls'], 3)

    def test_failed_database_process_is_counted_and_error_sanitized(self):
        context = {field: 0 for field in trace.COUNTERS + trace.TIMINGS}
        token = trace.request_context.set(context)
        env = {'RDS_PGHOST': 'host', 'RDS_PGPORT': '5432', 'RDS_PGUSER': 'user', 'RDS_PGDATABASE': 'db'}
        try:
            with patch.dict(os.environ, env), patch.object(rds_query.subprocess, 'run', return_value=Mock(returncode=1, stderr='secret SELECT password')):
                with self.assertRaisesRegex(rds_query.DatabaseQueryError, '^Database query failed$'):
                    rds_query._run('SELECT secret')
            self.assertEqual(context['psql_calls'], 1)
            self.assertGreater(context['db_wall_ms'], 0)
        finally:
            trace.request_context.reset(token)

    def test_trace_sink_is_private_and_handles_rotation(self):
        self.writer.stop()
        try:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'requests.jsonl'
                with patch.dict(os.environ, {'CPO_TRACE_LOG': str(path)}), patch.object(trace.logger, 'info'):
                    trace.emit_diagnostic({'event': 'request_complete', 'request_id': 'first'})
                    self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                    path.rename(path.with_suffix('.jsonl.1'))
                    trace.emit_diagnostic({'event': 'request_complete', 'request_id': 'second'})
                    self.assertEqual(trace.read_request_traces()[0]['request_id'], 'second')
        finally:
            self.writer.start()

    def test_release_uses_immutable_ref_without_shared_pointer(self):
        with patch.object(Path, 'read_text', return_value=json.dumps({'ref': 'cpo-v1.0.4', 'commit': 'a' * 40})) as read:
            self.assertEqual(trace.release_metadata(), {'release': 'cpo-v1.0.4', 'commit': 'a' * 40})
        self.assertEqual(read.call_count, 1)


if __name__ == '__main__':
    unittest.main()
