import gzip
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.services.diagnostics import diagnostic_status, request_traces


class DiagnosticsHistoryTests(unittest.TestCase):
    @patch('app.services.diagnostics.build_cache')
    def test_status_exposes_safe_redis_health_and_critical_alert(self, mocked_cache):
        mocked_cache.stats.return_value = {'backend': 'redis', 'enabled': True, 'url': 'redis://user:secret@host:6379/0', 'errors': 0}
        mocked_cache.health.return_value = {'enabled': True, 'available': False, 'status': 'unavailable', 'errors': 0, 'check_ms': 1.2}
        result = diagnostic_status()
        self.assertNotIn('url', result['cache']['redis'])
        self.assertNotIn('secret', json.dumps(result))
        self.assertEqual(result['redis_health']['status'], 'unavailable')
        self.assertEqual(result['alerts'][0]['level'], 'critical')
        self.assertEqual(result['alerts'][0]['code'], 'REDIS_UNAVAILABLE')

    @patch('app.services.diagnostics.build_cache')
    def test_status_warns_when_redis_is_degraded(self, mocked_cache):
        mocked_cache.stats.return_value = {'backend': 'redis', 'enabled': True, 'url': 'redis://host:6379/0', 'errors': 3}
        mocked_cache.health.return_value = {'enabled': True, 'available': True, 'status': 'degraded', 'errors': 3, 'check_ms': 0.8}
        result = diagnostic_status()
        self.assertEqual(result['alerts'][0]['level'], 'warning')
        self.assertEqual(result['alerts'][0]['code'], 'REDIS_ERRORS_RECORDED')

    @patch('app.services.diagnostics.build_cache')
    def test_status_has_no_redis_alert_when_healthy(self, mocked_cache):
        mocked_cache.stats.return_value = {'backend': 'redis', 'enabled': True, 'url': 'redis://host:6379/0', 'errors': 0}
        mocked_cache.health.return_value = {'enabled': True, 'available': True, 'status': 'healthy', 'errors': 0, 'check_ms': 0.5}
        result = diagnostic_status()
        self.assertEqual(result['alerts'], [])

    def test_filters_current_and_rotated_logs_and_omits_unapproved_fields(self):
        now = datetime.now(timezone.utc)
        def row(request_id, days=0, user_id=7):
            return {'event': 'request_complete', 'timestamp': (now-timedelta(days=days)).isoformat(),
                    'request_id': request_id, 'user_id': user_id, 'username': 'op_xm',
                    'endpoint': '/api/my-cpo', 'status_code': 200, 'authorization': 'SECRET'}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'requests.jsonl'
            path.write_text('incomplete\n'+json.dumps(row('latest'))+'\n'+json.dumps(row('other', user_id=8))+'\n')
            with gzip.open(str(path)+'.1.gz', 'wt') as stream:
                stream.write(json.dumps(row('old', 3))+'\n')
            with patch.dict(os.environ, {'CPO_TRACE_LOG': str(path)}):
                matched = request_traces(request_id='old')
                self.assertEqual([x['request_id'] for x in matched['items']], ['old'])
                filtered = request_traces(user_id='7', endpoint='/my-cpo')
                self.assertEqual([x['request_id'] for x in filtered['items']], ['latest'])
                self.assertNotIn('authorization', filtered['items'][0])

    def test_explicit_time_range_and_limit(self):
        now = datetime.now(timezone.utc)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'requests.jsonl'
            rows = [{'event': 'request_complete', 'request_id': str(i),
                     'timestamp': (now-timedelta(minutes=i)).isoformat()} for i in (3,2,1)]
            path.write_text('\n'.join(map(json.dumps, rows)))
            with patch.dict(os.environ, {'CPO_TRACE_LOG': str(path)}):
                result = request_traces(since=(now-timedelta(minutes=2, seconds=1)).isoformat(), limit=1)
                self.assertEqual(result['items'][0]['request_id'], '1')
                with self.assertRaises(ValueError):
                    request_traces(since='2026-10-06T12:00:00')
                with self.assertRaises(ValueError):
                    request_traces(since=(now+timedelta(hours=1)).isoformat(), until=now.isoformat())


if __name__ == '__main__':
    unittest.main()
