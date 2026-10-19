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

    def test_only_management_can_read_distribution_roster(self):
        with patch.object(api, 'read_overview', new_callable=AsyncMock, return_value={'members': []}) as read:
            self.assertEqual(self.client.get('/api/codex/overview').status_code,401)
            for role in ('operator','ai','viewer'):
                self.as_role(role)
                self.assertEqual(self.client.get('/api/codex/overview').status_code,403)
            read.assert_not_awaited()
            for role in ('management','super_admin'):
                self.as_role(role)
                self.assertEqual(self.client.get('/api/codex/overview').json(),{'members':[]})

    def test_preparation_phase_keeps_ingestion_disabled(self):
        self.as_role('management')
        with patch.object(api.telemetry.settings,'codex_telemetry_enabled',False):
            self.assertEqual(self.client.post('/api/codex/heartbeat',json={}).status_code,503)
            self.assertEqual(self.client.get('/api/codex/v1/models').status_code,503)
            self.assertEqual(self.client.post('/api/codex/usage',json={}).status_code,404)
