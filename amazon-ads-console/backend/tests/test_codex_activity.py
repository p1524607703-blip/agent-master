import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services import codex_activity as activity, codex_telemetry as telemetry
from app.core.config import settings


class RequestActivityTests(unittest.TestCase):
    def test_request_without_heartbeat_is_active_before_tokens_arrive(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'codex_event_spool_dir', tmp):
            marker = telemetry.start_activity('first', 'YE')
            try:
                sources, ok = activity.observe(Path(tmp)/'active')
                result = activity.present(datetime.now(timezone.utc), observed=sources['YE'], available=ok)
                self.assertEqual((result['activityStatus'], result['activeRequests'], result['online']), ('active', 1, True))
                self.assertEqual(list(Path(tmp).glob('*.json')), [])
            finally:
                telemetry.finish_activity(marker)
            sources, ok = activity.observe(Path(tmp)/'active')
            result = activity.present(datetime.now(timezone.utc), observed=sources['YE'], available=ok)
            self.assertEqual((result['activityStatus'], result['activeRequests']), ('recent', 0))

    def test_concurrent_requests_stay_separate_and_long_stream_remains_active(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'codex_event_spool_dir', tmp):
            markers = [telemetry.start_activity(str(n), owner) for n, owner in enumerate(['YE', 'YE', 'XT'])]
            try:
                value = json.loads(markers[0].read_text())
                value['startedAt'] = (datetime.now(timezone.utc)-timedelta(hours=1)).isoformat()
                markers[0].write_text(json.dumps(value))
                sources, ok = activity.observe(Path(tmp)/'active')
                self.assertTrue(ok)
                self.assertEqual(sources['YE']['activeRequests'], 2)
                self.assertEqual(sources['XT']['activeRequests'], 1)
                telemetry.finish_activity(markers[1])
                sources, _ = activity.observe(Path(tmp)/'active')
                result = activity.present(datetime.now(timezone.utc), observed=sources['YE'])
                self.assertEqual((result['activityStatus'], result['activeRequests']), ('active', 1))
            finally:
                for marker in markers:
                    telemetry.finish_activity(marker)

    def test_abrupt_server_exit_releases_active_status_across_processes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'request.json'
            code = "from app.services.codex_activity import begin; from pathlib import Path; import sys,time; begin(Path(sys.argv[1]), 'YE'); print('ready', flush=True); time.sleep(60)"
            process = subprocess.Popen([sys.executable, '-c', code, str(path)], stdout=subprocess.PIPE, text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), 'ready')
                sources, ok = activity.observe(Path(tmp))
                self.assertTrue(ok)
                self.assertEqual(sources['YE']['activeRequests'], 1)
            finally:
                process.kill(); process.wait(timeout=5); process.stdout.close()
            sources, ok = activity.observe(Path(tmp))
            result = activity.present(datetime.now(timezone.utc), observed=sources['YE'], available=ok)
            self.assertEqual((result['activityStatus'], result['activeRequests']), ('recent', 0))

    def test_five_minute_boundary_and_revocation(self):
        now = datetime.now(timezone.utc)
        self.assertEqual(activity.present(now)['activityStatus'], 'idle')
        self.assertEqual(activity.present(now, now-timedelta(seconds=300))['activityStatus'], 'recent')
        self.assertEqual(activity.present(now, now-timedelta(seconds=301))['activityStatus'], 'idle')
        result = activity.present(now, now, {'activeRequests': 2}, revoked=True)
        self.assertEqual((result['activityStatus'], result['online'], result['activeRequests']), ('revoked', False, 0))

    def test_unreadable_or_invalid_activity_does_not_claim_idle_or_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'invalid.json').write_text('{')
            sources, ok = activity.observe(Path(tmp))
            result = activity.present(datetime.now(timezone.utc), observed=sources.get('YE'), available=ok)
            self.assertEqual((result['activityStatus'], result['online']), ('unknown', False))
        now = datetime.now(timezone.utc)
        self.assertEqual(activity.present(now, now+timedelta(seconds=31))['activityStatus'], 'unknown')
        self.assertEqual(activity.present(now, 'invalid')['activityStatus'], 'unknown')

    def test_completion_failure_releases_lease_without_interfering_with_usage_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'codex_event_spool_dir', tmp):
            marker = telemetry.start_activity('first', 'YE')
            with patch.object(telemetry.os, 'replace', side_effect=OSError), self.assertLogs(telemetry.log, level='ERROR'):
                telemetry.finish_activity(marker)
            sources, ok = activity.observe(Path(tmp)/'active')
            self.assertTrue(ok)
            self.assertEqual(sources['YE']['activeRequests'], 0)

    def test_cancellation_before_response_headers_finishes_activity_and_keeps_unknown_usage(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings, 'codex_event_spool_dir', tmp):
            client = MagicMock()
            client.send = AsyncMock(side_effect=asyncio.CancelledError)
            client.aclose = AsyncMock()
            with patch.object(telemetry, 'upstream', return_value=('https://example.test', {})), patch.object(telemetry.httpx, 'AsyncClient', return_value=client):
                with self.assertRaises(asyncio.CancelledError):
                    asyncio.run(telemetry.proxy_response({'device_id': 'YE', 'user_id': 1}, b'{}'))
            sources, ok = activity.observe(Path(tmp)/'active')
            self.assertTrue(ok)
            self.assertEqual(sources['YE']['activeRequests'], 0)
            record = json.loads(next(Path(tmp).glob('*.json')).read_text())
            self.assertEqual((record['http_status'], record['usage']), (499, None))
            client.aclose.assert_awaited_once()


if __name__ == '__main__':
    unittest.main()
