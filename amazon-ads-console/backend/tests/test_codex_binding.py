import asyncio
import base64
import json
import os
import secrets
import subprocess
import time
import unittest
import uuid
from unittest.mock import AsyncMock, patch

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils
from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.api import codex_devices as api
from app.api.auth import require_session
from app.services import codex_binding as binding, codex_telemetry as telemetry
from app.services.auth import _connect


def identity():
    private = ec.generate_private_key(ec.SECP256R1())
    public = base64.b64encode(private.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).decode()
    return private, public


def headers(key, private, method, path, body=b'', timestamp=None, nonce=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    nonce = nonce or secrets.token_urlsafe(24)
    der = private.sign(binding.canonical(key, method, path, timestamp, nonce, body), ec.ECDSA(hashes.SHA256()))
    r, s = utils.decode_dss_signature(der)
    return {'Authorization': 'Bearer ' + key, 'X-CPO-Time': timestamp, 'X-CPO-Nonce': nonce,
            'X-CPO-Proof': base64.b64encode(r.to_bytes(32, 'big') + s.to_bytes(32, 'big')).decode(), 'Content-Type': 'application/json'}


class ProofTests(unittest.TestCase):
    def test_proof_covers_credential_method_path_body_timestamp_and_nonce(self):
        a, public = identity()
        key, method, path, body = 'fixture-key-' + 'a' * 40, 'POST', '/api/codex/v1/responses', b'{"input":"hi"}'
        h = {k.lower(): v for k, v in headers(key, a, method, path, body).items()}
        self.assertEqual(binding.verify(key, method, path, h, body, public), h['x-cpo-nonce'])
        for changed in [(key+'x', method, path, h, body), (key, 'GET', path, h, body),
                        (key, method, path+'/compact', h, body), (key, method, path, h, body+b' '),
                        (key, method, path, dict(h, **{'x-cpo-time':str(int(time.time())-120)}), body),
                        (key, method, path, dict(h, **{'x-cpo-nonce':secrets.token_urlsafe(24)}), body),
                        (key, method, path, {}, body)]:
            with self.assertRaises(HTTPException): binding.verify(*changed, public)
        _, other = identity()
        with self.assertRaises(HTTPException): binding.verify(key, method, path, h, body, other)


@unittest.skipUnless(os.environ.get('CODEX_BINDING_DB_TEST') == '1', 'requires isolated PostgreSQL')
class BindingIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        if '/tmp/cpo-xt-' not in settings.database_url: raise RuntimeError('Isolated database required')
        self.enabled = patch.object(settings, 'codex_telemetry_enabled', True); self.enabled.start(); self.addCleanup(self.enabled.stop)
        conn = await _connect()
        try:
            await conn.execute('TRUNCATE codex_ops.devices CASCADE')
            await conn.execute("UPDATE iam.users SET status='active'")
        finally: await conn.close()
        self.material = await telemetry.register_device(1, 'Device A', 'macos')
        self.key = self.material['apiKey']; self.a, self.public = identity(); self.b, self.other_public = identity()
        self.app = FastAPI(); self.app.include_router(api.router, prefix='/api')
        self.app.dependency_overrides[require_session] = lambda: ('fixture', {'roleCode':'super_admin','userId':1})
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url='https://fixture.test')
        self.addAsyncCleanup(self.client.aclose)
        self.catalog = patch.object(telemetry, 'model_catalog', AsyncMock(return_value={'data':[{'id':'fixture'}]})); self.catalog.start(); self.addCleanup(self.catalog.stop)

    async def request(self, method, path, private=None, body=b'', **kw):
        return await self.client.request(method, path, content=body,
            headers=headers(self.key, private or self.a, method, path.split('?')[0], body, **kw))

    async def claim(self, private=None, public=None):
        return await self.request('POST', '/api/codex/device-enrollment', private,
            json.dumps({'publicKey':public or self.public,'provider':'macos-secure-enclave-p256'}).encode())

    async def approve(self, claim):
        result = claim.json()
        return await self.client.post('/api/codex/device-bindings/'+result['claimId']+'/approve', json={'fingerprint':result['fingerprint']})

    async def test_pending_approval_not_first_use_and_copied_key_rejected(self):
        path = '/api/codex/v1/models'
        self.assertEqual((await self.request('GET', path)).status_code, 403)
        good = await self.claim(); self.assertEqual(good.json()['state'],'pending')
        # A copied Key can nominate another candidate, but cannot replace approved A.
        copied = await self.claim(self.b, self.other_public)
        self.assertEqual(copied.json()['state'], 'pending')
        self.assertEqual((await self.request('GET', path)).status_code, 403)
        self.assertEqual((await self.approve(good)).status_code, 200)
        self.assertEqual((await self.request('GET', path)).status_code, 200)
        self.assertEqual((await self.client.get(path,headers={'Authorization':'Bearer '+self.key})).status_code, 403)
        self.assertEqual((await self.request('GET', path, self.b)).status_code, 403)
        self.assertEqual((await self.approve(copied)).status_code,409)
        self.assertEqual((await self.claim(self.b, self.other_public)).status_code,403)

    async def test_replay_expiry_queries_and_revocation(self):
        self.assertEqual((await self.approve(await self.claim())).status_code,200)
        path = '/api/codex/v1/models'; h = headers(self.key,self.a,'GET',path)
        results = await asyncio.gather(*[self.client.get(path,headers=h) for _ in range(8)])
        self.assertEqual([r.status_code for r in results].count(200),1)
        self.assertEqual([r.status_code for r in results].count(403),7)
        self.assertEqual((await self.request('GET',path,timestamp=int(time.time())-180)).status_code,403)
        self.assertEqual((await self.request('GET',path+'?a=1')).status_code,400)
        await self.client.delete('/api/codex/devices/'+self.material['deviceId'])
        self.assertEqual((await self.request('GET',path)).status_code,401)
        self.assertEqual((await self.claim()).status_code,401)

    async def test_parallel_devices_do_not_bind_by_shared_ip(self):
        await self.approve(await self.claim())
        second = await telemetry.register_device(1,'Device B','windows')
        akey = self.key; self.key = second['apiKey']
        await self.approve(await self.claim(self.b,self.other_public))
        path = '/api/codex/v1/models'
        tasks = [self.client.get(path,headers=headers(akey,self.a,'GET',path)) for _ in range(10)]
        tasks += [self.client.get(path,headers=headers(self.key,self.b,'GET',path)) for _ in range(10)]
        self.assertTrue(all(r.status_code == 200 for r in await asyncio.gather(*tasks)))
        self.assertEqual((await self.client.get(path,headers=headers(akey,self.b,'GET',path))).status_code,403)

    async def test_model_body_is_authenticated_before_upstream_and_cache_is_preserved(self):
        await self.approve(await self.claim())
        path='/api/codex/v1/responses'; body=b'{"model":"fixture","input":"hi","stream":true}'
        async def chunks(): yield b'data: {"type":"response.completed"}\n\n'
        proxy=AsyncMock(return_value=(200,'text/event-stream','fixture-request',chunks()))
        with patch.object(telemetry,'proxy_response',proxy):
            h=headers(self.key,self.a,'POST',path,body)
            self.assertEqual((await self.client.post(path,content=body+b' ',headers=h)).status_code,403)
            proxy.assert_not_awaited()
            result=await self.client.post(path,content=body,headers=h)
            self.assertEqual(result.status_code,200); self.assertIn('response.completed',result.text)
            proxy.assert_awaited_once()
            self.assertEqual(json.loads(proxy.await_args.args[1])['model'],'fixture')

    async def test_permission_boundary_and_approval_fingerprint(self):
        claim=await self.claim(); info=claim.json()
        path='/api/codex/device-bindings/'+info['claimId']+'/approve'
        self.assertEqual((await self.client.post(path,json={'fingerprint':'0'*64})).status_code,409)
        self.app.dependency_overrides[require_session]=lambda:('fixture',{'roleCode':'operator','userId':1})
        self.assertEqual((await self.client.get('/api/codex/device-bindings')).status_code,403)
        self.assertEqual((await self.client.post(path,json={'fingerprint':info['fingerprint']})).status_code,403)
        self.app.dependency_overrides.clear()
        self.assertEqual((await self.client.get('/api/codex/device-bindings')).status_code,401)

    async def test_one_public_key_cannot_approve_two_credentials_even_concurrently(self):
        first=await self.claim()
        second=await telemetry.register_device(1,'Second credential','macos')
        self.key=second['apiKey']; other=await self.claim()
        results=await asyncio.gather(self.approve(first),self.approve(other))
        self.assertEqual(sorted(r.status_code for r in results),[200,409])

    async def test_candidate_bound_and_existing_claim_can_be_retried(self):
        first=await self.claim()
        for _ in range(4):
            private,public=identity()
            self.assertEqual((await self.claim(private,public)).status_code,200)
        private,public=identity()
        self.assertEqual((await self.claim(private,public)).status_code,429)
        retried=await self.claim()
        self.assertEqual(first.json()['claimId'],retried.json()['claimId'])

    @unittest.skipUnless(os.environ.get('CPO_MAC_KEY_HELPER'), 'requires a real Mac Secure Enclave')
    async def test_real_mac_hardware_key_and_copied_credential(self):
        helper=os.environ['CPO_MAC_KEY_HELPER']
        def call(payload):
            return json.loads(subprocess.check_output([helper], input=json.dumps(payload).encode()))
        material=call({'action':'create','name':'hardware-acceptance'})
        class HardwarePrivate:
            def sign(self, message, algorithm):
                value=call({'action':'sign','name':'hardware-acceptance','handle':material['handle'],'message':base64.b64encode(message).decode()})
                raw=base64.b64decode(value['signature'])
                return utils.encode_dss_signature(int.from_bytes(raw[:32],'big'),int.from_bytes(raw[32:],'big'))
        self.a,self.public=HardwarePrivate(),material['publicKey']
        self.assertEqual((await self.approve(await self.claim())).status_code,200)
        path='/api/codex/v1/models'
        self.assertEqual((await self.request('GET',path)).status_code,200)
        self.assertEqual((await self.request('GET',path,self.b)).status_code,403)
        self.assertEqual((await self.client.get(path,headers={'Authorization':'Bearer '+self.key})).status_code,403)
