import unittest
from app.services.cpo_identity import AdIdentityResolver, FullFunnelLedger
from app.services.operator_cpo import _campaign_prefix, _operator_full_funnel, _data_revision
from app.services import operator_cpo
from unittest.mock import patch


def meta(group,code):
    return {'group':group,'productCode':code,'operatorName':group[:2],'parentAsin':'B000000001','mappingStatus':'explicit'}


def row(name='XM2-S71女-DSP',day='2026-10-14',campaign='1',account='BLOOMNEXT',spend=10):
    return {'campaign_name':name,'stat_date':day,'campaign_id':campaign,'account_name':account,'spend':spend,'ad_orders':2,'ad_sales':50}


class IdentityTests(unittest.TestCase):
    def test_unicode_prefix_is_not_truncated(self):
        self.assertEqual(_campaign_prefix('XM2-S71女-DSP'),'XM2-S71女')
        self.assertEqual(_campaign_prefix('DSP_XH1-W81_Acquisition'),'XH1-W81')

    def test_unicode_identity_and_unique_product_without_group(self):
        r=AdIdentityResolver({('BLOOMNEXT','a'):meta('XM2','S71女')},[],[])
        self.assertEqual(r.resolve(row(), 'BLOOMNEXT')[0]['productCode'],'S71女')
        self.assertEqual(r.resolve(row('S71女-DSP-认知度'),'BLOOMNEXT')[0]['group'],'XM2')
        self.assertIsNone(r.resolve(row(),'WHITIN')[0])
        r.add('BLOOMNEXT',meta('XM1','S71女'))
        self.assertIsNone(r.resolve(row('S71女-DSP'),'BLOOMNEXT')[0])

    def test_confirmed_gender_alias_does_not_merge_versions(self):
        own=[{'operator_group':'XH1','product_code':'W81女','confirmation_source':'human','gender_segment':'女','owner_resolution':'parent_confirmation'}]
        r=AdIdentityResolver({('WHITIN','a'):meta('XH1','W81女'),('WHITIN','b'):meta('XH1','W81V2'),('WHITIN','c'):meta('XH1','W81K')},[],own)
        self.assertEqual(r.resolve(row('DSP_XH1-W81_RMK',account='WHITIN'),'WHITIN')[0]['productCode'],'W81女')
        self.assertEqual(r.resolve(row('XH1-W81V2-DSP',account='WHITIN'),'WHITIN')[0]['productCode'],'W81V2')
        r.confirmed_gender.clear()
        self.assertIsNone(r.resolve(row('XH1-W81-DSP'),'WHITIN')[0])

    def test_single_campaign_evidence_requires_same_day_and_period(self):
        r=AdIdentityResolver({},[],[]);m=meta('XM2','S71女')
        r.observe(row(), 'BLOOMNEXT',m)
        self.assertEqual(r.resolve(row('全流域广告活动'),'BLOOMNEXT')[0]['productCode'],'S71女')
        self.assertIsNone(r.resolve(row('全流域广告活动',day='2026-10-15'),'BLOOMNEXT')[0])
        r.observe(row(day='2026-10-15'),'BLOOMNEXT',meta('XM1','S73男'))
        self.assertIsNone(r.resolve(row('全流域广告活动'),'BLOOMNEXT')[0])

    def test_multiple_products_same_operator_remain_unallocated(self):
        r=AdIdentityResolver({},[],[])
        r.observe(row(), 'WHITIN',meta('ZJ1','W20'));r.observe(row(), 'WHITIN',meta('ZJ1','W30'))
        self.assertIsNone(r.resolve(row('全流域广告活动'),'WHITIN')[0])

    def test_mapping_change_invalidates_cache_without_a_new_fact_batch(self):
        with patch.object(operator_cpo,'query_one',side_effect=[{'revision':7},{'revision':'mapping-a'},{'revision':7},{'revision':'mapping-b'}]):
            self.assertNotEqual(_data_revision(),_data_revision())

    def test_full_funnel_credit_is_not_dropped(self):
        ledger=FullFunnelLedger();ledger.add(row(spend=-2),None)
        self.assertEqual(ledger.result()['unallocatedSpend'],-2)

    def test_full_funnel_ledger_preserves_allocated_and_pending_money(self):
        ledger=FullFunnelLedger();ledger.add(row(spend=12.34),meta('XM2','S71女'));ledger.add(row(campaign='2',spend=12.15),None)
        result=ledger.result()
        self.assertEqual(result['spend'],24.49)
        self.assertEqual(result['allocatedSpend'],12.34)
        self.assertEqual(result['unallocatedSpend'],12.15)
        private=_operator_full_funnel({'fullFunnel':result},'XM')
        self.assertEqual(private['spend'],12.34)
        self.assertEqual(len(private['rows']),1)
        self.assertTrue(all(r['operatorName']=='XM' for r in private['rows']))

if __name__=='__main__':unittest.main()
