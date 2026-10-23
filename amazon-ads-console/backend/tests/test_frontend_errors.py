import json, os, tempfile, unittest, uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app
from app.api import auth
from app.core.config import settings
from app.services import frontend_errors as service
USERS={role:{'userId':str(i),'username':name,'roleCode':role,'operatorCode':'ZJ1' if role=='operator' else None} for i,(role,name) in enumerate([('operator','op_lzz'),('management','manager'),('super_admin','admin')],1)}
def payload(**extra):
 return {'event_id':str(uuid.uuid4()),'kind':'vue_error','error_code':'CACHE_LIFECYCLE_ERROR','exception_type':'TypeError',
         'page_path':'/my-cpo?token=secret#private','target_path':'/ad-allocation?password=secret','client_commit':'a'*40,
         'stack':[{'file':'https://private-host/assets/app.js?token=secret','line':42,'column':9}],**extra}
class FrontendErrorsTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'trace.jsonl'
  self.patches=[patch.object(settings,'operator_warmup_enabled',False),patch.object(auth,'resolve_session',AsyncMock(side_effect=lambda key:USERS.get(key))),
   patch.dict(os.environ,{'CPO_TRACE_LOG':str(self.path)}),patch('app.core.observability.logger.info'),
   patch('app.services.frontend_errors.release_metadata',return_value={'release':'new-server','commit':'b'*40}),
   patch('app.services.rds_query.subprocess.run',side_effect=AssertionError('No business data access'))]
  for p in self.patches:p.start()
  service._buckets.clear();service._seen.clear();self.client=TestClient(app);self.client.__enter__()
 def tearDown(self):
  self.client.__exit__(None,None,None)
  for p in reversed(self.patches):p.stop()
  self.temp.cleanup()
 def post(self,data=None,role='operator'):
  return self.client.post('/api/diagnostics/frontend-errors',headers={'Authorization':'Bearer '+role} if role else {},json=payload() if data is None else data)
 def read(self,query='',role='super_admin'):
  return self.client.get('/api/diagnostics/frontend-errors'+query,headers={'Authorization':'Bearer '+role})
 def test_durable_account_safe_fields_and_old_browser_version(self):
  value=payload(is_test=True);response=self.post(value);self.assertEqual(response.status_code,202)
  rows=self.read('?username=op_lzz&page_path=/my-cpo&client_commit=aaaa&kind=vue_error&user_id=1').json()['items']
  self.assertEqual(len(rows),1);row=rows[0]
  self.assertTrue(row['is_test']);self.assertEqual(row['username'],'op_lzz');self.assertEqual(row['user_id'],'1')
  self.assertEqual(row['client_commit'],'a'*40);self.assertEqual(row['commit'],'b'*40)
  self.assertEqual(row['page_path'],'/my-cpo');self.assertEqual(row['target_path'],'/ad-allocation')
  self.assertEqual(row['stack'],[{'file':'/assets/app.js','line':42,'column':9}])
  self.assertEqual(row['message'],'页面缓存切换异常');self.assertEqual(row['request_id'],response.headers['X-Request-ID'])
  self.assertNotIn('secret',self.path.read_text());self.assertNotIn('private-host',self.path.read_text())
  self.assertEqual(self.read('?client_commit=cccc').json()['items'],[])
  self.assertEqual(self.read('?username=manager').json()['items'],[])
 def test_submit_all_roles_read_super_admin_only(self):
  self.assertEqual(self.post(role=None).status_code,401)
  for role in USERS:self.assertEqual(self.post(role=role).status_code,202)
  for role in ('operator','management'):self.assertEqual(self.read(role=role).status_code,403)
  self.assertEqual(len(self.read().json()['items']),3)
 def test_reject_arbitrary_identity_messages_and_asset_paths(self):
  for extra in ({'username':'admin'},{'message':'password=secret'},{'client_commit':'secret'}, {'error_code':'anything'},
                {'stack':[{'file':'/api/auth/login?token=secret','line':1}]}, {'duration_ms':-1}):
   response=self.post(payload(**extra));self.assertEqual(response.status_code,400);self.assertNotIn('secret',response.text)
  self.assertNotIn('secret',self.path.read_text())
 def test_size_and_malformed_body(self):
  headers={'Authorization':'Bearer operator'}
  self.assertEqual(self.client.post('/api/diagnostics/frontend-errors',headers=headers,content=b'x'*16385).status_code,413)
  self.assertEqual(self.client.post('/api/diagnostics/frontend-errors',headers=headers,content=b'{').status_code,400)
 def test_duplicate_and_rate_limit(self):
  value=payload();self.assertEqual(self.post(value).status_code,202)
  self.assertTrue(self.post(value).json()['duplicate']);self.assertEqual(len(self.read().json()['items']),1)
  import time
  service._buckets['1'].extend([time.monotonic()]*60)
  response=self.post();self.assertEqual(response.status_code,429);self.assertEqual(response.headers['Retry-After'],'60')
 def test_storage_failure_does_not_claim_accepted(self):
  with patch.object(service,'emit_diagnostic',return_value=False):self.assertEqual(self.post().status_code,503)
 def test_navigation_and_existing_server_lookup(self):
  self.post(payload(kind='navigation_timeout',error_code='NAVIGATION_TIMEOUT',exception_type='NavigationTimeout',duration_ms=30001,stack=[]))
  row=self.read('?kind=navigation_timeout').json()['items'][0]
  self.assertEqual(row['duration_ms'],30001);self.assertEqual(row['target_path'],'/ad-allocation')
  server=self.client.get('/api/diagnostics/requests',headers={'Authorization':'Bearer super_admin'}).json()
  self.assertTrue(all(row['event']=='request_complete' for row in server['items']))
