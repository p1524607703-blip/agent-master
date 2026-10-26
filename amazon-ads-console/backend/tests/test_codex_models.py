import asyncio
from contextlib import ExitStack
import json
from pathlib import Path
import tempfile
import unittest
import uuid
from unittest.mock import AsyncMock, Mock, patch

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from app.api import codex_devices as api
from app.api.auth import require_session
from app.core.config import settings
from app.services import codex_models as models, codex_telemetry as relay, codex_control, codex_access

CATALOG={'object':'list','data':[{'id':'gpt-6.1-sol','object':'model'},{'id':'gpt-6-astra','object':'model'}]}

class ModelAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.tmp=self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.object(settings,'codex_event_spool_dir',self.tmp))
        self.stack.enter_context(patch.object(settings,'codex_telemetry_enabled',True))
        self.stack.enter_context(patch.object(relay,'upstream',return_value=('http://fixture.invalid/v1',{})))
        client=self.stack.enter_context(patch.object(relay.httpx,'AsyncClient'))
        client.return_value.__aenter__.return_value.get=AsyncMock(return_value=httpx.Response(200,json=CATALOG))
        self.app=FastAPI();self.app.include_router(api.router,prefix='/api')
        self.app.dependency_overrides[require_session]=lambda:('fixture',{'roleCode':'super_admin','userId':1})
        self.device={'device_id':uuid.uuid4()}
        self.app.dependency_overrides[api.require_device]=lambda:self.device
        self.client=TestClient(self.app);self.addCleanup(self.client.close)

    def change(self,ids,revision=0):
        return self.client.patch('/api/codex/model-settings',json={'revision':revision,'enabledModels':ids})

    def test_default_catalog_survives_then_disabled_model_is_hidden_and_rejected(self):
        self.assertEqual(self.client.get('/api/codex/v1/models').json(),CATALOG)
        self.assertEqual(self.change(['gpt-6.1-sol']).status_code,200)
        self.assertEqual(self.client.get('/api/codex/v1/models').json()['data'],CATALOG['data'][:1])
        self.assertEqual(self.client.get('/api/codex/model-settings').json()['availableModels'],['gpt-6.1-sol','gpt-6-astra'])
        with patch.object(codex_control,'acquire',new_callable=AsyncMock) as acquire:
            for endpoint in ['/responses','/responses/compact']:
                response=self.client.post('/api/codex/v1'+endpoint,json={'model':'gpt-6-astra','input':'hello'})
                self.assertEqual(response.status_code,403,response.text)
                self.assertEqual(response.json()['error']['code'],'model_not_enabled')
            acquire.assert_not_awaited()
        self.assertEqual(self.change(['gpt-6.1-sol','gpt-6-astra'],1).status_code,200)
        models.require_model(b'{"model":"gpt-6-astra"}')

    def test_empty_list_explicitly_closes_all_and_stale_updates_do_not_overwrite(self):
        self.assertEqual(self.change([]).status_code,200)
        self.assertEqual(self.client.get('/api/codex/v1/models').json()['data'],[])
        self.assertEqual(self.change(['gpt-6-astra']).status_code,409)
        self.assertEqual(models.snapshot()['enabledModels'],[])

    def test_unverified_duplicate_and_invalid_payloads_never_change_policy(self):
        self.assertEqual(self.change(['made-up']).status_code,400)
        self.assertEqual(self.change(['gpt-6-astra']*2).status_code,400)
        self.assertEqual(self.change([1]).status_code,422)
        self.assertEqual(self.change(['gpt-6-astra']*65).status_code,422)
        self.assertEqual(models.snapshot()['revision'],0)

    def test_only_admins_can_read_or_change_global_models(self):
        for role in ['management','operator','ai','viewer']:
            self.app.dependency_overrides[require_session]=lambda role=role:('fixture',{'roleCode':role,'userId':1})
            self.assertEqual(self.client.get('/api/codex/model-settings').status_code,403)
            self.assertEqual(self.change([]).status_code,403)
        self.assertEqual(models.snapshot()['revision'],0)

    def test_policy_is_private_persistent_and_corruption_fails_closed(self):
        self.change(['gpt-6-astra'])
        path=Path(self.tmp)/'control/models.json'
        self.assertEqual(path.stat().st_mode&0o777,0o600)
        self.assertEqual(json.loads(path.read_text()),models.snapshot())
        self.assertEqual(models.snapshot()['updatedBy'],1)
        path.write_text('{bad')
        response=self.client.get('/api/codex/v1/models')
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json()['error']['code'],'model_policy_unavailable')

    def test_disable_while_waiting_is_rechecked_and_releases_lease(self):
        self.change(['gpt-6-astra'])
        lease=Mock()
        async def admitted(*args):
            models.update(revision=1,enabled_models=[],available_models=['gpt-6-astra'],actor=2)
            return lease
        with patch.object(codex_control,'acquire',side_effect=admitted),patch.object(codex_access,'recheck_queued',new_callable=AsyncMock),patch.object(relay,'_proxy_response',new_callable=AsyncMock) as upstream:
            with self.assertRaises(HTTPException) as raised:
                asyncio.run(relay.proxy_response(self.device,b'{"model":"gpt-6-astra"}'))
        self.assertEqual(raised.exception.status_code,403)
        upstream.assert_not_awaited();lease.close.assert_called_once()

    def test_model_setting_does_not_modify_device_limits(self):
        codex_control.update(revision=0,actor=1,max_concurrent=3)
        before=codex_control.snapshot()[0]
        self.change(['gpt-6-astra'])
        self.assertEqual(codex_control.snapshot()[0],before)

    def test_disabling_does_not_interrupt_an_already_admitted_stream(self):
        self.change(['gpt-6-astra'])
        lease=Mock()
        async def stream():
            yield b'finished'
        async def run():
            with patch.object(codex_control,'acquire',AsyncMock(return_value=lease)),patch.object(codex_access,'recheck_queued',new_callable=AsyncMock),patch.object(relay,'_proxy_response',AsyncMock(return_value=(200,'text/event-stream','fixture',stream()))):
                result=await relay.proxy_response(self.device,b'{"model":"gpt-6-astra"}')
            models.update(revision=1,enabled_models=[],available_models=['gpt-6-astra'],actor=2)
            return [chunk async for chunk in result[3]]
        self.assertEqual(asyncio.run(run()),[b'finished'])
        lease.close.assert_called_once()
