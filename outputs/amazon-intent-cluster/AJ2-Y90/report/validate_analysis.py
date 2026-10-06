import importlib.util
import json
from collections import Counter
from pathlib import Path

root = Path.cwd()
base = root / "outputs/amazon-intent-cluster/AJ2-Y90"
responses = base / "_audit/responses"
manifests = base / "_audit/manifests"
report_dir = base / "report"

spec = importlib.util.spec_from_file_location(
    "pipeline", root / ".opencode/skills/amazon-search-intent/scripts/run_pipeline.py"
)
pipeline = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(pipeline)

raw = []
normalized = []
for prefix, count in (("pilot", 5), ("full", 115)):
    for number in range(1, count + 1):
        batch = f"{prefix}-{number:04d}"
        response = json.loads((responses / f"{batch}.json").read_text(encoding="utf-8"))
        manifest = json.loads((manifests / f"{batch}.json").read_text(encoding="utf-8"))
        items = {item["term_id"]: item for item in manifest["terms"]}
        facts = {fact["id"] for fact in manifest["product_baseline"]["facts"]}
        for record in response["records"]:
            raw.append(record)
            normalized.append(
                pipeline.normalize_model_record(
                    record,
                    items[record["term_id"]],
                    facts,
                    manifest["run_id"],
                    manifest["model_name"],
                )
            )

assert len(raw) == 2394
assert len({row["term_id"] for row in raw}) == 2394

review = Counter(row["review_status"] for row in normalized)
fit = Counter(row["asin_fit"] for row in normalized)
raw_clusters = Counter(row["intent_cluster"] for row in raw)

flip_values = {"flip_flop", "flip_flops", "thong_sandal", "thong_sandals", "arch_support_flip_flops"}
sandal_values = {"sandal", "sandals", "womens_sandal", "orthopedic_sandals"}
women_values = {"women", "womens", "female", "ladies"}
core_product = sum(bool(set(row.get("product_type", [])) & (flip_values | sandal_values)) for row in normalized)
women = sum(bool(set(row.get("audience_intent", [])) & women_values) for row in normalized)

results = json.loads((report_dir / "analysis_results.json").read_text(encoding="utf-8"))
checks = {
    "unique_keyword_terms": (len(raw), 2394),
    "accepted_terms": (review["accepted"], 2315),
    "needs_review_terms": (review["needs_review"], 79),
    "normalized_fit_match": (fit["match"], 1122),
    "normalized_fit_partial": (fit["partial_match"], 954),
    "normalized_fit_mismatch": (fit["mismatch"], 311),
    "normalized_fit_unknown": (fit["unknown"], 7),
    "raw_cluster_count": (len(raw_clusters), 1674),
    "raw_singletons": (sum(value == 1 for value in raw_clusters.values()), 1433),
    "core_flipflop_or_sandal": (core_product, 2332),
    "women_audience": (women, 1565),
    "report_headline_total": (results["headline"]["unique_keyword_terms"], 2394),
}

failed = {key: value for key, value in checks.items() if value[0] != value[1]}
payload = {
    "status": "pass" if not failed else "fail",
    "confidence": "share_with_caveats",
    "checks": {key: {"actual": actual, "expected": expected} for key, (actual, expected) in checks.items()},
    "failed": failed,
    "caveats": [
        "唯一搜索词等权占比不等于用户人数、搜索量、曝光或点击占比。",
        "主题为多标签，主题占比不可相加。",
        "79条needs_review保留在全量统计中；排除后的最大主题差异为0.3个百分点。",
        "Raw intent_cluster高度碎片化，正式结论使用上层同义归并。",
        "打标和报告均未使用ACOS、CVR、点击、订单等绩效指标。",
    ],
}
(report_dir / "validation_summary.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(payload, ensure_ascii=False, indent=2))
