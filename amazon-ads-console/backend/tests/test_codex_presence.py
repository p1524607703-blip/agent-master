import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from contextlib import redirect_stdout
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT/'.agents/skills/codex-device-relay/scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load('windows_pilot')
with patch.dict(sys.modules, {'windows_pilot': helper}):
    presence = load('windows_presence')
builder = load('build_windows_pilot_bundle')


class PresenceTests(unittest.TestCase):
    def config(self):
        return {'deviceId': str(uuid.uuid4()), 'deviceName': 'fixture', 'providerName':'fixture',
            'platform':'windows','apiKey':'fixture-key-'+'x'*43,'baseUrl':'https://relay.example.test/api/codex/v1',
            'heartbeatUrl':'https://relay.example.test/api/codex/heartbeat','model':'fixture-model'}

    def test_stop_and_remove_only_affect_the_current_device(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {'LOCALAPPDATA':temp+'/local','APPDATA':temp+'/roaming'}):
            config = self.config()
            directory, shortcut = presence.locations(config)
            directory.mkdir(parents=True);shortcut.parent.mkdir(parents=True)
            shortcut.write_text('fixture startup')
            key = directory/'device.json';key.write_text(json.dumps(config))
            unrelated = shortcut.parent/'another-app.lnk';unrelated.write_text('keep')
            with patch.object(helper,'protect'), redirect_stdout(io.StringIO()):
                presence.stop(config,remove=True)
            self.assertTrue((directory/'presence.stop').exists())
            self.assertFalse(shortcut.exists())
            self.assertTrue(unrelated.exists())
            self.assertEqual(json.loads(key.read_text()),config)

    def test_no_background_python_means_no_installation_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle=Path(temp);(bundle/'device.json').write_text(json.dumps(self.config()))
            with patch.dict(os.environ,{'LOCALAPPDATA':temp+'/local','APPDATA':temp+'/roaming'}),patch.object(Path,'is_file',return_value=False),patch.object(helper,'install') as install:
                with self.assertRaises(RuntimeError):presence.install(bundle)
                install.assert_not_called()

    def test_startup_handles_spaces_quotes_without_a_key_in_arguments(self):
        script=presence.shortcut_script(Path("C:/User's Folder/start.lnk"),Path('C:/Python/pythonw.exe'),Path("C:/User's Folder/private"))
        self.assertIn("User''s Folder",script)
        self.assertIn('windows_presence.py',script)
        self.assertIn('" run',script)
        self.assertNotIn('apiKey',script)

    def test_bundle_has_versioned_presence_and_keeps_legacy_auth_out(self):
        with tempfile.TemporaryDirectory() as temp:
            config=self.config();target=Path(temp)/'bundle'
            builder.build(config,target,{'releaseId':'fixture-client-1','sourceCommit':'a'*40})
            version=json.loads((target/'版本清单.json').read_text())
            self.assertEqual(version['sourceCommit'],'a'*40)
            self.assertTrue((target/'windows_presence.py').exists())
            self.assertIn('windows_presence.py', (target/'4-开启持续在线检测.cmd').read_text())
            self.assertFalse((target/'pending-provider-import.json').exists())
            self.assertNotIn(config['apiKey'],(target/'0-交给AI.txt').read_text())
            self.assertNotIn('userId',json.loads((target/'device.json').read_text()))


if __name__ == '__main__':
    unittest.main()
