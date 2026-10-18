"""Opt-in real PostgreSQL acceptance; refuses to run against an application DB."""
import os
from pathlib import Path
import unittest
from urllib.parse import urlsplit

import asyncpg

from app.core.config import settings
from app.api.codex_devices import UsageRequest
from app.services import codex_devices as service

DSN = os.environ.get('CODEX_TEST_DATABASE_URL')


@unittest.skipUnless(DSN, 'Set CODEX_TEST_DATABASE_URL to an isolated cpo_codex_test_* database')
class CodexDatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        assert urlsplit(DSN).path.lstrip('/').startswith('cpo_codex_test_'), 'Refusing a non-test database'
        self.previous = settings.database_url
        settings.database_url = DSN
        self.conn = await asyncpg.connect(DSN)
        await self.conn.execute('''DROP SCHEMA IF EXISTS codex_ops CASCADE;
            CREATE SCHEMA codex_ops;
            CREATE TABLE codex_ops.personnel_memberships(user_id bigint PRIMARY KEY);
            INSERT INTO codex_ops.personnel_memberships VALUES(17);
            CREATE VIEW codex_ops.personnel_roster AS SELECT user_id, '测试人员'::text AS display_name,
                'test_pan'::text AS username, 'ai'::text AS group_code, 'AI小组'::text AS group_name,
                'Pan'::text AS person_code, 'ai'::text AS role_code, 'active'::text AS status
                FROM codex_ops.personnel_memberships;''')
        await self.conn.execute((Path(__file__).resolve().parents[1]/'migrations/20261018_codex_devices.sql').read_text())

    async def asyncTearDown(self):
        settings.database_url = self.previous
        await self.conn.close()

    async def test_real_registration_heartbeat_usage_dedup_and_revocation(self):
        self.assertIsNone(await service.create_device(999,'unbound','test'))
        device = await service.create_device(17,'Pan-test','macOS')
        self.assertIsNotNone(device)
        row = await self.conn.fetchrow('SELECT * FROM codex_ops.devices')
        self.assertNotEqual(row['heartbeat_key_hash'], device['heartbeatKey'])
        self.assertEqual(len(row['heartbeat_key_hash']),64)
        self.assertFalse(await service.heartbeat('wrong','1'))
        first = (await service.overview())['members'][0]['devices'][0]
        self.assertFalse(first['online'])
        self.assertIsNone(first['totalTokens'])
        self.assertTrue(await service.heartbeat(device['heartbeatKey'],'1'))
        occurred = await self.conn.fetchval('SELECT now()')
        payload = UsageRequest(device_id=device['deviceId'],response_id='resp_1',model='test-model',
            outcome='completed',occurred_at=occurred,input_tokens=100,output_tokens=20,cached_input_tokens=60,reasoning_tokens=10)
        self.assertTrue(await service.record_usage(payload))
        self.assertFalse(await service.record_usage(payload))
        unknown = UsageRequest(device_id=device['deviceId'],response_id='resp_2',model='test-model',outcome='interrupted',occurred_at=occurred)
        self.assertTrue(await service.record_usage(unknown))
        data = (await service.overview())['members'][0]['devices'][0]
        self.assertTrue(data['online'])
        self.assertEqual((data['totalTokens'],data['todayTokens'],data['requests'],data['unknownRequests']),(120,120,2,1))
        await self.conn.execute("UPDATE codex_ops.devices SET last_heartbeat_at=now()-interval '121 seconds'")
        self.assertFalse((await service.overview())['members'][0]['devices'][0]['online'])
        self.assertTrue(await service.revoke_device(payload.device_id))
        self.assertFalse(await service.heartbeat(device['heartbeatKey'],'1'))
        self.assertFalse(await service.record_usage(payload.model_copy(update={'response_id':'resp_3'})))
        self.assertFalse((await service.overview())['members'][0]['devices'][0]['online'])
