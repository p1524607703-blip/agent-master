import unittest
from unittest.mock import patch
from app.services import operator_cpo as cpo


class SourceCompletenessTests(unittest.TestCase):
    def test_independent_sources_reveal_missing_report_without_changing_intersection(self):
        rows = []
        for day in ('2026-10-03', '2026-10-04'):
            rows += [{'source': 'businessChild', 'd': day, 'accounts': list(cpo.BUSINESS_ACCOUNTS)},
                     {'source': 'advertisedProduct', 'd': day, 'accounts': list(cpo.AD_ACCOUNTS)}]
        rows += [{'source': 'purchasedProduct', 'd': '2026-10-03', 'accounts': list(cpo.AD_ACCOUNTS)},
                 {'source': 'purchasedProduct', 'd': '2026-10-04', 'accounts': list(cpo.AD_ACCOUNTS)[:-1]}]
        with patch.object(cpo, '_complete_days', return_value=['2026-10-03']), patch.object(cpo, 'query_rows', return_value=rows) as query:
            result = cpo._source_days('2026-10-03', '2026-10-04', '582')
        self.assertEqual(result['businessDays'], 2)
        self.assertEqual(result['advertisedProductDays'], 2)
        self.assertEqual(result['purchasedProductDays'], 1)
        self.assertEqual(result['completeDates'], ['2026-10-03'])
        self.assertEqual(result['sourceMissingDates']['purchasedProduct'], ['2026-10-04'])
        self.assertEqual(result['missingAccountsByDate']['purchasedProduct']['2026-10-04'], [cpo.AD_ACCOUNTS[-1]])
        query.assert_called_once()

    def test_partial_child_and_parent_cannot_combine_into_complete_business_day(self):
        accounts = list(cpo.BUSINESS_ACCOUNTS)
        rows = [{'source': 'businessChild', 'd': '2026-10-04', 'accounts': accounts[:1]},
                {'source': 'businessParent', 'd': '2026-10-04', 'accounts': accounts[1:]}]
        with patch.object(cpo, '_complete_days', return_value=[]), patch.object(cpo, 'query_rows', return_value=rows):
            result = cpo._source_days('2026-10-04', '2026-10-04', '582')
        self.assertEqual(result['businessDays'], 0)
        self.assertEqual(result['sourceMissingDates']['business'], ['2026-10-04'])


class QualityReasonTests(unittest.TestCase):
    def test_complete_reports_explain_global_mapping_block_without_global_amounts(self):
        result = cpo._quality_reasons({'unmappedAd': {'spend': 9876.54}, 'businessUnmappedOrders': 8765},
                                     {'completeDays': 1}, 1, 'daily')
        self.assertEqual(len(result), 2)
        self.assertIn('公司级广告产品归属', result[0])
        self.assertIn('业务订单尚有未明确归属', result[1])
        self.assertNotIn('9876', str(result))
        self.assertNotIn('8765', str(result))
        self.assertEqual(cpo._quality_reasons({'unmappedAd': {'spend': 0}, 'businessUnmappedOrders': 0},
                                             {'completeDays': 1}, 1, 'daily'), [])

    def test_operator_specific_and_coverage_reasons_remain_distinct(self):
        result = cpo._quality_reasons({}, {'completeDays': 2}, 3, 'monthly',
                                     has_business=False, missing_products=2, unpaired_spend=20)
        self.assertEqual(len(result), 4)
        self.assertIn('2/3', result[0])
        self.assertIn('当前运营范围', result[1])
        self.assertIn('2 个本组', result[2])
        self.assertIn('本组部分广告花费', result[3])
        self.assertNotIn('20', str(result))


if __name__ == '__main__':
    unittest.main()
