import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api import codex_devices as api
from app.api.auth import require_session
from app.core.config import settings
from app.services import codex_access, codex_telemetry as relay
from app.services.auth import _connect


@unittest.skipUnless(os.environ.get('CODEX_ISOLATED_DB_TEST')=='1','requires disposable PostgreSQL')
class ApiAccessTests(unittest.TestCase):
    def query(self,sql,*args):
        async def run():
            c=await _connect()
            try:return [dict(r) for r in await c.fetch(sql,*args)]
            finally:await c.close()
        return asyncio.run(run())

    def setUp(self):
        if '/tmp/cpo-xt-' not in settings.database_url:raise RuntimeError('Isolated database required')
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        tmp=self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.object(settings,'codex_event_spool_dir',tmp))
        self.stack.enter_context(patch.object(settings,'codex_telemetry_enabled',True))
        self.query('TRUNCATE codex_ops.devices CASCADE')
        self.query("UPDATE iam.users SET status='active'")
        self.app=FastAPI();self.app.include_router(api.router,prefix='/api')
        self.app.dependency_overrides[require_session]=lambda:('fixture',{'roleCode':'super_admin','userId':1})
        self.client=TestClient(self.app);self.addCleanup(self.client.close)
        self.catalog=self.stack.enter_context(patch.object(relay,'model_catalog',AsyncMock(return_value={'data':[{'id':'fixture'}]})))
        self.material=self.client.post('/api/codex/devices',json={'userId':1,'deviceName':'YE fixture','platform':'windows'}).json()
        self.key=self.material['apiKey'];self.device_id=self.material['deviceId']
        self.headers={'Authorization':'Bearer '+self.key}

    def policy(self,revision=0,mode='api_key',approved=True):
        return self.client.patch('/api/codex/devices/'+self.device_id+'/access',json={
            'revision':revision,'authMode':mode,'approved':approved})

    def models(self,headers=None):
        return self.client.get('/api/codex/v1/models',headers=headers or self.headers)

    def test_approval_required_then_original_key_works_without_connector_or_identity_headers(self):
        denied=self.models();self.assertEqual(denied.status_code,403)
        self.assertEqual(denied.json()['error']['code'],'access_approval_required')
        self.catalog.assert_not_awaited()
        before=self.query('SELECT device_id,user_id,key_hash FROM codex_ops.devices')[0]
        self.assertEqual(self.policy().status_code,200)
        self.assertEqual(self.models().status_code,200)
        self.assertEqual(self.models({**self.headers,'X-Device-ID':'somebody-else','X-CPO-Proof':'garbage'}).status_code,200)
        self.assertEqual(self.query('SELECT device_id,user_id,key_hash FROM codex_ops.devices')[0],before)
        self.assertNotIn(self.key,self.client.get('/api/codex/device-bindings').text)

    def test_hardware_is_opt_in_and_switching_does_not_rotate_key_or_bypass_approval(self):
        self.assertEqual(self.policy().status_code,200)
        self.assertEqual(self.policy(1,'hardware').status_code,200)
        self.assertEqual(self.models().status_code,403)
        self.assertEqual(self.policy(2,'api_key',False).status_code,200)
        self.assertEqual(self.models().status_code,403)
        self.assertEqual(self.policy(3).status_code,200)
        self.assertEqual(self.models().status_code,200)
        self.assertEqual(len(self.query('SELECT * FROM codex_ops.device_access_audit')),5)

    def test_invalid_revoked_and_disabled_keys_have_distinct_statuses_and_never_reach_upstream(self):
        self.assertEqual(self.models({'Authorization':'Bearer '+'z'*48}).status_code,401)
        self.assertEqual(self.policy().status_code,200)
        self.client.patch('/api/codex/devices/'+self.device_id+'/control',json={'revision':0,'enabled':False})
        disabled=self.models();self.assertEqual(disabled.status_code,403)
        self.assertEqual(disabled.json()['error']['code'],'device_disabled')
        self.client.delete('/api/codex/devices/'+self.device_id)
        revoked=self.models();self.assertEqual(revoked.status_code,401)
        self.assertEqual(revoked.json()['error']['code'],'invalid_api_key')
        self.catalog.assert_not_awaited()

    def test_permissions_revision_and_strict_payload_are_preserved(self):
        for role in ['management','operator','ai','viewer']:
            self.app.dependency_overrides[require_session]=lambda role=role:('fixture',{'roleCode':role,'userId':1})
            self.assertEqual(self.policy().status_code,403)
        self.app.dependency_overrides[require_session]=lambda:('fixture',{'roleCode':'super_admin','userId':1})
        self.assertEqual(self.policy().status_code,200)
        self.assertEqual(self.policy().status_code,409)
        self.assertEqual(self.client.patch('/api/codex/devices/'+self.device_id+'/access',json={
            'revision':1,'authMode':'api_key','approved':'true'}).status_code,422)

    def test_concurrent_admin_updates_require_the_same_revision_only_once(self):
        import uuid
        async def run():
            return await asyncio.gather(*[codex_access.update(uuid.UUID(self.device_id),revision=0,
                auth_mode='api_key',approved=True,actor=1) for _ in range(2)],return_exceptions=True)
        results=asyncio.run(run())
        self.assertEqual(sum(isinstance(r,dict) for r in results),1)
        self.assertEqual([r.status_code for r in results if not isinstance(r,dict)],[409])

    def test_cancelled_approval_is_rechecked_after_queue_and_never_calls_upstream(self):
        from app.services import codex_control as control
        import uuid
        self.assertEqual(self.policy().status_code,200)
        control.update(revision=0,actor=1,max_concurrent=1)
        async def run():
            lease=await control.acquire(uuid.uuid4())
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app),base_url='https://fixture.test') as client:
                    task=asyncio.create_task(client.post('/api/codex/v1/responses',headers=self.headers,
                        json={'model':'fixture','input':'hi','stream':True}))
                    for _ in range(100):
                        if control.snapshot()[1].get(self.device_id,{}).get('queuedRequests'):
                            break
                        await asyncio.sleep(.005)
                    else:self.fail('Request did not enter queue')
                    await codex_access.update(uuid.UUID(self.device_id),revision=1,auth_mode='api_key',approved=False,actor=1)
                    lease.close()
                    return await task
            finally:lease.close()
        with patch.object(relay,'_proxy_response',new_callable=AsyncMock) as upstream:
            response=asyncio.run(run())
        self.assertEqual(response.status_code,403)
        self.assertEqual(response.json()['error']['code'],'access_policy_changed')
        upstream.assert_not_awaited()
        self.assertEqual(control.snapshot()[1],{})

    def test_legacy_migration_is_idempotent_preserves_key_and_does_not_approve_new_pending_keys(self):
        old=asyncio.run(relay.register_device(1,'Legacy fixture','windows'))
        self.query('DELETE FROM codex_ops.device_access WHERE device_id=$1',__import__('uuid').UUID(old['deviceId']))
        before=self.query('SELECT device_id,key_hash FROM codex_ops.devices ORDER BY device_id')
        migration=Path(__file__).resolve().parents[1]/'migrations/20261023_codex_api_access.sql'
        async def migrate():
            c=await _connect()
            try:
                for _ in range(2):await c.execute(migration.read_text())
            finally:await c.close()
        asyncio.run(migrate())
        self.assertEqual(self.query('SELECT device_id,key_hash FROM codex_ops.devices ORDER BY device_id'),before)
        self.assertEqual(self.models({'Authorization':'Bearer '+old['apiKey']}).status_code,200)
        self.assertEqual(self.models().status_code,403)
