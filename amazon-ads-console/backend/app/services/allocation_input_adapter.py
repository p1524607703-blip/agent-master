"""Fail-closed source-ledger preflight; not an allocation calculation.

Only the campaign-day report contributes cost. Product/purchased reports are
evidence; never additive spend pools. No status here authorizes finance.
"""
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from .allocation_sources import AD_PRODUCTS, TABLES, audit_snapshot_quality
from .allocation_store import digest


class AllocationHandoffBlocked(ValueError):
    pass


def _decimal(value):
    if not isinstance(value, str) or len(value) > 128:
        raise AllocationHandoffBlocked("EXACT_DECIMAL_TEXT_REQUIRED")
    try:
        d = Decimal(value)
    except InvalidOperation as e:
        raise AllocationHandoffBlocked("INVALID_DECIMAL") from e
    if not d.is_finite() or d < 0 or abs(d.as_tuple().exponent) > 128 or d.adjusted() > 20:
        raise AllocationHandoffBlocked("NONFINITE_NEGATIVE_OR_EXTREME_COST")
    return d


def prepare_source_handoff(capture, *, coverage_manifest=None, mapping_reconciliation=None):
    """Summarize campaigns without inferring group, product or source eligibility."""
    if not isinstance(capture, dict) or not isinstance(capture.get("facts"), dict):
        raise AllocationHandoffBlocked("FROZEN_CAPTURE_REQUIRED")
    chash = capture.get("content_hash")
    if not isinstance(chash, str) or chash != digest({k: v for k, v in capture.items() if k != "content_hash"}):
        raise AllocationHandoffBlocked("CAPTURE_HASH_MISMATCH")
    scope = capture.get("scope")
    if not isinstance(scope, dict) or scope.get("currency") != "USD":
        raise AllocationHandoffBlocked("UNSUPPORTED_SCOPE")
    if set(capture["facts"]) != set(TABLES):
        raise AllocationHandoffBlocked("THREE_FACT_TABLES_REQUIRED")
    if capture.get("capabilities", {}).get("formal_publication") is not False:
        raise AllocationHandoffBlocked("PUBLICATION_CAPABILITY_MUST_REMAIN_FALSE")

    quality = audit_snapshot_quality(capture)
    if quality["issue_count"]:
        raise AllocationHandoffBlocked("CANONICAL_SOURCE_QUALITY_BLOCKED")

    grouped = defaultdict(lambda: {"spend": Decimal(0), "purchases": 0, "units": 0,
                                  "days": set(), "sources": set()})
    names = {v: k for k, v in AD_PRODUCTS.items()}
    pending = []
    for row in capture["facts"]["report_campaign_daily"]:
        if row["budget_currency"] != "USD":
            raise AllocationHandoffBlocked("CURRENCY_MISMATCH")
        if row["ad_product"] not in names:
            raise AllocationHandoffBlocked("UNKNOWN_AD_PRODUCT")
        if row["account_id"] not in scope.get("account_ids", []):
            raise AllocationHandoffBlocked("ACCOUNT_OUTSIDE_SCOPE")
        if names[row["ad_product"]] not in scope.get("ad_products", []):
            raise AllocationHandoffBlocked("AD_PRODUCT_OUTSIDE_SCOPE")
        if not str(row["stat_date"]).startswith(scope.get("period", "") + "-"):
            raise AllocationHandoffBlocked("REPORT_DATE_OUTSIDE_SCOPE")
        key = (row["account_id"], names[row["ad_product"]], row["campaign_id"])
        values = grouped[key]
        values["spend"] += _decimal(row["spend"])
        values["purchases"] += int(row["purchases"])
        values["units"] += int(row["units"])
        values["days"].add(str(row["stat_date"]))
        values["sources"].add(str(row.get("row_hash")))
    candidates = []
    for (account, adtype, campaign), value in sorted(grouped.items()):
        money = value["spend"]
        if money.as_tuple().exponent < -2 and money != money.quantize(Decimal(".01")):
            raise AllocationHandoffBlocked("CAMPAIGN_SPEND_NOT_CENTS")
        amount = format(money, ".2f")
        candidates.append({"account_id": account, "ad_product": adtype, "campaign_id": campaign,
                           "campaign_spend": amount, "observed_purchase_count": value["purchases"],
                           "observed_units": value["units"], "observed_days": sorted(value["days"]),
                           "source_row_hashes": sorted(value["sources"]),
                           "creator_group": None, "engine_rows": None,
                           "financial_approval": False})
    if not candidates:
        pending.append("CAMPAIGN_SOURCE_EMPTY_NOT_ZERO_SPEND_PROOF")
    pending.extend(["SOURCE_COVERAGE_EXPECTED_REQUESTS_UNVERIFIED",
                    "MAPPING_AUTHORITY_AND_BUSINESS_BINDINGS_UNAPPROVED",
                    "CAMPAIGN_CREATOR_AND_PURCHASE_RELATIONSHIP_UNCONFIRMED",
                    "PURCHASE_10_ORDER_AND_SOURCE_ELIGIBILITY_UNVERIFIED",
                    "FINANCIAL_PARAMETER_SET_NOT_SIGNED"])
    if coverage_manifest is not None:
        if coverage_manifest.get("capture_hash") != chash or coverage_manifest.get("manifest_hash") != digest(
                {k: v for k, v in coverage_manifest.items() if k != "manifest_hash"}):
            raise AllocationHandoffBlocked("COVERAGE_HASH_MISMATCH")
        if any(c.get("negative_eligibility_proven") is True for c in coverage_manifest.get("cells", [])):
            raise AllocationHandoffBlocked("UNTRUSTED_NEGATIVE_ELIGIBILITY")
    if mapping_reconciliation is not None:
        if mapping_reconciliation.get("reconciliation_hash") != digest(
                {k: v for k, v in mapping_reconciliation.items() if k != "reconciliation_hash"}):
            raise AllocationHandoffBlocked("MAPPING_RECONCILIATION_HASH_MISMATCH")
        if mapping_reconciliation.get("issues"):
            pending.append("APP_AND_WAREHOUSE_MAPPING_CONFLICTS")
    result = {"stage": "OBSERVED_SOURCE_ONLY", "scope": scope, "capture_hash": chash,
              "financial_ready": False, "may_run_engine": False, "may_publish": False,
              "spend_source": "core.report_campaign_daily",
              "evidence_tables": ["core.report_advertised_product_daily", "core.report_purchased_product_daily"],
              "campaigns": candidates, "pending": pending}
    result["handoff_hash"] = digest(result)
    return result


def require_financial_ready(handoff):
    # No trusted approval verifier is yet deployed; callers cannot bypass it with a flag.
    if not isinstance(handoff, dict) or handoff.get("handoff_hash") != digest(
            {k: v for k, v in handoff.items() if k != "handoff_hash"}):
        raise AllocationHandoffBlocked("HANDOFF_NOT_INTACT")
    raise AllocationHandoffBlocked("AUTHORITATIVE_ENGINE_INPUT_NOT_APPROVED")
