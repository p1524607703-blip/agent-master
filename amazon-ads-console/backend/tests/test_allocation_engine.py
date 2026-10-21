"""Synthetic acceptance cases, not a replay of the September source workbook."""
import copy
import json
import random
import unittest
from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP, localcontext

from app.services.allocation_engine import AllocationInputError, MAX_MINOR, calculate


def product(pid, group=None, style=None, **kwargs):
    return dict(id=pid, group=group or pid, style=style or pid, **kwargs)


def row(pid, units=1, purchases=1, promoted="A", **kwargs):
    return dict(id=kwargs.pop("id", pid), product_id=pid, units=units,
                purchases=purchases, promoted_product_id=promoted,
                promotion_confirmed=kwargs.pop("promotion_confirmed", promoted is not None),
                source_isolation_required=False, **kwargs)


def campaign(spend="10.00", rows=None, **kwargs):
    rows = [row("B")] if rows is None else rows
    return dict(source="AMS", account_id="000012345678901234567890", campaign_id=kwargs.pop("campaign_id", "0001"),
                creator_group="A", ad_product=kwargs.pop("ad_product", "SP"), spend=spend,
                units=sum(item["units"] for item in rows), rows=rows,
                remainder=kwargs.pop("remainder", {"manual_payer_id": "A", "manual_evidence_id": "confirmed-manual"}), **kwargs)


def snapshot(campaigns=None, products=None, **kwargs):
    return dict(currency="USD", mode="FULL", products=products or [product("A"), product("B", manual_baseline="3")],
                campaigns=campaigns or [campaign()], **kwargs)


def reference_campaign(spend, rows, manuals):
    """Bounded Decimal reference; deliberately does not import engine helpers."""
    with localcontext() as ctx:
        ctx.prec = 80
        source = Decimal(spend)
        units = sum(item["units"] for item in rows)
        rate = source / Decimal(units)
        targets = {}
        direct = Decimal(0)
        for item in rows:
            if item["product_id"] == "A":
                direct += rate * item["units"]
            else:
                pid = item["product_id"]
                targets[pid] = targets.get(pid, Decimal(0)) + min(rate, Decimal(manuals[pid])) * item["units"]
        desired = int((sum(targets.values()) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        cents = {pid: int((value * 100).to_integral_value(rounding=ROUND_FLOOR)) for pid, value in targets.items()}
        order = sorted(targets, key=lambda pid: (-(targets[pid] * 100 - cents[pid]), pid))
        for pid in order[:desired - sum(cents.values())]:
            cents[pid] += 1
        creator = int(source * 100) - desired
        direct_floor = int((direct * 100).to_integral_value(rounding=ROUND_FLOOR))
        remain = (source - sum(targets.values()) - direct) * 100
        remain_floor = int(remain.to_integral_value(rounding=ROUND_FLOOR))
        left = creator - direct_floor - remain_floor
        # Components for the same source product use DIRECT before transition.
        if left and direct * 100 - direct_floor >= remain - remain_floor:
            direct_floor += 1
        return dict(transfer=desired, creator=creator, direct=direct_floor, remainder=creator-direct_floor, by_product=cents)


class AllocationEngineTests(unittest.TestCase):
    def test_independent_reference_36_campaigns(self):
        rng = random.Random(20261019)
        inputs = []
        expected = {}
        for number in range(36):
            rows = [row("B", rng.randint(1, 6), id="B1"), row("B", rng.randint(1, 6), id="B2"),
                    row("C", rng.randint(1, 6)), row("A", rng.randint(1, 6))]
            spend = "%d.%02d" % (rng.randint(1, 50), rng.randint(0, 99))
            item = campaign(spend, rows, campaign_id="%04d" % number)
            inputs.append(item)
            expected[item["campaign_id"]] = reference_campaign(spend, rows, {"B": ".17", "C": ".23"})
        result = calculate(snapshot(inputs, [product("A"), product("B", manual_baseline=".17"), product("C", manual_baseline=".23")]))
        self.assertEqual(result["calculation_status"], "SUCCEEDED")
        for item in result["campaigns"]:
            ref = expected[item["campaign_id"]]
            with self.subTest(campaign=item["campaign_id"]):
                self.assertEqual(int(item["transfer_out_minor"]), ref["transfer"])
                self.assertEqual(int(item["creator_retained_minor"]), ref["creator"])
                self.assertEqual(int(item["direct_minor"]), ref["direct"])
                self.assertEqual(int(item["remainder_minor"]), ref["remainder"])
                transfers = {component["product_id"]: int(component["minor"]) for component in item["components"] if component["origin"] == "TRANSFER"}
                self.assertEqual(transfers, ref["by_product"])

    def test_own_baseline_uses_purchases_threshold_units_denominator(self):
        campaigns = [campaign("24.00", [row("B", 12, 9, promoted="B")], campaign_id="own"), campaign("10.00", [row("B")])]
        result = calculate(snapshot(campaigns))
        self.assertEqual(result["baselines"][1]["status"], "NOT_QUALIFIED")
        self.assertEqual(result["campaigns"][0]["transfer_out_minor"], "300")
        campaigns[0]["rows"][0]["purchases"] = 10
        result = calculate(snapshot(campaigns))
        self.assertEqual(result["baselines"][1]["rate"], {"numerator": "2", "denominator": "1"})
        self.assertEqual(result["campaigns"][0]["transfer_out_minor"], "200")

    def test_baseline_merges_accounts_and_types(self):
        campaigns = [campaign("16.00", [row("B", 8, 8, promoted="B")], campaign_id="sp"),
                     campaign("8.00", [row("B", 4, 2, promoted="B")], campaign_id="stv", ad_product="STV")]
        campaigns[1]["account_id"] = "other-real-account"
        baseline = calculate(snapshot(campaigns))["baselines"][1]
        self.assertEqual(baseline["direct_units"], 12)
        self.assertEqual(baseline["direct_purchases"], 10)
        self.assertEqual(baseline["rate"], {"numerator": "2", "denominator": "1"})

    def test_missing_purchases_blocks_manual_fallback(self):
        inputs = snapshot([campaign("10.00", [row("B", purchases=None, promoted="B")], campaign_id="own"), campaign()])
        result = calculate(inputs)
        self.assertEqual(result["calculation_status"], "PARTIAL")
        self.assertIsNone(result["summary"]["final_cost"])
        self.assertIsNone(next(c for c in result["campaigns"] if c["campaign_id"] == "0001")["transfer_out_minor"])

    def test_half_cent_and_unicode_tie(self):
        inputs = snapshot([campaign("0.03", [row("B"), row("C")])],
                          [product("A"), product("B", manual_baseline=".005"), product("C", manual_baseline=".005")])
        result = calculate(inputs)
        transfers = [item for item in result["campaigns"][0]["components"] if item["origin"] == "TRANSFER"]
        self.assertEqual([(item["product_id"], item["minor"]) for item in transfers], [("B", "1"), ("C", "0")])
        self.assertEqual(result["campaigns"][0]["creator_retained_minor"], "2")

    def test_campaign_aggregate_not_row_rounding(self):
        rows = [row("B", id=str(index)) for index in range(10)]
        inputs = snapshot([campaign("1.00", rows)], [product("A"), product("B", manual_baseline=".005")])
        self.assertEqual(calculate(inputs)["campaigns"][0]["transfer_out_minor"], "5")

    def test_row_order_stable_input_fingerprint(self):
        inputs = snapshot([campaign("3.01", [row("B", id="b"), row("A", id="a")]), campaign("4.00", campaign_id="02")])
        expected = calculate(inputs)
        inputs["campaigns"].reverse()
        inputs["products"].reverse()
        inputs["campaigns"][1]["rows"].reverse()
        actual = calculate(inputs)
        self.assertEqual(expected["input_fingerprint"], actual["input_fingerprint"])
        self.assertEqual(expected["summary"], actual["summary"])
        self.assertEqual(expected["products"], actual["products"])
        self.assertEqual(expected, actual)

    def test_direct_cross_group_ignores_isolation_and_clearance(self):
        item = row("B", promoted="B")
        item.update(source_isolation_required=True, source_eligibility="INELIGIBLE")
        result = calculate(snapshot([campaign(rows=[item])], [product("A"), product("B", clearance=True)]))
        self.assertEqual(result["campaigns"][0]["transfer_out_minor"], "1000")
        self.assertEqual(result["products"][1]["self_minor"], "1000")

    def test_source_four_states_and_evidence(self):
        for state, evidence, coverage, expected in (("ELIGIBLE", "positive", False, "300"),
                                                    ("INELIGIBLE", "negative", True, "0"),
                                                    ("INELIGIBLE", "negative", False, None),
                                                    ("ELIGIBLE", None, False, None),
                                                    ("PENDING_VERIFICATION", None, False, None),
                                                    ("NOT_APPLICABLE", None, False, None)):
            with self.subTest(state=state, evidence=evidence, coverage=coverage):
                item = row("B")
                item.update(source_isolation_required=True, source_eligibility=state, source_evidence_id=evidence, coverage_confirmed=coverage)
                result = calculate(snapshot([campaign(rows=[item])]))
                self.assertEqual(result["campaigns"][0]["transfer_out_minor"], expected)

    def test_same_group_halo_source_gate_not_applicable(self):
        item = row("B")
        item.update(source_isolation_required=True, source_eligibility="PENDING_VERIFICATION")
        result = calculate(snapshot([campaign(rows=[item])], [product("A"), product("B", group="A", manual_baseline="3")]))
        self.assertEqual(result["campaigns"][0]["halo_minor"], "300")
        self.assertEqual(result["campaigns"][0]["remainder_minor"], "700")

    def test_manual_source_cap_and_clearance_order(self):
        inputs = snapshot([campaign("1.50")], [product("A"), product("B", manual_baseline="3", clearance=True)])
        self.assertEqual(calculate(inputs)["campaigns"][0]["transfer_out_minor"], "150")
        inputs["products"][1].pop("manual_baseline")
        result = calculate(inputs)
        self.assertEqual(result["campaigns"][0]["transfer_out_minor"], "0")
        self.assertEqual(result["campaigns"][0]["remainder_minor"], "150")
        self.assertEqual(result["campaigns"][0]["retentions"][0]["reason"], "CLEARANCE_RETAIN")

    def test_ad_baseline_precedes_manual_and_clearance(self):
        inputs = snapshot([campaign("40.00", [row("B", 10, 10, promoted="B")], campaign_id="own"), campaign("5.00")],
                          [product("A"), product("B", manual_baseline="3", clearance=True)])
        result = calculate(inputs)
        self.assertEqual(result["campaigns"][0]["transfer_out_minor"], "400")
        self.assertEqual(result["campaigns"][0]["pricing"][0]["rule"], "HALO_AD")

    def test_unknown_stv_and_evidenced_sbv_are_halo(self):
        for ad_product, ad_format, evidence in (("STV", "UNKNOWN", None), ("SB", "VIDEO", "creative-row-link")):
            item = row("B", promoted=None, ad_format=ad_format, format_evidence_id=evidence)
            result = calculate(snapshot([campaign(rows=[item], ad_product=ad_product)]))
            self.assertEqual(result["calculation_status"], "SUCCEEDED")
            self.assertEqual(result["baselines"][1]["direct_units"], 0)
            self.assertEqual(result["campaigns"][0]["pricing"][0]["relation"], "HALO")

    def test_unknown_ordinary_promotion_blocks(self):
        for ad_product, ad_format in (("SP", "UNKNOWN"), ("SB", "VIDEO"), ("SB", "UNKNOWN"), ("SD", "UNKNOWN")):
            result = calculate(snapshot([campaign(rows=[row("B", promoted=None, ad_format=ad_format)], ad_product=ad_product)]))
            self.assertEqual(result["calculation_status"], "PARTIAL")
            self.assertIsNone(result["summary"]["final_minor"])

    def test_zero_attribution_retains_full_spend(self):
        result = calculate(snapshot([campaign("70.00", [])]))
        item = result["campaigns"][0]
        self.assertIsNone(item["source_rate"])
        self.assertEqual(item["remainder_minor"], "7000")
        self.assertEqual(result["products"][0]["final_minor"], "7000")

    def test_protection_not_allocated_twice(self):
        result = calculate(snapshot([campaign("70.00", [], protection_payer_id="A", protection_evidence_id="confirmed")]))
        item = result["campaigns"][0]
        self.assertEqual(item["protection_minor"], "7000")
        self.assertEqual(item["remainder_minor"], "0")
        self.assertEqual(result["summary"]["final_minor"], "7000")

    def test_remainder_weighted_60_40_excludes_other_group(self):
        config = {"promotion_scope_complete": True, "weights_complete": True, "promoted_products": [
            {"product_id": "A", "weight": "60", "evidence_id": "ad1"},
            {"product_id": "A2", "weight": "40", "evidence_id": "ad2"},
            {"product_id": "B", "weight": "999", "evidence_id": "ad3"}]}
        result = calculate(snapshot([campaign("10.00", [], remainder=config)], [product("A"), product("A2", group="A"), product("B")]))
        self.assertEqual([(item["product_id"], item["new_minor"]) for item in result["campaigns"][0]["remainders"]], [("A", "600"), ("A2", "400")])

    def test_single_promoted_zero_spend_allowed_only_complete(self):
        config = {"promotion_scope_complete": True, "promoted_products": [{"product_id": "A", "weight": "0", "evidence_id": "ad"}]}
        self.assertEqual(calculate(snapshot([campaign("10.00", [], remainder=config)]))["calculation_status"], "SUCCEEDED")
        config["promotion_scope_complete"] = False
        self.assertEqual(calculate(snapshot([campaign("10.00", [], remainder=config)]))["calculation_status"], "PARTIAL")

    def test_partial_or_missing_weights_not_normalized(self):
        config = {"promotion_scope_complete": True, "weights_complete": True, "promoted_products": [
            {"product_id": "A", "weight": "60", "evidence_id": "a"}, {"product_id": "A2", "evidence_id": "a2"}]}
        result = calculate(snapshot([campaign("10.00", [], remainder=config)], [product("A"), product("A2", group="A"), product("B")]))
        self.assertEqual(result["calculation_status"], "PARTIAL")
        self.assertEqual(result["campaigns"][0]["unallocated_minor"], "1000")

    def test_full_recalculation_ignores_old_n(self):
        inputs = snapshot([campaign("20.00", [])])
        base = calculate(inputs)
        inputs["base_result"] = base
        self.assertEqual(calculate(inputs)["campaigns"][0]["remainder_minor"], "2000")

    def test_remainder_only_fills_delta_and_is_idempotent(self):
        inputs = snapshot([campaign("20.00", [], remainder={})])
        base = calculate(inputs)
        inputs["campaigns"][0]["remainder"] = {"manual_payer_id": "A", "manual_evidence_id": "new-confirmed"}
        inputs.update(mode="REMAINDER_ONLY", base_result=base)
        result = calculate(inputs)
        self.assertEqual(result["campaigns"][0]["remainders"][0]["delta_minor"], "2000")
        inputs["base_result"] = result
        rerun = calculate(inputs)
        self.assertEqual(rerun["campaigns"][0]["remainders"][0]["delta_minor"], "0")
        self.assertEqual(rerun["summary"]["final_minor"], "2000")

    def test_remainder_only_preserves_old_5_adds_15(self):
        inputs = snapshot([campaign("20.00", [])])
        base = calculate(inputs)
        item = base["campaigns"][0]
        item.update(remainder_minor="500", remainder_cost="5.00", unallocated_minor="1500", unallocated_cost="15.00")
        item["components"][0]["minor"] = "500"
        inputs.update(mode="REMAINDER_ONLY", base_result=base)
        result = calculate(inputs)
        self.assertEqual(result["campaigns"][0]["remainders"][0]["old_minor"], "500")
        self.assertEqual(result["campaigns"][0]["remainders"][0]["delta_minor"], "1500")
        self.assertEqual(result["campaigns"][0]["remainder_minor"], "2000")

    def test_remainder_only_rejects_changed_facts_and_negative_old_n(self):
        inputs = snapshot()
        base = calculate(inputs)
        inputs.update(mode="REMAINDER_ONLY", base_result=base)
        inputs["campaigns"][0]["spend"] = "11.00"
        with self.assertRaisesRegex(AllocationInputError, "BASE_RUN_INCOMPATIBLE"):
            calculate(inputs)
        inputs["campaigns"][0]["spend"] = "10.00"
        base["campaigns"][0]["components"][-1]["minor"] = "-1"
        with self.assertRaisesRegex(AllocationInputError, "BASE_RUN_INCOMPATIBLE"):
            calculate(inputs)

    def test_opaque_ids_json_serializable_and_input_unchanged(self):
        inputs = snapshot()
        original = copy.deepcopy(inputs)
        result = calculate(inputs)
        self.assertEqual(inputs, original)
        self.assertEqual(result["campaigns"][0]["campaign_id"], "0001")
        self.assertEqual(result["campaigns"][0]["account_id"], "000012345678901234567890")
        json.dumps(result, allow_nan=False)

    def test_zero_spend_attribution_does_not_dilute_paid_baseline(self):
        inputs = snapshot([campaign("20.00", [row("B", 10, 10, promoted="B")], campaign_id="paid"),
                           campaign("0.00", [row("B", 100, 100, promoted="B")], campaign_id="unpaid")])
        baseline = calculate(inputs)["baselines"][1]
        self.assertEqual(baseline["direct_units"], 10)
        self.assertEqual(baseline["direct_purchases"], 10)
        self.assertEqual(baseline["rate"], {"numerator": "2", "denominator": "1"})

    def test_unknown_sbv_does_not_bypass_source_gate(self):
        item = row("B", promoted=None, ad_format="VIDEO", format_evidence_id="format")
        item.update(source_isolation_required=True, source_eligibility="INELIGIBLE", source_evidence_id="coverage", coverage_confirmed=True)
        result = calculate(snapshot([campaign(rows=[item], ad_product="SB")]))
        self.assertEqual(result["campaigns"][0]["transfer_out_minor"], "0")

    def test_metadata_passthrough_does_not_change_cost(self):
        inputs = snapshot()
        inputs["products"][1].update(product_category="鞋", classification_status="pending_review", unit="双")
        result = calculate(inputs)
        self.assertEqual(result["products"][1]["product_category"], "鞋")
        self.assertEqual(result["products"][1]["final_minor"], "300")

    def test_base_non_remainder_component_mutation_rejected(self):
        inputs = snapshot()
        inputs.update(base_result=calculate(inputs), mode="REMAINDER_ONLY")
        inputs["base_result"]["campaigns"][0]["components"][0]["minor"] = "999"
        with self.assertRaisesRegex(AllocationInputError, "BASE_RUN_INCOMPATIBLE"):
            calculate(inputs)

    def test_signed_bigint_maximum_is_accepted_exactly(self):
        result = calculate(snapshot([campaign("92233720368547758.07")]))
        self.assertEqual(result["summary"]["spend_minor"], str(MAX_MINOR))
        self.assertEqual(result["summary"]["final_minor"], str(MAX_MINOR))
        self.assertEqual(result["summary"]["final_cost"], "92233720368547758.07")

    def test_signed_bigint_overflow_rejected_per_campaign_and_snapshot(self):
        for campaigns in ([campaign("92233720368547758.08")],
                          [campaign("92233720368547758.07"), campaign(".01", campaign_id="second")]):
            with self.subTest(campaign_count=len(campaigns)):
                with self.assertRaisesRegex(AllocationInputError, "MONETARY_MINOR_RANGE_EXCEEDED"):
                    calculate(snapshot(campaigns))

    def test_decimal_resource_bounds_reject_before_fraction_expansion(self):
        for value in ("1e999999999", "1e-999999999", "0e999999999", "0e-999999999", "1e129", "1e-129", "1e21", "0" * 129):
            for target in ("spend", "manual_baseline", "weight"):
                with self.subTest(value=value, target=target):
                    inputs = snapshot()
                    if target == "spend":
                        inputs["campaigns"][0]["spend"] = value
                    elif target == "manual_baseline":
                        inputs["products"][1]["manual_baseline"] = value
                    else:
                        inputs["campaigns"][0]["remainder"] = {
                            "promotion_scope_complete": True,
                            "promoted_products": [{"product_id": "A", "weight": value, "evidence_id": "promotion"}]}
                    with self.assertRaises(AllocationInputError):
                        calculate(inputs)

    def test_supported_tiny_manual_precision_is_exact_and_not_truncated(self):
        inputs = snapshot(products=[product("A"), product("B", manual_baseline="1e-128")])
        result = calculate(inputs)
        self.assertEqual(result["campaigns"][0]["pricing"][0]["target"],
                         {"numerator": "1", "denominator": "1" + "0" * 128})
        self.assertEqual(result["campaigns"][0]["transfer_out_minor"], "0")
        self.assertEqual(result["summary"]["final_minor"], "1000")

    def test_invalid_inputs_fail_closed(self):
        changes = [lambda p: p["campaigns"][0].update(spend=1.1), lambda p: p["campaigns"][0].update(spend="NaN"),
                   lambda p: p["campaigns"][0].update(spend="-.01"), lambda p: p["campaigns"][0].update(spend=".001"),
                   lambda p: p["campaigns"][0].update(units=2), lambda p: p["campaigns"][0].update(campaign_id=123),
                   lambda p: p["campaigns"].append(copy.deepcopy(p["campaigns"][0])),
                   lambda p: p.update(currency="EUR"), lambda p: p["products"].append(copy.deepcopy(p["products"][0])),
                   lambda p: p["campaigns"][0]["rows"][0].update(purchases=-1),
                   lambda p: p["campaigns"][0]["rows"][0].update(units=True)]
        for change in changes:
            with self.subTest(change=change):
                inputs = snapshot()
                change(inputs)
                with self.assertRaises(AllocationInputError):
                    calculate(inputs)


if __name__ == "__main__":
    unittest.main()
