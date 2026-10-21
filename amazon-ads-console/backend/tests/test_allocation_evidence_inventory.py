import copy
import csv
import json
from pathlib import Path

import pytest
from app.services.allocation_evidence_inventory import (
    build_evidence_inventory, verify_evidence_inventory, EvidenceInventoryError)


def test_file_presence_never_means_approved(tmp_path):
    (tmp_path / "2026年9月_广告费用分摊_SOP_V2.3.1_试算待核验.xlsx").write_bytes(b"fake")
    r = build_evidence_inventory(tmp_path, expected=["approved_11sheet_template"])
    assert r["file_count"] == 1
    assert r["files"][0]["evidence_class"] == "UNAPPROVED_TRIAL"
    assert not r["original_11sheet_verified"] and not r["may_publish"]
    assert "INVENTORY" in r["source"]


def test_fingerprint_reproducibility_and_tamper(tmp_path):
    p=tmp_path/"report.csv"
    p.write_text("campaign_id,stat_date\n00001,2026-09-01\n",encoding="utf-8")
    r=build_evidence_inventory(tmp_path)
    assert r["inventory_hash"] == build_evidence_inventory(tmp_path)["inventory_hash"]
    assert verify_evidence_inventory(r)
    r["file_count"]=12
    with pytest.raises(EvidenceInventoryError,match="TAMPERED"):
        verify_evidence_inventory(r)


def test_csv_header_and_date_are_only_samples(tmp_path):
    p=tmp_path/"campaign.csv"
    p.write_text("campaign_id,stat_date,source_file_hash,account_id\n00001,2026-09-01,ff,account\n",encoding="utf-8")
    r=build_evidence_inventory(tmp_path)
    preview=r["files"][0]["preview"]
    assert preview["sample_dates"]==["2026-09-01"]
    assert preview["sample_accounts"]==["account"]
    assert preview["has_campaign_id_column"]


def test_duplicate_content_is_visible_without_double_count(tmp_path):
    (tmp_path/"a.csv").write_bytes(b"same")
    (tmp_path/"b.csv").write_bytes(b"same")
    r=build_evidence_inventory(tmp_path)
    assert len(r["identical_file_groups"])==1
    assert not r["source_coverage_proven"]


def test_symlink_is_not_followed(tmp_path):
    inner=tmp_path/"inner";inner.mkdir()
    outside=tmp_path.parent/"outer-facts.csv"
    outside.write_bytes(b"secret")
    (inner/"traversal.csv").symlink_to(outside)
    r=build_evidence_inventory(tmp_path)
    assert r["file_count"]==0
    outside.unlink()


def test_expected_kinds_reject_typo(tmp_path):
    with pytest.raises(EvidenceInventoryError,match="EXPECTED_SOURCE"):
        build_evidence_inventory(tmp_path,expected=["other"])
