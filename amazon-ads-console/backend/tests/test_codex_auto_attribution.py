import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from app.services.codex_auto_attribution import advance, atomic, reconcile, REPORTING_GUARD
from app.services.codex_attribution import account_attribution
from app.core.config import settings

class AutomaticTests(unittest.TestCase):
    def setUp(self):
        self.now=datetime.now(timezone.utc)-timedelta(minutes=40)
        self.reset=int(self.now.timestamp())+604000
        self.doc={'schemaVersion':1,'confirmations':[dict(confirmationId='manual-four',userId=17,deviceId='main',usedPercent=4,planType='prolite',resetsAt=self.reset,windowDurationMins=10080,confirmedAt=self.now.isoformat())]}
    def sample(self, used=4, seconds=0, main=10, child=0, **kwargs):
        at=(self.now+timedelta(seconds=seconds)).isoformat()
        sample={'window':dict(usedPercent=used,remainingPercent=100-used,resetsAt=self.reset,windowDurationMins=10080),'planType':'prolite','capturedAt':at,'startedAt':(self.now-timedelta(minutes=10)).isoformat(),'healthy':True,'userIds':[17,18],'sources':[
            dict(deviceId='main',userId=17,tokens=main*100,events=main,unknown=0,lastActivityAt=at if main else None),
            dict(deviceId='child',userId=18,tokens=child*100,events=child,unknown=0,lastActivityAt=at if child else None)]}
        sample.update(kwargs);return sample
    def test_bootstrap_is_inferred_and_audit_kept(self):
        doc=advance(self.doc,self.sample(5));entry=doc['automatic'][0]
        self.assertEqual((entry['userId'],entry['deviceId'],entry['usedPercent']),(17,'main',1))
        self.assertEqual(entry['method'],'observed-exclusive-period');self.assertFalse(entry['officialDeviceBilling'])
        self.assertEqual(self.doc['confirmations'][0]['usedPercent'],4)
    def test_increments_and_replay_idempotent(self):
        first=advance(self.doc,self.sample());sample=self.sample(5,120,11)
        second=advance(first,sample);self.assertEqual(len(second['automatic']),1)
        self.assertEqual(second,advance(second,sample))
        self.assertEqual(len(advance(second,self.sample(5,240,12))['automatic']),1)
    def test_mixed_is_explicitly_estimated_against_total_capacity(self):
        mixed=advance(self.doc,self.sample(5,child=1,main=100000))
        self.assertAlmostEqual(sum(row['usedPercent'] for row in mixed['automatic']),1)
        self.assertTrue(all(row['method']=='observed-token-weighted-interval' for row in mixed['automatic']))
        self.assertEqual(mixed['confirmations'],self.doc['confirmations'])
    def test_fractional_activity_carried_until_boundary(self):
        doc=advance(self.doc,self.sample());doc=advance(doc,self.sample(4,120,child=1))
        result=advance(doc,self.sample(5,240,main=11,child=1))
        self.assertEqual({row['deviceId']:row['usedPercent'] for row in result['automatic']},{'main':0.5,'child':0.5})
    def test_delayed_change_considers_overlap(self):
        doc=advance(self.doc,self.sample());doc=advance(doc,self.sample(5,120,11))
        sample=self.sample(6,240,11,1);sample['sources'][0]['lastActivityAt']=(self.now+timedelta(seconds=120)).isoformat()
        result=advance(doc,sample)
        self.assertEqual(result['automatic'][0]['usedPercent'],1)
        self.assertEqual(result['automatic'][-1]['method'],'observed-token-weighted-interval')
        self.assertTrue(result['automatic'][-1]['partialMeasurement'])
    def test_unknown_missing_owner_and_unhealthy(self):
        variants=[self.sample(5),self.sample(5,healthy=False),self.sample(5,main=0)]
        variants[0]['userIds']=[]
        for sample in variants:self.assertFalse(advance(self.doc,sample).get('automatic'))
    def test_unknown_token_quantity_keeps_known_device_identity(self):
        sample=self.sample(5);sample['sources'][0]['unknown']=3
        self.assertEqual(advance(self.doc,sample)['automatic'][0]['deviceId'],'main')
        sample['sources'][1]['unknown']=1
        self.assertFalse(advance(self.doc,sample).get('automatic'))
    def test_gap_and_counter_regression(self):
        first=advance(self.doc,self.sample())
        for sample in [self.sample(5,600,11),self.sample(5,120,9)]:self.assertFalse(advance(first,sample).get('automatic'))
    def test_failed_poll_taints_next_boundary(self):
        doc=advance(self.doc,self.sample(4,healthy=False))
        self.assertFalse(advance(doc,self.sample(5,120,11)).get('automatic'))
        doc=advance(self.doc,self.sample());doc=advance(doc,self.sample(4,120,healthy=False))
        self.assertFalse(advance(doc,self.sample(5,240,11)).get('automatic'))
    def test_downward_correction_freezes(self):
        doc=advance(self.doc,self.sample(5));doc=advance(doc,self.sample(4,120))
        self.assertEqual(doc['monitor']['status'],'reconciliation-required')
        self.assertEqual(len(advance(doc,self.sample(6,240,12))['automatic']),1)
    def test_new_window_does_not_reuse_old_amount(self):
        doc=advance(self.doc,self.sample(5));sample=self.sample(1,120,1);sample['window']['resetsAt']+=604800
        rows=advance(doc,sample)['automatic']
        self.assertEqual(sum(r['usedPercent'] for r in rows if r['resetsAt']==sample['window']['resetsAt']),1)
    def test_inflight_child_blocks_before_db_terminal(self):
        sample=self.sample(5);sample['sources'][1]['inFlight']=True
        self.assertFalse(advance(self.doc,sample).get('automatic'))
    def test_later_interval_preserves_prior_estimates_and_manual_history(self):
        doc=advance(self.doc,self.sample(5,child=1));prior=copy.deepcopy(doc['automatic'])
        for t in range(120,REPORTING_GUARD+241,120):
            sample=self.sample(5,t,main=10,child=1)
            for source in sample['sources']:source['lastActivityAt']=self.now.isoformat()
            doc=advance(doc,sample)
        sample=self.sample(6,REPORTING_GUARD+360,10,2);sample['sources'][0]['lastActivityAt']=self.now.isoformat()
        rows=advance(doc,sample)['automatic'];self.assertEqual(rows[-1]['deviceId'],'child')
        self.assertAlmostEqual(sum(r['usedPercent'] for r in rows),2)
        for before in prior:
            after=next(row for row in rows if row['confirmationId']==before['confirmationId'])
            self.assertEqual(after,before)
    def test_account_math_and_separate_evidence(self):
        doc=advance(self.doc,self.sample(5))
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'quota.json';atomic(path,doc);self.assertEqual(path.stat().st_mode & 0o777,0o600)
            with patch.object(settings,'codex_quota_attribution_file',str(path)):
                value=account_attribution(dict(status='available',planType='prolite',capturedAt=self.now.isoformat(),primary=self.sample(5)['window'],secondary=None),[17,18])
        self.assertEqual(value['ownerConfirmedPercent'],4);self.assertEqual(value['automaticPercent'],1)
        self.assertEqual(value['members'][0]['usedPercent'],5);self.assertEqual(value['deviceShares'][0]['usedPercent'],5)
        self.assertEqual(value['remainingPercent']+value['confirmedPercent']+value['unattributedPercent'],100)

    def test_second_scale_reset_jitter_never_bootstraps_a_new_period(self):
        doc=advance(self.doc,self.sample())
        sample=self.sample(5,120,11,1);sample['window']['resetsAt']-=1
        doc=advance(doc,sample)
        self.assertEqual(sum(row['usedPercent'] for row in doc['automatic']),1)
        sample=self.sample(5,240,12,2);sample['window']['resetsAt']+=1
        doc=advance(doc,sample)
        self.assertEqual(sum(row['usedPercent'] for row in doc['automatic']),1)
        self.assertEqual(doc['autoState']['window'][0],self.reset)

    def test_explicit_rejection_does_not_wait_forever_for_nonexistent_model_usage(self):
        doc=advance(self.doc,self.sample());sample=self.sample(5,120,11,0)
        sample['sources'][1].update(events=1,unknown=1,activityEvents=0,activityUnknown=0,recentActivity=True)
        doc=advance(doc,sample)
        self.assertEqual(doc['monitor']['pendingSettlementPercent'],0)
        self.assertEqual(doc['automatic'][0]['deviceId'],'main')
        self.assertEqual(doc['automatic'][0]['usedPercent'],1)

    def test_twenty_continuously_busy_devices_get_small_shares_of_account_capacity(self):
        first=self.sample();first['userIds']=list(range(1,21))
        first['sources']=[dict(deviceId=f'device-{n:02}',userId=n,tokens=0,events=0,unknown=0,lastActivityAt=None) for n in range(1,21)]
        doc=advance(self.doc,first)
        sample=copy.deepcopy(first);sample['window']['usedPercent']=5;sample['window']['remainingPercent']=95
        sample['capturedAt']=(self.now+timedelta(seconds=120)).isoformat()
        for source in sample['sources']:
            source.update(tokens=1000,events=1,inFlight=True,lastActivityAt=sample['capturedAt'])
        doc=advance(doc,sample)
        self.assertEqual(len(doc['automatic']),20)
        self.assertEqual({row['usedPercent'] for row in doc['automatic']},{0.05})
        self.assertTrue(all(row['partialMeasurement'] for row in doc['automatic']))
        self.assertEqual(doc['monitor']['pendingSettlementPercent'],0)

    def test_unequal_interval_weights_leave_confirmed_history_untouched(self):
        doc=advance(self.doc,self.sample())
        doc=advance(doc,self.sample(5,120,main=16,child=4))
        self.assertEqual({row['deviceId']:row['usedPercent'] for row in doc['automatic']},{'main':0.6,'child':0.4})
        self.assertEqual(doc['confirmations'],self.doc['confirmations'])
        self.assertEqual(doc['pendingAudit'][-1]['weights'],{'main':600,'child':400})

    def test_first_result_waits_then_automatically_settles_without_new_quota(self):
        doc=advance(self.doc,self.sample())
        sample=self.sample(5,120,main=11,child=0);sample['sources'][1]['inFlight']=True
        doc=advance(doc,sample)
        self.assertFalse(doc.get('automatic'));self.assertEqual(doc['monitor']['pendingSettlementPercent'],1)
        sample=self.sample(5,240,main=12,child=2)
        doc=advance(doc,sample)
        self.assertEqual({row['deviceId']:row['usedPercent'] for row in doc['automatic']},{'main':0.5,'child':0.5})
        self.assertEqual(doc['monitor']['pendingSettlementPercent'],0)

    def test_prior_weight_is_never_reused_in_next_interval(self):
        doc=advance(self.doc,self.sample())
        doc=advance(doc,self.sample(5,120,main=16,child=4))
        doc=advance(doc,self.sample(6,240,main=17,child=13))
        self.assertEqual({row['deviceId']:round(row['usedPercent'],6) for row in doc['automatic']},{'main':0.7,'child':1.3})
        self.assertEqual(doc['pendingAudit'][-1]['weights'],{'main':100,'child':900})

    def test_unknown_quantity_with_measured_work_is_explicit_low_confidence_estimate(self):
        doc=advance(self.doc,self.sample());sample=self.sample(5,120,11,1)
        sample['sources'][1]['unknown']=1
        doc=advance(doc,sample)
        self.assertTrue(all(row['partialMeasurement'] for row in doc['automatic']))
        self.assertEqual(doc['pendingAudit'][-1]['partialMeasurement'],True)

    def test_unregistered_owner_weight_leaves_only_its_share_unattributed(self):
        doc=advance(self.doc,self.sample());sample=self.sample(5,120,11,1);sample['userIds']=[17]
        doc=advance(doc,sample)
        self.assertEqual(len(doc['automatic']),1);self.assertEqual(doc['automatic'][0]['usedPercent'],0.5)

    def test_late_usage_enrichment_does_not_count_as_counter_regression(self):
        doc=advance(self.doc,self.sample());sample=self.sample(5,120,11,0)
        sample['sources'][1].update(events=1,unknown=1)
        doc=advance(doc,sample);self.assertEqual(doc['autoState']['pendingPoints'],1)
        sample=self.sample(5,240,11,1)
        doc=advance(doc,sample)
        self.assertEqual(sum(row['usedPercent'] for row in doc['automatic']),1)

    def test_rounding_has_no_lost_percentage_points(self):
        from decimal import Decimal
        from app.services.codex_auto_attribution import proportional_points
        result=proportional_points(Decimal(1),{'a':1,'b':1,'c':1})
        self.assertEqual(sum(result.values()),Decimal(1))
        self.assertEqual(result,{'a':Decimal('0.333334'),'b':Decimal('0.333333'),'c':Decimal('0.333333')})

    def test_busy_twenty_device_window_is_bounded_and_journalled_without_losing_history(self):
        from app.services.codex_auto_attribution import drain_audit
        first=self.sample();first['userIds']=list(range(1,21))
        first['sources']=[dict(deviceId=f'device-{n:02}',userId=n,tokens=0,events=0,unknown=0,lastActivityAt=None) for n in range(1,21)]
        doc=advance(self.doc,first)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'attribution.json'
            for tick in range(1,97):
                sample=copy.deepcopy(first);sample['window'].update(usedPercent=4+tick,remainingPercent=96-tick)
                sample['capturedAt']=(self.now+timedelta(seconds=120*tick)).isoformat()
                for row in sample['sources']:row.update(tokens=1000*tick,events=tick,inFlight=True)
                doc=advance(doc,sample);atomic(path,doc);drain_audit(path,doc)
            self.assertEqual(len(doc['automatic']),20)
            self.assertLess(path.stat().st_size,65536)
            self.assertAlmostEqual(sum(row['usedPercent'] for row in doc['automatic']),96)
            rows=[json.loads(line) for line in next(Path(tmp).glob('*.jsonl')).read_text().splitlines()]
            self.assertEqual(len({row['decisionId'] for row in rows}),96)
            self.assertEqual(sum(row['points'] for row in rows),96)
            self.assertEqual(next(Path(tmp).glob('*.jsonl')).stat().st_mode & 0o777,0o600)

    def test_journal_replay_does_not_allocate_quota_again(self):
        from app.services.codex_auto_attribution import drain_audit
        sample=self.sample(5);doc=advance(self.doc,sample);committed=copy.deepcopy(doc)
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'quota.json';atomic(path,doc);drain_audit(path,doc)
            drain_audit(path,committed) # Simulate crash after append before clearing outbox.
            self.assertEqual(doc['automatic'],committed['automatic'])
            rows=[json.loads(line) for line in next(Path(tmp).glob('*.jsonl')).read_text().splitlines()]
            self.assertEqual(len(rows),2);self.assertEqual(rows[0]['decisionId'],rows[1]['decisionId'])


class SamplingFailureTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sample_shape_decimal_tokens_and_active_marker_are_serializable(self):
        from decimal import Decimal
        from app.services import codex_auto_attribution as auto
        from app.services import codex_telemetry as telemetry
        now=datetime.now(timezone.utc).isoformat();reset=int(datetime.now(timezone.utc).timestamp())+604000
        quota=dict(status='available',planType='fixture',capturedAt=now,primary=dict(usedPercent=1,remainingPercent=99,resetsAt=reset,windowDurationMins=10080),secondary=None)
        host=dict(userId=17,deviceId='main',fresh=True,usageEvents=2,totalTokens=100,unknownSegments=0,lastActivityAt=now,capturedAt=now,resetsAt=reset,windowDurationMins=10080,planType='fixture')
        class Transaction:
            async def __aenter__(self): pass
            async def __aexit__(self,*args): pass
        class Connection:
            def transaction(self,**kwargs):return Transaction()
            async def fetch(self,sql,*args):
                if 'personnel_roster' in sql:return [dict(user_id=17),dict(user_id=18)]
                if 'SELECT r.request_id' in sql:return []
                return [dict(device_id='child',user_id=18,events=0,tokens=Decimal(0),unknown=0,last_activity_at=None)]
            async def close(self):pass
        with tempfile.TemporaryDirectory() as tmp, patch.object(settings,'codex_event_spool_dir',tmp):
            marker=telemetry.start_activity('fixture-request','child')
            with patch.object(auto,'snapshot',return_value=quota),patch.object(auto,'host_usage',return_value=host),patch.object(auto,'flush_events',new=AsyncMock()),patch.object(auto,'_connect',new=AsyncMock(return_value=Connection())):
                value=await auto.activity_sample()
                self.assertTrue(value['healthy']);self.assertTrue(value['sources'][1]['inFlight'])
                json.dumps(value)
                result=advance(dict(schemaVersion=1,confirmations=[]),value)
                self.assertFalse(result.get('automatic'))
                telemetry.finish_activity(marker)
                value=await auto.activity_sample()
                self.assertFalse(value['sources'][1]['inFlight']);self.assertTrue(value['sources'][1]['recentActivity'])

    async def test_pause_and_taint_are_persisted_without_private_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'quota.json';atomic(path,dict(schemaVersion=1,confirmations=[],autoState=dict(blocked=False)))
            with patch.object(settings,'codex_quota_attribution_file',str(path)),patch.object(settings,'codex_telemetry_enabled',True),patch('app.services.codex_auto_attribution.activity_sample',new=AsyncMock(side_effect=RuntimeError('private error'))):
                monitor=await reconcile()
            saved=json.loads(path.read_text());self.assertTrue(saved['autoState']['blocked'])
            self.assertEqual(monitor['status'],'paused');self.assertNotIn('private error',json.dumps(saved))

if __name__=='__main__':unittest.main()
