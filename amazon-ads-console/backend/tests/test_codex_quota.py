import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.services import codex_quota

spec = importlib.util.spec_from_file_location('quota_collector',Path(__file__).resolve().parents[2]/'scripts/collect_codex_quota.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)


class QuotaTests(unittest.TestCase):
    def fixture(self, age=0):
        return {'schemaVersion':1,'status':'available',
            'capturedAt':(datetime.now(timezone.utc)-timedelta(seconds=age)).isoformat(),
            'primary':{'usedPercent':76,'windowDurationMins':300,'resetsAt':1900000000},
            'secondary':{'usedPercent':59,'windowDurationMins':10080,'resetsAt':1900000000},
            'planType':'fixture','accountTotalTokens':999999,'access_token':'must-not-leak'}

    def read(self, value, mode=0o600):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'quota.json';path.write_text(json.dumps(value));path.chmod(mode)
            with patch.object(codex_quota.settings,'codex_quota_snapshot_file',str(path)):
                return codex_quota.snapshot()

    def test_official_remaining_does_not_use_device_subtotal_or_unverified_global_total(self):
        value=self.read(self.fixture())
        self.assertEqual(value['primary']['remainingPercent'],24)
        self.assertEqual(value['secondary']['remainingPercent'],41)
        self.assertIsNone(value['accountTotalTokens'])
        self.assertEqual(value['tokenTotalScope'],'unverified')
        self.assertNotIn('access_token',value)

    def test_expired_or_failed_snapshot_does_not_keep_percentages_fresh(self):
        for data in [self.fixture(301),dict(self.fixture(),status='unavailable')]:
            value=self.read(data)
            self.assertNotEqual(value['status'],'available')
            self.assertIsNone(value['primary'])

    def test_pro_weekly_primary_without_secondary_is_available(self):
        data=self.fixture();data['primary']=data['secondary'];data['secondary']=None
        data['planType']='prolite'
        identity='fixture-account';digest=hashlib.sha256(identity.encode()).hexdigest()
        sanitized=collector.sanitize({'accountId':identity,'rateLimitsByLimitId':{'codex':data}},digest)
        value=self.read(sanitized)
        self.assertEqual(value['status'],'available')
        self.assertEqual(value['planType'],'prolite')
        self.assertEqual(value['primary']['windowDurationMins'],10080)
        self.assertEqual(value['primary']['remainingPercent'],41)
        self.assertIsNone(value['secondary'])

    def test_no_windows_cannot_be_inferred_as_unlimited(self):
        data=dict(self.fixture(),primary=None,secondary=None)
        self.assertEqual(self.read(data)['status'],'unavailable')
        with self.assertRaises(ValueError):
            collector.sanitize({'accountId':'fixture-account','rateLimits':data},hashlib.sha256(b'fixture-account').hexdigest())

    def test_world_readable_or_invalid_counters_are_rejected(self):
        self.assertEqual(self.read(self.fixture(),0o644)['status'],'unavailable')
        data=self.fixture();data['primary']['usedPercent']=101
        self.assertEqual(self.read(data)['status'],'unavailable')

    def test_notification_health_metadata_is_whitelisted(self):
        data = self.fixture()
        data['collection'] = {'mode':'notifications-first','fallbackSeconds':60,
            'publishSeconds':30,'readerConnected':True,'deviceNotificationsConnected':False,
            'reads':2,'usageEvents':20,'access_token':'never-export'}
        value = self.read(data)['collection']
        self.assertEqual(value['fallbackSeconds'],60)
        self.assertFalse(value['deviceNotificationsConnected'])
        self.assertNotIn('access_token',value)

    def test_collector_strips_private_fields_and_checks_source_identity(self):
        identity='fixture-account';digest=hashlib.sha256(identity.encode()).hexdigest()
        limits=self.fixture()
        value=collector.sanitize({'accountId':identity,'rateLimits':limits,'access_token':'never-transfer'},digest)
        self.assertEqual(set(value),{'schemaVersion','status','capturedAt','primary','secondary','planType'})
        with self.assertRaises(ValueError):
            collector.sanitize({'accountId':'different','rateLimits':limits},digest)


class QuotaEndpointTests(unittest.IsolatedAsyncioTestCase):
    async def test_anonymous_and_operator_cannot_read_account_quota(self):
        import httpx
        from unittest.mock import AsyncMock
        from app.main import app
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture.test') as client:
            response=await client.get('/api/codex/account-quota')
            self.assertEqual(response.status_code,401)
            with patch('app.api.auth.resolve_session',new=AsyncMock(return_value={'userId':1,'username':'fixture','roleCode':'operator','operatorCode':'ZJ1'})):
                response=await client.get('/api/codex/account-quota',headers={'Authorization':'Bearer fixture-session'})
                self.assertEqual(response.status_code,403)


if __name__=='__main__':
    unittest.main()
