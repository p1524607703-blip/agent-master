import asyncio
import json
import os
import secrets
import tempfile
import unittest
import uuid
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import AsyncMock,patch

import httpx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import codex_devices as api
from app.api.auth import require_session
from app.core.config import settings
from app.services import codex_telemetry as service
from app.services.auth import _connect


class ParserTests(unittest.TestCase):
    def test_active_request_journal_is_private_and_separate_from_terminal_outbox(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings,'codex_event_spool_dir',tmp):
            path=service.start_activity(str(uuid.uuid4()),'fixture-device')
            self.assertEqual(path.stat().st_mode & 0o777,0o600)
            self.assertEqual(list(service.spool_dir().glob('*.json')),[])
            self.assertEqual(set(json.loads(path.read_text())),{'schemaVersion','deviceId','startedAt'})
            service.finish_activity(path)
            self.assertIn('finishedAt',json.loads(path.read_text()))
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_terminal_usage_without_newline_is_read_at_eof(self):
        observer = service.UsageObserver()
        observer.feed(b'data: {"type":"response.incomplete","response":{"id":"eof","usage":{"input_tokens":2,"output_tokens":1,"total_tokens":3}}}')
        observer.finish()
        self.assertEqual(observer.usage['total_tokens'],3)
        self.assertFalse(observer.completed)

    def test_usage_from_different_response_is_not_reused(self):
        observer = service.UsageObserver()
        observer.observe_response({'id':'one','usage':{'input_tokens':1,'output_tokens':1,'total_tokens':2}}, True)
        observer.observe_response({'id':'two'}, False)
        self.assertIsNone(observer.usage)

    def test_chunks_utf8_and_parent_token_counts(self):
        observer = service.UsageObserver()
        value = {'type':'response.completed','response':{'id':'resp-test','usage':{
            'input_tokens':10,'output_tokens':4,'total_tokens':14,
            'input_tokens_details':{'cached_tokens':6},'output_tokens_details':{'reasoning_tokens':3}}}}
        data = ('data: '+json.dumps(value)+'\n\n').encode()
        for i in range(0,len(data),3):observer.feed(data[i:i+3])
        self.assertTrue(observer.completed)
        self.assertEqual(observer.usage['total_tokens'],14)
        self.assertEqual(observer.usage['cached_tokens'],6)
        self.assertEqual(observer.usage['reasoning_tokens'],3)

    def test_missing_invalid_or_boolean_usage_stays_unknown(self):
        for usage in [None,{}, {'input_tokens':True,'output_tokens':2,'total_tokens':3},
                      {'input_tokens':2,'output_tokens':3,'total_tokens':9}]:
            self.assertIsNone(service.valid_usage(usage))

    def test_unbounded_delta_is_skipped_without_losing_final_usage(self):
        observer = service.UsageObserver()
        observer.feed(b'data: '+b'x'*(1024*1024+20))
        observer.feed(b'\n\ndata: {"type":"response.completed","response":{"id":"r","usage":{"input_tokens":0,"output_tokens":0,"total_tokens":0}}}\n\n')
        self.assertTrue(observer.completed)
        self.assertEqual(observer.usage['total_tokens'],0)


class NotificationTests(unittest.IsolatedAsyncioTestCase):
    async def test_notification_failure_does_not_replay_committed_accounting(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings,'codex_event_spool_dir',tmp):
            record = {'request_id':str(uuid.uuid4()),'device_id':str(uuid.uuid4()),
                'finished_at':datetime.now(timezone.utc).isoformat(),
                'http_status':200,'completed':True,'usage':{'input_tokens':2,'output_tokens':1,'total_tokens':3}}
            conn = AsyncMock()
            async def execute(sql, *args):
                if 'pg_notify' in sql: raise RuntimeError('notification unavailable')
            conn.execute.side_effect = execute
            with patch.object(service,'_connect',new=AsyncMock(return_value=conn)):
                await service.save_event(record)
            self.assertEqual(list(Path(tmp).glob('*.json')), [])
            calls = [call.args[0] for call in conn.execute.await_args_list]
            self.assertEqual(sum('INSERT INTO' in sql for sql in calls),1)
            self.assertEqual(sum('pg_notify' in sql for sql in calls),1)
            conn.close.assert_awaited_once()


@unittest.skipUnless(os.environ.get('CODEX_ISOLATED_DB_TEST')=='1','requires disposable private PostgreSQL fixture')
class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if '/tmp/cpo-xt-' not in settings.database_url:
            raise RuntimeError('Refusing to run against a non-isolated database')
        cls.temp = tempfile.TemporaryDirectory(prefix='cpo-xt-events-')
        settings.codex_telemetry_enabled = True
        settings.codex_event_spool_dir = cls.temp.name+'/events'
        settings.codex_upstream_base_url = 'http://127.0.0.1:1/v1'
        path = Path(cls.temp.name)/'upstream.key'
        path.write_text('fixture-upstream-credential')
        path.chmod(0o600)
        settings.codex_upstream_key_file = str(path)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def query(self,sql,*args):
        async def run():
            conn = await _connect()
            try:return [dict(row) for row in await conn.fetch(sql,*args)]
            finally:await conn.close()
        return asyncio.run(run())

    def setUp(self):
        self.query('TRUNCATE codex_ops.model_requests,codex_ops.devices')
        self.query("UPDATE iam.users SET status='active'")
        self.app = FastAPI()
        self.app.include_router(api.router,prefix='/api')
        self.app.dependency_overrides[require_session] = lambda:('test',{'roleCode':'super_admin'})
        self.client = TestClient(self.app)
        result = self.client.post('/api/codex/devices',json={'userId':1,'deviceName':'Test Windows','platform':'windows'})
        self.assertEqual(result.status_code,200,result.text)
        self.device = result.json()
        self.headers = {'Authorization':'Bearer '+self.device['apiKey']}

    def overview_device(self):
        response = self.client.get('/api/codex/overview')
        self.assertEqual(response.status_code,200,response.text)
        return response.json()['members'][0]['devices'][0]

    def fake_upstream(self,kind='completed',response_id='resp-one'):
        original = httpx.AsyncClient
        def handler(request):
            self.assertEqual(request.headers['authorization'],'Bearer fixture-upstream-credential')
            self.assertNotIn(self.device['apiKey'],str(request.headers))
            if kind=='error':return httpx.Response(400,json={'error':{'message':'fixture rejection'}})
            if request.method=='GET':return httpx.Response(200,json={'data':[{'id':'fixture-model'}]})
            usage = {'input_tokens':10,'output_tokens':4,'total_tokens':14,
                'input_tokens_details':{'cached_tokens':6},'output_tokens_details':{'reasoning_tokens':3}}
            response = {'id':response_id,'status':'completed'}
            if kind!='missing':response['usage']=usage
            if request.url.path.endswith('/compact'):return httpx.Response(200,json=response)
            event = {'type':'response.completed','response':response}
            return httpx.Response(200,headers={'Content-Type':'text/event-stream'},content=('data: '+json.dumps(event)+'\n\n').encode())
        return patch.object(service.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))

    def call_model(self):
        return self.client.post('/api/codex/v1/responses',headers=self.headers,json={'model':'fixture-model','stream':True,'input':'synthetic test'})

    def test_bad_key_cannot_call_or_heartbeat(self):
        for headers in [{},{'Authorization':'Bearer '+'x'*43}]:
            self.assertEqual(self.client.get('/api/codex/v1/models',headers=headers).status_code,401)
            self.assertEqual(self.client.post('/api/codex/heartbeat',headers=headers,json={'codexRunning':True}).status_code,401)
        stored = self.query('SELECT key_hash FROM codex_ops.devices')[0]['key_hash']
        self.assertNotEqual(stored,self.device['apiKey'])

    def test_only_super_admin_provisions_and_reads(self):
        for role in ['management','ai','operator','viewer']:
            self.app.dependency_overrides[require_session] = lambda role=role:('test',{'roleCode':role})
            self.assertEqual(self.client.get('/api/codex/overview').status_code,403)
            self.assertEqual(self.client.post('/api/codex/devices',json={'userId':1,'deviceName':'Forbidden','platform':'windows'}).status_code,403)

    def test_no_device_identity_or_usage_can_be_forged_by_heartbeat(self):
        for extra in [{'userId':2},{'deviceId':str(uuid.uuid4())},{'totalTokens':99999}]:
            response = self.client.post('/api/codex/heartbeat',headers=self.headers,json={'codexRunning':True,**extra})
            self.assertEqual(response.status_code,422)
        self.assertEqual(self.client.post('/api/codex/usage',headers=self.headers,json={'totalTokens':100}).status_code,404)

    def test_heartbeat_and_catalog_do_not_claim_model_activity(self):
        self.assertFalse(self.overview_device()['online'])
        with self.fake_upstream():self.assertEqual(self.client.get('/api/codex/v1/models',headers=self.headers).status_code,200)
        self.assertFalse(self.overview_device()['online'])
        self.assertEqual(self.client.post('/api/codex/heartbeat',headers=self.headers,json={'codexRunning':True}).status_code,200)
        self.assertFalse(self.overview_device()['online'])
        self.assertTrue(self.overview_device()['agentOnline'])
        self.query("UPDATE codex_ops.devices SET last_heartbeat_at=now()-interval '121 seconds'")
        self.assertFalse(self.overview_device()['online'])
        self.client.post('/api/codex/heartbeat',headers=self.headers,json={'codexRunning':False})
        d=self.overview_device()
        self.assertTrue(d['agentOnline'])
        self.assertFalse(d['online'])
        self.assertEqual(d['activityStatus'], 'idle')

    def test_real_usage_deduplicated_cached_and_reasoning_not_added(self):
        with self.fake_upstream():
            self.assertEqual(self.call_model().status_code,200)
            self.assertEqual(self.call_model().status_code,200)
        d=self.overview_device()
        self.assertEqual(d['requests'],1)
        self.assertEqual(d['totalTokens'],14)
        self.assertEqual(d['inputTokens'],10)
        self.assertEqual(d['outputTokens'],4)
        self.assertEqual(d['cachedTokens'],6)
        self.assertEqual(d['reasoningTokens'],3)
        self.assertTrue(d['online'])
        self.assertFalse(d['agentOnline'])
        self.assertEqual(d['activityStatus'], 'recent')
        self.assertEqual(d['activeRequests'], 0)

    def test_missing_usage_and_error_are_unknown_not_zero(self):
        with self.fake_upstream('missing'):self.call_model()
        with self.fake_upstream('error'):self.assertEqual(self.call_model().status_code,400)
        d=self.overview_device()
        self.assertEqual(d['requests'],2)
        self.assertEqual(d['unknownRequests'],2)
        self.assertIsNone(d['totalTokens'])

    def test_compaction_uses_same_device_accounting(self):
        with self.fake_upstream():
            result=self.client.post('/api/codex/v1/responses/compact',headers=self.headers,json={'model':'fixture-model','input':[]})
            self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(self.overview_device()['totalTokens'],14)

    def test_only_safe_session_headers_reach_upstream(self):
        original=httpx.AsyncClient
        def handler(request):
            self.assertEqual(request.headers['session-id'],'fixture-session')
            self.assertEqual(request.headers['authorization'],'Bearer fixture-upstream-credential')
            self.assertNotIn('cookie',request.headers)
            self.assertNotIn('x-untrusted-upstream',request.headers)
            return httpx.Response(400,json={'error':'synthetic rejected request'})
        with patch.object(service.httpx,'AsyncClient',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler),**kw)):
            response=self.client.post('/api/codex/v1/responses',headers={**self.headers,
                'session-id':'fixture-session','cookie':'untrusted-cookie','x-untrusted-upstream':'https://untrusted.example'},
                json={'model':'fixture-model','stream':True,'input':'synthetic'})
            self.assertEqual(response.status_code,400)

    def test_connect_failure_is_recorded_as_unknown(self):
        original=httpx.AsyncClient
        def unavailable(request):
            raise httpx.ConnectError('synthetic connection failure')
        with patch.object(service.httpx,'AsyncClient',side_effect=lambda **kw:original(transport=httpx.MockTransport(unavailable),**kw)):
            self.assertEqual(self.call_model().status_code,502)
        d=self.overview_device()
        self.assertEqual(d['unknownRequests'],1)
        self.assertIsNone(d['totalTokens'])

    def test_client_disconnect_records_unknown_before_cleanup(self):
        async def run():
            with self.fake_upstream():
                _,_,_,stream=await service.proxy_response({'device_id':uuid.UUID(self.device['deviceId']),'user_id':1},b'{}')
                await stream.__anext__()
                await stream.aclose()
        asyncio.run(run())
        records=self.query('SELECT http_status,completed FROM codex_ops.model_requests')
        self.assertEqual(records[0]['http_status'],499)
        # The fixture returned a complete final event before disconnect, so measured
        # tokens remain legitimate even though downstream delivery was interrupted.
        self.assertEqual(self.overview_device()['totalTokens'],14)

    def test_revoked_device_and_inactive_person_rejected(self):
        self.query("UPDATE iam.users SET status='inactive' WHERE user_id=1")
        self.assertEqual(self.client.get('/api/codex/v1/models',headers=self.headers).status_code,401)
        self.query("UPDATE iam.users SET status='active' WHERE user_id=1")
        response=self.client.delete('/api/codex/devices/'+self.device['deviceId'])
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(self.client.post('/api/codex/heartbeat',headers=self.headers,json={'codexRunning':True}).status_code,401)

    def test_registration_manifest_idempotent_and_cannot_rebind(self):
        args=(1,'Test Windows','windows')
        result=asyncio.run(service.register_device(*args,key=self.device['apiKey'],device_id=self.device['deviceId']))
        self.assertEqual(result['deviceId'],self.device['deviceId'])
        self.assertEqual(len(self.query('SELECT device_id FROM codex_ops.devices')),1)
        with self.assertRaises(Exception):asyncio.run(service.register_device(*args,key='z'*43,device_id=self.device['deviceId']))

    def test_private_outbox_replays_after_database_outage(self):
        record={'request_id':str(uuid.uuid4()),'device_id':self.device['deviceId'],'response_id':'resp-offline-db',
            'finished_at':'2026-10-18T20:00:00+00:00','http_status':200,'completed':True,
            'usage':{'input_tokens':2,'output_tokens':3,'total_tokens':5}}
        with patch.object(service,'_connect',new_callable=AsyncMock,side_effect=RuntimeError('fixture db outage')):
            with self.assertRaises(RuntimeError):asyncio.run(service.save_event(record))
        paths=list(service.spool_dir().glob('*.json'))
        self.assertEqual(len(paths),1)
        self.assertEqual(paths[0].stat().st_mode & 0o077,0)
        self.assertNotIn('synthetic test',paths[0].read_text())
        asyncio.run(service.flush_events())
        self.assertEqual(self.overview_device()['totalTokens'],5)
        self.assertFalse(list(service.spool_dir().glob('*.json')))

    def test_late_usage_enriches_unknown_response_only_once(self):
        record={'request_id':str(uuid.uuid4()),'device_id':self.device['deviceId'],
            'response_id':'late-usage','finished_at':'2026-10-18T20:00:00+00:00',
            'http_status':200,'completed':False,'usage':None}
        asyncio.run(service.save_event(record))
        record.update(request_id=str(uuid.uuid4()),completed=True,
            usage={'input_tokens':10,'output_tokens':4,'total_tokens':14})
        asyncio.run(service.save_event(record))
        asyncio.run(service.save_event(record))
        d=self.overview_device()
        self.assertEqual((d['requests'],d['totalTokens'],d['unknownRequests']),(1,14,0))

    def test_ledger_includes_inactive_and_revoked_sources_and_excludes_earlier_records(self):
        self.query("INSERT INTO iam.users VALUES (2,'fixture_other','Synthetic Other','operator','active') ON CONFLICT DO NOTHING")
        other=asyncio.run(service.register_device(2,'Other device','windows'))
        def save(did,rid,total,when):
            asyncio.run(service.save_event({'request_id':str(uuid.uuid4()),'device_id':did,
                'response_id':rid,'finished_at':when,'http_status':200,'completed':True,
                'usage':None if total is None else {'input_tokens':total,'output_tokens':0,'total_tokens':total}}))
        current=datetime.now(timezone.utc).isoformat()
        save(self.device['deviceId'],'current-one',14,current)
        save(other['deviceId'],'current-other',6,current)
        save(self.device['deviceId'],'unknown-current',None,current)
        save(self.device['deviceId'],'before-period',500,'2025-01-01T00:00:00+00:00')
        self.query("UPDATE iam.users SET status='inactive' WHERE user_id=2")
        self.query('UPDATE codex_ops.devices SET revoked_at=now() WHERE device_id=$1',uuid.UUID(self.device['deviceId']))
        with patch.object(settings,'codex_ledger_started_at',datetime(2026,1,1,tzinfo=timezone.utc)):
            view=self.client.get('/api/codex/overview').json()
            ledger=view['ledger']
        self.assertEqual(ledger['totals']['totalTokens'],20)
        self.assertEqual((ledger['totals']['requests'],ledger['totals']['measuredRequests'],ledger['totals']['unknownRequests']),(3,2,1))
        self.assertEqual(len(ledger['sources']),2)
        self.assertEqual(ledger['accountCoverage'],'partial')
        self.assertTrue(next(x for x in ledger['sources'] if x['userId']==1)['revoked'])
        history=view['recordedHistory']
        self.assertEqual(history['totals']['totalTokens'],520)
        self.assertEqual(history['scope'],'recorded-unified-entry')
        self.assertEqual(history['startSource'],'first-stored-record')
        self.assertEqual(history['accountCoverage'],'partial')
        self.assertEqual(len(history['sources']),2)

    def test_ledger_is_unstarted_without_explicit_aware_start(self):
        for start in [None,datetime(2026,1,1)]:
            with patch.object(settings,'codex_ledger_started_at',start):
                ledger=self.client.get('/api/codex/overview').json()['ledger']
            self.assertEqual(ledger['status'],'not-started')
            self.assertIsNone(ledger['totals']['totalTokens'])

    def test_history_is_available_when_no_requests_exist_after_activation(self):
        record={'request_id':str(uuid.uuid4()),'device_id':self.device['deviceId'],
            'response_id':'old-history','finished_at':'2025-01-01T00:00:00+00:00',
            'http_status':200,'completed':True,'usage':{'input_tokens':20,'output_tokens':2,'total_tokens':22}}
        asyncio.run(service.save_event(record))
        with patch.object(settings,'codex_ledger_started_at',datetime(2026,1,1,tzinfo=timezone.utc)):
            view=self.client.get('/api/codex/overview').json()
        self.assertIsNone(view['ledger']['totals']['totalTokens'])
        self.assertEqual(view['recordedHistory']['totals']['totalTokens'],22)
        self.assertEqual(view['recordedHistory']['totals']['measuredRequests'],1)

    def test_pending_outbox_does_not_hide_committed_ledger(self):
        from app.services import codex_devices
        path=service.stage_event({'request_id':str(uuid.uuid4()),'device_id':self.device['deviceId']})
        try:
            with patch.object(codex_devices,'flush_events',new_callable=AsyncMock,side_effect=RuntimeError('synthetic write failure')):
                response=self.client.get('/api/codex/overview')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['ledger']['pendingAccountingEvents'],1)
        finally:
            path.unlink(missing_ok=True)

    def test_usage_enrichment_grant_does_not_allow_identity_or_time_edits(self):
        async def run():
            import asyncpg
            conn=await _connect()
            try:
                await conn.execute("DO $$ BEGIN CREATE ROLE amazon_ads_admin; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
                await conn.execute('GRANT USAGE ON SCHEMA codex_ops TO amazon_ads_admin')
                await conn.execute('GRANT SELECT,INSERT ON codex_ops.model_requests TO amazon_ads_admin')
                grant=Path(__file__).resolve().parents[1]/'migrations/20261020_codex_ledger_usage_grant.sql'
                await conn.execute(grant.read_text())
                await conn.execute('SET ROLE amazon_ads_admin')
                await conn.execute('UPDATE codex_ops.model_requests SET completed=completed WHERE false')
                for column in ['device_id','finished_at','response_id']:
                    with self.assertRaises(asyncpg.InsufficientPrivilegeError):
                        await conn.execute('UPDATE codex_ops.model_requests SET '+column+'='+column+' WHERE false')
            finally:
                await conn.close()
        asyncio.run(run())


@unittest.skipUnless(os.environ.get('CODEX_LIVE_KEY_FILE'),'requires explicit real-model opt-in')
class LiveProxyTests(unittest.TestCase):
    def test_live_model_accounting(self):
        self.assertIn('/tmp/cpo-xt-',settings.database_url)
        with tempfile.TemporaryDirectory(prefix='cpo-xt-live-events-') as temporary:
            settings.codex_telemetry_enabled=True
            settings.codex_upstream_base_url=os.environ['CODEX_LIVE_BASE_URL']
            settings.codex_upstream_key_file=os.environ['CODEX_LIVE_KEY_FILE']
            settings.codex_event_spool_dir=temporary
            device=asyncio.run(service.register_device(1,'Synthetic live acceptance','windows'))
            app=FastAPI();app.include_router(api.router,prefix='/api')
            app.dependency_overrides[require_session]=lambda:('test',{'roleCode':'super_admin'})
            marker='candidate-live-'+secrets.token_hex(8)
            with TestClient(app) as client:
                response=client.post('/api/codex/v1/responses',
                    headers={'Authorization':'Bearer '+device['apiKey']},json={
                        'model':'gpt-6.1-sol','stream':True,'store':False,
                        'input':[{'role':'user','content':'Reply exactly '+marker}]})
                self.assertEqual(response.status_code,200,'Real model response status was not 200')
                observer=service.UsageObserver();observer.feed(response.content)
                text=[]
                for line in response.text.splitlines():
                    if not line.startswith('data:'):continue
                    try:event=json.loads(line[5:].strip())
                    except ValueError:continue
                    if event.get('type')=='response.output_text.delta':text.append(event.get('delta',''))
                self.assertTrue(observer.completed)
                self.assertEqual(''.join(text).strip(),marker)
                self.assertIsNotNone(observer.usage,'Upstream did not supply valid token usage')
                overview=client.get('/api/codex/overview').json()
                item=overview['members'][0]['devices'][0]
                self.assertEqual(item['totalTokens'],observer.usage['total_tokens'])
                self.assertEqual(item['inputTokens'],observer.usage['input_tokens'])
                self.assertEqual(item['outputTokens'],observer.usage['output_tokens'])
                self.assertEqual(item['requests'],1)
                self.assertTrue(item['online'])
                self.assertEqual(item['activityStatus'], 'recent')
                receipt={'testedAt':datetime.now(timezone.utc).isoformat(),
                    'source':'administrator candidate acceptance, synthetic isolated DB identity',
                    'status':response.status_code,'completed':observer.completed,'markerMatched':True,
                    'usage':observer.usage,'overviewTokensMatched':True,'onlineWithoutHeartbeat':item['online'],
                    'realWindowsDeviceTested':False,'desktopVerified':False,'localToolVerified':False,
                    'productionDatabaseTouched':False}
                target=Path(os.environ['CODEX_LIVE_RECEIPT']);target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
                fd=os.open(target,os.O_CREAT|os.O_WRONLY|os.O_EXCL,0o600)
                with os.fdopen(fd,'w') as stream:json.dump(receipt,stream,ensure_ascii=False,indent=2)
                print(json.dumps(receipt,ensure_ascii=False))
