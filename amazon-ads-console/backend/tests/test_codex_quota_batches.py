import copy
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services import codex_quota_batches as service
from app.services.codex_attribution import account_attribution
from app.core.config import settings


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'batches.sqlite3'
        self.start = datetime.now(timezone.utc)-timedelta(hours=3)
        self.reset = int(self.start.timestamp())+604000
        self.document = {'schemaVersion':1,'confirmations':[],'automatic':[]}
        self.native = {'complete':True,'events':[]}

    def tearDown(self):
        self.temp.cleanup()

    def at(self, seconds):
        return (self.start+timedelta(seconds=seconds)).isoformat()

    def sample(self, used, seconds, quota_seconds=None, **overrides):
        value = {'window':{'usedPercent':used,'remainingPercent':100-used,'resetsAt':self.reset,'windowDurationMins':10080},
            'capturedAt':self.at(seconds if quota_seconds is None else quota_seconds),'observedAt':self.at(seconds),
            'startedAt':self.at(-800),'planType':'fixture','healthy':True,'userIds':list(range(1,21)),
            'sources':[{'deviceId':f'device-{n}','userId':n,'tokens':0,'events':0,'unknown':0} for n in range(1,21)],
            'activeRequests':[]}
        value.update(overrides)
        return value

    def tick(self, used, seconds, quota_seconds=None, **overrides):
        sample = self.sample(used,seconds,quota_seconds,**overrides)
        with service.database(self.path) as conn:
            result = service.advance(conn,self.document,sample,self.native)
        self.document['autoState']={'window':result['window']}
        self.document['batchSummary']=result
        return result

    def add(self, uid, tokens, start, end, observed, key=None, response=None):
        value = {'eventKey':key or f'event-{uid}-{start}','responseId':response,
            'source':f'device-{uid}','userId':uid,'startedAt':self.at(start),'endedAt':self.at(end),
            'totalTokens':tokens,'inputTokens':tokens,'outputTokens':0 if tokens is not None else None,
            'cachedTokens':0 if tokens is not None else None,'reasoningTokens':0 if tokens is not None else None,
            'timingComplete':True,'eligible':True,'model':'fixture-model'}
        with service.database(self.path) as conn:
            service.upsert_evidence(conn,value,service.timestamp(self.at(observed)))

    def shares(self, result):
        output = {}
        for row in result['allocations']:
            output[row['userId']]=output.get(row['userId'],0)+row['usedPercent']
        return output

    def test_late_measurement_revises_previous_estimate_without_new_quota_or_token_duplication(self):
        self.tick(0,0)
        self.add(1,100,10,30,80); self.add(2,300,20,50,80)
        first = self.tick(1,120)
        self.assertEqual(self.shares(first),{1:.25,2:.75})
        self.add(3,600,15,40,200)
        second = self.tick(1,240,120)
        self.assertEqual(self.shares(second),{1:.1,2:.3,3:.6})
        self.assertEqual(second['latestBatches'][0]['revision'],2)
        self.assertEqual(second['recalculationCount'],1)
        replay = self.tick(1,240,120)
        self.assertEqual(replay,second)
        with service.database(self.path) as conn:
            self.assertEqual(conn.execute('SELECT sum(tokens) FROM evidence').fetchone()[0],1000)
            self.assertEqual(conn.execute('SELECT count(*) FROM revisions').fetchone()[0],2)

    def test_unknown_source_waits_and_enrichment_returns_to_original_request_time(self):
        self.tick(0,0);self.add(1,100,10,20,80);self.add(2,None,15,25,80,key='late')
        result = self.tick(1,120)
        self.assertEqual(result['pendingBatchPercent'],1)
        self.assertEqual(result['allocations'],[])
        self.add(2,300,15,25,200,key='late')
        result = self.tick(1,240,120)
        self.assertEqual(self.shares(result),{1:.25,2:.75})
        self.assertEqual(result['pendingBatchPercent'],0)
        with service.database(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM evidence').fetchone()[0],2)

    def test_delayed_official_change_includes_prior_device_instead_of_only_current_device(self):
        self.tick(0,0);self.add(1,900,5,30,30);self.tick(0,60)
        self.add(2,100,90,100,100)
        result = self.tick(1,120)
        self.assertEqual(self.shares(result),{1:.9,2:.1})

    def test_continuous_twenty_sources_get_revisable_shares_without_waiting_for_idle(self):
        self.tick(0,0)
        for uid in range(1,21):self.add(uid,uid*100,10,30,30)
        active=[{'deviceId':f'device-{uid}','startedAt':self.at(40),'requestId':str(uid)} for uid in range(1,21)]
        first=self.tick(1,120,activeRequests=active)
        self.assertEqual(len(first['allocations']),20)
        self.assertEqual(first['pendingBatchPercent'],0)
        self.assertEqual(first['provisionalPercent'],1)
        for uid in range(1,21):self.add(uid,100,130,160,160)
        second=self.tick(2,240,activeRequests=active)
        self.assertAlmostEqual(sum(self.shares(second).values()),2)
        self.assertEqual(second['latestBatches'][-1]['revision'],2)
        with service.database(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(DISTINCT group_id) FROM batches').fetchone()[0],1)
            self.assertEqual(conn.execute('SELECT sum(tokens) FROM evidence').fetchone()[0],23000)

    def test_separate_batches_do_not_reuse_old_tokens_and_very_late_evidence_reopens_old_estimate(self):
        self.tick(0,0);self.add(1,100,10,30,30);self.tick(1,120)
        for n in range(240,2161,120):self.tick(1,n)
        self.add(2,300,2200,2220,2220)
        self.tick(2,2280)
        self.add(3,100,20,40,2300)
        result=self.tick(2,2400,2280)
        self.assertEqual(self.shares(result),{1:.5,2:1,3:.5})
        with service.database(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(DISTINCT group_id) FROM batches').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT count(*) FROM evidence WHERE group_id IS NOT NULL').fetchone()[0],3)

    def test_long_request_is_owned_once_and_marks_boundary_uncertainty(self):
        self.tick(0,0);self.add(1,100,10,20,30);self.tick(1,120)
        self.add(2,300,110,200,210)
        result=self.tick(1,240,120)
        self.assertEqual(self.shares(result),{1:.25,2:.75})
        self.assertEqual(result['latestBatches'][0]['confidence'],'low')

    def test_gap_points_remain_unattributed_and_future_healthy_points_can_estimate(self):
        self.tick(0,0);self.add(1,100,10,20,20)
        result=self.tick(1,600)
        self.assertEqual(result['pendingBatchPercent'],1)
        self.add(2,300,650,660,660)
        result=self.tick(2,720)
        self.assertEqual(self.shares(result),{2:1})
        self.assertEqual(result['pendingBatchPercent'],1)

    def test_native_coverage_failure_freezes_estimates_and_does_not_zero_missing_source(self):
        self.tick(0,0);self.add(1,100,10,20,30);first=self.tick(1,120)
        self.native['complete']=False
        self.add(2,300,15,25,180)
        result=self.tick(1,240)
        self.assertEqual(self.shares(result),self.shares(first))
        self.assertEqual(result['status'],'paused')
        self.native['complete']=True
        result=self.tick(1,300)
        self.assertEqual(self.shares(result),{1:.25,2:.75})

    def test_private_ledger_dedup_and_identity_binding(self):
        self.add(1,100,10,20,30,key='request-one',response='response-one')
        self.add(1,100,10,20,40,key='request-two',response='response-one')
        with self.assertRaises(ValueError):self.add(2,100,10,20,50,key='request-three',response='response-one')
        with service.database(self.path) as conn:self.assertEqual(conn.execute('SELECT count(*) FROM evidence').fetchone()[0],1)
        self.assertEqual(self.path.stat().st_mode & 0o777,0o600)

    def test_richer_gateway_timing_can_follow_sql_recovery_without_double_counting(self):
        self.tick(0,0)
        fallback=dict(eventKey='race',source='device-1',userId=1,startedAt=self.at(80),endedAt=self.at(80),
            totalTokens=100,inputTokens=100,outputTokens=0,timingComplete=False)
        with service.database(self.path) as conn:service.upsert_evidence(conn,fallback,service.timestamp(self.at(90)))
        self.tick(1,120)
        richer={**fallback,'startedAt':self.at(10),'timingComplete':True,'model':'fixture-model'}
        with service.database(self.path) as conn:service.upsert_evidence(conn,richer,service.timestamp(self.at(150)))
        result=self.tick(1,240,120)
        self.assertEqual(self.shares(result),{1:1})
        with service.database(self.path) as conn:
            self.assertEqual(conn.execute('SELECT sum(tokens) FROM evidence').fetchone()[0],100)
            self.assertEqual(conn.execute('SELECT sum(tokens) FROM group_sources').fetchone()[0],100)
            self.assertEqual(conn.execute('SELECT sum(incomplete_count) FROM group_sources').fetchone()[0],0)

    def test_roster_unknown_weight_is_pending_instead_of_renormalizing_other_members(self):
        self.tick(0,0);self.add(1,100,10,20,30);self.add(2,100,10,20,30)
        result=self.tick(1,120,userIds=[1])
        self.assertEqual(self.shares(result),{1:.5})
        self.assertEqual(result['pendingBatchPercent'],.5)

    def test_downward_correction_and_window_change_preserve_legacy_history(self):
        legacy={'confirmationId':'manual','userId':1,'deviceId':'device-1','usedPercent':4,
            'resetsAt':self.reset,'windowDurationMins':10080,'planType':'fixture','confirmedAt':self.at(0)}
        self.document['confirmations']=[legacy]
        original=copy.deepcopy(self.document['confirmations'])
        self.tick(4,0);self.add(2,100,10,20,30);self.tick(5,120)
        self.assertEqual(self.tick(4,240)['status'],'reconciliation-required')
        self.assertEqual(self.document['confirmations'],original)

    def test_period_jitter_is_stable_and_projection_has_exact_account_balance(self):
        self.tick(0,0)
        for uid in (1,2,3):self.add(uid,1,10,20,30)
        self.reset+=1
        result=self.tick(1,120)
        self.assertEqual(sum(row['usedPercent'] for row in result['allocations']),1)
        self.document['batchSummary']=result
        path=Path(self.temp.name)/'attribution.json';path.write_text(json.dumps(self.document));path.chmod(0o600)
        q=self.sample(1,120)
        quota={'status':'available','capturedAt':q['capturedAt'],'planType':'fixture','primary':q['window'],'secondary':None}
        with patch.object(settings,'codex_quota_attribution_file',str(path)):
            presented=account_attribution(quota,[1,2,3])
        self.assertEqual(presented['status'],'available')
        self.assertEqual(presented['provisionalPercent'],1)
        self.assertEqual(presented['confirmedPercent']+presented['unattributedPercent']+presented['remainingPercent'],100)

    def test_crash_before_json_projection_and_epoch_jitter_reuses_committed_cursor(self):
        self.tick(0,0);self.add(1,100,10,20,30);first=self.tick(1,120)
        self.document={'schemaVersion':1,'confirmations':[]}
        self.reset+=1
        result=self.tick(1,240)
        self.assertEqual(self.shares(first),self.shares(result))
        self.assertEqual(first['latestBatches'][0]['batchId'],result['latestBatches'][0]['batchId'])

    def test_many_batches_keep_json_projection_bounded_and_replay_safe(self):
        self.tick(0,0)
        for tick in range(1,41):
            for uid in range(1,21):self.add(uid,100,tick*120-20,tick*120-10,tick*120-5)
            result=self.tick(tick,tick*120)
        self.assertEqual(len(result['latestBatches']),12)
        self.assertAlmostEqual(sum(self.shares(result).values()),40)
        self.assertLess(len(json.dumps(self.document).encode()),65536)
        with service.database(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM batches').fetchone()[0],40)
            self.assertEqual(conn.execute('SELECT count(*) FROM evidence').fetchone()[0],800)
            self.assertEqual(conn.execute('SELECT count(*) FROM revisions').fetchone()[0],40)
            self.assertEqual(conn.execute('SELECT sum(tokens) FROM group_sources').fetchone()[0],80000)

    def test_persisted_revision_history_explains_before_after_without_changing_tokens(self):
        self.tick(0,0);self.add(1,100,10,20,30);first=self.tick(1,120)
        self.add(2,300,15,25,150);self.tick(1,240,120)
        with patch.object(service,'database_path',return_value=self.path):
            history=service.revisions(first['latestBatches'][0]['batchId'])
            with self.assertRaises(ValueError):service.revisions('../outside')
        self.assertEqual(history['revisions'][0]['revision'],2)
        self.assertEqual(history['revisions'][0]['before']['device-1']['micros'],1000000)
        self.assertEqual(history['revisions'][0]['after']['device-1']['micros'],250000)
        self.assertEqual(history['revisions'][0]['after']['device-2']['micros'],750000)

    def test_new_batch_has_no_fictional_before_amount_and_shares_one_group_audit_vector(self):
        self.tick(0,0);self.add(1,100,10,20,30);self.tick(1,120)
        result=self.tick(2,240)
        with patch.object(service,'database_path',return_value=self.path):
            history=service.revisions(result['latestBatches'][0]['batchId'])
        self.assertEqual(len(history['revisions']),1)
        self.assertEqual(history['revisions'][0]['before'],{})
        with service.database(self.path) as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM batches').fetchone()[0],2)
            self.assertEqual(conn.execute('SELECT count(*) FROM revisions').fetchone()[0],2)

    def test_request_started_before_upgrade_waits_then_recalculates_and_does_not_block_unrelated_later_groups(self):
        self.tick(0,0);self.add(1,100,10,20,30)
        active=[dict(deviceId='device-2',requestId='straddling',startedAt=self.at(-10))]
        first=self.tick(1,120,activeRequests=active)
        self.assertEqual(first['pendingBatchPercent'],1)
        self.add(2,300,-10,150,160)
        result=self.tick(1,240,120)
        self.assertEqual(self.shares(result),{1:.25,2:.75})


class HistoryEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_authorized_history_reconstructs_revisions_and_is_not_cached(self):
        import httpx
        from fastapi import FastAPI
        from app.api.codex_devices import router
        from app.api.auth import require_super_admin_session
        fixture=BatchTests();fixture.setUp()
        try:
            fixture.tick(0,0);fixture.add(1,100,10,20,30);result=fixture.tick(1,120)
            bid=result['latestBatches'][0]['batchId']
            fixture.add(2,300,15,25,150);fixture.tick(1,240,120)
            app=FastAPI();app.include_router(router,prefix='/api')
            app.dependency_overrides[require_super_admin_session]=lambda:('fixture',{'roleCode':'super_admin'})
            with patch.object(service,'database_path',return_value=fixture.path):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture.test') as client:
                    response=await client.get('/api/codex/quota-batches/'+bid+'/revisions')
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(response.headers['cache-control'],'no-store')
                    self.assertEqual(response.json()['revisions'][0]['after']['device-2']['micros'],750000)
                    self.assertEqual((await client.get('/api/codex/quota-batches/not-a-batch/revisions')).status_code,404)
        finally:fixture.tearDown()


if __name__=='__main__':unittest.main()
