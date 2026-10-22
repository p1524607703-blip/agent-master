import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from unittest.mock import AsyncMock

from app.services import codex_attribution as service

spec = importlib.util.spec_from_file_location('host_counter',Path(__file__).resolve().parents[2]/'scripts/collect_codex_host_usage.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name)/'confirmed.json'
        self.reset = int(datetime.now(timezone.utc).timestamp())+604000
        self.confirmation = {'confirmationId':'owner-confirmed-initial-3','confirmedAt':datetime.now(timezone.utc).isoformat(),
                             'userId':17,'usedPercent':3,'planType':'prolite','resetsAt':self.reset,'windowDurationMins':10080}
        self.write([self.confirmation])
        self.setting = patch.object(service.settings,'codex_quota_attribution_file',str(self.path))
        self.setting.start()

    def tearDown(self):
        self.setting.stop(); self.temp.cleanup()

    def write(self, confirmations):
        self.path.write_text(json.dumps({'schemaVersion':1,'confirmations':confirmations}));self.path.chmod(0o600)

    def quota(self, used=3, reset=None, plan='prolite'):
        return {'status':'available','planType':plan,'capturedAt':datetime.now(timezone.utc).isoformat(),
                'primary':{'usedPercent':used,'remainingPercent':100-used,'windowDurationMins':10080,'resetsAt':reset or self.reset},'secondary':None}

    def test_total_capacity_denominator_not_normalized_member_subtotal(self):
        result=service.account_attribution(self.quota(),[17,18,19])
        self.assertEqual([(r['userId'],r['usedPercent']) for r in result['members']],[(17,3),(18,0),(19,0)])
        self.assertEqual(result['confirmedPercent'],3)
        self.assertEqual(result['unattributedPercent'],0)
        self.assertEqual(result['remainingPercent'],97)

    def test_unconfirmed_increase_remains_unattributed_without_token_weighting(self):
        result=service.account_attribution(self.quota(5),[17,18])
        self.assertEqual(result['confirmedPercent'],3)
        self.assertEqual(result['unattributedPercent'],2)
        self.assertEqual(result['remainingPercent']+result['confirmedPercent']+result['unattributedPercent'],100)

    def test_new_window_or_plan_never_reuses_old_confirmation(self):
        for q in [self.quota(1,self.reset+604800),self.quota(1,plan='pro')]:
            result=service.account_attribution(q,[17,18])
            self.assertEqual(result['confirmedPercent'],0)
            self.assertEqual(result['unattributedPercent'],1)

    def test_downward_correction_requires_review_instead_of_negative_remainder(self):
        result=service.account_attribution(self.quota(2),[17,18])
        self.assertEqual(result['status'],'reconciliation-required')
        self.assertIsNone(result['unattributedPercent'])
        self.assertEqual(result['members'],[])

    def test_stale_quota_never_presents_confirmation_as_current(self):
        q=self.quota();q['status']='stale'
        result=service.account_attribution(q,[17])
        self.assertIsNone(result['confirmedPercent'])

    def test_duplicate_or_unknown_member_confirmations_fail_closed(self):
        for confirmations in [[self.confirmation,self.confirmation],[dict(self.confirmation,userId=999)]]:
            self.write(confirmations)
            self.assertEqual(service.account_attribution(self.quota(),[17])['status'],'invalid-configuration')

    def test_public_file_permissions_are_rejected(self):
        self.path.chmod(0o644)
        self.assertEqual(service.account_attribution(self.quota(),[17])['status'],'invalid-configuration')


def event(at, total, last):
    def counts(n):
        return {'input_tokens':n-2,'output_tokens':2,'total_tokens':n,'cached_input_tokens':0,'reasoning_output_tokens':0}
    return {'type':'event_msg','timestamp':at.isoformat(),'payload':{'type':'token_count',
        'info':{'total_token_usage':counts(total),'last_token_usage':counts(last)}}}


class LocalLogTests(unittest.TestCase):
    def test_uses_counter_differences_deduplicates_files_and_only_exports_counters(self):
        now=datetime.now(timezone.utc);start=now-timedelta(minutes=10)
        reset=int(start.timestamp())+604800
        meta={'type':'session_meta','payload':{'id':'fixture-session','timestamp':(start-timedelta(days=1)).isoformat()}}
        first=event(start-timedelta(seconds=1),100,100)
        second=event(start+timedelta(seconds=1),160,60)
        third=event(start+timedelta(seconds=2),200,40)
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);(home/'sessions').mkdir()
            lines=[meta,first,second,second,third,{'type':'response_item','payload':{'text':'private conversation must not export'}}]
            for name in ['one.jsonl','duplicate.jsonl']:
                (home/'sessions'/name).write_text(''.join(json.dumps(v)+'\n' for v in lines))
            quota={'status':'available','planType':'fixture','primary':{'resetsAt':reset,'windowDurationMins':10080},'secondary':None}
            with patch.object(host,'main_running',return_value=True):
                value=host.collect_host({'codexHome':tmp,'deviceId':'host-fixture','userId':17,'mainExecutable':'fixture'},quota)
            self.assertEqual(value['totalTokens'],100)
            self.assertEqual(value['usageEvents'],2)
            self.assertEqual(value['scannedSessions'],1)
            self.assertEqual(value['unknownSegments'],0)
            self.assertNotIn('private conversation',json.dumps(value))
            self.assertNotIn(tmp,json.dumps(value))

    def test_missing_baseline_and_counter_regression_are_not_invented_usage(self):
        now=datetime.now(timezone.utc);start=now-timedelta(minutes=10)
        def row(at,n):
            return (at,(n-2,2,n,0,0),(8,2,10,0,0))
        rows=[row(start+timedelta(seconds=1),1000),row(start+timedelta(seconds=2),1010),
              row(start+timedelta(seconds=3),10),row(start+timedelta(seconds=4),20)]
        totals,unknown,count=host.measured(rows,{'created':start-timedelta(days=1),'forked':False},start)
        self.assertEqual(totals['totalTokens'],20)
        self.assertEqual(unknown,2)
        self.assertEqual(count,2)

    def test_forked_session_does_not_charge_inherited_counter(self):
        now=datetime.now(timezone.utc)
        totals,unknown,count=host.measured([(now,(998,2,1000,0,0),(8,2,10,0,0))],{'created':now,'forked':True},now)
        self.assertEqual(totals['totalTokens'],0)
        self.assertEqual(unknown,1)


class OverviewTests(unittest.IsolatedAsyncioTestCase):
    async def test_host_is_added_without_an_api_key_and_old_tokens_do_not_allocate_quota(self):
        from app.services import codex_devices
        class Transaction:
            async def __aenter__(self):pass
            async def __aexit__(self,*args):pass
        class Connection:
            def transaction(self,**kwargs):return Transaction()
            async def fetchval(self,sql):return datetime.now(timezone.utc)
            async def fetch(self,sql,*args):
                if 'personnel_roster' in sql:
                    return [dict(user_id=17,display_name='Pan',username='pan',group_code='ai',group_name='AI',person_code='Pan',role_code='operator')]
                return []
            async def close(self):pass
        reset=int(datetime.now(timezone.utc).timestamp())+604000
        quota={'status':'available','planType':'fixture','primary':{'usedPercent':3,'remainingPercent':97,'windowDurationMins':10080,'resetsAt':reset},'secondary':None}
        host_value={'userId':17,'deviceId':'host','capturedAt':datetime.now(timezone.utc).isoformat(),
                    'fresh':True,'codexRunning':True,'resetsAt':reset,'windowDurationMins':10080,'planType':'fixture',
                    'totalTokens':1234,'todayTokens':1234,'inputTokens':1200,'outputTokens':34,'usageEvents':2,'unknownSegments':0}
        with patch.object(codex_devices,'_connect',new=AsyncMock(return_value=Connection())), patch.object(codex_devices,'quota_snapshot',return_value=quota), patch.object(codex_devices,'host_usage',return_value=host_value), patch.object(codex_devices.settings,'codex_telemetry_enabled',False), patch.object(service.settings,'codex_quota_attribution_file',None):
            result=await codex_devices.overview()
        device=result['members'][0]['devices'][0]
        self.assertEqual(device['sourceKind'],'local-host')
        self.assertEqual(device['currentWindowTokens'],1234)
        self.assertTrue(device['online'])
        self.assertNotIn('apiKey',device)
        self.assertEqual(result['accountAttribution']['unattributedPercent'],3)
        self.assertEqual(result['accountAttribution']['confirmedPercent'],0)


if __name__=='__main__':unittest.main()
