import copy
import unittest
from app.services.full_funnel_visibility import filter_full_funnel

POLICIES = [
    dict(account_name='WHITIN', brand_name='Shared', access_scope='all_operators', allowed_groups=[], display_order=0, is_active=True),
    dict(account_name='BLOOMNEXT', brand_name='XM brand', access_scope='operator_groups', allowed_groups=['XM'], display_order=1, is_active=True),
    dict(account_name='JOOMRA DIRECT', brand_name='AJ brand', access_scope='operator_groups', allowed_groups=['AJ'], display_order=2, is_active=True),
]
LEDGER = {'spend': 99999, 'modules': [{'secret': 'cached-private'}], 'rows': [
    dict(account='WHITIN', date='2026-10-15', campaignId='c1', campaignName='shared-other-owner', operatorName='ZF', group='ZF1', spend=10, internalSecret='hidden'),
    dict(account='WHITIN', date='2026-10-15', campaignId='c1', campaignName='shared-pending', operatorName=None, spend=2),
    dict(account='WHITIN', date='2026-10-15', campaignId='c1', campaignName='other-group', operatorName='XH', group='XH1', spend=20),
    dict(account='BLOOMNEXT', campaignName='private-xm', operatorName='Alias', group='XM2', spend=30),
    dict(account='JOOMRA DIRECT', campaignName='private-aj', operatorName='Alias', group='AJ1', spend=40),
    dict(account='UNKNOWN', campaignName='private-unknown', operatorName='XM', group='XM1', spend=50),
]}


class FullFunnelVisibilityTests(unittest.TestCase):
    def test_role_and_group_matrix_uses_source_account(self):
        for role, code, expected, spend in [
            ('management', None, ['WHITIN','BLOOMNEXT','JOOMRA DIRECT','UNKNOWN'],152),
            ('super_admin', None, ['WHITIN','BLOOMNEXT','JOOMRA DIRECT','UNKNOWN'],152),
            ('operator','XM1',['BLOOMNEXT'],30),
            ('operator','XM2',['BLOOMNEXT'],30),
            ('operator','AJ1',['JOOMRA DIRECT'],40),
            ('operator','AJ2',['JOOMRA DIRECT'],40),
            ('operator','ZF1',['WHITIN'],12),
            ('operator','XH1',['WHITIN'],22),
            ('operator','YS1',[],0),
            ('operator',None,[],0), ('operator','XM-private',[],0),
            ('viewer','XM1',[],0), (None,'XM1',[],0),
        ]:
            with self.subTest(role=role, code=code):
                result = filter_full_funnel(LEDGER, POLICIES, role, code)
                self.assertEqual([m['account'] for m in result['modules']], expected)
                self.assertEqual(result['spend'], spend)
                self.assertEqual(result['unallocatedSpend'], 2 if role in ('management','super_admin') or code in ('ZF1','XH1') else 0)

    def test_does_not_mutate_cache_or_reuse_hidden_metadata(self):
        before = copy.deepcopy(LEDGER)
        result = filter_full_funnel(LEDGER, POLICIES, 'operator', 'AJ1')
        self.assertEqual(LEDGER, before)
        self.assertNotIn('private-xm', str(result))
        self.assertNotIn('private-unknown', str(result))
        self.assertNotIn('cached-private', str(result))
        self.assertNotIn('internalSecret', str(result))
        self.assertEqual(result['allocatedSpend'], 40)

    def test_inactive_policy_is_management_only(self):
        policies = copy.deepcopy(POLICIES)
        policies[1]['is_active'] = False
        self.assertEqual(len(filter_full_funnel(LEDGER, policies, 'operator','XM1')['modules']),0)
        self.assertEqual(len(filter_full_funnel(LEDGER, policies, 'management')['modules']),4)

    def test_empty_modules_and_credit_are_preserved(self):
        result = filter_full_funnel({'rows': []}, POLICIES, 'operator', 'XM1')
        self.assertEqual(result['modules'], [])
        self.assertTrue(all(m['rows'] == [] and m['spend'] == 0 for m in result['modules']))
        result = filter_full_funnel({'rows': [dict(account='WHITIN',operatorName='ZF',group='ZF1',spend=-2)]}, POLICIES, 'operator','ZF1')
        self.assertEqual(result['spend'],-2)
        self.assertEqual(result['allocatedSpend'],-2)

    def test_pending_requires_same_day_campaign_participation(self):
        ledger = copy.deepcopy(LEDGER)
        ledger['rows'].extend([
            dict(account='WHITIN',date='2026-10-15',campaignId='c2',spend=7),
            dict(account='WHITIN',date='2026-10-14',campaignId='c1',spend=3),
            dict(account='WHITIN',operatorName='ZF',group=None,spend=4),
        ])
        result = filter_full_funnel(ledger,POLICIES,'operator','ZF2')
        self.assertEqual(result['spend'],12)
        self.assertEqual(result['unallocatedSpend'],2)
        self.assertEqual(len(result['rows']),2)
        self.assertEqual(filter_full_funnel(ledger,POLICIES,'management')['spend'],166)

    def test_brand_permission_remains_an_upper_bound(self):
        ledger = {'rows':[dict(account='JOOMRA DIRECT',operatorName='XM',group='XM1',spend=9)]}
        self.assertEqual(filter_full_funnel(ledger,POLICIES,'operator','XM1')['rows'],[])
        self.assertEqual(filter_full_funnel(ledger,POLICIES,'operator','AJ1')['rows'],[])

if __name__ == '__main__':
    unittest.main()
