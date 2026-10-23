"""Deterministic USD allocation over an already frozen, normalized snapshot.

This module never reads production facts or infers missing evidence. See the
contract in docs/allocation_engine_contract.md before building an adapter.
"""
import copy
import hashlib
import json
import unicodedata
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, Dict, List

ENGINE_VERSION = "allocation-0.1.0"
MAX_MINOR = (1 << 63) - 1
MAX_DECIMAL_TEXT_LENGTH = 128
MAX_DECIMAL_EXPONENT = 128


class AllocationInputError(ValueError):
    pass


def _text(value, field):
    if not isinstance(value, str) or not value or unicodedata.normalize("NFC", value) != value:
        raise AllocationInputError("%s must be a nonempty NFC string" % field)
    return value


def _decimal(value, field):
    if not isinstance(value, str):
        raise AllocationInputError("%s must be a decimal string" % field)
    if len(value) > MAX_DECIMAL_TEXT_LENGTH:
        raise AllocationInputError("%s decimal text exceeds 128 characters" % field)
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise AllocationInputError("%s must be decimal" % field)
    if not number.is_finite() or number < 0:
        raise AllocationInputError("%s must be finite and nonnegative" % field)
    # Check before Fraction: a tiny textual exponent can otherwise allocate
    # hundreds of millions of integer digits before the monetary check runs.
    if abs(number.as_tuple().exponent) > MAX_DECIMAL_EXPONENT or number.adjusted() > 20:
        raise AllocationInputError("%s decimal exponent or magnitude exceeds supported bounds" % field)
    return Fraction(number)


def _integer(value, field):
    if type(value) is not int or value < 0:
        raise AllocationInputError("%s must be a nonnegative integer" % field)
    return value


def _rational(value):
    return {"numerator": str(value.numerator), "denominator": str(value.denominator)}


def _half_up(value):
    if value < 0:
        raise AllocationInputError("negative allocation")
    return (value.numerator * 2 + value.denominator) // (2 * value.denominator)


def _money(minor):
    if minor is None:
        return None
    sign = "-" if minor < 0 else ""
    minor = abs(minor)
    return "%s%d.%02d" % (sign, minor // 100, minor % 100)


def _amounts(target, name, minor):
    target[name + "_minor"] = None if minor is None else str(minor)
    target[name + "_cost"] = _money(minor)


def _allocate(values, target_minor=None):
    """Largest remainder over tuple keys using Unicode codepoint ordering."""
    values = {key: value for key, value in values.items() if value > 0}
    if not values:
        if target_minor not in (None, 0):
            raise AllocationInputError("positive allocation without weights")
        return {}
    exact = {key: value * 100 for key, value in values.items()}
    floors = {key: value.numerator // value.denominator for key, value in exact.items()}
    target = _half_up(sum(exact.values(), Fraction())) if target_minor is None else target_minor
    left = target - sum(floors.values())
    if left < 0 or left > len(values):
        raise AllocationInputError("inconsistent allocation target")
    order = sorted(exact, key=lambda key: (-(exact[key] - floors[key]), key))
    for key in order[:left]:
        floors[key] += 1
    return floors


def _fingerprint(payload, exclude_remainder=False):
    value = copy.deepcopy(payload)
    if exclude_remainder:
        value.pop("mode", None)
    else:
        value["mode"] = payload.get("mode", "FULL")
        if value["mode"] == "REMAINDER_ONLY":
            base_json = json.dumps(payload.get("base_result"), sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
            value["base_result_hash"] = hashlib.sha256(base_json.encode("utf-8")).hexdigest()
    value.pop("base_result", None)
    value["products"] = sorted(value.get("products", []), key=lambda item: item["id"])
    for campaign in value.get("campaigns", []):
        campaign["rows"] = sorted(campaign.get("rows", []), key=lambda item: item["id"])
        if exclude_remainder:
            campaign.pop("remainder", None)
        elif "remainder" in campaign:
            config = campaign["remainder"]
            config["promoted_products"] = sorted(config.get("promoted_products", []), key=lambda item: item["product_id"])
        for row in campaign["rows"]:
            if "baseline_candidate_ids" in row:
                row["baseline_candidate_ids"] = sorted(row["baseline_candidate_ids"])
    value["campaigns"] = sorted(value.get("campaigns", []), key=lambda item: (item["source"], item["account_id"], item["campaign_id"]))
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256((ENGINE_VERSION + "\n" + raw).encode("utf-8")).hexdigest()


def _remainder_weights(campaign, products):
    config = campaign.get("remainder", {})
    observed = {row["promoted_product_id"] for row in campaign["rows"] if row.get("promotion_confirmed") and row.get("promoted_product_id")}
    actual = {}
    for item in config.get("promoted_products", []):
        pid = item.get("product_id")
        if pid not in products:
            raise AllocationInputError("unknown remainder promoted product")
        if pid not in observed and not item.get("evidence_id"):
            raise AllocationInputError("remainder promotion requires evidence")
        if products[pid]["group"] != campaign["creator_group"]:
            continue
        weight = None if item.get("weight") is None else _decimal(item["weight"], "promotion weight")
        if pid not in actual:
            actual[pid] = weight
        elif actual[pid] is None or weight is None:
            actual[pid] = None
        else:
            actual[pid] += weight
    # Conversions alone do not prove the entire promoted-product scope.
    if len(actual) == 1 and config.get("promotion_scope_complete") is True:
        return {next(iter(actual)): Fraction(1)}, "SINGLE_PROMOTED"
    if len(actual) > 1 and config.get("promotion_scope_complete") is True and config.get("weights_complete") is True:
        if all(weight is not None for weight in actual.values()):
            positive = {pid: weight for pid, weight in actual.items() if weight > 0}
            if positive:
                return positive, "PROMOTION_SPEND"
    for field, evidence, method in (("name_payer_id", "name_evidence_id", "CONFIRMED_NAME"), ("manual_payer_id", "manual_evidence_id", "MANUAL")):
        pid = config.get(field)
        if pid is not None:
            if pid not in products or products[pid]["group"] != campaign["creator_group"]:
                raise AllocationInputError("remainder payer must belong to creator group")
            if not config.get(evidence):
                raise AllocationInputError("remainder payer requires confirmed evidence")
            return {pid: Fraction(1)}, method
    return {}, "PENDING_VERIFICATION"


def _distribute_remainder(campaign, products, total):
    if total == 0:
        return {}, "NO_REMAINDER"
    weights, method = _remainder_weights(campaign, products)
    if not weights:
        return {}, method
    total_weight = sum(weights.values(), Fraction())
    targets = {(products[pid]["style"], pid): Fraction(total, 100) * weight / total_weight for pid, weight in weights.items()}
    allocated = _allocate(targets, total)
    return {key[1]: amount for key, amount in allocated.items()}, method


def calculate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Calculate a complete frozen snapshot. No I/O, mutation, float arithmetic."""
    if not isinstance(payload, dict):
        raise AllocationInputError("snapshot must be an object")
    mode = payload.get("mode", "FULL")
    if mode not in ("FULL", "RULE_REVISION", "REMAINDER_ONLY"):
        raise AllocationInputError("unsupported mode")
    if payload.get("currency") != "USD":
        raise AllocationInputError("only USD is supported")
    if not isinstance(payload.get("products"), list) or not payload["products"]:
        raise AllocationInputError("products must be a nonempty list")
    products = {}
    display_keys = set()
    for product in payload.get("products", []):
        if not isinstance(product, dict):
            raise AllocationInputError("product must be an object")
        pid = _text(product.get("id"), "product id")
        group = _text(product.get("group"), "product group")
        style = _text(product.get("style"), "product style")
        if pid in products or (group, style) in display_keys:
            raise AllocationInputError("duplicate financial product")
        display_keys.add((group, style))
        products[pid] = product
        if product.get("manual_baseline") is not None and _decimal(product["manual_baseline"], "manual baseline") <= 0:
            raise AllocationInputError("manual baseline must be positive")
        if "clearance" in product and type(product["clearance"]) is not bool:
            raise AllocationInputError("clearance must be boolean")
    campaigns = payload.get("campaigns", [])
    if not isinstance(campaigns, list) or not campaigns:
        raise AllocationInputError("campaigns must be a nonempty list")
    seen = set()
    total_spend_minor = 0
    facts = {}
    direct_totals = {pid: {"units": 0, "purchases": 0, "cost": Fraction(), "pending": False} for pid in products}
    issues = []

    def issue(code, key, row_id=None, product_id=None):
        item = {"code": code, "campaign_key": list(key)}
        if row_id is not None:
            item["row_id"] = row_id
        if product_id is not None:
            item["product_id"] = product_id
        issues.append(item)

    for campaign in campaigns:
        if not isinstance(campaign, dict):
            raise AllocationInputError("campaign must be an object")
        key = tuple(_text(campaign.get(field), field) for field in ("source", "account_id", "campaign_id"))
        if key in seen:
            raise AllocationInputError("duplicate Campaign key")
        seen.add(key)
        _text(campaign.get("creator_group"), "creator group")
        if campaign.get("ad_product") not in ("SP", "SB", "SD", "STV"):
            raise AllocationInputError("unsupported ad product")
        spend = _decimal(campaign.get("spend"), "Campaign spend")
        if (spend * 100).denominator != 1:
            raise AllocationInputError("Campaign spend must be exact cents")
        spend_minor = int(spend * 100)
        total_spend_minor += spend_minor
        if spend_minor > MAX_MINOR or total_spend_minor > MAX_MINOR:
            raise AllocationInputError("MONETARY_MINOR_RANGE_EXCEEDED: each Campaign and snapshot total must fit signed BIGINT")
        units = _integer(campaign.get("units"), "Campaign units")
        rows = campaign.get("rows", [])
        if not isinstance(rows, list):
            raise AllocationInputError("rows must be a list")
        if any(not isinstance(row, dict) for row in rows):
            raise AllocationInputError("row must be an object")
        if sum(_integer(row.get("units"), "row units") for row in rows) != units:
            raise AllocationInputError("all raw row units must equal Campaign units")
        cpc = spend / units if units else None
        row_ids = set()
        normalized = []
        for row in rows:
            row_id = _text(row.get("id"), "row id")
            if row_id in row_ids:
                raise AllocationInputError("duplicate Campaign row id")
            row_ids.add(row_id)
            pid = row.get("product_id")
            if pid not in products:
                raise AllocationInputError("unknown purchased financial product")
            if type(row.get("promotion_confirmed")) is not bool:
                raise AllocationInputError("promotion_confirmed must be boolean")
            promo = row.get("promoted_product_id")
            if promo is not None and promo not in products:
                raise AllocationInputError("unknown promoted financial product")
            if row.get("purchases") is not None:
                _integer(row["purchases"], "row purchases")
            if type(row.get("source_isolation_required")) is not bool:
                raise AllocationInputError("source_isolation_required must be explicit boolean")
            state = row.get("source_eligibility", "NOT_APPLICABLE")
            if state not in ("NOT_APPLICABLE", "ELIGIBLE", "INELIGIBLE", "PENDING_VERIFICATION"):
                raise AllocationInputError("invalid source eligibility")
            if row.get("ad_format", "UNKNOWN") not in ("VIDEO", "NON_VIDEO", "UNKNOWN"):
                raise AllocationInputError("invalid ad format")
            confirmed = row["promotion_confirmed"] and promo is not None
            special_halo = campaign["ad_product"] == "STV" or (campaign["ad_product"] == "SB" and row.get("ad_format") == "VIDEO" and bool(row.get("format_evidence_id")))
            relation = "DIRECT" if confirmed and promo == pid else "HALO" if confirmed or special_halo else "PENDING_VERIFICATION"
            if relation == "PENDING_VERIFICATION" and row["units"]:
                candidates = row.get("baseline_candidate_ids")
                if candidates is None:
                    candidates = list(products)
                    issue("BASELINE_INFLUENCE_SCOPE_UNKNOWN", key, row_id)
                if not isinstance(candidates, list) or not candidates or any(candidate not in products for candidate in candidates):
                    raise AllocationInputError("invalid baseline candidate scope")
                for candidate in candidates:
                    direct_totals[candidate]["pending"] = True
                issue("PROMOTION_UNCONFIRMED", key, row_id, pid)
            if relation == "DIRECT" and spend > 0:
                entry = direct_totals[pid]
                entry["units"] += row["units"]
                entry["cost"] += (cpc or Fraction()) * row["units"]
                if row.get("purchases") is None:
                    entry["pending"] = True
                    issue("PURCHASES_UNAVAILABLE", key, row_id, pid)
                else:
                    entry["purchases"] += row["purchases"]
            normalized.append((row, relation))
        facts[key] = (campaign, spend, units, cpc, normalized)

    baselines = []
    baseline_rates = {}
    for pid in sorted(products):
        totals = direct_totals[pid]
        rate = totals["cost"] / totals["units"] if totals["units"] else None
        valid = not totals["pending"] and totals["purchases"] >= 10 and rate is not None and rate > 0
        baseline_rates[pid] = rate if valid else None
        baselines.append({"product_id": pid, "status": "PENDING_VERIFICATION" if totals["pending"] else "VALID" if valid else "NOT_QUALIFIED", "direct_units": totals["units"], "direct_purchases": None if totals["pending"] else totals["purchases"], "known_direct_purchases": totals["purchases"], "direct_cost": _rational(totals["cost"]), "rate": _rational(rate) if valid else None})

    # Trace arrays must be canonical too: persisted result hashes should not
    # depend on file order even when the financial inputs are identical.
    issues.sort(key=lambda entry: (tuple(entry["campaign_key"]), entry.get("row_id", ""), entry.get("product_id", ""), entry["code"]))
    result_campaigns = []
    # Components are authoritative financial leaves; original row units remain separate.
    for key in sorted(facts):
        campaign, spend, units, cpc, rows = facts[key]
        item = {"source": key[0], "account_id": key[1], "campaign_id": key[2], "campaign_key": list(key), "creator_group": campaign["creator_group"], "ad_product": campaign["ad_product"], "units": units, "source_rate": _rational(cpc) if cpc is not None else None, "pricing": [], "components": [], "remainders": [], "retentions": [], "status": "SUCCEEDED"}
        _amounts(item, "spend", int(spend * 100))
        cross = defaultdict(Fraction)
        base = defaultdict(Fraction)
        retention = defaultdict(Fraction)
        pending = False
        protection_payer = campaign.get("protection_payer_id")
        if protection_payer is not None:
            if protection_payer not in products or products[protection_payer]["group"] != campaign["creator_group"] or not campaign.get("protection_evidence_id"):
                raise AllocationInputError("protection payer requires creator-group product and evidence")
        for row, relation in sorted(rows, key=lambda entry: entry[0]["id"]):
            pid = row["product_id"]
            product = products[pid]
            raw = (cpc or Fraction()) * row["units"]
            is_cross = product["group"] != campaign["creator_group"]
            target = None
            rule = "PENDING_VERIFICATION"
            eligible = "NOT_APPLICABLE"
            if row["units"] == 0:
                target, rule = Fraction(), "DIRECT" if relation == "DIRECT" else "HALO_SOURCE"
            elif relation == "DIRECT":
                target, rule = raw, "DIRECT"
            elif relation != "PENDING_VERIFICATION":
                applicable = is_cross and row["source_isolation_required"]
                eligible = row.get("source_eligibility", "PENDING_VERIFICATION") if applicable else "NOT_APPLICABLE"
                if applicable and (eligible == "NOT_APPLICABLE" or not row.get("source_evidence_id") or (eligible == "INELIGIBLE" and row.get("coverage_confirmed") is not True)):
                    eligible = "PENDING_VERIFICATION"
                if eligible == "PENDING_VERIFICATION":
                    issue("SOURCE_ELIGIBILITY_UNCONFIRMED", key, row["id"], pid)
                elif eligible == "INELIGIBLE":
                    target, rule = Fraction(), "HALO_SOURCE_BLOCKED"
                elif direct_totals[pid]["pending"]:
                    issue("BASELINE_UNCONFIRMED", key, row["id"], pid)
                elif baseline_rates[pid] is not None:
                    target, rule = min(cpc, baseline_rates[pid]) * row["units"], "HALO_AD"
                elif product.get("manual_baseline") is not None:
                    target, rule = min(cpc, _decimal(product["manual_baseline"], "manual baseline")) * row["units"], "HALO_MANUAL"
                elif product.get("clearance") is True:
                    target, rule = Fraction(), "HALO_CLEARANCE"
                else:
                    target, rule = raw, "HALO_SOURCE"
            priced = {"row_id": row["id"], "product_id": pid, "relation": relation, "cross_group": is_cross, "source_eligibility": eligible, "rule": rule, "raw_cost": _rational(raw), "target": _rational(target) if target is not None else None, "units": row["units"]}
            item["pricing"].append(priced)
            if target is None:
                pending = True
                continue
            if is_cross:
                cross[(product["group"], product["style"], rule, pid)] += target
            else:
                base[(product["style"], "DIRECT" if relation == "DIRECT" else "HALO", pid)] += target
            difference = raw - target
            if difference:
                reason = "SOURCE_RETAIN" if rule == "HALO_SOURCE_BLOCKED" else "CLEARANCE_RETAIN" if rule == "HALO_CLEARANCE" else "CAP_RETAIN"
                retention[reason] += difference
                payer = protection_payer or "__GROUP_REMAINDER__"
                style = products[payer]["style"] if protection_payer else payer
                base[(style, reason, payer)] += difference
        if not units and spend:
            payer = protection_payer or "__GROUP_REMAINDER__"
            style = products[payer]["style"] if protection_payer else payer
            base[(style, "NO_ATTRIBUTION", payer)] += spend
            retention["NO_ATTRIBUTION"] += spend
        if pending:
            item["status"] = "PARTIAL"
            for name in ("transfer_out", "creator_retained", "direct", "halo", "protection", "remainder", "unallocated"):
                _amounts(item, name, None)
            result_campaigns.append(item)
            continue
        cross_allocated = _allocate(cross)
        x = sum(cross_allocated.values())
        k = int(spend * 100) - x
        if k < 0:
            raise AllocationInputError("negative creator retained cost")
        base_allocated = _allocate(base, k)
        direct_fee = halo_fee = protected_fee = remainder_target = 0
        for (_, code, pid), minor in sorted(base_allocated.items()):
            if pid == "__GROUP_REMAINDER__":
                remainder_target += minor
                continue
            component = {"product_id": pid, "code": code, "origin": "CREATOR", "minor": str(minor)}
            item["components"].append(component)
            if code == "DIRECT":
                direct_fee += minor
            elif code == "HALO":
                halo_fee += minor
            else:
                protected_fee += minor
        for (_, _, rule, pid), minor in sorted(cross_allocated.items()):
            item["components"].append({"product_id": pid, "code": "DIRECT" if rule == "DIRECT" else "HALO", "rule": rule, "origin": "TRANSFER", "minor": str(minor)})
        allocated_n, method = _distribute_remainder(campaign, products, remainder_target)
        for pid, minor in sorted(allocated_n.items()):
            item["components"].append({"product_id": pid, "code": "REMAINDER", "origin": "CREATOR", "minor": str(minor)})
            item["remainders"].append({"product_id": pid, "old_minor": "0", "delta_minor": str(minor), "new_minor": str(minor), "method": method})
        n = sum(allocated_n.values())
        r = remainder_target - n
        if r:
            item["status"] = "PARTIAL"
            issue("REMAINDER_PAYER_UNCONFIRMED", key)
        for reason, exact in sorted(retention.items()):
            item["retentions"].append({"reason": reason, "exact_cost": _rational(exact)})
        for name, minor in (("transfer_out", x), ("creator_retained", k), ("direct", direct_fee), ("halo", halo_fee), ("protection", protected_fee), ("remainder", n), ("unallocated", r)):
            _amounts(item, name, minor)
        result_campaigns.append(item)
    result = {"engine_version": ENGINE_VERSION, "mode": mode, "currency": "USD", "minor_unit_scale": 2, "input_fingerprint": _fingerprint(payload), "base_financial_fingerprint": _fingerprint(payload, True), "capabilities": {"pure_frozen_snapshot": True, "formal_fact_adapter": False, "historical_replay_proven": False, "automatic_version_comparison": False, "scoped_dependency_recompute": False, "rule_revision_full_snapshot_recompute": True}, "baselines": baselines, "campaigns": result_campaigns, "issues": issues}
    if mode == "REMAINDER_ONLY":
        _apply_remainder_only(result, payload, products)
    result["issues"].sort(key=lambda entry: (tuple(entry["campaign_key"]), entry.get("row_id", ""), entry.get("product_id", ""), entry["code"]))
    _aggregate(result, products)
    return result


def _apply_remainder_only(result, payload, products):
    base = payload.get("base_result")
    if not isinstance(base, dict) or base.get("engine_version") != ENGINE_VERSION or base.get("base_financial_fingerprint") != result["base_financial_fingerprint"]:
        raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
    old_campaigns = {tuple(item["campaign_key"]): item for item in base.get("campaigns", [])}
    current_inputs = {tuple(item[field] for field in ("source", "account_id", "campaign_id")): item for item in payload["campaigns"]}
    if set(old_campaigns) != set(current_inputs):
        raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
    for item in result["campaigns"]:
        key = tuple(item["campaign_key"])
        old = old_campaigns.get(key)
        if old is None:
            raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
        for field in ("spend_minor", "transfer_out_minor", "creator_retained_minor", "direct_minor", "halo_minor", "protection_minor"):
            if old.get(field) is None or old.get(field) != item.get(field):
                raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
        fresh_fixed = sorted(json.dumps(component, sort_keys=True) for component in item["components"] if component.get("code") != "REMAINDER")
        old_fixed = sorted(json.dumps(component, sort_keys=True) for component in old.get("components", []) if component.get("code") != "REMAINDER")
        if fresh_fixed != old_fixed:
            raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
        old_n = {}
        for component in old.get("components", []):
            if component.get("code") == "REMAINDER":
                pid = component["product_id"]
                if pid not in products or products[pid]["group"] != item["creator_group"]:
                    raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
                old_n[pid] = old_n.get(pid, 0) + int(component["minor"])
        if any(minor < 0 for minor in old_n.values()) or sum(old_n.values()) != int(old.get("remainder_minor", "-1")):
            raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
        target = int(item["creator_retained_minor"]) - int(item["direct_minor"]) - int(item["halo_minor"]) - int(item["protection_minor"])
        remainder = target - sum(old_n.values())
        if target < 0 or remainder < 0 or int(old.get("unallocated_minor", "-1")) != remainder:
            raise AllocationInputError("BASE_RUN_INCOMPATIBLE")
        increment, method = _distribute_remainder(current_inputs[key], products, remainder)
        item["components"] = [component for component in old["components"] if component.get("code") != "REMAINDER"]
        item["remainders"] = []
        for pid in sorted(set(old_n) | set(increment)):
            minor = old_n.get(pid, 0) + increment.get(pid, 0)
            item["components"].append({"product_id": pid, "code": "REMAINDER", "origin": "CREATOR", "minor": str(minor)})
            item["remainders"].append({"product_id": pid, "old_minor": str(old_n.get(pid, 0)), "delta_minor": str(increment.get(pid, 0)), "new_minor": str(minor), "method": method})
        total_n = sum(old_n.values()) + sum(increment.values())
        _amounts(item, "remainder", total_n)
        _amounts(item, "unallocated", target - total_n)
        item["status"] = "SUCCEEDED" if target == total_n else "PARTIAL"
    result["issues"] = [issue for issue in result["issues"] if issue["code"] != "REMAINDER_PAYER_UNCONFIRMED"]
    for item in result["campaigns"]:
        if item["status"] == "PARTIAL":
            result["issues"].append({"code": "REMAINDER_PAYER_UNCONFIRMED", "campaign_key": item["campaign_key"]})


def _aggregate(result, products):
    complete = all(item["status"] == "SUCCEEDED" for item in result["campaigns"])
    result["calculation_status"] = "SUCCEEDED" if complete else "PARTIAL"
    result["review_status"] = "READY" if complete else "DRAFT"
    totals = {pid: defaultdict(int) for pid in products}
    groups = defaultdict(lambda: defaultdict(int))
    source_spend = 0
    for campaign in result["campaigns"]:
        source_spend += int(campaign["spend_minor"])
        group = campaign["creator_group"]
        groups[group]["created"] += int(campaign["spend_minor"])
        if campaign["transfer_out_minor"] is not None:
            groups[group]["transfer_out"] += int(campaign["transfer_out_minor"])
            groups[group]["creator_retained"] += int(campaign["creator_retained_minor"])
        for pricing in campaign["pricing"]:
            totals[pricing["product_id"]]["attributed_units"] += pricing["units"]
        for component in campaign["components"]:
            pid, minor = component["product_id"], int(component["minor"])
            code = component["code"]
            column = "self" if code == "DIRECT" else "halo" if code == "HALO" else "remainder" if code == "REMAINDER" else "protection"
            totals[pid][column] += minor
            if component["origin"] == "TRANSFER":
                groups[products[pid]["group"]]["transfer_in"] += minor
    output_products = []
    for pid in sorted(products, key=lambda pid: (products[pid]["group"], products[pid]["style"], pid)):
        item = {"id": pid, "group": products[pid]["group"], "style": products[pid]["style"], "attributed_units": totals[pid]["attributed_units"]}
        for field in ("product_category", "age_segment", "business_group", "classification_status", "unit"):
            if field in products[pid]:
                item[field] = copy.deepcopy(products[pid][field])
        total = sum(totals[pid][column] for column in ("self", "halo", "protection", "remainder"))
        for column in ("self", "halo", "protection", "remainder"):
            _amounts(item, column, totals[pid][column] if complete else None)
        _amounts(item, "final", total if complete else None)
        _amounts(item, "provisional", total)
        groups[item["group"]]["allocated"] += total
        output_products.append(item)
    output_groups = []
    for group in sorted(groups):
        item = {"group": group}
        for field in ("created", "transfer_out", "transfer_in", "creator_retained"):
            _amounts(item, field, groups[group][field] if complete else None)
        _amounts(item, "final", groups[group]["allocated"] if complete else None)
        output_groups.append(item)
    summary = {}
    _amounts(summary, "spend", source_spend)
    for name, key in (("transfer_out", "transfer_out_minor"), ("creator_retained", "creator_retained_minor"), ("protection", "protection_minor"), ("remainder", "remainder_minor"), ("unallocated", "unallocated_minor")):
        values = [campaign[key] for campaign in result["campaigns"]]
        _amounts(summary, name, sum(int(value) for value in values) if all(value is not None for value in values) else None)
    _amounts(summary, "final", sum(int(item["final_minor"]) for item in output_products) if complete else None)
    _amounts(summary, "transfer_in", sum(groups[group]["transfer_in"] for group in groups) if complete else None)
    result.update({"summary": summary, "products": output_products, "groups": output_groups})
    if complete:
        if int(summary["final_minor"]) != source_spend or summary["transfer_out_minor"] != summary["transfer_in_minor"]:
            raise AllocationInputError("INTERNAL_RECONCILIATION_FAILED")
        for campaign in result["campaigns"]:
            if int(campaign["spend_minor"]) != int(campaign["creator_retained_minor"]) + int(campaign["transfer_out_minor"]):
                raise AllocationInputError("INTERNAL_CAMPAIGN_RECONCILIATION_FAILED")
            if int(campaign["creator_retained_minor"]) != sum(int(campaign[field + "_minor"]) for field in ("direct", "halo", "protection", "remainder")):
                raise AllocationInputError("INTERNAL_COMPONENT_RECONCILIATION_FAILED")
        for group in output_groups:
            if int(group["created_minor"]) - int(group["transfer_out_minor"]) + int(group["transfer_in_minor"]) != int(group["final_minor"]):
                raise AllocationInputError("INTERNAL_GROUP_RECONCILIATION_FAILED")
