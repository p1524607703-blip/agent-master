"""Disposable-DB concurrent request -> measured usage -> quota estimate integration."""
import asyncio
import json
import os
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import httpx
from app.core.config import settings
from app.services.auth import _connect
from app.services import codex_telemetry as relay
from app.services.codex_auto_attribution import atomic, reconcile
from app.services.codex_devices import overview


@unittest.skipUnless(os.environ.get('CODEX_ISOLATED_DB_TEST')=='1','requires disposable private PostgreSQL fixture')
class ConcurrentFlowTests(unittest.IsolatedAsyncioTestCase):
    async def test_twenty_sources_have_separate_keys_tokens_and_automatic_quota_estimates(self):
        if '/tmp/cpo-xt-' not in settings.database_url:
            raise RuntimeError('Refusing a non-isolated database')
        with tempfile.TemporaryDirectory(prefix='cpo-xt-concurrent-') as tmp:
            directory=Path(tmp);quota_path=directory/'quota.json';host_path=directory/'host.json';attribution_path=directory/'attribution.json'
            reset=int(datetime.now(timezone.utc).timestamp())+604200
            upstream=directory/'upstream.key';upstream.write_text('fixture-upstream-only');upstream.chmod(0o600)
            native_at = None
            def snapshots(used,tokens,events):
                nonlocal native_at
                now=datetime.now(timezone.utc).isoformat()
                if tokens and native_at is None:native_at=now
                atomic(quota_path,dict(schemaVersion=1,status='available',capturedAt=now,planType='fixture',primary=dict(usedPercent=used,resetsAt=reset,windowDurationMins=10080),secondary=None))
                atomic(host_path,dict(schemaVersion=1,status='available',userId=17,deviceId='fixture-main',capturedAt=now,codexRunning=True,
                    planType='fixture',resetsAt=reset,windowDurationMins=10080,totalTokens=tokens,todayTokens=tokens,
                    inputTokens=tokens,outputTokens=0,cachedTokens=0,reasoningTokens=0,usageEvents=events,unknownSegments=0,lastActivityAt=now if events else None))
                native_rows=[dict(eventKey='host:fixture-main-event',source='fixture-main',userId=17,
                    startedAt=native_at,endedAt=native_at,timingComplete=True,totalTokens=tokens,
                    inputTokens=tokens,outputTokens=0,cachedTokens=0,reasoningTokens=0)] if tokens else []
                atomic(host_path.with_suffix('.evidence.json'),dict(schemaVersion=1,status='available',
                    capturedAt=now,planType='fixture',userId=17,deviceId='fixture-main',complete=True,
                    periodStartedAt=datetime.fromtimestamp(reset-604800,timezone.utc).isoformat(),events=native_rows))
            names=dict(codex_telemetry_enabled=True,codex_quota_snapshot_file=str(quota_path),
                       codex_host_usage_snapshot_file=str(host_path),codex_quota_attribution_file=str(attribution_path),
                       codex_event_spool_dir=str(directory/'events'),codex_upstream_key_file=str(upstream),
                       codex_upstream_base_url='http://127.0.0.1:1/v1')
            patches=[patch.object(settings,name,value) for name,value in names.items()]
            for item in patches:item.start()
            try:
                conn=await _connect()
                try:
                    await conn.execute('TRUNCATE codex_ops.model_requests,codex_ops.devices')
                    await conn.execute("INSERT INTO iam.users(user_id,username,display_name,role_code,status) SELECT n,'fixture-'||n,'Fixture '||n,'operator','active' FROM generate_series(1,20) n ON CONFLICT(user_id) DO UPDATE SET status='active'")
                finally:await conn.close()
                snapshots(0,0,0);atomic(attribution_path,dict(schemaVersion=1,confirmations=[]))
                await reconcile()
                credentials={uid:await relay.register_device(uid,'Fixture device '+str(uid),'windows') for uid in range(1,21) if uid!=17}
                self.assertEqual(len({v['apiKey'] for v in credentials.values()}),19)
                original=httpx.AsyncClient
                async def handler(request):
                    self.assertEqual(request.headers['authorization'],'Bearer fixture-upstream-only')
                    uid=int(request.headers['session-id']);await asyncio.sleep(0.002)
                    usage=dict(input_tokens=uid*90,output_tokens=uid*10,total_tokens=uid*100,input_tokens_details=dict(cached_tokens=uid*80),output_tokens_details=dict(reasoning_tokens=uid*5))
                    event=dict(type='response.completed',response=dict(id='fixture-response-'+str(uid),usage=usage))
                    return httpx.Response(200,headers={'content-type':'text/event-stream'},content=('data: '+json.dumps(event)+'\n\n').encode())
                async def request(uid,material):
                    device=await relay.authenticate(material['apiKey'])
                    status,_,_,stream=await relay.proxy_response(device,b'{}',forward_headers={'session-id':str(uid)})
                    async for _ in stream:pass
                    self.assertEqual(status,200)
                with patch.object(relay.httpx,'AsyncClient',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
                    listener = await _connect()
                    changed = asyncio.Event()
                    payloads = []
                    def notified(connection, pid, channel, payload):
                        payloads.append(payload); changed.set()
                    try:
                        await listener.add_listener('codex_usage_changed', notified)
                        await asyncio.gather(*(request(uid,material) for uid,material in credentials.items()))
                        await asyncio.wait_for(changed.wait(), 2)
                        self.assertTrue(payloads)
                        self.assertEqual(set(payloads), {''})
                    finally:
                        await listener.close()
                # Measured requests arrive while the official total is still zero.
                snapshots(0,1700,1);await reconcile()
                self.assertEqual((await overview())['accountAttribution']['confirmedPercent'],0)
                snapshots(1,1700,1)
                monitor=await reconcile();self.assertEqual(monitor['reason'],'provisional-batches-updated')
                result=await overview();allocation=result['accountAttribution']
                self.assertEqual(allocation['status'],'available');self.assertEqual(allocation['concurrentEstimatedPercent'],1)
                self.assertEqual(allocation['unattributedPercent'],0);self.assertEqual(allocation['remainingPercent'],99)
                self.assertEqual(len(allocation['deviceShares']),20)
                for member in result['members']:
                    self.assertEqual(member['devices'][0]['currentWindowTokens'],member['userId']*100)
                    share=next(row for row in allocation['members'] if row['userId']==member['userId'])
                    self.assertGreater(share['usedPercent'],0);self.assertLess(share['usedPercent'],1)
                    self.assertEqual(share['evidence'][0]['method'],'provisional-token-weighted-batch')
                before=json.loads(attribution_path.read_text())['batchSummary']['allocations'];await reconcile()
                self.assertEqual(json.loads(attribution_path.read_text())['batchSummary']['allocations'],before)
                batch_id=allocation['batchMonitoring']['latestBatches'][0]['batchId']
                # A committed unknown terminal event later receives its real usage.
                late={'request_id':str(uuid.uuid4()),'response_id':'fixture-late-response',
                    'device_id':credentials[20]['deviceId'],'user_id':20,'started_at':native_at,
                    'finished_at':native_at,'http_status':200,'completed':False,'usage':None,'model_slug':'fixture-model'}
                await relay.save_event(late);await reconcile()
                late['usage']=dict(input_tokens=18000,output_tokens=1000,total_tokens=19000,cached_tokens=9000,reasoning_tokens=500)
                await relay.save_event(late);await reconcile();await relay.save_event(late);await reconcile()
                revised=await overview();updated=revised['accountAttribution']
                self.assertEqual(updated['usedPercent'],1)
                self.assertEqual(updated['confirmedPercent'],1)
                self.assertEqual(updated['unattributedPercent'],0)
                share=next(row for row in updated['members'] if row['userId']==20)
                self.assertEqual(share['usedPercent'],.525)
                self.assertEqual(updated['batchMonitoring']['latestBatches'][0]['batchId'],batch_id)
                self.assertGreater(updated['batchMonitoring']['latestBatches'][0]['revision'],1)
                measured=next(row for row in revised['members'] if row['userId']==20)['devices'][0]
                self.assertEqual(measured['currentWindowTokens'],21000)
                self.assertEqual(measured['currentWindowUnknownRequests'],0)
                output=os.environ.get('CODEX_CONCURRENT_FIXTURE_OUT')
                if output:
                    path=Path(output);path.write_text(json.dumps(revised,default=str));path.chmod(0o600)
            finally:
                for item in reversed(patches):item.stop()
