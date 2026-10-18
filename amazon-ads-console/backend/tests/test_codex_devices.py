import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.auth import require_session
from app.api import codex_devices as api
from app.services.codex_devices import heartbeat_online


class CodexDeviceTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(api.router, prefix='/api')
        self.client = TestClient(self.app)

    def as_role(self, role):
        self.app.dependency_overrides[require_session] = lambda: ('test', {'roleCode': role})

    def test_management_only_for_roster_and_provisioning(self):
        with patch.object(api.service, 'overview', new_callable=AsyncMock, return_value={'members': []}) as read:
            self.assertEqual(self.client.get('/api/codex/overview').status_code, 401)
            for role in ('operator', 'ai', 'viewer'):
                self.as_role(role)
                self.assertEqual(self.client.get('/api/codex/overview').status_code, 403)
                self.assertEqual(self.client.post('/api/codex/devices', json={'user_id':17,'device_name':'test'}).status_code, 403)
                self.assertEqual(self.client.delete('/api/codex/devices/'+str(uuid4())).status_code, 403)
            read.assert_not_awaited()
            for role in ('management','super_admin'):
                self.as_role(role)
                self.assertEqual(self.client.get('/api/codex/overview').status_code, 200)

    def test_online_expiration_and_revocation(self):
        now = datetime.now(timezone.utc)
        self.assertTrue(heartbeat_online(now-timedelta(seconds=120), None, now))
        for beat, revoked in [(None,None),(now-timedelta(seconds=121),None),(now,now),(now+timedelta(seconds=1),None)]:
            self.assertFalse(heartbeat_online(beat,revoked,now))

    def test_heartbeat_has_its_own_device_auth(self):
        with patch.object(api.service, 'heartbeat', new_callable=AsyncMock, return_value=False) as beat:
            self.assertEqual(self.client.post('/api/codex/heartbeat', json={}).status_code,401)
            self.assertEqual(self.client.post('/api/codex/heartbeat',json={},headers={'Authorization':'Bearer wrong'}).status_code,401)
            beat.return_value = True
            self.assertEqual(self.client.post('/api/codex/heartbeat',json={},headers={'Authorization':'Bearer device'}).status_code,200)

    def usage(self, **values):
        payload = dict(device_id=str(uuid4()),response_id='resp_test',model='test-model',outcome='completed',
                       occurred_at=datetime.now(timezone.utc).isoformat(),input_tokens=100,output_tokens=20,
                       cached_input_tokens=60,reasoning_tokens=10)
        return {**payload,**values}

    def test_usage_validation_and_missing_usage(self):
        for change in [dict(input_tokens=-1),dict(cached_input_tokens=101),dict(reasoning_tokens=21),
                       dict(input_tokens=None),dict(occurred_at='2026-10-18T01:00:00'),
                       dict(occurred_at=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat())]:
            with self.assertRaises(ValidationError):
                api.UsageRequest(**self.usage(**change))
        unknown = api.UsageRequest(**self.usage(input_tokens=None,output_tokens=None,cached_input_tokens=None,reasoning_tokens=None,outcome='interrupted'))
        self.assertIsNone(unknown.input_tokens)

    def test_usage_requires_trusted_proxy_and_preserves_duplicate_result(self):
        with patch.object(api.settings,'codex_usage_reporter_key',None), patch.object(api.service,'record_usage',new_callable=AsyncMock) as write:
            self.assertEqual(self.client.post('/api/codex/usage',json=self.usage()).status_code,503)
            write.assert_not_awaited()
        with patch.object(api.settings,'codex_usage_reporter_key','reporter'), patch.object(api.service,'record_usage',new_callable=AsyncMock,return_value=False) as write:
            self.assertEqual(self.client.post('/api/codex/usage',json=self.usage(),headers={'Authorization':'Bearer device'}).status_code,401)
            write.assert_not_awaited()
            response=self.client.post('/api/codex/usage',json=self.usage(),headers={'Authorization':'Bearer reporter'})
            self.assertEqual(response.json(),{'recorded':False})


if __name__ == '__main__':
    unittest.main()
