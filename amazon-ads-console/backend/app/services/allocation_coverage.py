"""Conservative source-coverage inventory for frozen allocation facts.

Observed rows are never evidence that all reports were delivered. Empty results
are not proof that an account had no ads. A reviewer must certify coverage out
of band before eligibility-negative or financial publication decisions.
"""
from collections import defaultdict
from datetime import date
from .allocation_sources import AD_PRODUCTS, TABLES, validate_scope
from .allocation_store import digest


def _month_bounds(period):
    y, m = map(int, period.split("-"))
    start = date(y, m, 1)
    end = date(y + (m == 12), (m % 12) + 1, 1)
    return start.isoformat(), end.isoformat()


def build_coverage_manifest(scope, captured):
    """Create a matrix of requested vs observed facts, never approve coverage."""
    scope = validate_scope(scope)
    if captured.get("scope") != scope:
        raise ValueError("COVERAGE_SCOPE_MISMATCH")
    if captured.get("content_hash") != digest({k: v for k, v in captured.items() if k != "content_hash"}):
        raise ValueError("CAPTURE_FINGERPRINT_MISMATCH")
    begin, end_exclusive = _month_bounds(scope["period"])
    cells = []
    problems = []
    for table in TABLES:
        rows = captured.get("facts", {}).get(table)
        if not isinstance(rows, list):
            raise ValueError("COVERAGE_FACT_TABLE_MISSING")
        grouped = defaultdict(list)
        for row in rows:
            key = (row.get("account_id"), row.get("ad_product"))
            if key[0] not in scope["account_ids"] or key[1] not in [AD_PRODUCTS[x] for x in scope["ad_products"]]:
                raise ValueError("COVERAGE_FACT_OUT_OF_SCOPE")
            grouped[key].append(row)
        for account in scope["account_ids"]:
            for adtype in scope["ad_products"]:
                product = AD_PRODUCTS[adtype]
                group = grouped[(account, product)]
                files = sorted({str(r["source_file_hash"]) for r in group if r.get("source_file_hash")})
                batches = sorted({str(r["batch_id"]) for r in group if r.get("batch_id") is not None})
                missing_manifest = sum(not all(r.get(c) is not None for c in
                    ("manifest_file_hash", "manifest_start_date", "manifest_end_date")) for r in group)
                cell = {"source_table": "core." + table, "account_id": account,
                    "ad_product": adtype, "period_start": begin, "period_end_exclusive": end_exclusive,
                    "observed_rows": len(group), "observed_files": files, "observed_batches": batches,
                    "missing_batch_manifest_rows": missing_manifest,
                    "coverage_status": "PENDING_REVIEW",
                    "negative_eligibility_proven": False, "complete_request_set_proven": False}
                if not group:
                    problems.append({"code": "NO_ROWS_OBSERVED_NOT_NEGATIVE_PROOF", "source_table": cell["source_table"],
                                     "account_id": account, "ad_product": adtype})
                if missing_manifest:
                    problems.append({"code": "MISSING_BATCH_MANIFEST_FIELDS", "source_table": cell["source_table"],
                                     "account_id": account, "ad_product": adtype, "rows": missing_manifest})
                cells.append(cell)
    result = {"scope": scope, "capture_hash": captured["content_hash"], "cells": cells, "issues": problems,
              "policy": "OBSERVATION_ONLY_NOT_A_SOURCE_COVERAGE_APPROVAL"}
    result["manifest_hash"] = digest(result)
    return result


def check_review_receipt(manifest, receipt):
    """Fail closed until externally confirmed expected request identity and signature.

    Validation is deliberately not implemented because the authority registry,
    review roles, immutable request ledger and signatures are not yet approved.
    """
    if not isinstance(manifest, dict) or not isinstance(receipt, dict):
        raise ValueError("COVERAGE_RECEIPT_INVALID")
    raise ValueError("COVERAGE_SIGNOFF_ADAPTER_NOT_CONFIGURED")
