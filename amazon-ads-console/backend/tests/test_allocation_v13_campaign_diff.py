import csv
from decimal import Decimal
from pathlib import Path

import pytest

from scripts.allocation_v13_campaign_diff import build_priority_rows


HEADERS = ["来源","Campaign ID","Campaign名称","旧创建组","新创建组","确认版花费",
           "当前同范围花费","新版减旧版","当前原始双数","当前待计价成本","覆盖关系"]


def sample_file(tmp_path: Path, values):
    path = tmp_path / "sample.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fd:
        writer = csv.DictWriter(fd, HEADERS)
        writer.writeheader()
        for i, (old, new, diff) in enumerate(values):
            writer.writerow({"来源":"AMS", "Campaign ID":str(i + 1), "确认版花费":old,
                             "当前同范围花费":new, "新版减旧版":diff})
    return path


def test_threshold_and_conservation(tmp_path):
    path = sample_file(tmp_path, [("10.00", "8.00", "-2.00"),
                                  ("1.00", "0.99", "-0.01"),
                                  ("5.00", "5.00", "0")])
    rows, stats = build_priority_rows(path)
    assert (stats["campaigns"], stats["changed"], stats["high"], stats["low"], stats["unchanged"]) == (3, 2, 1, 1, 1)
    assert stats["delta"] == Decimal("-2.01")
    assert rows[0]["Campaign ID"] == "1"
    assert stats["old_total"] + stats["delta"] == stats["new_total"]


def test_reject_duplicate_campaign_key(tmp_path):
    path = sample_file(tmp_path, [("10", "8", "-2"), ("10", "9", "-1")])
    content = path.read_text(encoding="utf-8-sig").replace(",2,", ",1,")
    path.write_text(content, encoding="utf-8-sig")
    with pytest.raises(ValueError, match="duplicate"):
        build_priority_rows(path)


def test_reject_inconsistent_row_amount(tmp_path):
    path = sample_file(tmp_path, [("10", "8", "-1")])
    with pytest.raises(ValueError, match="reconcile"):
        build_priority_rows(path)


def test_reject_nonfinite_and_negative_threshold(tmp_path):
    path = sample_file(tmp_path, [("NaN", "8", "-2")])
    with pytest.raises(ValueError, match="nonfinite"):
        build_priority_rows(path)
    with pytest.raises(ValueError, match="threshold"):
        build_priority_rows(path, Decimal("-1"))
