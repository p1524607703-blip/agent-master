"""Deterministic, read-only comparison of app and ops_products financial mappings.

This does not choose an authority or produce an approved mapping version.
Every account alias and approved status must be supplied explicitly.
"""
from datetime import date
from .allocation_store import digest


def _value(row, name):
    value = row.get(name)
    return value.strip() if isinstance(value, str) else ""


def _key_text(row, name):
    return _value(row, name).upper()


def _issue(code, source, key, **details):
    return {"code": code, "source": source, "key": list(key), **details}


def _normalize(rows, source, kind, account_registry, approved_statuses, as_of):
    index, problems = {}, []
    if not isinstance(rows, list):
        raise ValueError("MAPPING_ROWS_MUST_BE_LIST")
    for index_no, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(_issue("INVALID_MAPPING_ROW", source, (index_no,)))
            continue
        account_label = _value(row, "account_scope")
        account_id = account_registry.get(account_label)
        local_key = _key_text(row, "child_asin" if kind == "child" else "parent_asin")
        key = (account_id or account_label or "<unknown>", local_key)
        if not account_id:
            problems.append(_issue("ACCOUNT_SCOPE_UNRESOLVED", source, key, account_scope=account_label))
        if not local_key:
            problems.append(_issue("EMPTY_ASIN", source, key))
        if kind == "child" and not _key_text(row, "parent_asin"):
            problems.append(_issue("MISSING_PARENT", source, key))
        status = _value(row, "mapping_status")
        if status not in approved_statuses:
            problems.append(_issue("STATUS_NOT_APPROVED", source, key, mapping_status=status))
        if status.lower().startswith("blocked") or status.lower().startswith("conflict"):
            problems.append(_issue("BLOCKED_MAPPING", source, key, mapping_status=status))
        effective = _value(row, "effective_date")
        expires = _value(row, "effective_to")
        try:
            if not effective or date.fromisoformat(effective) > as_of:
                problems.append(_issue("EFFECTIVE_DATE_NOT_CONFIRMED", source, key, effective_date=effective))
            if expires and date.fromisoformat(expires) < as_of:
                problems.append(_issue("MAPPING_EXPIRED", source, key, effective_to=expires))
        except ValueError:
            problems.append(_issue("EFFECTIVE_DATE_INVALID", source, key, effective_date=effective, effective_to=expires))
        product_code = _value(row, "product_code")
        group = _value(row, "operator_group").upper()
        if not product_code or not group:
            problems.append(_issue("FINANCIAL_PRODUCT_INCOMPLETE", source, key))
        normalized = {
            "account_id": account_id or "",
            "financial_product": (group, product_code),
            "parent_asin": _key_text(row, "parent_asin"),
            "child_asin": _key_text(row, "child_asin") if kind == "child" else None,
            "mapping_status": status,
            "effective_date": effective,
            "effective_to": expires,
        }
        if key in index:
            problems.append(_issue("DUPLICATE_MAPPING_KEY", source, key,
                                   previous_financial_product=list(index[key]["financial_product"]),
                                   financial_product=list(normalized["financial_product"])))
        else:
            index[key] = normalized
    return index, problems


def reconcile(app, warehouse, account_registry, approved_statuses=None, as_of=None):
    """Compare frozen read-only data; do not infer authority from a matching label.

    app and warehouse must each carry 'child' and 'parent' row collections.
    account_registry maps every source account alias to a known canonical ID;
    no account display name is interpreted as an account ID automatically.
    """
    if not isinstance(account_registry, dict) or not account_registry:
        raise ValueError("EXPLICIT_ACCOUNT_REGISTRY_REQUIRED")
    if not all(isinstance(k, str) and isinstance(v, str) and k.strip() and v.strip()
               for k, v in account_registry.items()):
        raise ValueError("ACCOUNT_REGISTRY_INVALID")
    if not isinstance(app, dict) or not isinstance(warehouse, dict):
        raise ValueError("EXPLICIT_MAPPING_SNAPSHOTS_REQUIRED")
    if approved_statuses is None:
        approved_statuses = set()
    if not isinstance(approved_statuses, (set, list, tuple)):
        raise ValueError("APPROVAL_STATUS_SET_INVALID")
    approved = set(approved_statuses)
    if as_of is None:
        raise ValueError("EXPLICIT_EFFECTIVE_DATE_REQUIRED")
    day = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    if not isinstance(day, date):
        raise ValueError("EFFECTIVE_DATE_INVALID")

    issues, matched = [], {}
    for kind in ("child", "parent"):
        x, i1 = _normalize(app.get(kind), "app", kind, account_registry, approved, day)
        y, i2 = _normalize(warehouse.get(kind), "ops_products", kind, account_registry, approved, day)
        issues.extend(i1 + i2)
        for key in sorted(x.keys() | y.keys()):
            if key not in x or key not in y:
                issues.append(_issue("ONLY_ONE_SOURCE", "app" if key in x else "ops_products",
                                     key, kind=kind))
                continue
            left, right = x[key], y[key]
            fields = ("financial_product", "parent_asin", "effective_date", "effective_to")
            diff = [field for field in fields if left[field] != right[field]]
            if diff:
                issues.append(_issue("FINANCIAL_MAPPING_CONFLICT", "both", key, kind=kind,
                                     fields=diff, app_financial_product=list(left["financial_product"]),
                                     warehouse_financial_product=list(right["financial_product"])))
            else:
                matched[(kind,) + key] = {"kind": kind, "account_id": key[0], "asin": key[1],
                                         "financial_product": list(left["financial_product"])}
    issues.sort(key=lambda i: (i["code"], i["source"], str(i["key"]), i.get("kind", "")))
    result = {"ready_for_financial_use": not issues and bool(matched),
              "authority_selected": False, "applied": False,
              "compared_as_of": day.isoformat(), "matched_count": len(matched),
              "matching": sorted(matched.values(), key=lambda r: (r["kind"], r["account_id"], r["asin"])),
              "issues": issues, "source": "EXPLICIT_FROZEN_SNAPSHOTS_ONLY"}
    # Even fully matching records do not constitute independent approval.
    result["ready_for_financial_use"] = False
    result["reconciliation_hash"] = digest(result)
    return result
