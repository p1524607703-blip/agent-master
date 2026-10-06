import json
import time
import unittest
from monitor import classify, record, signature, report


def result(body, **extra):
    return dict(content=[{'type': 'text', 'text': json.dumps(body)}], isError=False, **extra)


class MonitorTests(unittest.TestCase):
    def test_outer_success_does_not_hide_body_failure(self):
        self.assertEqual(classify('dsh', result({'ok': False}))['status'], 'fail')

    def test_permission_and_tunnel_errors(self):
        for message, expected in [('FORBIDDEN: This conversation does not support developer MCPs', 'session_forbidden'),
                                  ('tunnel_client_not_seen', 'tunnel_offline'), ('request timed out', 'timeout')]:
            self.assertEqual(classify('dsh', result({'error': message}))['reason'], expected)

    def test_empty_is_not_success(self):
        self.assertEqual(classify('seller', {'isError': False})['status'], 'unverified')

    def test_unknown_schema_not_pass(self):
        self.assertEqual(classify('seller', result({'active_tools': 45}))['status'], 'unverified')

    def test_catalog_boundary(self):
        c = {'registered_tool_count': 10, 'read_only_tool_count': 10, 'write_tool_count': 0, 'database_admin_tool_count': 0}
        self.assertEqual(classify('ads_catalog', result({'mcp_catalog': c}))['status'], 'pass')
        c['write_tool_count'] = 1
        self.assertEqual(classify('ads_catalog', result({'mcp_catalog': c}))['status'], 'fail')

    def test_doctor_ack_scope(self):
        self.assertEqual(classify('ziniao', result({'ok': True, 'command': 'doctor', 'data': None}))['reason'], 'doctor_ack_only')

    def test_sensitive_data_not_persisted(self):
        r = classify('dsh', result({'ok': True, 'bridge': 'gpt-mcp-bridge', 'token': 'SENSITIVE'}))
        self.assertNotIn('SENSITIVE', json.dumps(r))

    def test_stale_and_closed_evidence_rejected(self):
        now = time.time()
        run = {'started': now, 'targets': {'ads': {'cloud': {}}}}
        with self.assertRaises(ValueError):
            record(run, 'ads_db', {}, now - 1)
        with self.assertRaises(ValueError):
            record(run, 'ads_db', {}, now)
        run['finished'] = now
        with self.assertRaises(ValueError):
            record(run, 'seller', {}, now)

    def test_conflicting_body_error_wins(self):
        r = result({'ok': False}, structuredContent={'ok': True, 'bridge': 'gpt-mcp-bridge'})
        self.assertEqual(classify('dsh', r)['status'], 'fail')

    def test_nested_timeout_metadata_is_not_a_current_call_failure(self):
        r = result({'ok': True, 'bridge': 'gpt-mcp-bridge',
                    'taskLimits': {'idleTimeoutMs': 900000},
                    'lastExecution': {'error': 'previous timeout'}})
        self.assertEqual(classify('dsh', r)['status'], 'pass')

    def test_local_pass_never_becomes_cloud_or_web_pass(self):
        run = {'time': 'test', 'configured_servers': [], 'targets': {'x': {'name': 'X', 'local': 'pass', 'cloud': {}}}}
        text = report(run)
        self.assertIn('| X | 通过 | 未验证 | 未验证 |', text)
        self.assertEqual(signature(run)['x']['cloud'], {})


if __name__ == '__main__':
    unittest.main()
