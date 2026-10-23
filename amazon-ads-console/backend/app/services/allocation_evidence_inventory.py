"""Filesystem-only financial evidence index; no database or network requests.

No file name, file presence, or row sample can prove financial approval.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path
from .allocation_store import digest

MAX_FILES = 1000
ALLOWED = {".csv", ".xlsx", ".json", ".zip"}
CSV_SAMPLE_ROWS = 20
SOURCE_KINDS = {"campaign_daily", "advertised_product_daily", "purchased_product_daily",
                "approved_11sheet_template"}


class EvidenceInventoryError(ValueError):
    pass


def _recognize(name):
    lower = name.lower()
    if "v2.3.1" in lower or "试算待核验" in lower:
        return "UNAPPROVED_TRIAL"
    if "v2.10.3" in lower and lower.endswith(".xlsx"):
        return "HISTORICAL_REFERENCE_CANDIDATE_UNVERIFIED"
    return "UNCLASSIFIED_UNVERIFIED"


def _sha256_file(path):
    result = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            result.update(chunk)
    return result.hexdigest()


def _inspect_csv(path):
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            samples = []
            for _, row in zip(range(CSV_SAMPLE_ROWS), reader):
                samples.append(row)
    except (UnicodeError, csv.Error, OSError):
        return {"status": "CSV_PREVIEW_UNAVAILABLE", "columns": [], "sampled_rows": 0}
    if not fields:
        return {"status": "EMPTY_OR_HEADERLESS", "columns": [], "sampled_rows": 0}
    lower_columns = {str(c).casefold() for c in fields if c is not None}
    candidate_dates = ("stat_date", "date", "日期", "report_date")
    candidate_accounts = ("account_id", "advertising_account_id", "广告账户id")
    date_field = next((s for s in fields if s and s.casefold() in candidate_dates), None)
    account_field = next((s for s in fields if s and s.casefold() in candidate_accounts), None)
    dates = sorted({v for row in samples if (v := row.get(date_field))} if date_field else [])
    accounts = sorted({v for row in samples if (v := row.get(account_field))} if account_field else [])
    return {"status": "CSV_SAMPLE_ONLY", "columns": fields[:100],
            "sampled_rows": len(samples), "sample_dates": dates[:20],
            "sample_accounts": accounts[:20],
            "has_campaign_id_column": "campaign_id" in lower_columns,
            "has_source_file_hash_column": "source_file_hash" in lower_columns}


def _inspect_xlsx(path):
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) > 20000:
                raise EvidenceInventoryError("XLSX_ENTRY_LIMIT_EXCEEDED")
            return {"status": "XLSX_ZIP_CONTAINS_WORKBOOK" if "xl/workbook.xml" in names
                    else "XLSX_INVALID_STRUCTURE",
                    "worksheet_parts": len([n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)])}
    except (zipfile.BadZipFile, OSError):
        return {"status": "XLSX_UNREADABLE"}


def build_evidence_inventory(directory, *, expected=None):
    """Inventory files under user-selected root, avoiding symlink escapes."""
    root = Path(directory).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise EvidenceInventoryError("EVIDENCE_ROOT_NOT_DIRECTORY")
    expected = expected or []
    if not isinstance(expected, list) or any(k not in SOURCE_KINDS for k in expected):
        raise EvidenceInventoryError("EXPLICIT_EXPECTED_SOURCE_KIND_REQUIRED")
    files = []
    for p in sorted(root.rglob("*")):
        if p.is_symlink() or not p.is_file() or p.suffix.lower() not in ALLOWED:
            continue
        if not p.resolve().is_relative_to(root):
            raise EvidenceInventoryError("FILE_PATH_OUTSIDE_EVIDENCE_ROOT")
        if len(files) >= MAX_FILES:
            raise EvidenceInventoryError("EVIDENCE_FILE_LIMIT_EXCEEDED")
        # Hash is the only full-file operation; previews stay bounded.
        item = {"file": str(p.relative_to(root)), "bytes": p.stat().st_size,
                "sha256": _sha256_file(p),
                "evidence_class": _recognize(p.name), "financial_approved": False}
        if p.suffix.lower() == ".csv":
            item["preview"] = _inspect_csv(p)
        elif p.suffix.lower() == ".xlsx":
            item["preview"] = _inspect_xlsx(p)
        files.append(item)
    seen_hashes = {}
    duplicate_files = []
    for item in files:
        h = item["sha256"]
        if h in seen_hashes:
            duplicate_files.append({"same_hash": h, "first": seen_hashes[h], "other": item["file"]})
        else:
            seen_hashes[h] = item["file"]
    result = {"source": "LOCAL_FILE_INVENTORY_ONLY", "root": str(root),
              "file_count": len(files), "files": files,
              "identical_file_groups": duplicate_files,
              "expected_source_kinds": expected,
              "source_coverage_proven": False, "original_11sheet_verified": False,
              "real_monthly_finance_replayed": False, "may_publish": False,
              "blockers": ["REPORT_REQUEST_LEDGER_NOT_VERIFIED",
                           "AUTHORITATIVE_11SHEET_TEMPLATE_NOT_ATTESTED",
                           "SAME_SCOPE_RAW_FACTS_NOT_ATTESTED",
                           "BUSINESS_BINDINGS_AND_APPROVALS_NOT_ATTESTED"]}
    result["inventory_hash"] = digest(result)
    return result


def verify_evidence_inventory(value):
    if not isinstance(value, dict) or value.get("inventory_hash") != digest(
            {k: v for k, v in value.items() if k != "inventory_hash"}):
        raise EvidenceInventoryError("EVIDENCE_INVENTORY_TAMPERED")
    return True


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(description="Offline hash inventory, NOT financial approval")
    parser.add_argument("directory")
    parser.add_argument("--output", help="JSON file; default stdout")
    args = parser.parse_args(argv)
    result = build_evidence_inventory(args.directory,
        expected=["campaign_daily", "advertised_product_daily",
                  "purchased_product_daily", "approved_11sheet_template"])
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
