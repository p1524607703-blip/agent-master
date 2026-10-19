import hashlib
from contextlib import redirect_stdout
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import uuid
import urllib.error
from unittest.mock import patch


ROOT=Path(__file__).resolve().parents[3]
SCRIPTS=ROOT/'.agents/skills/codex-device-relay/scripts'


def load(name):
    spec=importlib.util.spec_from_file_location('pilot_'+name,SCRIPTS/(name+'.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


helper=load('windows_pilot')
builder=load('build_windows_pilot_bundle')


class WindowsHandoffTests(unittest.TestCase):
    def manifest(self):
        return {'deviceId':str(uuid.uuid4()),'userId':1,'deviceName':'Synthetic-Windows',
            'providerName':'Synthetic trial','platform':'windows','apiKey':'fixture-key-'+'x'*43,
            'baseUrl':'https://relay.example.test/api/codex/v1',
            'heartbeatUrl':'https://relay.example.test/api/codex/heartbeat','model':'fixture-model'}

    def test_secret_never_sent_to_different_heartbeat_host(self):
        value=self.manifest();value['heartbeatUrl']='https://different.example.test/heartbeat'
        with patch.object(helper.urllib.request,'build_opener') as opener:
            with self.assertRaises(RuntimeError):helper.call(value,'heartbeatUrl',{'codexRunning':True})
            opener.assert_not_called()

    def test_plaintext_or_credential_in_url_is_rejected(self):
        for base in ['http://relay.example.test/v1','https://user:password@relay.example.test/v1','https://relay.example.test/v1?key=x']:
            value=self.manifest();value['baseUrl']=base
            with patch.object(helper.urllib.request,'build_opener') as opener:
                with self.assertRaises(RuntimeError):helper.call(value,'/models')
                opener.assert_not_called()

    def test_preparation_does_not_touch_default_provider_or_main_auth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);home=root/'user';home.mkdir()
            protected=[home/'.codex/config.toml',home/'.codex/auth.json',home/'.codex-session-delete/settings.json']
            for p in protected:p.parent.mkdir(parents=True,exist_ok=True);p.write_text('synthetic-original-state')
            before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
            manifest=self.manifest();bundle=root/'bundle';builder.build(manifest,bundle)
            printed=io.StringIO()
            with redirect_stdout(printed),patch.object(helper.Path,'home',return_value=home),patch.dict(os.environ,{'LOCALAPPDATA':str(root/'appdata')}),patch.object(helper,'protect'),patch.object(helper,'call',return_value=io.BytesIO(b'{"data":[{"id":"fixture-model"}]}')):
                helper.install(bundle)
            self.assertEqual(before,{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in protected})
            self.assertFalse((home/'.codex-session-delete/pending-provider-import.json').exists())
            client=json.loads((bundle/'device.json').read_text())
            self.assertNotIn('userId',client)
            self.assertNotIn(manifest['apiKey'],printed.getvalue())
            self.assertTrue((bundle/'技能/codex-device-relay/SKILL.md').exists())

    def test_unactivated_server_leaves_installation_and_default_state_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bundle=root/'bundle';builder.build(self.manifest(),bundle)
            target=root/'appdata'
            error=urllib.error.HTTPError('https://relay.example.test',503,'pending',{},None)
            with patch.dict(os.environ,{'LOCALAPPDATA':str(target)}),patch.object(helper,'call',side_effect=error),patch.object(helper,'protect') as protect:
                with self.assertRaises(urllib.error.HTTPError):helper.install(bundle)
                protect.assert_not_called()
            self.assertFalse(target.exists())
