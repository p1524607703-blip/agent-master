import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import require_session
from app.api import codex_devices as api


class CodexDeviceTests(unittest.TestCase):
    def setUp(self):
        self.app = FastAPI()
        self.app.include_router(api.router, prefix='/api')
        self.client = TestClient(self.app)

    def as_role(self, role):
        self.app.dependency_overrides[require_session] = lambda: ('test', {'roleCode': role})

    def test_only_super_admin_can_read_distribution_roster(self):
        with patch.object(api, 'read_overview', new_callable=AsyncMock, return_value={'members': []}) as read:
            self.assertEqual(self.client.get('/api/codex/overview').status_code,401)
            for role in ('management','operator','ai','viewer'):
                self.as_role(role)
                self.assertEqual(self.client.get('/api/codex/overview').status_code,403)
            read.assert_not_awaited()
            for role in ('super_admin',):
                self.as_role(role)
                self.assertEqual(self.client.get('/api/codex/overview').json(),{'members':[]})

    def test_management_cannot_read_or_mutate_any_device_administration_route(self):
        self.as_role('management')
        device = '00000000-0000-0000-0000-000000000001'
        requests = [
            ('GET', '/overview', None), ('GET', '/access-control', None),
            ('GET', '/access-config', None), ('GET', '/account-quota', None),
            ('GET', '/quota-batches/fixture/revisions', None),
            ('POST', '/devices', {'userId': 1, 'deviceName': 'fixture', 'platform': 'windows'}),
            ('PATCH', '/devices/' + device, {'deviceName': 'fixture'}),
            ('DELETE', '/devices/' + device, None),
            ('PATCH', '/access-control', {'revision': 0, 'maxConcurrent': 1}),
            ('POST', '/devices/status', {'revision': 0, 'scope': 'all', 'enabled': False}),
            ('PATCH', '/devices/' + device + '/control', {'revision': 0, 'enabled': False}),
        ]
        for method, path, body in requests:
            with self.subTest(method=method, path=path):
                self.assertEqual(self.client.request(method, '/api/codex' + path, json=body).status_code, 403)

    def test_preparation_phase_keeps_ingestion_disabled(self):
        self.as_role('super_admin')
        with patch.object(api.telemetry.settings,'codex_telemetry_enabled',False):
            self.assertEqual(self.client.post('/api/codex/heartbeat',json={}).status_code,503)
            self.assertEqual(self.client.get('/api/codex/v1/models').status_code,503)
            self.assertEqual(self.client.post('/api/codex/usage',json={}).status_code,404)
