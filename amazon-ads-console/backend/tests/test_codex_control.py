import asyncio
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from fastapi import HTTPException
from app.core.config import settings
from app.services import codex_control as control
from app.api.auth import require_session
from tests import test_codex_compat as compat

A, B, C = [str(uuid.UUID(int=i)) for i in (1,2,3)]


class AdmissionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='cpo-control-')
        self.addCleanup(self.temp.cleanup)
        self.config=patch.object(settings,'codex_event_spool_dir',self.temp.name)
        self.config.start();self.addCleanup(self.config.stop)

    def update(self,**values):
        policy,_=control.snapshot()
        return control.update(revision=policy['revision'],actor=1,**values)

    async def queued(self,device):
        for _ in range(100):
            _,counts=control.snapshot()
            if counts.get(device,{}).get('queuedRequests')==1:return
            await asyncio.sleep(.005)
        self.fail('Request did not queue')

    async def test_global_limit_is_atomic_across_overlapping_requests(self):
        self.update(max_concurrent=2)
        peak=0
        async def request(device):
            nonlocal peak
            lease=await control.acquire(device)
            try:
                _,counts=control.snapshot()
                peak=max(peak,sum(c['activeRequests'] for c in counts.values()))
                await asyncio.sleep(.02)
            finally:lease.close()
        await asyncio.gather(*(request([A,B,C][i%3]) for i in range(8)))
        self.assertEqual(peak,2)
        self.assertEqual(control.snapshot()[1],{})

    async def test_unlimited_really_allows_more_than_six_requests(self):
        self.update(max_concurrent=None)
        leases=await asyncio.gather(*(control.acquire(A) for _ in range(10)))
        self.assertEqual(control.snapshot()[1][A]['activeRequests'],10)
        for lease in leases:lease.close()

    async def test_device_limit_does_not_block_other_devices_and_pause_cancels_queue(self):
        self.update(max_concurrent=None)
        self.update(device_ids=[A],device_limit=True,max_concurrent=1)
        first=await control.acquire(A)
        waiting=asyncio.create_task(control.acquire(A));await self.queued(A)
        other=await asyncio.wait_for(control.acquire(B),1)
        self.update(device_ids=[A],enabled=False)
        with self.assertRaises(HTTPException) as raised:await waiting
        self.assertEqual(raised.exception.status_code,403)
        self.assertEqual(control.snapshot()[1][A],{'activeRequests':1,'queuedRequests':0})
        first.close();other.close()
        self.update(device_ids=[A],enabled=True)
        resumed=await control.acquire(A);resumed.close()

    async def test_lowering_limit_keeps_running_tasks_and_delays_new_tasks(self):
        self.update(max_concurrent=2)
        a,b=await control.acquire(A),await control.acquire(B)
        self.update(max_concurrent=1)
        task=asyncio.create_task(control.acquire(C));await self.queued(C)
        a.close();await asyncio.sleep(.12);self.assertFalse(task.done())
        b.close();c=await asyncio.wait_for(task,1);c.close()

    async def test_cancelling_a_waiter_frees_its_queue_entry(self):
        self.update(max_concurrent=1)
        first=await control.acquire(A)
        waiting=asyncio.create_task(control.acquire(B));await self.queued(B)
        waiting.cancel()
        with self.assertRaises(asyncio.CancelledError):await waiting
        self.assertNotIn(B,control.snapshot()[1])
        first.close();third=await control.acquire(C);third.close()

    async def test_queue_timeout_and_overflow_never_hold_a_model_slot(self):
        self.update(max_concurrent=1)
        first=await control.acquire(A)
        with patch.object(control,'QUEUE_SECONDS',.02):
            with self.assertRaises(HTTPException) as raised:await control.acquire(B)
        self.assertEqual(raised.exception.status_code,429)
        self.assertEqual(raised.exception.headers['Retry-After'],'2')
        self.assertNotIn(B,control.snapshot()[1])
        with patch.object(control,'QUEUE_LIMIT',0):
            with self.assertRaises(HTTPException):await control.acquire(C)
        self.assertNotIn(C,control.snapshot()[1]);first.close()

    async def test_crashed_process_cannot_leave_a_slot_occupied(self):
        self.update(max_concurrent=1)
        code="from app.core.config import settings;from app.services.codex_control import *;import sys;settings.codex_event_spool_dir=sys.argv[1];lease=asyncio.run(acquire(sys.argv[2]));print('ready',flush=True);sys.stdin.read()"
        child=subprocess.Popen([sys.executable,'-c',code,self.temp.name,A],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        try:
            self.assertTrue(select.select([child.stdout],[],[],5)[0]);self.assertEqual(child.stdout.readline().strip(),'ready')
            self.assertEqual(control.snapshot()[1][A]['activeRequests'],1)
            child.kill();child.wait(5)
            recovered=await asyncio.wait_for(control.acquire(B),1)
            self.assertNotIn(A,control.snapshot()[1]);recovered.close()
        finally:
            if child.poll() is None:child.kill();child.wait(5)
            child.stdin.close();child.stdout.close()

    def test_settings_are_private_persistent_and_stale_edits_are_rejected(self):
        value=self.update(device_ids=[A],enabled=False)
        policy=control.read_policy(control.directory())
        self.assertEqual(policy,value)
        self.assertFalse(control.device_policy(policy,A)['enabled'])
        self.assertEqual((control.directory()/'policy.json').stat().st_mode&0o777,0o600)
        with self.assertRaises(HTTPException) as raised:control.update(revision=0,actor=2,max_concurrent=None)
        self.assertEqual(raised.exception.status_code,409)
        self.assertEqual(control.snapshot()[0],value)


@unittest.skipUnless(os.environ.get('CODEX_ISOLATED_DB_TEST')=='1','requires disposable PostgreSQL')
class ControlApiTests(unittest.TestCase):
    query=compat.CompatibilityAndAccessTests.query
    upstream=compat.CompatibilityAndAccessTests.upstream
    doctor=compat.CompatibilityAndAccessTests.doctor

    def setUp(self):
        compat.CompatibilityAndAccessTests.setUp(self)
        self.app.dependency_overrides[require_session]=lambda:('fixture',{'roleCode':'super_admin','userId':1})
        self.other=self.client.post('/api/codex/devices',json={'userId':1,'deviceName':'XT Fixture','platform':'windows'}).json()

    def state(self):return self.client.get('/api/codex/access-control').json()
    def change(self,device,**values):
        return self.client.patch('/api/codex/devices/'+device['deviceId']+'/control',json={'revision':self.state()['revision'],**values})
    def bulk(self,scope,enabled,ids=None):
        return self.client.post('/api/codex/devices/status',json={'revision':self.state()['revision'],'scope':scope,'enabled':enabled,'deviceIds':ids or []})

    def test_disable_and_resume_use_the_same_key_and_preserve_history(self):
        with self.upstream():self.assertEqual(self.doctor().status_code,200)
        before=self.query('SELECT device_id,key_hash,user_id FROM codex_ops.devices ORDER BY device_id')
        self.assertEqual(self.change(self.device,enabled=False).status_code,200)
        with self.upstream():
            self.assertEqual(self.doctor().status_code,403)
            self.assertEqual(self.client.get('/api/codex/v1/models',headers=self.headers).status_code,403)
        self.assertEqual(self.change(self.device,enabled=True).status_code,200)
        with self.upstream():self.assertEqual(self.client.get('/api/codex/v1/models',headers=self.headers).status_code,200)
        self.assertEqual(self.query('SELECT device_id,key_hash,user_id FROM codex_ops.devices ORDER BY device_id'),before)
        self.assertEqual(self.query('SELECT total_tokens FROM codex_ops.model_requests'),[{'total_tokens':20}])

    def test_bulk_selection_all_and_revoked_keys(self):
        result=self.bulk('selected',False,[self.device['deviceId']]);self.assertEqual(result.status_code,200)
        by_id={r['deviceId']:r for r in self.state()['devices']}
        self.assertFalse(by_id[self.device['deviceId']]['enabled']);self.assertTrue(by_id[self.other['deviceId']]['enabled'])
        self.assertEqual(self.bulk('all',False).status_code,200)
        self.assertTrue(all(not r['enabled'] for r in self.state()['devices']))
        self.client.delete('/api/codex/devices/'+self.other['deviceId'])
        self.assertEqual(self.bulk('all',True).status_code,200)
        self.assertEqual(self.client.get('/api/codex/v1/models',headers={'Authorization':'Bearer '+self.other['apiKey']}).status_code,401)
        self.assertEqual(self.change(self.other,enabled=True).status_code,404)

    def test_bulk_rejects_invalid_selection_atomically(self):
        revision=self.state()['revision']
        response=self.bulk('selected',False,[self.device['deviceId'],str(uuid.uuid4())])
        self.assertEqual(response.status_code,404)
        self.assertEqual(self.state()['revision'],revision)
        self.assertTrue(all(r['enabled'] for r in self.state()['devices']))

    def test_total_and_device_limits_and_stale_edits(self):
        state=self.state();self.assertEqual(state['globalMaxConcurrent'],6)
        result=self.client.patch('/api/codex/access-control',json={'revision':state['revision'],'maxConcurrent':None})
        self.assertEqual(result.status_code,200);self.assertIsNone(result.json()['globalMaxConcurrent'])
        result=self.client.patch('/api/codex/access-control',json={'revision':state['revision'],'maxConcurrent':1})
        self.assertEqual(result.status_code,409)
        result=self.change(self.device,maxConcurrent=1);self.assertEqual(result.status_code,200)
        self.assertEqual(next(d for d in result.json()['devices'] if d['deviceId']==self.device['deviceId'])['maxConcurrent'],1)
        self.assertEqual(self.change(self.device,maxConcurrent=None).status_code,200)
        self.assertNotIn(self.device['apiKey'],self.client.get('/api/codex/access-control').text)

    def test_only_super_admin_can_change_controls(self):
        for role in ('management','operator','ai','viewer'):
            self.app.dependency_overrides[require_session]=lambda role=role:('fixture',{'roleCode':role,'userId':1})
            self.assertEqual(self.client.get('/api/codex/access-control').status_code,403)
            self.assertEqual(self.client.patch('/api/codex/access-control',json={'revision':0,'maxConcurrent':1}).status_code,403)
            self.assertEqual(self.client.post('/api/codex/devices/status',json={'revision':0,'scope':'all','enabled':False}).status_code,403)
            self.assertEqual(self.client.patch('/api/codex/devices/'+self.device['deviceId']+'/control',json={'revision':0,'enabled':False}).status_code,403)
        self.app.dependency_overrides[require_session]=lambda:('fixture',{'roleCode':'super_admin','userId':1})
        self.assertEqual(self.client.patch('/api/codex/access-control',json={'revision':0,'maxConcurrent':2}).status_code,200)

    def test_invalid_limits_states_and_scopes_are_rejected(self):
        for value in (True,0,-1,1.5,'2',100001):
            self.assertEqual(self.client.patch('/api/codex/access-control',json={'revision':0,'maxConcurrent':value}).status_code,422)
            self.assertEqual(self.change(self.device,maxConcurrent=value).status_code,422)
        self.assertEqual(self.change(self.device,enabled=None).status_code,422)
        self.assertEqual(self.bulk('selected',False).status_code,422)
        self.assertEqual(self.bulk('all',False,[self.device['deviceId']]).status_code,422)
        self.assertEqual(self.state()['revision'],0)

    def test_source_failures_release_slots_and_corrupt_policy_fails_closed(self):
        with self.upstream('error'):self.assertEqual(self.doctor(stream=True).status_code,400)
        self.assertEqual(self.state()['activeRequests'],0)
        self.change(self.device,enabled=False)
        (control.directory()/'policy.json').write_text('corrupt')
        self.assertEqual(self.client.get('/api/codex/v1/models',headers=self.headers).status_code,503)
        self.assertEqual(self.client.get('/api/codex/access-control').status_code,503)


if __name__=='__main__':unittest.main()
