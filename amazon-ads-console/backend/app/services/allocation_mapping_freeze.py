"""Immutable mapping approval *request*; no approval authority is installed.

Uses the two-source reconciliation. Matching app/V2 rows are candidates, not
permission to change operational ownership or finance accounting.
"""
from datetime import date

from .allocation_mapping_audit import reconcile
from .allocation_store import digest


class MappingFreezeError(ValueError):
    pass


def _require_registry(registry, accounts):
    if not isinstance(registry, dict) or not registry:
        raise MappingFreezeError("EXPLICIT_ACCOUNT_REGISTRY_REQUIRED")
    if not isinstance(accounts, list) or not accounts or not all(isinstance(a, str) and a for a in accounts):
        raise MappingFreezeError("EXPLICIT_ACCOUNT_SCOPE_REQUIRED")
    if len(set(accounts)) != len(accounts):
        raise MappingFreezeError("DUPLICATE_ACCOUNT_SCOPE")
    if set(accounts) - set(registry.values()):
        raise MappingFreezeError("ACCOUNT_SCOPE_NOT_IN_REGISTRY")
    if any(not k or not v or not isinstance(k, str) or not isinstance(v, str) for k,v in registry.items()):
        raise MappingFreezeError("INVALID_ACCOUNT_REGISTRY")


def freeze_review_request(app, warehouse, account_registry, approved_statuses,
                          as_of, account_ids, reviewer_scope):
    """Deterministic request for human review; no state may be auto-approved."""
    _require_registry(account_registry, account_ids)
    if not isinstance(approved_statuses, (set, list, tuple)) or not approved_statuses:
        raise MappingFreezeError("STATUS_ALLOWLIST_REQUIRED")
    if not isinstance(reviewer_scope, str) or not reviewer_scope.strip():
        raise MappingFreezeError("REVIEW_SCOPE_REQUIRED")
    try:
        day = date.fromisoformat(as_of)
    except (TypeError, ValueError) as e:
        raise MappingFreezeError("EFFECTIVE_DATE_REQUIRED") from e
    if not isinstance(app, dict) or not isinstance(warehouse, dict):
        raise MappingFreezeError("TWO_SOURCE_SNAPSHOTS_REQUIRED")
    if not all(isinstance(app.get(k), list) and isinstance(warehouse.get(k), list)
               for k in ("child", "parent")):
        raise MappingFreezeError("MAPPING_COLLECTION_MISSING")
    report = reconcile(app, warehouse, account_registry,
                       approved_statuses=set(approved_statuses), as_of=as_of)
    selected_accounts = set(account_ids)
    foreign = [m for m in report["matching"] if m["account_id"] not in selected_accounts]
    if foreign:
        # An in-scope financial version must never be built from other account mappings.
        raise MappingFreezeError("CROSS_ACCOUNT_FINANCIAL_MAPPING")
    issues = list(report["issues"])
    pending = ["FINANCIAL_AUTHORITY_NOT_SELECTED",
               "TRUSTED_APPROVAL_SIGNATURE_NOT_CONFIGURED",
               "FINANCIAL_EFFECTIVE_VERSION_NOT_INSTALLED"]
    if issues:
        pending.insert(0,"APP_AND_WAREHOUSE_RECONCILIATION_ISSUES")
    package = {"schema_version": "mapping-freeze-review-v1", "as_of": day.isoformat(),
               "account_ids": sorted(account_ids), "reviewer_scope": reviewer_scope.strip(),
               "app_hash": digest(app), "warehouse_hash": digest(warehouse),
               "account_registry_hash": digest(account_registry),
               "technical_comparison_hash": report["reconciliation_hash"],
               "candidate_products": report["matching"], "technical_issues": issues,
               "status": "AWAITING_INDEPENDENT_APPROVAL",
               "financial_approved": False, "authority_selected": None,
               "apply_allowed": False, "pending": pending}
    package["request_hash"] = digest(package)
    return package


def verify_review_request(package, *, app=None, warehouse=None):
    """Verify review request hasn't changed since the freeze."""
    if not isinstance(package, dict):
        raise MappingFreezeError("REVIEW_REQUEST_REQUIRED")
    h = package.get("request_hash")
    if not isinstance(h, str) or h != digest({k: v for k,v in package.items() if k != "request_hash"}):
        raise MappingFreezeError("MAPPING_REVIEW_REQUEST_TAMPERED")
    if app is not None and digest(app) != package.get("app_hash"):
        raise MappingFreezeError("APP_MAPPING_DRIFTED")
    if warehouse is not None and digest(warehouse) != package.get("warehouse_hash"):
        raise MappingFreezeError("WAREHOUSE_MAPPING_DRIFTED")
    if package.get("financial_approved") is not False or package.get("apply_allowed") is not False:
        raise MappingFreezeError("UNVERIFIED_APPROVAL_FORBIDDEN")
    return {"request_hash": h, "integrity": "HASH_VERIFIED",
            "financial_approved": False, "apply_allowed": False}


def accept_mapping_approval(package, receipt):
    """Fail closed until the IAM/administrator signature verifier is implemented."""
    verify_review_request(package)
    if not isinstance(receipt, dict) or not receipt:
        raise MappingFreezeError("APPROVAL_RECEIPT_REQUIRED")
    raise MappingFreezeError("TRUSTED_APPROVAL_VERIFIER_UNAVAILABLE")
