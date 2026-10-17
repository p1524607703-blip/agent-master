import copy
import unittest
from app.services.full_funnel_visibility import filter_full_funnel

POLICIES = [
    dict(account_name='WHITIN', brand_name='Shared', access_scope='all_operators', allowed_groups=[], display_order=0, is_active=True),
    dict(account_name='BLOOMNEXT', brand_name='XM brand', access_scope='operator_groups', allowed_groups=['XM'], display_order=1, is_active=True),
    dict(account_name='JOOMRA DIRECT', brand_name='AJ brand', access_scope='operator_groups', allowed_groups=['AJ'], display_order=2, is_active=True),
]
LEDGER = {'spend': 99999, 'modules': [{'secret': 'cached-private'}], 'rows': [
    dict(account='WHITIN', campaignName='shared-other-owner', operatorName='ZF', spend=10, internalSecret='hidden'),
    dict(account='WHITIN', campaignName='shared-pending', operatorName=None, spend=2),
    dict(account='BLOOMNEXT', campaignName='private-xm', operatorName='AJ', spend=30),
    dict(account='JOOMRA DIRECT', campaignName='private-aj', operatorName='XM', spend=40),
    dict(account='UNKNOWN', campaignName='private-unknown', operatorName='XM', spend=50),
]}


class FullFunnelVisibilityTests(unittest.TestCase):
    def test_role_and_group_matrix_uses_source_account(self):
        for role, code, expected, spend in [
            ('management', None, ['WHITIN','BLOOMNEXT','JOOMRA DIRECT','UNKNOWN'],132),
            ('super_admin', None, ['WHITIN','BLOOMNEXT','JOOMRA DIRECT','UNKNOWN'],132),
            ('operator','XM1',['WHITIN','BLOOMNEXT'],42),
            ('operator','XM2',['WHITIN','BLOOMNEXT'],42),
            ('operator','AJ1',['WHITIN','JOOMRA DIRECT'],52),
            ('operator','AJ2',['WHITIN','JOOMRA DIRECT'],52),
            ('operator','ZF1',['WHITIN'],12),
            ('operator','XH1',['WHITIN'],12),
            ('operator','YS1',['WHITIN'],12),
            ('operator',None,[],0), ('operator','XM-private',[],0),
            ('viewer','XM1',[],0), (None,'XM1',[],0),
        ]:
            with self.subTest(role=role, code=code):
                result = filter_full_funnel(LEDGER, POLICIES, role, code)
                self.assertEqual([m['account'] for m in result['modules']], expected)
                self.assertEqual(result['spend'], spend)
                self.assertEqual(result['unallocatedSpend'], 2 if expected else 0)

    def test_does_not_mutate_cache_or_reuse_hidden_metadata(self):
        before = copy.deepcopy(LEDGER)
        result = filter_full_funnel(LEDGER, POLICIES, 'operator', 'AJ1')
        self.assertEqual(LEDGER, before)
        self.assertNotIn('private-xm', str(result))
        self.assertNotIn('private-unknown', str(result))
        self.assertNotIn('cached-private', str(result))
        self.assertNotIn('internalSecret', str(result))
        self.assertEqual(result['allocatedSpend'], 50)

    def test_inactive_policy_is_management_only(self):
        policies = copy.deepcopy(POLICIES)
        policies[1]['is_active'] = False
        self.assertEqual(len(filter_full_funnel(LEDGER, policies, 'operator','XM1')['modules']),1)
        self.assertEqual(len(filter_full_funnel(LEDGER, policies, 'management')['modules']),4)

    def test_empty_modules_and_credit_are_preserved(self):
        result = filter_full_funnel({'rows': []}, POLICIES, 'operator', 'XM1')
        self.assertEqual(len(result['modules']),2)
        self.assertTrue(all(m['rows'] == [] and m['spend'] == 0 for m in result['modules']))
        result = filter_full_funnel({'rows': [dict(account='WHITIN',spend=-2)]}, POLICIES, 'operator','ZF1')
        self.assertEqual(result['spend'],-2)
        self.assertEqual(result['unallocatedSpend'],-2)

if __name__ == '__main__':
    unittest.main()
