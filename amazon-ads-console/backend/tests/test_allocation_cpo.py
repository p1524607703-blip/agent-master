import copy
from datetime import date, timedelta

import pytest

from app.services.allocation_cpo import business_metrics


PRODUCT = {"id": "p", "group": "AJ1", "style": "S1", "unit": "双", "final_cost": "100.00", "attributed_units": 20}


def business():
    return {"id": "frozen-business", "period": "2026-09", "report_timezone": "America/Los_Angeles", "binding_version": "v1",
            "bindings": [{"product_id": "p", "account_id": "store", "marketplace": "US", "child_asins": ["B000000001"],
                          "effective_from": "2026-01-01", "effective_to": "2026-12-31", "confirmed": True,
                          "evidence_id": "binding-proof", "unit": "双", "unit_evidence_id": "unit-proof"}],
            "facts": [{"account_id": "store", "marketplace": "US", "date": "2026-09-30", "child_asin": "B000000001",
                       "fact_version": "v1", "ordered_product_units": 10}],
            "coverage": [{"account_id": "store", "marketplace": "US", "child_asin": "B000000001", "date_from": "2026-09-01", "date_to": "2026-09-30",
                          "complete": True, "evidence_id": "complete-zero-report", "empty_dates": ["2026-09-%02d" % d for d in range(1, 30)]}]}


def calculate(snapshot):
    return business_metrics([PRODUCT], snapshot, "2026-09", "America/Los_Angeles")[0]


def test_complete_business_denominator_and_separate_ad_metric():
    result = calculate(business())
    assert result["ordered_product_units"] == 10
    assert result["allocation_business_cpo"] == "10.000000"
    assert result["allocation_attributed_unit_cost"] == "5.000000"
    assert result["daily_business_cpo"] is None


def test_missing_child_coverage_cannot_be_called_complete():
    snapshot = business()
    snapshot["bindings"][0]["child_asins"].append("B000000002")
    result = calculate(snapshot)
    assert result["denominator_status"] == "BUSINESS_COVERAGE_INCOMPLETE"
    assert result["ordered_product_units"] is None
    assert result["final_cost"] == "100.00"


def test_partial_dates_not_imputed_zero():
    snapshot = business()
    snapshot["coverage"][0]["empty_dates"] = []
    assert calculate(snapshot)["denominator_status"] == "BUSINESS_FACT_MISSING"


def test_outside_month_fact_never_inflates_denominator():
    snapshot = business()
    snapshot["facts"].append(dict(snapshot["facts"][0], date="2026-10-01", ordered_product_units=200))
    with pytest.raises(ValueError, match="OUTSIDE_PERIOD"):
        calculate(snapshot)


def test_duplicate_sku_copy_of_asin_fact_rejected():
    snapshot = business()
    snapshot["facts"].append(dict(snapshot["facts"][0], sku="another-SKU"))
    with pytest.raises(ValueError, match="FACT_CONFLICT"):
        calculate(snapshot)


def test_same_asin_different_real_store_adds_legitimate_sales():
    snapshot = business()
    snapshot["bindings"].append(dict(snapshot["bindings"][0], account_id="store2"))
    snapshot["facts"].append(dict(snapshot["facts"][0], account_id="store2", ordered_product_units=5))
    snapshot["coverage"].append(dict(snapshot["coverage"][0], account_id="store2"))
    assert calculate(snapshot)["ordered_product_units"] == 15


def test_binding_cannot_consume_same_child_fact_twice():
    snapshot = business()
    snapshot["bindings"].append(copy.deepcopy(snapshot["bindings"][0]))
    with pytest.raises(ValueError, match="REUSED"):
        calculate(snapshot)


@pytest.mark.parametrize("change", ["unit", "date", "scope"])
def test_unit_period_and_snapshot_scope_checked(change):
    snapshot = business()
    if change == "unit":
        snapshot["bindings"][0]["unit"] = "件"
        assert calculate(snapshot)["denominator_status"] == "BUSINESS_UNIT_UNVERIFIED"
    elif change == "date":
        snapshot["bindings"][0]["effective_to"] = "2026-99-01"
        with pytest.raises(ValueError):
            calculate(snapshot)
    else:
        snapshot["period"] = "2026-10"
        with pytest.raises(ValueError, match="SCOPE_MISMATCH"):
            calculate(snapshot)


def test_zero_business_denominator_is_null_cost_preserved():
    snapshot = business()
    snapshot["facts"][0]["ordered_product_units"] = 0
    result = calculate(snapshot)
    assert result["ordered_product_units"] == 0
    assert result["denominator_status"] == "ZERO_UNITS"
    assert result["allocation_business_cpo"] is None
    assert result["final_cost"] == "100.00"


def test_empty_proofs_cannot_be_borrowed_from_another_interval():
    snapshot = business()
    snapshot["coverage"][0]["date_to"] = "2026-09-01"
    with pytest.raises(ValueError, match="EMPTY_PROOF_OUTSIDE_COVERAGE"):
        calculate(snapshot)


def test_confirmed_flag_must_be_boolean():
    snapshot = business()
    snapshot["bindings"][0]["confirmed"] = "false"
    assert calculate(snapshot)["denominator_status"] == "BINDING_UNVERIFIED"
