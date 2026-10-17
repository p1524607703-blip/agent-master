import copy
import unittest

from app.services.cpo_identity import CampaignOwnerRules


class CampaignOwnerTests(unittest.TestCase):
    def setUp(self):
        self.target = {'group': 'AA1', 'productCode': 'P100', 'parentAsin': 'B000000001'}
        self.source = {'group': 'AA1', 'productCode': 'P200', 'parentAsin': 'B000000002'}
        self.rule = {
            'rule_id': 1, 'active': True, 'account_name': 'seller-a', 'campaign_id': '123',
            'ad_product': 'Sponsored Brands', 'expected_campaign_name': 'AA1-P100 collection',
            'allocation_mode': 'campaign_owner', 'business_account': 'seller-a',
            'operator_group': 'AA1', 'product_code': 'P100', 'parent_asin': 'B000000001',
            'allowed_source_products': ['P100', 'P200'], 'valid_from': '2026-10-09', 'valid_to': '2026-10-31',
        }
        self.row = {'stat_date': '2026-10-14', 'account_name': 'seller-a', 'campaign_id': '123',
                    'ad_product': 'Sponsored Brands', 'campaign_name': 'AA1-P100 collection'}
        self.candidates = {'seller-a': {('AA1', 'P100'): self.target}}
        self.parents = {'B000000001': self.target}

    def engine(self, rules=None):
        return CampaignOwnerRules(rules if rules is not None else [self.rule], self.candidates, self.parents)

    def test_confirmed_budget_owner_precedes_other_valid_product_identity(self):
        old_source = copy.deepcopy(self.source)
        target, method, rule = self.engine().resolve(self.row, 'seller-a', self.source)
        self.assertEqual(target['productCode'], 'P100')
        self.assertEqual(method, 'campaign_owner_confirmed')
        self.assertEqual(rule['rule_id'], 1)
        self.assertEqual(self.source, old_source)
        self.assertEqual(self.source['parentAsin'], 'B000000002')

    def test_account_campaign_and_ad_product_are_exact_boundaries(self):
        for key, value in [('account_name', 'seller-b'), ('campaign_id', '124'), ('ad_product', 'Sponsored Products')]:
            with self.subTest(key=key):
                row = {**self.row, key: value}
                self.assertEqual(self.engine().resolve(row, 'seller-a', self.source), (None, '', None))

    def test_effective_dates_and_disabled_rules(self):
        for day in ['2026-10-08', '2026-11-01']:
            self.assertEqual(self.engine().resolve({**self.row, 'stat_date': day}, 'seller-a', self.source), (None, '', None))
        for day in ['2026-10-09', '2026-10-31']:
            self.assertIsNotNone(self.engine().resolve({**self.row, 'stat_date': day}, 'seller-a', self.source)[0])
        self.rule['active'] = False
        self.assertEqual(self.engine().resolve(self.row, 'seller-a', self.source), (None, '', None))

    def test_changed_creative_pool_name_scope_or_operator_requires_review(self):
        cases = [({**self.row, 'campaign_name': 'renamed'}, 'seller-a', self.source),
                 (self.row, 'seller-b', self.source),
                 (self.row, 'seller-a', {**self.source, 'productCode': 'P300'}),
                 (self.row, 'seller-a', {**self.source, 'group': 'BB1'}),
                 (self.row, 'seller-a', None)]
        for row, scope, source in cases:
            target, method, matched_rule = self.engine().resolve(row, scope, source)
            self.assertIsNone(target)
            self.assertEqual(method, 'campaign_owner_rule_needs_review')
            self.assertIsNotNone(matched_rule)

    def test_overlapping_rules_fail_closed(self):
        target, method, matched_rule = self.engine([self.rule, {**self.rule, 'rule_id': 2}]).resolve(self.row, 'seller-a', self.source)
        self.assertIsNone(target)
        self.assertEqual(method, 'campaign_owner_rule_conflict')
        self.assertIsNotNone(matched_rule)

    def test_target_must_remain_confirmed_in_account_and_parent_mapping(self):
        self.parents['B000000001'] = {**self.target, 'group': 'BB1'}
        self.assertIsNone(self.engine().resolve(self.row, 'seller-a', self.source)[0])
        self.parents['B000000001'] = self.target
        self.candidates.clear()
        self.assertIsNone(self.engine().resolve(self.row, 'seller-a', self.source)[0])


if __name__ == '__main__':
    unittest.main()
