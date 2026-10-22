import unittest
from unittest.mock import patch

from app.services import operator_cpo


class WhitinAccountScopeTests(unittest.TestCase):
    def test_whitin_is_a_direct_ad_account(self):
        self.assertEqual(operator_cpo.DIRECT_AD_TO_BUSINESS["WHITIN"], "WHITIN")
        self.assertIn("WHITIN", operator_cpo.AD_ACCOUNTS)
        self.assertEqual(len(operator_cpo.AD_ACCOUNTS), 4)

    def test_amazon_dsp_is_classified_explicitly(self):
        self.assertIn("DSP", operator_cpo.AD_TYPES)
        self.assertEqual(operator_cpo._classify_ad_type("Amazon DSP"), "DSP")
        self.assertEqual(operator_cpo._classify_ad_type("DSP"), "DSP")

    def test_complete_days_requires_all_ad_accounts(self):
        captured = {}

        def fake_query(sql):
            captured["sql"] = sql
            return []

        with patch.object(operator_cpo, "query_rows", side_effect=fake_query):
            self.assertEqual(operator_cpo._complete_days(revision="test"), [])

        sql = captured["sql"]
        self.assertIn("WHITIN", sql)
        self.assertEqual(sql.count('FROM core.report_advertised_product_daily r JOIN'), len(operator_cpo.AD_ACCOUNTS))
        self.assertEqual(sql.count('FROM core.report_purchased_product_daily r JOIN'), len(operator_cpo.AD_ACCOUNTS))
        for account in operator_cpo.AD_ACCOUNTS:
            self.assertGreaterEqual(sql.count(f"r.account_name='{account}'"), 2)


if __name__ == "__main__":
    unittest.main()
