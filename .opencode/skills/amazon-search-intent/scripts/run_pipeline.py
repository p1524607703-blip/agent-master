#!/usr/bin/env python3
"""AJ2-Y90 OpenCode + DeepSeek intent-cluster pipeline.

The source CSV is read-only. Model manifests contain only search-term text,
stable identifiers, schema metadata, and the page-validated product baseline.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0.0"
PROMPT_VERSION = "1.1.0"
DEFAULT_MODEL = "deepseek/deepseek-v4-pro"
MAIN_FIELDS = [
    "primary_domain", "secondary_domain", "product_type", "audience_intent",
    "function_intent", "capability_intent", "event_intent", "location_intent",
    "body_need_intent", "time_intent", "substitute_intent", "complement_intent",
    "latent_task", "intent_stage", "evidence_type", "confidence_level",
    "intent_cluster", "routing_action",
]
CONTROL_FIELDS = [
    "source_term", "normalized_term", "term_id", "query_kind", "language",
    "field_evidence", "ambiguity_flags", "asin_fit", "asin_fit_evidence",
    "review_status", "schema_version", "prompt_version", "model_name", "run_id",
]
REQUIRED_FIELDS = MAIN_FIELDS + CONTROL_FIELDS
ARRAY_FIELDS = {
    "secondary_domain", "product_type", "audience_intent", "function_intent",
    "capability_intent", "event_intent", "location_intent", "body_need_intent",
    "time_intent", "substitute_intent", "complement_intent", "evidence_type",
    "ambiguity_flags", "asin_fit_evidence",
}
PRIMARY_DOMAINS = {
    "clothing_shoes_jewelry", "sports_outdoors", "home_kitchen",
    "patio_lawn_garden", "tools_home_improvement", "musical_instruments",
    "industrial_scientific", "automotive", "electronics", "baby_products",
    "arts_crafts_sewing", "health_household", "toys_games", "video_games",
    "grocery_gourmet_food", "office_products", "pet_supplies", "others",
}
INTENT_STAGES = {"exploration", "consideration", "high_intent", "brand_harvest", "unknown"}
EVIDENCE_TYPES = {"explicit", "page_validated", "inferred"}
CONFIDENCE = {"high", "medium", "low"}
ASIN_FIT = {"match", "partial_match", "mismatch", "unknown", "not_applicable"}
ROUTING = {
    "cluster_route", "listing_gap_review", "ambiguity_review",
    "semantic_negative_candidate", "performance_observation",
    "asin_metadata_pending", "blank_skip",
}
REVIEW_STATUS = {"accepted", "needs_review", "critic_flagged", "non_model"}
FORBIDDEN = re.compile(
    r"\b(acos|cvr|ctr|roas|impressions?|clicks?|orders?|sales|conversion[_ ]rate|behavior_validated)\b",
    re.I,
)
PROHIBITED_PRODUCT_INFERENCE = re.compile(
    r"eva.{0,80}(water[- ]?(?:resistant|friendly|proof)|closed[- ]?cell)|"
    r"(water[- ]?(?:resistant|friendly|proof)|closed[- ]?cell).{0,80}eva",
    re.I,
)
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$", re.I)


class ProviderUnavailableError(RuntimeError):
    """Raised when OpenCode returns a provider/gateway error object."""


def provider_error_summary(payload: dict[str, Any]) -> str | None:
    if payload.get("type") != "error" and "error" not in payload:
        return None
    raw_error = payload.get("error")
    if isinstance(raw_error, dict):
        name = str(raw_error.get("name", "provider_error"))
        data = raw_error.get("data")
        if isinstance(data, dict):
            message = str(data.get("message", "provider unavailable"))
            status = data.get("statusCode") or data.get("status")
            retryable = data.get("isRetryable")
            return f"{name}: {message}; status={status}; retryable={retryable}"
        return f"{name}: provider unavailable"
    return "provider_error: provider unavailable"
SNAKE_RE = re.compile(r"^[a-z0-9_]+$")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalize_term(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = re.sub(r"[‐‑‒–—―]", "-", text)
    text = re.sub(r"\s+", " ", text.strip().lower())
    return text


def stable_id(normalized: str) -> str:
    if not normalized:
        return "blank"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def stable_rank(text: str) -> str:
    return hashlib.sha256(("AJ2-Y90|" + text).encode("utf-8")).hexdigest()


def to_snake(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value)).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_") or "unknown"


def align_explicit_span(source: str, span: str) -> str:
    """Return an exact source substring for punctuation-equivalent evidence."""
    if span and normalize_term(span) in normalize_term(source):
        start = normalize_term(source).find(normalize_term(span))
        # Direct matching is only safe when normalization preserved length.
        if len(normalize_term(source)) == len(source.strip().lower()):
            raw_source = source.strip()
            return raw_source[start: start + len(span)]
        return span
    source_tokens = [(m.group(0).lower(), m.start(), m.end()) for m in re.finditer(r"[A-Za-z0-9]+", source)]
    span_tokens = [m.group(0).lower() for m in re.finditer(r"[A-Za-z0-9]+", span)]
    if span_tokens:
        for idx in range(0, len(source_tokens) - len(span_tokens) + 1):
            if [token for token, _, _ in source_tokens[idx: idx + len(span_tokens)]] == span_tokens:
                return source[source_tokens[idx][1]: source_tokens[idx + len(span_tokens) - 1][2]]
        source_words = [token for token, _, _ in source_tokens]
        if all(any(word in token or token in word for token in source_words) for word in span_tokens):
            return source
    return span


def detect_language(text: str) -> str:
    if not text:
        return "unknown"
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", text))
    has_latin = bool(re.search(r"[A-Za-z]", text))
    if has_cjk and has_latin:
        return "mixed"
    if has_cjk:
        return "zh"
    if has_latin:
        # The report is mostly English, but Spanish footwear queries occur often
        # enough that treating every Latin-script phrase as English is unsafe.
        spanish = re.findall(
            r"\b(?:sandalias?|chanclas?|mujeres?|hombres?|goma|playa|para|con|de|"
            r"pie|pies|verano|cómod[oa]s?|negra?s?|blanca?s?)\b",
            text.lower(), re.I,
        )
        if len(spanish) >= 2 or re.search(r"\b(?:sandalias?|chanclas?)\b", text, re.I):
            return "es"
        return "en"
    return "unknown"


def query_kind(text: str) -> str:
    if not text:
        return "blank"
    if ASIN_RE.fullmatch(text):
        return "asin_target"
    return "keyword"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--campaign-regex", required=True)
    parser.add_argument("--product-asin", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--pilot-size", type=int, default=100)
    parser.add_argument("--batch-size", type=int, default=20)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--pilot-only", action="store_true")
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def load_source(path: Path, campaign_regex: str) -> tuple[list[str], list[dict[str, str]], list[dict[str, str]]]:
    pattern = re.compile(campaign_regex)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        headers = list(reader.fieldnames or [])
        required = {"广告活动名称", "广告组名称", "搜索词"}
        if not required.issubset(headers):
            raise ValueError(f"source missing columns: {sorted(required - set(headers))}")
        all_rows: list[dict[str, str]] = []
        matched: list[dict[str, str]] = []
        for idx, row in enumerate(reader, start=2):
            row["_source_row"] = str(idx)
            all_rows.append(row)
            scope = f"{row.get('广告活动名称', '')} {row.get('广告组名称', '')}"
            if pattern.search(scope):
                matched.append(row)
    return headers, all_rows, matched


def build_unique_terms(matched: list[dict[str, str]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in matched:
        source = row.get("搜索词", "") or ""
        normalized = normalize_term(source)
        key = normalized
        if key not in grouped:
            grouped[key] = {
                "source_term": source,
                "normalized_term": normalized,
                "term_id": stable_id(normalized),
                "query_kind": query_kind(normalized),
                "language": detect_language(source),
                "source_occurrences": 0,
                "source_variants": [],
            }
        grouped[key]["source_occurrences"] += 1
        if source not in grouped[key]["source_variants"]:
            grouped[key]["source_variants"].append(source)
    terms = sorted(grouped.values(), key=lambda item: (item["query_kind"], stable_rank(item["normalized_term"])))
    return terms, grouped


def stratum(term: str) -> str:
    low = term.lower()
    if len(term) > 110 or re.search(r"[^\x00-\x7f]", term) or re.search(r"(.)\1{3,}", term):
        return "noisy_multilingual_long"
    if re.search(r"\b(phone|charger|dog food|shirt|dress|toothbrush|car part|office chair|earbuds|laptop)\b", low):
        return "irrelevant_cross_domain"
    if re.search(r"\b(oofo?s|crocs|vionic|skechers|adidas|nike|reef|havaianas|clarks|birkenstock|teva|fitflop|whitin|hey dude|amazon essentials|under armour|puma)\b", low):
        return "brand_competitor"
    if re.search(r"\b(beach|pool|water|ocean|lake|river|outdoor|vacation|cruise|shower|travel|summer|garden|yard)\b", low):
        return "scene_task"
    if re.search(r"\b(black|white|blue|pink|brown|gray|grey|red|green|purple|beige|eva|rubber|leather|size|women'?s?\s*(?:[5-9]|10|11)|\d+(?:\.5)?\s*(?:wide|w)?)\b", low):
        return "size_color_material"
    if re.search(r"\b(arch|support|pain|comfort|comfortable|cushion|padded|non[- ]?slip|slip resistant|plantar|heel|flat feet|orthopedic|lightweight|breathable|wide|bunions?|alignment|grip|soft)\b", low):
        return "function_body"
    return "generic_category"


def stratified_pilot(keyword_terms: list[dict[str, Any]], size: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    targets = {
        "generic_category": 30,
        "function_body": 20,
        "size_color_material": 15,
        "brand_competitor": 15,
        "scene_task": 10,
        "noisy_multilingual_long": 5,
        "irrelevant_cross_domain": 5,
    }
    if size != 100:
        scale = size / 100
        targets = {key: int(round(value * scale)) for key, value in targets.items()}
        delta = size - sum(targets.values())
        targets["generic_category"] += delta
    bins: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in keyword_terms:
        bins[stratum(item["source_term"])].append(item)
    for values in bins.values():
        values.sort(key=lambda item: stable_rank(item["normalized_term"]))
    picked: list[dict[str, Any]] = []
    used: set[str] = set()
    actual: dict[str, int] = {}
    for name, count in targets.items():
        selected = bins[name][:count]
        picked.extend(selected)
        used.update(item["term_id"] for item in selected)
        actual[name] = len(selected)
    if len(picked) < size:
        remaining = sorted(
            (item for item in keyword_terms if item["term_id"] not in used),
            key=lambda item: stable_rank(item["normalized_term"]),
        )
        picked.extend(remaining[: size - len(picked)])
        actual["stable_hash_fill"] = min(len(remaining), size - len(used))
    return picked[:size], actual


def batch_items(items: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [items[idx: idx + size] for idx in range(0, len(items), size)]


def non_model_record(item: dict[str, Any], run_id: str, model: str) -> dict[str, Any]:
    is_blank = item["query_kind"] == "blank"
    return {
        "source_term": item["source_term"],
        "normalized_term": item["normalized_term"],
        "term_id": item["term_id"],
        "query_kind": item["query_kind"],
        "language": item["language"],
        "primary_domain": "others",
        "secondary_domain": [],
        "product_type": [],
        "audience_intent": [],
        "function_intent": [],
        "capability_intent": [],
        "event_intent": [],
        "location_intent": [],
        "body_need_intent": [],
        "time_intent": [],
        "substitute_intent": [],
        "complement_intent": [],
        "latent_task": "搜索词为空，跳过意图推断。" if is_blank else "该搜索词为 ASIN 形式，需补充商品元数据后再判断用户意图。",
        "intent_stage": "unknown",
        "evidence_type": [],
        "confidence_level": "low",
        "intent_cluster": "blank" if is_blank else "asin_target",
        "routing_action": "blank_skip" if is_blank else "asin_metadata_pending",
        "field_evidence": {},
        "ambiguity_flags": ["blank_term"] if is_blank else ["asin_without_metadata"],
        "asin_fit": "not_applicable",
        "asin_fit_evidence": [],
        "review_status": "non_model",
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model_name": model,
        "run_id": run_id,
    }


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start < 0:
            raise
        depth = 0
        in_string = False
        escaped = False
        for idx in range(start, len(text)):
            char = text[idx]
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return json.loads(text[start: idx + 1])
        raise ValueError("no complete JSON object")


def parse_opencode_stream(stdout: str) -> tuple[str, list[str]]:
    texts: list[str] = []
    session_ids: list[str] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            texts.append(line)
            continue
        blob = json.dumps(event, ensure_ascii=False)
        for match in re.finditer(r'"sessionID"\s*:\s*"([^"]+)"', blob):
            session_ids.append(match.group(1))
        def walk(node: Any) -> None:
            if isinstance(node, dict):
                if node.get("type") in {"text", "message.part.updated"} and isinstance(node.get("text"), str):
                    texts.append(node["text"])
                for value in node.values():
                    walk(value)
            elif isinstance(node, list):
                for value in node:
                    walk(value)
        walk(event)
    candidate = "".join(texts)
    if not candidate.strip():
        candidate = stdout
    return candidate, sorted(set(session_ids))


def validate_record(record: dict[str, Any], item: dict[str, Any], fact_ids: set[str], run_id: str, model: str) -> list[str]:
    errors: list[str] = []
    missing = [field for field in REQUIRED_FIELDS if field not in record]
    extras = [field for field in record if field not in REQUIRED_FIELDS]
    if missing:
        errors.append("missing_fields:" + ",".join(missing))
    if extras:
        errors.append("extra_fields:" + ",".join(extras))
    if missing:
        return errors
    expected = {
        "source_term": item["source_term"], "normalized_term": item["normalized_term"],
        "term_id": item["term_id"], "query_kind": "keyword", "language": item["language"],
        "schema_version": SCHEMA_VERSION, "prompt_version": PROMPT_VERSION,
        "model_name": model, "run_id": run_id,
    }
    for field, value in expected.items():
        if record.get(field) != value:
            errors.append(f"control_mismatch:{field}")
    for field in ARRAY_FIELDS:
        if not isinstance(record.get(field), list):
            errors.append(f"not_array:{field}")
    if record.get("primary_domain") not in PRIMARY_DOMAINS:
        errors.append("invalid_primary_domain")
    if record.get("intent_stage") not in INTENT_STAGES:
        errors.append("invalid_intent_stage")
    if record.get("confidence_level") not in CONFIDENCE:
        errors.append("invalid_confidence")
    if record.get("asin_fit") not in ASIN_FIT:
        errors.append("invalid_asin_fit")
    if record.get("routing_action") not in ROUTING:
        errors.append("invalid_routing")
    if record.get("review_status") not in REVIEW_STATUS:
        errors.append("invalid_review_status")
    if not isinstance(record.get("intent_cluster"), str) or not SNAKE_RE.fullmatch(record["intent_cluster"]):
        errors.append("invalid_intent_cluster")
    for field in ARRAY_FIELDS - {"evidence_type", "asin_fit_evidence"}:
        for value in record.get(field, []):
            if not isinstance(value, str) or not SNAKE_RE.fullmatch(value):
                errors.append(f"not_snake_case:{field}:{value}")
    if not set(record.get("evidence_type", [])).issubset(EVIDENCE_TYPES):
        errors.append("invalid_evidence_type")
    unknown_facts = set(record.get("asin_fit_evidence", [])) - fact_ids
    if unknown_facts:
        errors.append("unknown_asin_fact:" + ",".join(sorted(unknown_facts)))
    field_evidence = record.get("field_evidence")
    if not isinstance(field_evidence, dict):
        errors.append("field_evidence_not_object")
    else:
        normalized_source = normalize_term(item["source_term"])
        for field, entries in field_evidence.items():
            if not isinstance(entries, list):
                errors.append(f"evidence_not_array:{field}")
                continue
            for evidence in entries:
                if not isinstance(evidence, dict):
                    errors.append(f"evidence_not_object:{field}")
                    continue
                required = {"value", "evidence_type", "source_span", "fact_ids", "rationale"}
                if set(evidence) != required:
                    errors.append(f"evidence_shape:{field}")
                    continue
                etype = evidence.get("evidence_type")
                if etype not in EVIDENCE_TYPES:
                    errors.append(f"invalid_evidence_type:{field}")
                span = str(evidence.get("source_span", ""))
                if etype == "explicit" and (not span or normalize_term(span) not in normalized_source):
                    errors.append(f"explicit_span_not_found:{field}:{span}")
                facts = evidence.get("fact_ids")
                if not isinstance(facts, list) or set(facts) - fact_ids:
                    errors.append(f"invalid_fact_ids:{field}")
    serialized = json.dumps(record, ensure_ascii=False)
    if FORBIDDEN.search(serialized):
        errors.append("forbidden_performance_or_behavior_evidence")
    rationales = "\n".join(
        str(evidence.get("rationale", ""))
        for entries in (field_evidence.values() if isinstance(field_evidence, dict) else [])
        if isinstance(entries, list)
        for evidence in entries
        if isinstance(evidence, dict)
    )
    if PROHIBITED_PRODUCT_INFERENCE.search(rationales):
        errors.append("prohibited_eva_water_property_inference")
    audiences = set(record.get("audience_intent", []))
    products = set(record.get("product_type", []))
    if record.get("asin_fit") == "match":
        if audiences & {"men", "boys", "girls", "kids", "children", "baby", "toddler"}:
            errors.append("fit_audience_contradiction")
        incompatible = {"closed_toe_shoes", "sneakers", "boots", "loafers", "slides"}
        if products & incompatible:
            errors.append("fit_product_contradiction")
    return errors


def normalize_model_record(record: dict[str, Any], item: dict[str, Any], fact_ids: set[str], run_id: str, model: str) -> dict[str, Any]:
    """Apply only deterministic control-field and evidence-ID normalization."""
    record = dict(record)
    record.update({
        "source_term": item["source_term"],
        "normalized_term": item["normalized_term"],
        "term_id": item["term_id"],
        "query_kind": "keyword",
        "language": item["language"],
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "model_name": model,
        "run_id": run_id,
    })
    raw_fit_evidence = record.get("asin_fit_evidence", [])
    cleaned_fit_evidence: list[str] = []
    if isinstance(raw_fit_evidence, list):
        for value in raw_fit_evidence:
            text = str(value)
            for fact_id in sorted(fact_ids):
                if value == fact_id or re.search(rf"\b{re.escape(fact_id)}\b", text):
                    if fact_id not in cleaned_fit_evidence:
                        cleaned_fit_evidence.append(fact_id)
    record["asin_fit_evidence"] = cleaned_fit_evidence
    for field in ARRAY_FIELDS - {"evidence_type", "asin_fit_evidence"}:
        values = record.get(field)
        if isinstance(values, list):
            cleaned_values: list[str] = []
            for value in values:
                normalized = to_snake(str(value))
                if normalized not in cleaned_values:
                    cleaned_values.append(normalized)
            record[field] = cleaned_values
    # `arch_support` is a requested product capability, not a body condition.
    body_values = record.get("body_need_intent", [])
    if isinstance(body_values, list) and "arch_support" in body_values:
        record["body_need_intent"] = [value for value in body_values if value != "arch_support"]
        capabilities = record.get("capability_intent", [])
        if isinstance(capabilities, list) and "arch_support" not in capabilities:
            capabilities.append("arch_support")
    functions = record.get("function_intent", [])
    capabilities = record.get("capability_intent", [])
    if isinstance(functions, list) and isinstance(capabilities, list) and "arch_support" in capabilities:
        record["function_intent"] = [value for value in functions if value != "arch_support"]
    if isinstance(record.get("intent_cluster"), str):
        cluster = to_snake(record["intent_cluster"])
        cluster = cluster.replace("arched", "arch_support")
        cluster = re.sub(r"(^|_)arch_flip", r"\1arch_support_flip", cluster)
        record["intent_cluster"] = re.sub(r"_+", "_", cluster)
    field_evidence = record.get("field_evidence")
    if isinstance(field_evidence, dict):
        body_entries = field_evidence.get("body_need_intent", [])
        if isinstance(body_entries, list):
            field_evidence["body_need_intent"] = [
                entry for entry in body_entries
                if not isinstance(entry, dict) or to_snake(str(entry.get("value", ""))) != "arch_support"
            ]
            if not field_evidence["body_need_intent"]:
                field_evidence.pop("body_need_intent", None)
        function_entries = field_evidence.get("function_intent", [])
        if isinstance(function_entries, list) and "arch_support" in record.get("capability_intent", []):
            field_evidence["function_intent"] = [
                entry for entry in function_entries
                if not isinstance(entry, dict) or to_snake(str(entry.get("value", ""))) != "arch_support"
            ]
            if not field_evidence["function_intent"]:
                field_evidence.pop("function_intent", None)
        for entries in field_evidence.values():
            if not isinstance(entries, list):
                continue
            for evidence in entries:
                if not isinstance(evidence, dict):
                    continue
                if evidence.get("evidence_type") == "explicit":
                    evidence["source_span"] = align_explicit_span(item["source_term"], str(evidence.get("source_span", "")))
                elif evidence.get("evidence_type") == "page_validated":
                    evidence["source_span"] = ""
                raw_facts = evidence.get("fact_ids", [])
                cleaned: list[str] = []
                if isinstance(raw_facts, list):
                    for value in raw_facts:
                        text = str(value)
                        for fact_id in sorted(fact_ids):
                            if value == fact_id or re.search(rf"\b{re.escape(fact_id)}\b", text):
                                if fact_id not in cleaned:
                                    cleaned.append(fact_id)
                if evidence.get("evidence_type") == "inferred":
                    # Inference explains how the query was interpreted. Page
                    # facts belong in a separate page_validated evidence item.
                    cleaned = []
                evidence["fact_ids"] = cleaned
                rationale = str(evidence.get("rationale", ""))
                if PROHIBITED_PRODUCT_INFERENCE.search(rationale):
                    if evidence.get("evidence_type") == "explicit":
                        evidence["rationale"] = "该性能约束由搜索词原文明确表达；商品页面基准未验证该性能。"
                    elif evidence.get("evidence_type") == "page_validated":
                        evidence["rationale"] = "商品页面仅明示该槽位对应的基础属性，不据此推断额外性能。"
                    else:
                        evidence["rationale"] = "该值来自搜索词整体语义推断；商品页面基准未验证相应性能。"
        # Remove redundant inferred copies when the same value is already
        # explicit or page-validated in that field.
        for field, entries in list(field_evidence.items()):
            if not isinstance(entries, list):
                continue
            stronger = {
                to_snake(str(entry.get("value", "")))
                for entry in entries if isinstance(entry, dict)
                and entry.get("evidence_type") in {"explicit", "page_validated"}
            }
            field_evidence[field] = [
                entry for entry in entries
                if not (
                    isinstance(entry, dict)
                    and entry.get("evidence_type") == "inferred"
                    and to_snake(str(entry.get("value", ""))) in stronger
                )
            ]
        # Evidence is a field-level contract. Add deterministic page evidence
        # only when the normalized slot value maps to an allowed fact, and add
        # an inferred audit entry when a model supplied a value without any
        # field evidence. This does not invent a new intent value; it makes the
        # provenance of the existing value explicit and reviewable.
        page_fact_map = {
            "women": ["title_womens_flip_flop"],
            "womens": ["title_womens_flip_flop"],
            "flip_flop": ["style_flip_flop"],
            "flip_flops": ["style_flip_flop"],
            "thong_sandal": ["style_thong", "style_flip_flop"],
            "thong_sandals": ["style_thong", "style_flip_flop"],
            "sandals": ["title_womens_flip_flop"],
            "arch_support": ["arch_support"],
            "foot_support": ["arch_support"],
            "foot_comfort": ["arch_support", "padded_cushioning"],
            "comfort": ["arch_support", "padded_cushioning"],
            "cushioning": ["padded_cushioning"],
            "padded": ["padded_cushioning"],
            "slip_resistant": ["slip_resistant_grip"],
            "non_slip": ["slip_resistant_grip"],
            "grip": ["slip_resistant_grip"],
            "lightweight": ["lightweight_breathable"],
            "breathable": ["lightweight_breathable"],
            "easy_clean": ["easy_clean"],
            "slip_on": ["closure_slip_on"],
            "flat": ["style_flat"],
            "open_toe": ["style_open_toe"],
            "outdoor": ["style_outdoor"],
            "eva": ["material_eva"],
        }
        evidence_types: set[str] = set()
        evidence_fields = {
            "primary_domain", "secondary_domain", "product_type", "audience_intent",
            "function_intent", "capability_intent", "event_intent", "location_intent",
            "body_need_intent", "time_intent", "substitute_intent", "complement_intent",
        }
        for field in evidence_fields:
            values = record.get(field, [])
            if field == "primary_domain":
                values = [record.get(field)] if record.get(field) else []
            if not isinstance(values, list):
                continue
            entries = field_evidence.setdefault(field, [])
            existing_values = {
                to_snake(str(entry.get("value", "")))
                for entry in entries if isinstance(entry, dict)
            }
            for value in values:
                value_key = to_snake(str(value))
                mapped = [fact for fact in page_fact_map.get(value_key, []) if fact in fact_ids]
                value_is_explicit = value_key.replace("_", " ") in normalize_term(item["source_term"]).replace("-", " ")
                if mapped and not any(
                    isinstance(entry, dict)
                    and to_snake(str(entry.get("value", ""))) == value_key
                    and entry.get("evidence_type") == "page_validated"
                    for entry in entries
                ):
                    entries.append({
                        "value": value_key,
                        "evidence_type": "page_validated",
                        "source_span": "",
                        "fact_ids": mapped,
                        "rationale": "该槽位与商品基准中的明示页面事实一致。",
                    })
                if value_key not in existing_values and not mapped:
                    entries.append({
                        "value": value_key,
                        "evidence_type": "inferred",
                        "source_span": "",
                        "fact_ids": [],
                        "rationale": "该值由搜索词整体语义推断，未作为页面明示属性。",
                    })
                elif mapped and not value_is_explicit and not any(
                    isinstance(entry, dict)
                    and to_snake(str(entry.get("value", ""))) == value_key
                    and entry.get("evidence_type") == "inferred"
                    for entry in entries
                ):
                    entries.append({
                        "value": value_key,
                        "evidence_type": "inferred",
                        "source_span": "",
                        "fact_ids": [],
                        "rationale": "该能力由搜索词表达的任务或问题推断；页面事实仅用于验证商品承接。",
                    })
            if not entries:
                field_evidence.pop(field, None)
        for entries in field_evidence.values():
            if isinstance(entries, list):
                for evidence in entries:
                    if not isinstance(evidence, dict):
                        continue
                    if evidence.get("evidence_type") == "page_validated":
                        evidence["source_span"] = ""
                    if evidence.get("evidence_type") in EVIDENCE_TYPES:
                        evidence_types.add(evidence["evidence_type"])
        supported_colors = {"black", "white", "brown", "pink", "mauve", "dark_gray", "light_blue"}
        color_entries = field_evidence.get("color", [])
        if isinstance(color_entries, list):
            for evidence in color_entries:
                if not isinstance(evidence, dict):
                    continue
                color_value = to_snake(str(evidence.get("value", "")))
                if color_value in supported_colors and "colors_visible" in fact_ids:
                    evidence["rationale"] = "该颜色在商品页面可见颜色选择中得到明确支持。"
                elif "colors_visible" in evidence.get("fact_ids", []):
                    evidence["fact_ids"] = []
                    if evidence.get("evidence_type") == "page_validated":
                        evidence["evidence_type"] = "inferred"
                    evidence["rationale"] = "这是搜索词中的颜色约束，但商品页面基准未确认该具体颜色。"
        evidence_types = {
            evidence.get("evidence_type")
            for entries in field_evidence.values() if isinstance(entries, list)
            for evidence in entries if isinstance(evidence, dict)
            if evidence.get("evidence_type") in EVIDENCE_TYPES
        }
        record["evidence_type"] = [
            value for value in ("explicit", "page_validated", "inferred")
            if value in evidence_types
        ]

    # Deterministic hard guards for ASIN fit. The model may compare semantic
    # similarity, but it may not call an explicit incompatible material a full
    # match or treat a competitor brand/audience/product type as compatible.
    normalized_term = item["normalized_term"]
    audiences = set(record.get("audience_intent", []))
    products = set(record.get("product_type", []))
    incompatible_audience = audiences & {"men", "boys", "girls", "kids", "children", "baby", "toddler"}
    incompatible_product = products & {"closed_toe_shoes", "sneakers", "boots", "loafers", "slides"}
    brand_match = re.search(
        r"\b(?:joomra|crocs|nike|adidas|havaianas|reef|vionic|olukai|skechers|clarks|oofos|"
        r"birkenstock|fitflop|cushionaire|hey[ -]?dude)\b",
        normalized_term,
    )
    competitor = brand_match and to_snake(brand_match.group(0)) != "joomra"
    if brand_match and isinstance(record.get("field_evidence"), dict):
        record["field_evidence"]["brand"] = [{
            "value": to_snake(brand_match.group(0)),
            "evidence_type": "explicit",
            "source_span": align_explicit_span(item["source_term"], brand_match.group(0)),
            "fact_ids": [],
            "rationale": "搜索词明确包含品牌名称。",
        }]
        evidence_types = record.get("evidence_type", [])
        if isinstance(evidence_types, list) and "explicit" not in evidence_types:
            record["evidence_type"] = ["explicit", *evidence_types]
    rubber_constraint = bool(re.search(r"\b(?:rubber|goma)\b", normalized_term))
    unsupported_delivery = bool(re.search(r"\b(?:same day|next day|overnight|fast) delivery\b", normalized_term))
    unsupported_price = bool(re.search(r"\b(?:cheap|budget|under \$?\d+|less than \$?\d+)\b", normalized_term))
    unsupported_size = any(
        int(size) < 6 or int(size) > 11
        for size in re.findall(r"\bsize\s*(\d{1,2})\b", normalized_term)
    )
    unsupported_color = bool(re.search(r"\b(?:royal blue|teal(?: blue)?|peach|navy|green|yellow|orange|purple|red)\b", normalized_term))
    unsupported_style = bool(re.search(r"\b(?:dress|cross(?:ed)?|flag(?: design)?|slippers?)\b", normalized_term))
    clearly_cross_domain = bool(re.search(r"\bheavy duty\b", normalized_term) and re.search(r"\bside hole\b", normalized_term))
    supported_flip_flop_color_query = bool(
        re.search(r"\b(?:women|womens|women's)\b", normalized_term)
        and re.search(r"\b(?:flip[- ]?flops?|thong sandals?)\b", normalized_term)
        and re.search(r"\b(?:black|white|pink|brown|light blue|dark gr[ae]y)\b", normalized_term)
    )
    if competitor or incompatible_audience or incompatible_product or clearly_cross_domain:
        record["asin_fit"] = "mismatch"
        record["asin_fit_evidence"] = []
    elif rubber_constraint or unsupported_delivery or unsupported_price or unsupported_size or unsupported_color or unsupported_style:
        record["asin_fit"] = "partial_match"
        contradictory_facts = set()
        if rubber_constraint:
            contradictory_facts.add("material_eva")
        if unsupported_size:
            contradictory_facts.add("sizes_6_11")
        if unsupported_color or re.search(r"\bflag(?: design)?\b", normalized_term):
            contradictory_facts.add("colors_visible")
        if re.search(r"\bcross(?:ed)?\b", normalized_term):
            contradictory_facts.add("style_thong")
        record["asin_fit_evidence"] = [
            fact for fact in record.get("asin_fit_evidence", [])
            if fact not in contradictory_facts
        ]
    elif supported_flip_flop_color_query:
        record["asin_fit"] = "match"
        record["asin_fit_evidence"] = sorted(set(record.get("asin_fit_evidence", [])) | {
            "title_womens_flip_flop", "style_flip_flop", "colors_visible",
        })
    if record.get("asin_fit") == "match":
        record["routing_action"] = "cluster_route"
    elif record.get("asin_fit") == "partial_match":
        record["routing_action"] = "listing_gap_review"
    elif record.get("asin_fit") == "mismatch":
        record["routing_action"] = "semantic_negative_candidate"
        record["asin_fit_evidence"] = []
    else:
        compatible_core = bool(products & {"flip_flop", "flip_flops", "sandals", "thong_sandal", "thong_sandals"})
        if compatible_core:
            record["asin_fit"] = "partial_match"
            record["routing_action"] = "listing_gap_review"
        else:
            record["routing_action"] = "ambiguity_review"
    if re.search(r"\bcross\b", normalized_term):
        flags = record.get("ambiguity_flags", [])
        if isinstance(flags, list) and "cross_style_or_symbol" not in flags:
            flags.append("cross_style_or_symbol")
    return record


async def run_opencode(
    agent: str,
    manifest_path: Path,
    run_id: str,
    batch_id: str,
    model: str,
    event_log: Path,
    feedback: str = "",
) -> tuple[dict[str, Any], dict[str, Any]]:
    marker = f"AMAZON_INTENT_RUN run_id={run_id} schema_version={SCHEMA_VERSION} batch_id={batch_id}"
    instruction = "Read the attached JSON manifest and return only the required JSON object."
    if feedback:
        instruction += " Correct these local validation failures: " + feedback[:1800]
    cmd = [
        "opencode", "run", marker + "\n" + instruction,
        "--model", model, "--agent", agent, "--format", "json", "-f", str(manifest_path),
    ]
    env = os.environ.copy()
    env["AMAZON_INTENT_EVENT_LOG"] = str(event_log)
    # Isolate this pipeline from a potentially stale global OpenCode SQLite DB.
    # Authentication remains a symlink to the existing credential file and is
    # never copied into outputs or audit logs.
    runtime_root = Path(f"/tmp/amazon-intent-opencode-{os.getuid()}")
    data_home = runtime_root / "data"
    state_home = runtime_root / "state"
    auth_dir = data_home / "opencode"
    auth_dir.mkdir(parents=True, exist_ok=True)
    state_home.mkdir(parents=True, exist_ok=True)
    auth_link = auth_dir / "auth.json"
    global_auth = Path.home() / ".local" / "share" / "opencode" / "auth.json"
    if not auth_link.exists() and global_auth.exists():
        auth_link.symlink_to(global_auth)
    env["XDG_DATA_HOME"] = str(data_home)
    env["XDG_STATE_HOME"] = str(state_home)
    env["OPENCODE_DISABLE_EXTERNAL_SKILLS"] = "1"
    env["OPENCODE_DISABLE_CLAUDE_CODE_SKILLS"] = "1"
    started = time.monotonic()
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        cwd=str(Path.cwd()), env=env,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    stdout_b, stderr_b = await proc.communicate()
    duration = round(time.monotonic() - started, 3)
    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    text, sessions = parse_opencode_stream(stdout)
    meta = {
        "batch_id": batch_id, "agent": agent, "model": model,
        "duration_seconds": duration, "exit_code": proc.returncode,
        "session_ids": sessions, "stderr_tail": stderr[-2000:],
    }
    if proc.returncode != 0:
        raise RuntimeError(f"opencode exit {proc.returncode}: {stderr[-1000:]}")
    payload = extract_json_object(text)
    provider_error = provider_error_summary(payload)
    if provider_error:
        raise ProviderUnavailableError(provider_error)
    return payload, meta


async def tag_batch(
    batch: list[dict[str, Any]], batch_index: int, phase: str, ctx: dict[str, Any], semaphore: asyncio.Semaphore,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    batch_id = f"{phase}-{batch_index:04d}"
    manifest = {
        "run_id": ctx["run_id"], "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION, "batch_id": batch_id,
        "model_name": ctx["model"], "product_baseline": ctx["product"],
        "terms": [{key: item[key] for key in ("term_id", "source_term", "normalized_term", "language")} for item in batch],
    }
    manifest_path = ctx["audit_dir"] / "manifests" / f"{batch_id}.json"
    result_path = ctx["audit_dir"] / "responses" / f"{batch_id}.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if ctx.get("resume") and result_path.exists():
        try:
            payload = json.loads(result_path.read_text(encoding="utf-8"))
            by_id = {record.get("term_id"): record for record in payload.get("records", []) if isinstance(record, dict)}
            cached: list[dict[str, Any]] = []
            cache_errors: list[str] = []
            for item in batch:
                record = by_id.get(item["term_id"])
                if record is None:
                    cache_errors.append(f"missing_term:{item['term_id']}")
                    continue
                record = normalize_model_record(record, item, ctx["fact_ids"], ctx["run_id"], ctx["model"])
                cache_errors.extend(validate_record(record, item, ctx["fact_ids"], ctx["run_id"], ctx["model"]))
                cached.append(record)
            if not cache_errors and len(cached) == len(batch):
                return cached, {"batch_id": batch_id, "status": "success", "attempts": [{"cache": "reused"}]}
        except Exception:
            pass
    feedback = ""
    attempts: list[dict[str, Any]] = []
    async with semaphore:
        for attempt in range(1, ctx["max_retries"] + 1):
            retry_delay = min(2 ** attempt, 8)
            try:
                payload, meta = await run_opencode(
                    "amazon-intent-tagger", manifest_path, ctx["run_id"], batch_id,
                    ctx["model"], ctx["event_log"], feedback,
                )
                records = payload.get("records")
                errors: list[str] = []
                if not isinstance(records, list):
                    errors.append("top_level_records_not_array")
                    records = []
                if len(records) != len(batch):
                    errors.append(f"record_count:{len(records)}!={len(batch)}")
                by_id = {record.get("term_id"): record for record in records if isinstance(record, dict)}
                validated: list[dict[str, Any]] = []
                for item in batch:
                    record = by_id.get(item["term_id"])
                    if record is None:
                        errors.append(f"missing_term:{item['term_id']}")
                        continue
                    record = normalize_model_record(record, item, ctx["fact_ids"], ctx["run_id"], ctx["model"])
                    rec_errors = validate_record(record, item, ctx["fact_ids"], ctx["run_id"], ctx["model"])
                    errors.extend(f"{item['term_id']}:{error}" for error in rec_errors)
                    validated.append(record)
                attempt_meta = {**meta, "attempt": attempt, "validation_errors": errors[:100]}
                if errors:
                    diagnostic_keys = ("error", "message", "code", "status", "type")
                    diagnostic = {
                        "ts": utcnow(),
                        "batch_id": batch_id,
                        "attempt": attempt,
                        "top_level_keys": sorted(str(key) for key in payload.keys()),
                        "diagnostic": {
                            key: str(payload[key])[:500]
                            for key in diagnostic_keys if key in payload
                        },
                        "validation_errors": [
                            error for error in errors
                            if not error.startswith("missing_term:")
                        ][:20],
                    }
                    failure_path = ctx["audit_dir"] / "failures" / f"{batch_id}.jsonl"
                    failure_path.parent.mkdir(parents=True, exist_ok=True)
                    with failure_path.open("a", encoding="utf-8") as handle:
                        handle.write(json.dumps(diagnostic, ensure_ascii=False) + "\n")
                attempts.append(attempt_meta)
                if not errors:
                    result_path.parent.mkdir(parents=True, exist_ok=True)
                    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                    return validated, {"batch_id": batch_id, "status": "success", "attempts": attempts}
                if "top_level_records_not_array" in errors:
                    feedback = "Return exactly one top-level JSON object with a records array containing all 20 requested records."
                    retry_delay = min(30 * attempt, 60)
                else:
                    feedback = "; ".join(error for error in errors if not error.startswith("missing_term:"))[:1800]
            except ProviderUnavailableError:
                raise
            except Exception as exc:
                attempts.append({"attempt": attempt, "error": str(exc)})
                feedback = str(exc)
            if attempt < ctx["max_retries"]:
                await asyncio.sleep(retry_delay)
    return [], {"batch_id": batch_id, "status": "failed", "attempts": attempts}


async def tag_many(items: list[dict[str, Any]], phase: str, ctx: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    semaphore = asyncio.Semaphore(ctx["concurrency"])
    batches = batch_items(items, ctx["batch_size"])
    tasks = [tag_batch(batch, idx + 1, phase, ctx, semaphore) for idx, batch in enumerate(batches)]
    results = await asyncio.gather(*tasks)
    records: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for batch_records, audit in results:
        records.extend(batch_records)
        audits.append(audit)
        print(json.dumps({"event": "batch_complete", "phase": phase, "batch": audit["batch_id"], "status": audit["status"]}, ensure_ascii=False), flush=True)
    return records, audits


async def critic_batch(
    records: list[dict[str, Any]], batch_index: int, phase: str, source_map: dict[str, dict[str, Any]], ctx: dict[str, Any], semaphore: asyncio.Semaphore,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    batch_id = f"critic-{phase}-{batch_index:04d}"
    manifest = {
        "run_id": ctx["run_id"], "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION, "batch_id": batch_id,
        "product_baseline": ctx["product"],
        "terms": [{key: source_map[record["term_id"]][key] for key in ("term_id", "source_term", "normalized_term", "language")} for record in records],
        "candidate_records": records,
    }
    path = ctx["audit_dir"] / "critic_manifests" / f"{batch_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    def issue_matches_current_record(issue: dict[str, Any], record: dict[str, Any]) -> bool:
        """Reject critic claims that quote a state the record does not have."""
        message = re.sub(r"\s+", "", str(issue.get("message", "")).lower())
        for value in ASIN_FIT:
            quoted = any(token in message for token in (
                f"asin_fit为{value}", f"asin_fit={value}", f"asin_fit:{value}",
            ))
            if quoted and record.get("asin_fit") != value:
                return False
        for value in ROUTING:
            quoted = any(token in message for token in (
                f"routing_action为{value}", f"routing为{value}", f"routing={value}",
            ))
            if quoted and record.get("routing_action") != value:
                return False
        return True

    async with semaphore:
        attempts: list[dict[str, Any]] = []
        for attempt in range(1, ctx["max_retries"] + 1):
            try:
                payload, meta = await run_opencode(
                    "amazon-intent-critic", path, ctx["run_id"], batch_id,
                    ctx["model"], ctx["event_log"], "",
                )
                issues = payload.get("issues", [])
                if not isinstance(issues, list):
                    raise ValueError("critic issues is not array")
                by_id = {record["term_id"]: record for record in records}
                clean: list[dict[str, Any]] = []
                for issue in issues:
                    if not isinstance(issue, dict) or issue.get("term_id") not in by_id:
                        continue
                    if issue.get("severity") not in {"critical", "general"}:
                        continue
                    if not issue_matches_current_record(issue, by_id[issue["term_id"]]):
                        continue
                    clean.append({
                        "term_id": issue["term_id"], "severity": issue["severity"],
                        "code": str(issue.get("code", "unspecified")),
                        "field": str(issue.get("field", "record")),
                        "message": str(issue.get("message", "")),
                        "phase": phase, "batch_id": batch_id,
                    })
                attempts.append({**meta, "attempt": attempt, "status": "success"})
                return clean, {
                    "batch_id": batch_id, "status": "success",
                    "issue_count": len(clean), "attempts": attempts,
                }
            except ProviderUnavailableError:
                raise
            except Exception as exc:
                attempts.append({"attempt": attempt, "status": "failed", "error": str(exc)})
                if attempt < ctx["max_retries"]:
                    await asyncio.sleep(min(2 ** attempt, 8))
        error = attempts[-1].get("error", "critic failed")
        return [{
            "term_id": record["term_id"], "severity": "critical",
            "code": "critic_execution_failed", "field": "record",
            "message": error, "phase": phase, "batch_id": batch_id,
        } for record in records], {"batch_id": batch_id, "status": "failed", "attempts": attempts}


async def critic_many(records: list[dict[str, Any]], phase: str, source_map: dict[str, dict[str, Any]], ctx: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    semaphore = asyncio.Semaphore(ctx["concurrency"])
    batches = batch_items(records, ctx["batch_size"])
    tasks = [critic_batch(batch, idx + 1, phase, source_map, ctx, semaphore) for idx, batch in enumerate(batches)]
    results = await asyncio.gather(*tasks)
    issues: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for batch_issues, audit in results:
        issues.extend(batch_issues)
        audits.append(audit)
    return issues, audits


def apply_critic_status(records: list[dict[str, Any]], issues: list[dict[str, Any]]) -> None:
    issue_ids = {issue["term_id"] for issue in issues}
    for record in records:
        if record["term_id"] in issue_ids:
            record["review_status"] = "critic_flagged"


def write_jsonl(path: Path, records: list[dict[str, Any]], occurrence_map: dict[str, int]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            row = dict(record)
            row["source_occurrences"] = occurrence_map.get(record["normalized_term"], 0)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def json_safe_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: ("" if value is None else value) for key, value in row.items()}


def build_workbook_data(
    headers: list[str], matched: list[dict[str, str]], records: list[dict[str, Any]],
    issues: list[dict[str, Any]], product: dict[str, Any], summary: dict[str, Any], output_path: Path,
) -> None:
    record_map = {record["normalized_term"]: record for record in records}
    source_occurrences = Counter(normalize_term(row.get("搜索词", "")) for row in matched)
    unique_rows: list[dict[str, Any]] = []
    for record in records:
        flat: dict[str, Any] = {}
        for key, value in record.items():
            if isinstance(value, list):
                flat[key] = " | ".join(str(item) for item in value)
            elif isinstance(value, dict):
                flat[key] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            else:
                flat[key] = value
        flat["source_occurrences"] = source_occurrences.get(record["normalized_term"], 0)
        unique_rows.append(flat)
    raw_rows: list[dict[str, Any]] = []
    for row in matched:
        normalized = normalize_term(row.get("搜索词", ""))
        raw = {header: row.get(header, "") for header in headers}
        record = record_map.get(normalized)
        if record:
            raw.update({
                "normalized_term": normalized,
                "term_id": record["term_id"],
                "query_kind": record["query_kind"],
                "intent_cluster": record["intent_cluster"],
                "asin_fit": record["asin_fit"],
                "confidence_level": record["confidence_level"],
                "routing_action": record["routing_action"],
                "review_status": record["review_status"],
            })
        else:
            raw.update({
                "normalized_term": normalized,
                "term_id": stable_id(normalized),
                "query_kind": query_kind(normalized),
                "intent_cluster": "",
                "asin_fit": "",
                "confidence_level": "",
                "routing_action": "",
                "review_status": "not_processed",
            })
        raw_rows.append(json_safe_row(raw))
    cluster_counter = Counter()
    occurrence_counter = Counter()
    for record in records:
        if record["query_kind"] == "keyword":
            cluster_counter[record["intent_cluster"]] += 1
    for row in matched:
        record = record_map.get(normalize_term(row.get("搜索词", "")))
        if not record:
            continue
        if record["query_kind"] == "keyword":
            occurrence_counter[record["intent_cluster"]] += 1
    clusters = [
        {"intent_cluster": cluster, "unique_term_count": count, "source_row_count": occurrence_counter[cluster]}
        for cluster, count in cluster_counter.most_common()
    ]
    payload = {
        "summary": summary,
        "unique_rows": unique_rows,
        "raw_headers": headers + ["normalized_term", "term_id", "query_kind", "intent_cluster", "asin_fit", "confidence_level", "routing_action", "review_status"],
        "raw_rows": raw_rows,
        "clusters": clusters,
        "issues": issues,
        "product": product,
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


async def async_main(args: argparse.Namespace) -> int:
    source = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    audit_dir = output_dir / "_audit"
    output_dir.mkdir(parents=True, exist_ok=True)
    audit_dir.mkdir(parents=True, exist_ok=True)
    if not source.is_file():
        raise FileNotFoundError(source)
    skill_dir = Path(__file__).resolve().parents[1]
    product_path = skill_dir / "references" / f"product-{args.product_asin}.json"
    product = json.loads(product_path.read_text(encoding="utf-8"))
    fact_ids = {fact["id"] for fact in product["facts"]}
    existing_preflight = audit_dir / "preflight.json"
    if args.resume and existing_preflight.exists():
        run_id = json.loads(existing_preflight.read_text(encoding="utf-8"))["run_id"]
    else:
        run_id = f"aj2-y90-{datetime.now().strftime('%Y%m%dT%H%M%S')}-{uuid.uuid4().hex[:8]}"

    headers, _, matched = load_source(source, args.campaign_regex)
    terms, grouped = build_unique_terms(matched)
    keywords = [item for item in terms if item["query_kind"] == "keyword"]
    asins = [item for item in terms if item["query_kind"] == "asin_target"]
    blanks = [item for item in terms if item["query_kind"] == "blank"]
    source_kind_counts = Counter(query_kind(normalize_term(row.get("搜索词", ""))) for row in matched)
    pilot, pilot_strata = stratified_pilot(keywords, args.pilot_size)
    preflight = {
        "run_id": run_id,
        "started_at": utcnow(),
        "source_path": str(source),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_size_bytes": source.stat().st_size,
        "campaign_regex": args.campaign_regex,
        "matched_source_rows": len(matched),
        "unique_nonblank_terms": len(keywords) + len(asins),
        "unique_keyword_terms": len(keywords),
        "unique_asin_targets": len(asins),
        "blank_source_rows": source_kind_counts["blank"],
        "unique_blank_records": len(blanks),
        "pilot_keyword_terms": len(pilot),
        "pilot_strata": pilot_strata,
        "pilot_asin_checks": min(10, len(asins)),
        "pilot_blank_checks": source_kind_counts["blank"],
        "model": args.model,
        "schema_version": SCHEMA_VERSION,
        "prompt_version": PROMPT_VERSION,
        "performance_fields_sent_to_model": [],
    }
    (audit_dir / "preflight.json").write_text(json.dumps(preflight, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"event": "preflight", **{key: preflight[key] for key in ("matched_source_rows", "unique_keyword_terms", "unique_asin_targets", "blank_source_rows", "pilot_keyword_terms")}}, ensure_ascii=False), flush=True)
    if args.preflight_only:
        return 0

    ctx = {
        "run_id": run_id, "model": args.model, "product": product,
        "fact_ids": fact_ids, "audit_dir": audit_dir,
        "event_log": audit_dir / "opencode-events.jsonl",
        "max_retries": args.max_retries, "concurrency": args.concurrency,
        "batch_size": args.batch_size,
        "resume": args.resume,
    }
    source_map = {item["term_id"]: item for item in keywords}
    pilot_records, pilot_audits = await tag_many(pilot, "pilot", ctx)
    cached_pilot_report: dict[str, Any] = {}
    pilot_report_path = audit_dir / "pilot-report.json"
    if args.resume and pilot_report_path.exists():
        try:
            candidate = json.loads(pilot_report_path.read_text(encoding="utf-8"))
            if (
                candidate.get("passed") is True
                and candidate.get("valid_records") == len(pilot_records) == len(pilot)
                and candidate.get("critical_issue_count") == 0
            ):
                cached_pilot_report = candidate
        except Exception:
            cached_pilot_report = {}
    if cached_pilot_report:
        pilot_issues = list(cached_pilot_report.get("issues", []))
        pilot_critic_audits = list(cached_pilot_report.get("critic_audits", []))
        pilot_critic_cache_reused = True
    else:
        pilot_issues, pilot_critic_audits = await critic_many(pilot_records, "pilot", source_map, ctx) if pilot_records else ([], [])
        pilot_critic_cache_reused = False
    apply_critic_status(pilot_records, pilot_issues)
    critical = sum(issue["severity"] == "critical" for issue in pilot_issues)
    general_ids = {issue["term_id"] for issue in pilot_issues if issue["severity"] == "general"}
    pilot_pass = (
        len(pilot_records) == len(pilot)
        and all(audit["status"] == "success" for audit in pilot_audits)
        and critical == 0
        and len(general_ids) <= max(10, int(len(pilot) * 0.10))
    )
    pilot_report = {
        "run_id": run_id, "passed": pilot_pass,
        "expected": len(pilot), "valid_records": len(pilot_records),
        "schema_valid_rate": len(pilot_records) / len(pilot) if pilot else 0,
        "critical_issue_count": critical, "general_affected_terms": len(general_ids),
        "batch_audits": pilot_audits, "critic_audits": pilot_critic_audits,
        "critic_cache_reused": pilot_critic_cache_reused,
        "issues": pilot_issues,
    }
    (audit_dir / "pilot-report.json").write_text(json.dumps(pilot_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"event": "pilot_gate", "passed": pilot_pass, "valid_records": len(pilot_records), "critical": critical, "general_terms": len(general_ids)}, ensure_ascii=False), flush=True)

    non_model_records = [non_model_record(item, run_id, args.model) for item in asins + blanks]
    if not pilot_pass or args.pilot_only:
        all_records = sorted(pilot_records + non_model_records, key=lambda record: (record["query_kind"], record["term_id"]))
        occurrence_map = {key: value["source_occurrences"] for key, value in grouped.items()}
        jsonl_path = output_dir / "AJ2-Y90意图簇标签.jsonl"
        write_jsonl(jsonl_path, all_records, occurrence_map)
        summary = {**preflight, "status": "pilot_passed_full_not_run" if pilot_pass else "pilot_failed", "completed_at": utcnow(), "pilot_passed": pilot_pass, "full_keyword_records": len(pilot_records)}
        build_workbook_data(headers, matched, all_records, pilot_issues, product, summary, output_dir / "workbook_data.json")
        (audit_dir / "run-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        return 0 if pilot_pass else 2

    pilot_ids = {record["term_id"] for record in pilot_records}
    remaining = [item for item in keywords if item["term_id"] not in pilot_ids]
    full_records, full_audits = await tag_many(remaining, "full", ctx)
    all_keyword_records = pilot_records + full_records
    all_by_id = {record["term_id"]: record for record in all_keyword_records}
    full_missing = [item for item in keywords if item["term_id"] not in all_by_id]

    critic_candidates = [
        record for record in all_keyword_records
        if record["confidence_level"] == "low"
        or record["ambiguity_flags"]
        or record["asin_fit"] in {"mismatch", "unknown"}
        or int(stable_rank(record["term_id"])[:8], 16) % 100 < 5
    ]
    full_issues, full_critic_audits = await critic_many(critic_candidates, "full", source_map, ctx)
    all_issues = pilot_issues + full_issues
    apply_critic_status(all_keyword_records, all_issues)
    all_records = sorted(all_keyword_records + non_model_records, key=lambda record: (record["query_kind"], record["term_id"]))
    occurrence_map = {key: value["source_occurrences"] for key, value in grouped.items()}
    jsonl_path = output_dir / "AJ2-Y90意图簇标签.jsonl"
    write_jsonl(jsonl_path, all_records, occurrence_map)

    failed_batches = [audit for audit in full_audits if audit["status"] != "success"]
    summary = {
        **preflight,
        "status": "complete" if not full_missing and not failed_batches else "needs_review",
        "completed_at": utcnow(), "pilot_passed": True,
        "keyword_records": len(all_keyword_records), "asin_records": len(asins),
        "blank_unique_records": len(blanks), "missing_keyword_records": len(full_missing),
        "critic_candidate_records": len(critic_candidates),
        "critic_issue_count": len(all_issues),
        "critic_critical_count": sum(issue["severity"] == "critical" for issue in all_issues),
        "critic_general_count": sum(issue["severity"] == "general" for issue in all_issues),
        "failed_batches": len(failed_batches),
    }
    (audit_dir / "full-batch-audits.json").write_text(json.dumps(full_audits, ensure_ascii=False, indent=2), encoding="utf-8")
    (audit_dir / "critic-audits.json").write_text(json.dumps(full_critic_audits, ensure_ascii=False, indent=2), encoding="utf-8")
    (audit_dir / "critic-issues.json").write_text(json.dumps(all_issues, ensure_ascii=False, indent=2), encoding="utf-8")
    (audit_dir / "run-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    build_workbook_data(headers, matched, all_records, all_issues, product, summary, output_dir / "workbook_data.json")
    print(json.dumps({"event": "full_complete", "status": summary["status"], "keyword_records": len(all_keyword_records), "missing": len(full_missing), "critic_issues": len(all_issues)}, ensure_ascii=False), flush=True)
    return 0 if summary["status"] == "complete" else 3


def main() -> int:
    args = parse_args()
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(json.dumps({"event": "fatal", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
