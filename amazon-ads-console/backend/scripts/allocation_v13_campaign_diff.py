"""Offline comparison of an old/new Campaign spend snapshot.

This script does not access a database or compute approved financial allocations.
"""
from __future__ import annotations

import argparse
import csv
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

FIELDS = (
    "差额等级", "来源", "Campaign ID", "Campaign名称", "旧创建组", "新创建组",
    "确认版花费", "当前同范围花费", "新版减旧版", "差额绝对值",
    "当前原始双数", "当前待计价成本", "覆盖关系", "原因结论",
)


def build_priority_rows(input_path: Path, threshold: Decimal = Decimal("2")):
    if threshold < 0:
        raise ValueError("threshold must be >= 0")
    with Path(input_path).open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise ValueError("empty campaign comparison")
    keys = set()
    total = Decimal("0")
    old_total = Decimal("0")
    new_total = Decimal("0")
    stats = {"changed": 0, "high": 0, "low": 0, "unchanged": 0}
    for row in rows:
        key = (row.get("来源", ""), row.get("Campaign ID", ""))
        if not all(key) or key in keys:
            raise ValueError("empty or duplicate (source, campaign_id) key")
        keys.add(key)
        try:
            old = Decimal(row["确认版花费"])
            new = Decimal(row["当前同范围花费"])
            delta = Decimal(row["新版减旧版"])
        except (KeyError, InvalidOperation, TypeError) as exc:
            raise ValueError("invalid decimal amount") from exc
        if not all(x.is_finite() for x in (old, new, delta)):
            raise ValueError("nonfinite amount")
        if abs(new - old - delta) > Decimal("0.00001"):
            raise ValueError("row spend does not reconcile")
        if delta:
            stats["changed"] += 1
            if abs(delta) >= threshold:
                row["差额等级"] = "重点核查(≥$2)" if threshold == 2 else "重点核查"
                stats["high"] += 1
            else:
                row["差额等级"] = "小额守恒留底(<$2)" if threshold == 2 else "小额守恒留底"
                stats["low"] += 1
        else:
            stats["unchanged"] += 1
            row["差额等级"] = "无差异"
        row["差额绝对值"] = str(abs(delta))
        row["原因结论"] = "未解释，须对齐来源请求/归因时点/财务规则" if delta else "金额未变，仍需同口径确认"
        total += delta
        old_total += old
        new_total += new
    rows.sort(key=lambda r: (-Decimal(r["差额绝对值"]), r["来源"], r["Campaign ID"]))
    stats.update({"campaigns": len(rows), "delta": total, "old_total": old_total, "new_total": new_total})
    return rows, stats


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only 9月Campaign spend snapshot comparison")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--threshold", type=Decimal, default=Decimal("2"))
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output cannot be identical")
    rows, stats = build_priority_rows(args.input, args.threshold)
    if args.summary:
        expected = json.loads(args.summary.read_text(encoding="utf-8"))
        if (
            stats["campaigns"] != int(expected["old_campaigns"])
            or stats["changed"] != int(expected["campaign_spend_changed"])
            or abs(stats["delta"] - Decimal(str(expected["comparable_spend_diff"]))) > Decimal("0.00001")
        ):
            raise ValueError("comparison summary does not reconcile")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.DictWriter(out, FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({k: str(v) if isinstance(v, Decimal) else v for k, v in stats.items()}, ensure_ascii=False))


if __name__ == "__main__":
    main()
