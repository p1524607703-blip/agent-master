"""Offline checks for destructive-scope boundaries and recoverable host changes."""
import fnmatch
import importlib.util
import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


cache = module('cache_release', ROOT / 'deploy/cache_release.py')
watchdog = module('redis_watchdog', ROOT / 'deploy/redis_watchdog.py')
infra = module('install_infra', ROOT / 'scripts/install_infra.py')


class FakeRedis:
    def __init__(self, keys):
        self.keys = set(keys)
        self.delete_batches = []

    def ping(self):
        return True

    def scan_iter(self, match, count):
        return iter(sorted(key for key in self.keys if fnmatch.fnmatch(key.decode(), match)))

    def delete(self, *keys):
        self.delete_batches.append(len(keys))
        deleted = len(self.keys.intersection(keys))
        self.keys.difference_update(keys)
        return deleted


class ReleaseOperationsTests(unittest.TestCase):
    def test_clear_preserves_locks_sessions_and_other_namespaces(self):
        snapshots = {f'cpo:build:v1:rev:day:{number}'.encode() for number in range(450)}
        snapshots.add(b'cpo:complete-days:v1:rev:all:all')
        retained = {b'cpo:build:v1:rev:day:0:lock', b'cpo:complete-days:v1:rev:all:all:lock',
                    b'iam:session:1', b'cpo:unrelated:1'}
        client = FakeRedis(snapshots | retained)
        result = cache.clear_snapshots(client)
        self.assertEqual(client.keys, retained)
        self.assertEqual(result, {'deleted_snapshots': 451, 'preserved_locks': 2})
        self.assertLessEqual(max(client.delete_batches), 200)

    def test_watchdog_warns_on_transition_reminds_and_recovers_once(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(watchdog, 'emit') as emit:
            state = Path(directory) / 'state.json'
            watchdog.update_state(state, True, now=1000)
            watchdog.update_state(state, False, 'ConnectionError', now=1060)
            watchdog.update_state(state, False, 'ConnectionError', now=1120)
            watchdog.update_state(state, False, 'ConnectionError', now=1960)
            watchdog.update_state(state, True, now=2020)
            watchdog.update_state(state, True, now=2080)
            self.assertEqual([call.args[0] for call in emit.call_args_list],
                             ['healthy', 'degraded', 'degraded', 'recovered'])
            self.assertEqual(state.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('redis://', state.read_text())

    def test_infra_backup_restores_files_symlinks_and_absent_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / 'original.conf'
            original.write_text('original\n')
            link = root / 'enabled'
            link.symlink_to(original)
            absent = root / 'new.conf'
            manifest = {}
            backup = root / 'backup'
            backup.mkdir()
            for path in (original, link, absent):
                infra.snapshot(path, backup, manifest)
            original.write_text('modified')
            link.unlink()
            link.write_text('replaced')
            absent.write_text('new')
            infra.restore(manifest)
            self.assertEqual(original.read_text(), 'original\n')
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.read_text(), 'original\n')
            self.assertFalse(absent.exists())

    def test_watchdog_request_errors_alert_even_when_ping_healthy_once_per_event(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(watchdog, 'emit') as emit:
            state = Path(directory) / 'state.json'
            trace = Path(directory) / 'requests.jsonl'
            trace.write_text('')
            watchdog.update_state(state, True, now=1000, trace_file=trace)
            trace.write_text(json.dumps({'event': 'request_complete', 'l2_error': 2,
                                         'timestamp': '1970-01-01T00:17:00+00:00'}) + '\n')
            current, event = watchdog.update_state(state, True, now=1060, trace_file=trace)
            self.assertEqual(event, 'degraded')
            self.assertTrue(current['ping_healthy'])
            self.assertEqual(current['request_cache_errors'], 2)
            self.assertEqual(emit.call_args.args[1], 'RedisRequestError')
            current, event = watchdog.update_state(state, True, now=1120, trace_file=trace)
            self.assertEqual(event, 'recovered')
            self.assertEqual(current['request_cache_errors'], 0)
            watchdog.update_state(state, True, now=1180, trace_file=trace)
            self.assertEqual([call.args[0] for call in emit.call_args_list], ['healthy', 'degraded', 'recovered'])

    def test_trace_cursor_survives_rotation_and_partial_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            trace = Path(directory) / 'requests.jsonl'
            record = json.dumps({'event': 'request_complete', 'l2_error': 1,
                                 'timestamp': '1970-01-01T00:17:00+00:00'})
            trace.write_text(record)
            errors, cursor, _ = watchdog.read_trace_errors(trace, {}, now=1060)
            self.assertEqual(errors, 0)
            with trace.open('a') as stream:
                stream.write('\n')
            errors, cursor, _ = watchdog.read_trace_errors(trace, {'trace_cursor': cursor}, now=1120)
            self.assertEqual(errors, 1)
            trace.rename(trace.with_suffix('.jsonl.1'))
            trace.write_text(record + '\n')
            errors, cursor, _ = watchdog.read_trace_errors(trace, {'trace_cursor': cursor}, now=1180)
            self.assertEqual(errors, 1)
            errors, _, _ = watchdog.read_trace_errors(trace, {'trace_cursor': cursor}, now=1240)
            self.assertEqual(errors, 0)

    def test_removes_only_cpo_legacy_log_format(self):
        text = "http {\n  log_format cpo_api 'request_uri=$request_uri';\n  log_format other '$uri';\n}\n"
        self.assertEqual(infra.without_legacy_format(text), "http {\n  log_format other '$uri';\n}\n")

    def test_rejects_config_injection(self):
        with self.assertRaises(ValueError):
            infra.configuration_plan('example.com; include /tmp/evil', '/etc/cert')
        with self.assertRaises(ValueError):
            infra.configuration_plan('example.com', '/etc/cert;')


if __name__ == '__main__':
    unittest.main()
