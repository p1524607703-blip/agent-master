"""Fault-injected rolling activation: preserve live streams and exact rollback."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('rolling', Path(__file__).with_name('rolling_release.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


class RollingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base = self.root / 'cpo'
        self.old = self.base / 'releases' / ('a' * 40)
        self.new = self.base / 'releases' / ('b' * 40)
        for release in (self.old, self.new):
            backend = release / 'amazon-ads-console/backend/app/services'
            backend.mkdir(parents=True)
            (backend / 'build_cache.py').write_text('def namespace(): pass')
            (release / 'release.json').write_text(json.dumps({'commit': release.name, 'public_url': 'https://example.invalid'}))
        self.current = self.base / 'current'
        self.current.symlink_to(self.old)
        self.front = self.root / 'frontend'
        self.front.symlink_to(self.current / 'amazon-ads-console/frontend/dist')
        self.units = {'cpo-console.service': True}
        self.enabled = {'cpo-console.service'}
        self.connections = {8000: 0, 8001: 0, 8002: 0}
        self.actions = []
        self.fail_warm = False
        self.fail_public = False
        self.fail_retirement = False
        self.patch('BASE', self.base)
        self.patch('FRONTEND', self.front)
        self.patch('STATE', self.base / 'shared/rolling.json')
        self.patch('SYSTEMD', self.root / 'systemd')
        self.patch('UNIT', self.root / 'systemd/cpo-console.service')
        self.patch('UPSTREAM', self.root / 'nginx/active.conf')
        self.patch('INTERNAL', self.root / 'nginx/internal.conf')
        self.patch('SNIPPETS', [self.root / 'nginx/api.conf', self.root / 'nginx/model.conf'])
        for path in r.SNIPPETS:
            r.write(path, 'proxy_pass http://127.0.0.1:8000;\n')
        self.legacy_unit = f'ExecStart={self.base}/current/.venv/bin/python run_rds.py\nWorkingDirectory={self.base}/current/amazon-ads-console/backend\n'
        r.write(r.UNIT, self.legacy_unit)
        self.original_link = r.link
        self.patch('link', self.link)
        self.patch('run', self.host_run)
        self.patch('connections', lambda port: self.connections[port])
        self.patch('idle', lambda port: not self.connections[port])
        self.patch('ready', lambda *a, **k: None)
        self.patch('public_ready', self.public_ready)
        self.patch('retirement_timer', lambda *a: None)
        self.patch('save_state', lambda value: r.write(r.STATE, json.dumps(value), 0o600))

    def patch(self, name, value):
        obj = patch.object(r, name, value)
        obj.start()
        self.addCleanup(obj.stop)

    def link(self, path, target):
        return self.original_link(self.front if str(path) == '/var/www/cpo-console' else path, target)

    def host_run(self, *args, **kwargs):
        self.actions.append(args)
        if args[:3] == ('systemctl', 'is-active', '--quiet'):
            return subprocess.CompletedProcess(args, 0 if self.units.get(args[3]) else 3, b'', b'')
        if args[:2] == ('systemctl', 'enable'):
            self.enabled.add(args[-1])
        if args[:2] == ('systemctl', 'disable'):
            self.enabled.discard(args[-1])
        if args[:2] == ('systemctl', 'start'):
            self.units[args[2]] = True
        if args[:2] == ('systemctl', 'stop'):
            if self.fail_retirement and args[2] == 'cpo-console.service':
                raise RuntimeError('retirement failure')
            self.units[args[2]] = False
        if args and args[0] == 'runuser' and self.fail_warm:
            raise RuntimeError('warm failed')
        return subprocess.CompletedProcess(args, 0, b'', b'')

    def public_ready(self, *args):
        self.assertTrue(self.units['cpo-console.service'])
        self.assertTrue(self.units['cpo-console-blue.service'])
        self.assertIn(('systemctl', 'enable', 'cpo-console-blue.service'), self.actions)
        if self.fail_public:
            self.connections[8001] = 1
            raise RuntimeError('public failed')

    def activate(self):
        r.activate(self.new, self.root / 'engine/rolling_release.py')

    def test_warm_failure_preserves_legacy_and_routing(self):
        self.fail_warm = True
        with self.assertRaises(RuntimeError): self.activate()
        self.assertEqual(self.current.resolve(), self.old)
        self.assertTrue(self.units['cpo-console.service'])
        self.assertFalse(self.units['cpo-console-blue.service'])
        self.assertFalse(r.STATE.exists())
        self.assertNotIn('cpo-console-blue.service', self.enabled)
        self.assertEqual(r.SNIPPETS[0].read_text(), 'proxy_pass http://127.0.0.1:8000;\n')

    def test_live_legacy_stream_never_stopped_then_eventually_retires(self):
        self.connections[8000] = 1
        self.activate()
        self.assertEqual(self.current.resolve(), self.new)
        self.assertTrue(self.units['cpo-console.service'])
        self.assertEqual(r.active_state()['draining']['port'], 8000)
        self.assertIn('cpo-console-blue.service', self.enabled)
        self.assertIn(str(self.old) + '/', r.UNIT.read_text())
        self.assertNotIn(('systemctl', 'stop', 'cpo-console.service'), self.actions)
        self.connections[8000] = 0
        r.retire()
        self.assertIsNone(r.active_state()['draining'])
        self.assertIn('listen 127.0.0.1:8000;', r.INTERNAL.read_text())
        self.assertIn('Requires=cpo-console-blue.service', r.UNIT.read_text())

    def test_public_failure_rolls_back_but_keeps_candidate_stream_then_retires_it(self):
        self.fail_public = True
        with self.assertRaises(RuntimeError): self.activate()
        self.assertEqual(self.current.resolve(), self.old)
        self.assertTrue(self.units['cpo-console.service'])
        self.assertTrue(self.units['cpo-console-blue.service'])
        self.assertEqual(r.active_state()['slot'], 'legacy')
        self.assertNotIn('cpo-console-blue.service', self.enabled)
        self.assertFalse(r.INTERNAL.exists())
        self.connections[8001] = 0
        r.retire()
        self.assertIsNone(r.active_state()['draining'])
        self.assertEqual(r.UNIT.read_text(), self.legacy_unit)
        self.assertFalse(self.units['cpo-console-blue.service'])

    def test_retirement_failure_does_not_rollback_committed_healthy_release(self):
        self.fail_retirement = True
        self.activate()
        self.assertEqual(self.current.resolve(), self.new)
        self.assertEqual(r.active_state()['commit'], self.new.name)
        self.assertIsNotNone(r.active_state()['draining'])
        self.fail_retirement = False
        r.retire()
        self.assertIsNone(r.active_state()['draining'])

    def test_second_activation_refuses_to_reuse_undrained_slot(self):
        self.connections[8000] = 1
        self.activate()
        with self.assertRaisesRegex(RuntimeError, 'still draining'): self.activate()
        self.assertTrue(self.units['cpo-console.service'])

    def test_unit_uses_pinned_release_not_mutable_current_and_no_forced_kill(self):
        value = r.slot_unit(self.new, 8001, Path('/verified/rolling_release.py'))
        self.assertIn(str(self.new) + '/.venv/bin/python', value)
        self.assertNotIn('/current/', value)
        self.assertIn('TimeoutStopSec=infinity', value)
        self.assertIn('CPO_CACHE_NAMESPACE=' + self.new.name, value)

    def test_unknown_proxy_refused_and_allowed_replacement_unique(self):
        with self.assertRaises(ValueError): r.proxy_snippet('proxy_pass http://other;')
        self.assertEqual(r.proxy_snippet('proxy_pass http://127.0.0.1:8000;'), 'proxy_pass http://cpo_active;')

    def test_idle_requires_consecutive_zero_samples(self):
        actual = spec.loader
        # Exercise the real idle routine, overriding only its connection source.
        imported = importlib.util.module_from_spec(spec)
        actual.exec_module(imported)
        with patch.object(imported, 'connections', side_effect=[0, 1]):
            self.assertFalse(imported.idle(8000, pause=lambda _: None))
        with patch.object(imported, 'connections', return_value=0) as count:
            self.assertTrue(imported.idle(8000, pause=lambda _: None))
            self.assertEqual(count.call_count, 3)


if __name__ == '__main__': unittest.main()
