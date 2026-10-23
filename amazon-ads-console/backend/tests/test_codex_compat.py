import asyncio
from contextlib import ExitStack
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.api import codex_devices as api
from app.api.auth import require_session
from app.core.config import settings
from app.services import codex_telemetry as relay, codex_responses
from app.services.auth import _connect


class PreparationTests(unittest.TestCase):
    def test_doctor_payload_keeps_the_model_and_output_limit(self):
        original = {'model':'fixture','input':'你好','max_output_tokens':16}
        body, stream = codex_responses.prepare(original)
        adapted = json.loads(body)
        self.assertFalse(stream)
        self.assertEqual(adapted, {'model':'fixture','input':[{'role':'user','content':[{'type':'input_text','text':'你好'}]}],
                                  'max_output_tokens':16,'store':False,'stream':True})
        self.assertEqual(original, {'model':'fixture','input':'你好','max_output_tokens':16})

    def test_tool_history_and_other_request_options_are_preserved(self):
        value = {'model':'fixture','input':[{'type':'function_call_output','call_id':'c1','output':'result'}],
                 'tools':[{'type':'function','name':'fixture','parameters':{}}],'reasoning':{'effort':'low'},
                 'instructions':'Keep instructions','stream':True,'store':False,'max_output_tokens':128}
        body, stream = codex_responses.prepare(value)
        self.assertTrue(stream)
        self.assertEqual(json.loads(body),value)

    def test_invalid_stream_and_persistence_are_rejected_before_model_use(self):
        for payload in ({'stream':'false'},{'stream':0},{'store':True},{'store':None}):
            with self.assertRaises(HTTPException):codex_responses.prepare(payload)

    def test_compact_preserves_opaque_history_and_adds_only_one_native_trigger(self):
        value = {'model':'fixture','input':[{'type':'compaction','encrypted_content':'prior-opaque-state'},
                    {'role':'user','content':'Continue'}],'instructions':'preserve constraints'}
        body, stream = codex_responses.prepare_compact(value)
        expected = {**value,'input':[*value['input'],{'type':'compaction_trigger'}],'stream':True,'store':False}
        self.assertEqual(json.loads(body),expected)
        self.assertFalse(stream)
        body2,_ = codex_responses.prepare_compact({**expected,'stream':False})
        self.assertEqual(json.loads(body2),expected)
        self.assertEqual(len(value['input']),2)
        for extra in ({'input':None},{'input':{}},{'input':[],'stream':True}):
            with self.assertRaises(HTTPException):codex_responses.prepare_compact(extra)

    def test_buffered_final_response_supports_split_unicode_and_large_output(self):
        final = {'id':'response-fixture','status':'completed','output':[{'type':'message','role':'assistant',
                  'content':[{'type':'output_text','text':'你好'+'a'*(1024*1024)}]}],
                 'usage':{'input_tokens':7,'output_tokens':13,'total_tokens':20}}
        observer = relay.UsageObserver(capture_response=True)
        wire = ('data: '+json.dumps({'type':'response.completed','response':final},ensure_ascii=False)).encode()
        for i in range(0,len(wire),997):observer.feed(wire[i:i+997])
        observer.finish()
        self.assertTrue(observer.completed)
        self.assertEqual(observer.response, final)
        self.assertEqual(observer.usage['total_tokens'],20)


@unittest.skipUnless(os.environ.get('CODEX_ISOLATED_DB_TEST')=='1','requires disposable private PostgreSQL fixture')
class CompatibilityAndAccessTests(unittest.TestCase):
    def query(self,sql,*args):
        async def run():
            conn = await _connect()
            try:return [dict(row) for row in await conn.fetch(sql,*args)]
            finally:await conn.close()
        return asyncio.run(run())

    def setUp(self):
        if '/tmp/cpo-xt-' not in settings.database_url:raise RuntimeError('Isolated database required')
        self.temp = tempfile.TemporaryDirectory(prefix='cpo-xt-compat-')
        self.stack = ExitStack()
        self.addCleanup(self.temp.cleanup);self.addCleanup(self.stack.close)
        directory = Path(self.temp.name)
        key = directory/'upstream.key';key.write_text('fixture-upstream-private');key.chmod(0o600)
        for field,value in dict(codex_telemetry_enabled=True,codex_event_spool_dir=str(directory/'events'),
                                codex_public_base_url='https://relay.example.test/api/codex/v1',
                                codex_upstream_base_url='http://127.0.0.1:1/v1',codex_upstream_key_file=str(key)).items():
            self.stack.enter_context(patch.object(settings,field,value))
        self.query('TRUNCATE codex_ops.model_requests,codex_ops.devices CASCADE')
        self.query("UPDATE iam.users SET status='active'")
        self.app = FastAPI();self.app.include_router(api.router,prefix='/api')
        self.app.dependency_overrides[require_session] = lambda:('fixture',{'roleCode':'super_admin','userId':1})
        self.client = TestClient(self.app)
        self.device = self.client.post('/api/codex/devices',json={'userId':1,'deviceName':'YE 测试 Key','platform':'windows'}).json()
        self.headers = {'Authorization':'Bearer '+self.device['apiKey']}
        self.assertEqual(self.client.patch('/api/codex/devices/'+self.device['deviceId']+'/access',json={'revision':0,'authMode':'api_key','approved':True}).status_code,200)
        self.final = {'id':'response-doctor','object':'response','status':'completed',
                      'output':[{'type':'message','role':'assistant','content':[{'type':'output_text','text':'你好！'}]}],
                      'usage':{'input_tokens':7,'output_tokens':13,'total_tokens':20,
                               'input_tokens_details':{'cached_tokens':0},'output_tokens_details':{'reasoning_tokens':0}}}

    def upstream(self,kind='completed'):
        original = httpx.AsyncClient
        def handler(request):
            self.assertEqual(request.headers['authorization'],'Bearer fixture-upstream-private')
            self.assertNotIn(self.device['apiKey'],str(request.headers))
            if request.method=='GET':return httpx.Response(200,json={'data':[{'id':'fixture-model'}]})
            payload = json.loads(request.content)
            self.assertIsInstance(payload['input'],list)
            self.assertIs(payload['stream'],True);self.assertIs(payload['store'],False)
            self.assertEqual(payload['max_output_tokens'],16)
            if kind=='error':return httpx.Response(400,json={'error':{'message':'fixture upstream rejection'}})
            if kind=='busy':return httpx.Response(429,headers={'Retry-After':'2','X-Relay-Limit-Origin':'local'},
                json={'error':{'code':'relay_queue_timeout'}})
            created = {'type':'response.created','response':{'id':'response-doctor','status':'in_progress'}}
            wire = 'data: '+json.dumps(created)+'\n\n'
            if kind!='truncated':wire += 'data: '+json.dumps({'type':'response.completed','response':self.final})
            return httpx.Response(200,headers={'content-type':'text/event-stream'},content=wire.encode())
        return patch.object(relay.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))

    def doctor(self,**extra):
        return self.client.post('/api/codex/v1/responses',headers=self.headers,
                                json={'model':'fixture-model','input':'hi','max_output_tokens':16,**extra})

    def compact_upstream(self,kind='native'):
        original = httpx.AsyncClient
        self.compact_calls = []
        self.retained_item = {'type':'message','role':'user','content':[{'type':'input_text','text':'retained context'}]}
        self.native_item = {'type':'compaction','id':'cmp_fixture','encrypted_content':'opaque-native-checkpoint'}
        def handler(request):
            payload = json.loads(request.content)
            self.compact_calls.append(payload)
            self.assertEqual(request.url.path,'/v1/responses')
            self.assertEqual(payload['input'][-1],{'type':'compaction_trigger'})
            self.assertEqual(payload['input'][0],{'type':'compaction','encrypted_content':'prior-opaque-state'})
            self.assertEqual(payload['instructions'],'Keep all constraints')
            self.assertIs(payload['stream'],True);self.assertIs(payload['store'],False)
            if kind=='limited':return httpx.Response(429,headers={'Retry-After':'7','X-Relay-Limit-Origin':'upstream'},json={'error':{'code':'upstream_fixture_limit'}})
            items = [self.retained_item,self.native_item]
            if kind=='plaintext':items = [self.retained_item]
            elif kind=='local-summary':items = [{**self.native_item,'encrypted_content':'codexplusplus:summary:v1:"not native"'}]
            elif kind=='duplicate':items = [self.native_item,{**self.native_item,'id':'cmp_second'}]
            # Completion order can differ from canonical output_index order.
            events = [{'type':'response.output_item.done','output_index':i,'item':item} for i,item in reversed(list(enumerate(items)))]
            final = {**self.final,'id':self.final['id']+'-'+kind}
            if kind!='truncated':events.append({'type':'response.completed','response':final})
            wire = ''.join('data: '+json.dumps(e)+'\n\n' for e in events).encode()
            return httpx.Response(200,headers={'Content-Type':'text/event-stream'},content=wire)
        return patch.object(relay.httpx,'AsyncClient',side_effect=lambda **kwargs:original(transport=httpx.MockTransport(handler),**kwargs))

    def compact(self):
        return self.client.post('/api/codex/v1/responses/compact',headers=self.headers,json={'model':'fixture-model',
            'input':[{'type':'compaction','encrypted_content':'prior-opaque-state'},{'role':'user','content':'Recent turn'}],
            'instructions':'Keep all constraints'})

    def test_legacy_compact_returns_native_checkpoint_and_retained_window_once(self):
        with self.compact_upstream():result = self.compact()
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json(),{'id':self.final['id']+'-native','object':'response.compaction',
            'output':[self.retained_item,self.native_item],'usage':self.final['usage']})
        self.assertEqual(len(self.compact_calls),1)
        rows = self.query('SELECT device_id,completed,total_tokens FROM codex_ops.model_requests')
        self.assertEqual(len(rows),1)
        self.assertEqual(str(rows[0]['device_id']),self.device['deviceId'])
        self.assertEqual(rows[0]['total_tokens'],20)
        self.assertTrue(rows[0]['completed'])

    def test_compact_rejects_missing_or_fake_checkpoint_and_interruption_without_replay(self):
        for kind in ('plaintext','local-summary','duplicate','truncated'):
            with self.subTest(kind=kind),self.compact_upstream(kind):result = self.compact()
            self.assertEqual(result.status_code,502,result.text)
            self.assertEqual(len(self.compact_calls),1)
        rows = self.query('SELECT total_tokens FROM codex_ops.model_requests')
        self.assertEqual(len(rows),4)
        self.assertEqual(sum(r['total_tokens'] is None for r in rows),1)

    def test_compact_retains_upstream_limit_and_retry_guidance_without_replay(self):
        with self.compact_upstream('limited'):result = self.compact()
        self.assertEqual(result.status_code,429)
        self.assertEqual(result.headers['retry-after'],'7')
        self.assertEqual(result.headers['x-relay-limit-origin'],'upstream')
        self.assertEqual(result.json()['error']['code'],'upstream_fixture_limit')
        self.assertEqual(len(self.compact_calls),1)

    def test_unmodified_codexplusplus_doctor_gets_actual_json_and_measured_usage(self):
        with self.upstream():result = self.doctor()
        self.assertEqual(result.status_code,200,result.text)
        self.assertIn('application/json',result.headers['content-type'])
        self.assertEqual(result.json(),self.final)
        self.assertEqual(result.headers['cache-control'],'no-store')
        rows = self.query('SELECT * FROM codex_ops.model_requests')
        self.assertEqual(len(rows),1)
        self.assertEqual((rows[0]['input_tokens'],rows[0]['output_tokens'],rows[0]['total_tokens']),(7,13,20))
        self.assertTrue(rows[0]['completed'])
        self.assertEqual(str(rows[0]['device_id']),self.device['deviceId'])

    def test_explicit_streaming_stays_sse_and_is_counted_once(self):
        with self.upstream():result = self.doctor(stream=True)
        self.assertEqual(result.status_code,200)
        self.assertIn('text/event-stream',result.headers['content-type'])
        self.assertIn('response.completed',result.text)
        self.assertEqual(self.query('SELECT total_tokens FROM codex_ops.model_requests'),[{'total_tokens':20}])

    def test_upstream_error_and_incomplete_transport_never_become_fake_success(self):
        with self.upstream('error'):result = self.doctor()
        self.assertEqual(result.status_code,400)
        self.assertEqual(result.json(),{'error':{'message':'fixture upstream rejection'}})
        with self.upstream('truncated'):result = self.doctor()
        self.assertEqual(result.status_code,502)
        rows=self.query('SELECT completed,total_tokens FROM codex_ops.model_requests')
        self.assertEqual(len(rows),2)
        self.assertTrue(all(not row['completed'] and row['total_tokens'] is None for row in rows))

    def test_retry_guidance_survives_json_and_streaming_entry_without_replay(self):
        for stream in (False,True):
            with self.upstream('busy'):result = self.doctor(stream=stream)
            self.assertEqual(result.status_code,429)
            self.assertEqual(result.headers['retry-after'],'2')
            self.assertEqual(result.headers['x-relay-limit-origin'],'local')
            self.assertEqual(result.json()['error']['code'],'relay_queue_timeout')
        rows=self.query('SELECT http_status,total_tokens FROM codex_ops.model_requests')
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row['http_status']==429 and row['total_tokens'] is None for row in rows))

    def test_named_key_create_rename_and_revoke_preserve_identity_and_history(self):
        self.assertTrue(self.device['apiKey'].startswith('sk-cpo-'))
        with self.upstream():self.doctor()
        before=self.query('SELECT device_id,user_id,key_hash FROM codex_ops.devices')[0]
        response=self.client.patch('/api/codex/devices/'+self.device['deviceId'],json={'deviceName':'  YE 新名称  '})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()['deviceName'],'YE 新名称')
        self.assertEqual(self.query('SELECT device_id,user_id,key_hash FROM codex_ops.devices')[0],before)
        with self.upstream():self.assertEqual(self.client.get('/api/codex/v1/models',headers=self.headers).status_code,200)
        self.assertEqual(self.client.delete('/api/codex/devices/'+self.device['deviceId']).status_code,200)
        self.assertEqual(self.client.get('/api/codex/v1/models',headers=self.headers).status_code,401)
        self.assertEqual(self.query('SELECT total_tokens FROM codex_ops.model_requests'),[{'total_tokens':20}])
        self.assertEqual(self.client.patch('/api/codex/devices/'+self.device['deviceId'],json={'deviceName':'late'}).status_code,404)

    def test_legacy_keys_work_and_plaintext_is_not_listed(self):
        original='legacy-device-key-'+'x'*40
        result=asyncio.run(relay.register_device(1,'Legacy Key','windows',key=original))
        self.assertEqual(result['apiKey'],original)
        with self.upstream():
            self.assertEqual(self.client.get('/api/codex/v1/models',headers={'Authorization':'Bearer '+original}).status_code,200)
            config=self.client.get('/api/codex/access-config',headers={'Host':'attacker.example'})
        self.assertEqual(config.json()['baseUrl'],'https://relay.example.test/api/codex/v1')
        self.assertEqual(config.json()['models'],['fixture-model'])
        overview=self.client.get('/api/codex/overview').text
        self.assertNotIn(original,overview);self.assertNotIn(self.device['apiKey'],overview)
        self.assertNotIn('fixture-upstream-private',config.text+overview)

    def test_super_admin_permissions_and_name_validation(self):
        for role in ['management','operator','ai','viewer']:
            self.app.dependency_overrides[require_session]=lambda role=role:('fixture',{'roleCode':role})
            self.assertEqual(self.client.get('/api/codex/access-config').status_code,403)
            self.assertEqual(self.client.patch('/api/codex/devices/'+self.device['deviceId'],json={'deviceName':'bad'}).status_code,403)
            self.assertEqual(self.client.post('/api/codex/devices',json={'userId':1,'deviceName':'forbidden','platform':'windows'}).status_code,403)
        self.app.dependency_overrides[require_session]=lambda:('fixture',{'roleCode':'super_admin','userId':1})
        for name in ['   ','a\nb','x'*81]:
            self.assertEqual(self.client.patch('/api/codex/devices/'+self.device['deviceId'],json={'deviceName':name}).status_code,422)
        self.assertEqual(self.client.patch('/api/codex/devices/'+self.device['deviceId'],json={'deviceName':'name','userId':2}).status_code,422)


if __name__=='__main__':unittest.main()
