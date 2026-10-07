import gzip
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from app.services.diagnostics import request_traces


class DiagnosticsHistoryTests(unittest.TestCase):
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
