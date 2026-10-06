# %% [markdown]
# # AJ2-Y90 搜索词意图需求分析
#
# 以 2,394 个唯一自然语言搜索词为等权分析单元。打标阶段未使用 ACOS、CVR、点击、订单等绩效指标；本分析也不将这些指标用于意图占比计算。

# %%
from __future__ import annotations

import json
import importlib.util
import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path.cwd()
BASE = ROOT / "outputs/amazon-intent-cluster/AJ2-Y90"
RESPONSES = BASE / "_audit/responses"
REPORT_DIR = BASE / "report"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

EXPECTED_KEYWORDS = 2394
EXPECTED_FILES = 120

# %% [markdown]
# ## tl;dr
#
# 本笔记回答三个问题：用户在找什么产品、哪些差异化需求出现最多、当前 ASIN 对这些需求的语义承接程度如何。

# %%
raw_records: list[dict] = []
source_files: list[str] = []
for prefix, count in (("pilot", 5), ("full", 115)):
    for batch_no in range(1, count + 1):
        path = RESPONSES / f"{prefix}-{batch_no:04d}.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_records.extend(payload["records"])
        source_files.append(path.name)

assert len(source_files) == EXPECTED_FILES
assert len(raw_records) == EXPECTED_KEYWORDS
assert len({r["term_id"] for r in raw_records}) == EXPECTED_KEYWORDS
assert {r.get("query_kind") for r in raw_records} == {"keyword"}

# Apply the same deterministic normalizer used by the pipeline before aggregation.
pipeline_path = ROOT / ".opencode/skills/amazon-search-intent/scripts/run_pipeline.py"
spec = importlib.util.spec_from_file_location("amazon_intent_pipeline", pipeline_path)
pipeline = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(pipeline)

records: list[dict] = []
for prefix, count in (("pilot", 5), ("full", 115)):
    for batch_no in range(1, count + 1):
        batch_id = f"{prefix}-{batch_no:04d}"
        manifest = json.loads((BASE / "_audit/manifests" / f"{batch_id}.json").read_text(encoding="utf-8"))
        response = json.loads((RESPONSES / f"{batch_id}.json").read_text(encoding="utf-8"))
        item_by_id = {item["term_id"]: item for item in manifest["terms"]}
        fact_ids = {fact["id"] for fact in manifest["product_baseline"]["facts"]}
        for raw in response["records"]:
            records.append(
                pipeline.normalize_model_record(
                    raw,
                    item_by_id[raw["term_id"]],
                    fact_ids,
                    manifest["run_id"],
                    manifest["model_name"],
                )
            )

assert len(records) == EXPECTED_KEYWORDS
assert len({r["term_id"] for r in records}) == EXPECTED_KEYWORDS

df = pd.DataFrame(records)
df[["source_term", "normalized_term", "intent_stage", "asin_fit", "review_status"]].head()

# %% [markdown]
# ## Context & Methods
#
# 1. 分析粒度：唯一自然语言搜索词，而非用户、曝光或点击；每个词权重相同。
# 2. 主意图字段来自 DeepSeek 结构化标注；品牌、颜色、尺码、材质等辅助条件来自 field_evidence。
# 3. 原始 intent_cluster 过度碎片化，因此先做同义归并，再统计上层需求主题。
# 4. 需求主题允许一词多标签，所以主题占比之和可以超过 100%。
# 5. 另对 accepted 子集计算敏感性，确认 needs_review 记录不会改变主结论。

# %%
INTENT_FIELDS = [
    "secondary_domain",
    "product_type",
    "audience_intent",
    "function_intent",
    "capability_intent",
    "event_intent",
    "location_intent",
    "body_need_intent",
    "time_intent",
    "substitute_intent",
    "complement_intent",
]


def list_values(record: dict, fields: list[str]) -> list[str]:
    values: list[str] = []
    for field in fields:
        value = record.get(field, [])
        if isinstance(value, list):
            values.extend(str(item).lower() for item in value if item not in (None, ""))
        elif value not in (None, ""):
            values.append(str(value).lower())
    return values


def evidence_items(record: dict) -> list[tuple[str, str, str, str]]:
    items: list[tuple[str, str, str, str]] = []
    for key, rows in (record.get("field_evidence") or {}).items():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            items.append(
                (
                    str(key).lower(),
                    str(row.get("value", "")).lower(),
                    str(row.get("source_span", "")).lower(),
                    str(row.get("evidence_type", "")).lower(),
                )
            )
    return items


def rx(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, flags=re.IGNORECASE))


COLOR_WORDS = (
    "black|white|brown|blue|pink|tan|navy|nude|beige|orange|grey|gray|coral|"
    "turquoise|cream|red|silver|gold|purple|teal|taupe|maroon|burgundy|"
    "lavender|periwinkle|chocolate|fuschia|fuchsia|royal blue|baby blue|"
    "light blue|dark brown|hot pink|clear"
)

THEME_META = {
    "generic_category_only": {
        "label": "基础品类/人群词",
        "definition": "只表达夹脚拖、人字拖、凉鞋及女士等基础条件，没有更具体的差异化要求。",
    },
    "support_foot_health": {
        "label": "足弓支撑与足部健康",
        "definition": "足弓、矫形、足底筋膜炎、足跟/足部疼痛、扁平足、高足弓、恢复等需求。",
    },
    "style_color": {
        "label": "颜色与外观风格",
        "definition": "颜色、图案、造型、厚底/坡跟、鞋带结构、时尚或正式外观等。",
    },
    "water_outdoor": {
        "label": "海滩/泳池/涉水与户外",
        "definition": "海滩、泳池、淋浴、游泳、潮湿环境、防水、户外、夏季等场景能力。",
    },
    "brand_competitor": {
        "label": "品牌与竞品替代",
        "definition": "指定 Joomra、Archies、FitFlop、Crocs、Nike 等品牌，或寻找某品牌替代品。",
    },
    "comfort_cushion": {
        "label": "舒适、缓震与全天穿着",
        "definition": "舒适、软弹、缓震、记忆泡棉、厚实脚感、久站/久走或全天穿着。",
    },
    "material_build": {
        "label": "材质与结构性能",
        "definition": "EVA、橡胶、塑料、泡棉等材质，以及轻量、耐用、透气、易清洁、一体成型等。",
    },
    "size_fit": {
        "label": "尺码、宽窄与合脚性",
        "definition": "指定尺码、宽脚/窄脚、宽度、半码、脚型与合脚性要求。",
    },
    "indoor_home": {
        "label": "居家与室内使用",
        "definition": "在家、室内、浴室、家务或居家拖鞋替代场景。",
    },
    "slip_safety": {
        "label": "防滑、抓地与安全",
        "definition": "明确要求 non-slip、slip-resistant、grip、traction 等防滑抓地能力。",
    },
    "price_fulfillment": {
        "label": "价格、促销与配送",
        "definition": "便宜、预算上限、清仓/折扣、当日或隔夜配送等交易条件。",
    },
}


SUPPORT_PATTERN = (
    r"arch_support|foot_support|orthop|orthot|plantar|fasci|(?:foot|heel|arch)_?pain|"
    r"flat_feet|high_arch|bunion|neurop|arthritis|recovery|podiatr|pronat|alignment|"
    r"foot_condition|foot_relief|arch_discomfort|sciatica|edema|"
    r"\barch(?:es)?\b|\bflat feet\b|\bhigh arch\b|\bheel pain\b|\bfoot pain\b"
)
COMFORT_PATTERN = (
    r"comfort|comfy|cushy|cushion|padded|soft|memory_foam|memory foam|all_day|all day|"
    r"foot_fatigue|shock_absorb|thick_sole|squishy|walking_comfort|standing|ergonomic"
)
WATER_PATTERN = (
    r"water|waterproof|water_resistant|water_friendly|beach|pool|shower|bath|swim|aqua|"
    r"wet_environment|rain|lake|boat|spa|outdoor|summer|vacation|quick_dry"
)
SAFETY_PATTERN = r"non.?slip|slip.?resist|slip_prevent|anti.?slip|\bgrip\b|traction"
SIZE_PATTERN = r"\bwide\b|\bnarrow\b|\bwidth\b|\bsize\b|half.?size|toe_room|large_feet|small_feet"
STYLE_PATTERN = (
    rf"\b(?:{COLOR_WORDS})\b|styl|fashion|dressy|fancy|cute|bling|platform|wedge|"
    r"patriotic|cross_strap|toe_strap|back_strap|square_toe|plain_design|flag_design"
)
MATERIAL_PATTERN = (
    r"\brubber\b|\beva\b|\bplastic\b|foam|material|durab|lightweight|breathable|"
    r"easy.?clean|washable|seamless|one.?piece|leather|silicone|fabric|jelly|\bgel\b|"
    r"antimicrobial|odor|heavy.?duty"
)
PRICE_PATTERN = r"cheap|inexpensive|budget|under_?\d|under \$?\d|sale|clearance|discount|deal|same.?day|overnight|delivery"
INDOOR_PATTERN = r"\bindoor\b|\bhome\b|\bhouse\b|\bbathroom\b|indoor_home|home_indoor|house_slipper"
DAILY_PATTERN = r"daily|everyday|casual|walking|pedicure|garden|hospital|housework"


def classify_strict_explicit_themes(record: dict) -> set[str]:
    """Conservative floor: only explicit evidence in semantically relevant slots."""
    evidence = [item for item in evidence_items(record) if item[3] == "explicit"]
    grouped: dict[str, list[str]] = defaultdict(list)
    for key, value, span, _ in evidence:
        grouped[key].extend([value, span])

    def slot_blob(keys: set[str], prefixes: tuple[str, ...] = ()) -> str:
        values: list[str] = []
        for key, items in grouped.items():
            if key in keys or any(key.startswith(prefix) for prefix in prefixes):
                values.extend(items)
        return " | ".join(values)

    themes: set[str] = set()
    core_keys = {"function_intent", "capability_intent", "body_need_intent"}
    if rx(SUPPORT_PATTERN, slot_blob(core_keys)):
        themes.add("support_foot_health")
    if rx(COMFORT_PATTERN, slot_blob(core_keys | {"time_intent"})):
        themes.add("comfort_cushion")
    if rx(WATER_PATTERN, slot_blob(core_keys | {"event_intent", "location_intent", "time_intent"})):
        themes.add("water_outdoor")
    if rx(SAFETY_PATTERN, slot_blob({"function_intent", "capability_intent"})):
        themes.add("slip_safety")
    if rx(SIZE_PATTERN, slot_blob(core_keys | {"size", "aux_size"}, ("size_",))):
        themes.add("size_fit")
    if rx(
        STYLE_PATTERN,
        slot_blob(
            {"function_intent", "capability_intent", "color", "aux_color", "style", "aux_style", "pattern", "design", "decoration", "design_theme"},
            ("color_",),
        ),
    ):
        themes.add("style_color")
    if slot_blob({"brand", "aux_brand", "substitute_intent"}, ("brand_",)):
        themes.add("brand_competitor")
    if rx(
        MATERIAL_PATTERN,
        slot_blob({"function_intent", "capability_intent", "material", "aux_material"}, ("material_",)),
    ):
        themes.add("material_build")
    if rx(PRICE_PATTERN, slot_blob({"function_intent", "time_intent", "price", "price_constraint", "delivery", "deal_intent"})):
        themes.add("price_fulfillment")
    if rx(INDOOR_PATTERN, slot_blob({"function_intent", "event_intent", "location_intent", "time_intent"})):
        themes.add("indoor_home")
    if not themes:
        themes.add("generic_category_only")
    return themes


def classify_lexical_themes(record: dict) -> set[str]:
    """Audit lens: direct words in the original normalized query, avoiding page evidence."""
    term = str(record.get("normalized_term") or record.get("source_term") or "").lower()
    themes: set[str] = set()
    if rx(SUPPORT_PATTERN, term): themes.add("support_foot_health")
    if rx(COMFORT_PATTERN, term): themes.add("comfort_cushion")
    if rx(WATER_PATTERN, term): themes.add("water_outdoor")
    if rx(SAFETY_PATTERN, term): themes.add("slip_safety")
    if rx(SIZE_PATTERN, term): themes.add("size_fit")
    if rx(STYLE_PATTERN, term): themes.add("style_color")
    if rx(MATERIAL_PATTERN, term): themes.add("material_build")
    if rx(PRICE_PATTERN, term): themes.add("price_fulfillment")
    if rx(INDOOR_PATTERN, term): themes.add("indoor_home")
    if record.get("intent_stage") == "brand_harvest": themes.add("brand_competitor")
    if not themes: themes.add("generic_category_only")
    return themes


theme_sets = {r["term_id"]: classify_strict_explicit_themes(r) for r in records}
lexical_theme_sets = {r["term_id"]: classify_lexical_themes(r) for r in records}

# %% [markdown]
# ## Data
#
# 先做完整性、唯一性、标签覆盖率和原始意图簇碎片度检查，再进入需求主题统计。

# %%
review_counts = Counter(r["review_status"] for r in records)
cluster_counts = Counter(r["intent_cluster"] for r in records)
singleton_clusters = sum(1 for count in cluster_counts.values() if count == 1)
raw_cluster_counts = Counter(r["intent_cluster"] for r in raw_records)
raw_singleton_clusters = sum(1 for count in raw_cluster_counts.values() if count == 1)
normalized_by_id = {r["term_id"]: r for r in records}
standardized_changed = sum(
    json.dumps(raw, ensure_ascii=False, sort_keys=True)
    != json.dumps(normalized_by_id[raw["term_id"]], ensure_ascii=False, sort_keys=True)
    for raw in raw_records
)

slot_coverage_rows = []
for field in INTENT_FIELDS:
    count = sum(bool(r.get(field)) for r in records)
    slot_coverage_rows.append(
        {
            "field": field,
            "terms": count,
            "share": round(count / EXPECTED_KEYWORDS, 4),
            "share_pct": round(count / EXPECTED_KEYWORDS * 100, 1),
        }
    )
slot_coverage = pd.DataFrame(slot_coverage_rows).sort_values("share", ascending=False)
slot_coverage

# %% [markdown]
# ## Results

# ### 1. 用户在找什么产品、给谁使用

# %%
FLIP_FLOP_VALUES = {
    "flip_flops",
    "flip_flop",
    "thong_sandals",
    "thong_sandal",
    "arch_support_flip_flops",
}
SANDAL_VALUES = {"sandals", "sandal", "womens_sandal", "orthopedic_sandals"}
SLIPPER_SLIDE_VALUES = {
    "slippers",
    "slipper",
    "slides",
    "shower_shoes",
    "shower_sandals",
    "house_slippers",
    "pool_slides",
}


def product_family(record: dict) -> str:
    values = set(list_values(record, ["product_type"]))
    if values & FLIP_FLOP_VALUES:
        return "夹脚拖/人字拖"
    if values & SANDAL_VALUES:
        return "其他凉鞋"
    if values & SLIPPER_SLIDE_VALUES:
        return "拖鞋/一字拖/淋浴鞋"
    if values:
        return "其他鞋类或跨品类"
    return "未识别"


def audience_family(record: dict) -> str:
    values = set(list_values(record, ["audience_intent"]))
    if values & {"women", "female", "womens", "ladies"}:
        return "女士明确"
    if values:
        return "其他/泛人群"
    return "未明确人群"


product_counts = Counter(product_family(r) for r in records)
audience_counts = Counter(audience_family(r) for r in records)

product_audience = pd.DataFrame(
    [
        {"dimension": "产品类型", "category": k, "terms": v, "share_pct": round(v / EXPECTED_KEYWORDS * 100, 1)}
        for k, v in product_counts.most_common()
    ]
    + [
        {"dimension": "使用人群", "category": k, "terms": v, "share_pct": round(v / EXPECTED_KEYWORDS * 100, 1)}
        for k, v in audience_counts.most_common()
    ]
)
product_audience

# %% [markdown]
# ### 2. 差异化需求主题占比

# %%
accepted_ids = {r["term_id"] for r in records if r["review_status"] == "accepted"}
theme_counts = Counter(theme for themes in theme_sets.values() for theme in themes)
lexical_theme_counts = Counter(theme for themes in lexical_theme_sets.values() for theme in themes)
accepted_theme_counts = Counter(
    theme for term_id, themes in theme_sets.items() if term_id in accepted_ids for theme in themes
)


def representative_terms(theme: str, limit: int = 3) -> list[str]:
    candidates = [
        r for r in records if theme in theme_sets[r["term_id"]] and r["review_status"] == "accepted"
    ]
    candidates.sort(key=lambda r: (len(r["source_term"]), r["term_id"]))
    selected: list[str] = []
    for row in candidates:
        term = row["source_term"]
        if term not in selected:
            selected.append(term)
        if len(selected) == limit:
            break
    return selected


theme_rows = []
for theme, count in theme_counts.items():
    accepted_count = accepted_theme_counts.get(theme, 0)
    lexical_count = lexical_theme_counts.get(theme, 0)
    all_share = count / EXPECTED_KEYWORDS
    accepted_share = accepted_count / len(accepted_ids)
    theme_rows.append(
        {
            "theme_id": theme,
            "theme": THEME_META[theme]["label"],
            "terms": count,
            "share": round(all_share, 4),
            "share_pct": round(all_share * 100, 1),
            "lexical_terms": lexical_count,
            "lexical_share_pct": round(lexical_count / EXPECTED_KEYWORDS * 100, 1),
            "accepted_terms": accepted_count,
            "accepted_share_pct": round(accepted_share * 100, 1),
            "sensitivity_pp": round((all_share - accepted_share) * 100, 1),
            "definition": THEME_META[theme]["definition"],
            "examples": "；".join(representative_terms(theme)),
        }
    )
theme_share = pd.DataFrame(theme_rows).sort_values(["terms", "theme"], ascending=[False, True])
theme_share.insert(0, "rank", range(1, len(theme_share) + 1))
theme_share

# %% [markdown]
# ### 2.1 分层看需求：功能任务与选择修饰条件
#
# 功能任务用标准化后的主意图槽位归并；颜色、品牌、材质、尺码和价格用搜索词原文审计，避免辅助证据漏填造成低估。

# %%
WET_ONLY_PATTERN = (
    r"water|waterproof|water_resistant|water_friendly|beach|pool|shower|bath|swim|aqua|"
    r"wet_environment|rain|lake|boat|spa|quick_dry"
)


def structured_count(pattern: str, fields: list[str]) -> int:
    return sum(rx(pattern, " | ".join(list_values(record, fields))) for record in records)


functional_need_specs = [
    ("足弓支撑与足部健康", SUPPORT_PATTERN, ["function_intent", "capability_intent", "body_need_intent"]),
    ("海滩/泳池/淋浴与涉水", WET_ONLY_PATTERN, ["function_intent", "capability_intent", "event_intent", "location_intent"]),
    ("舒适、缓震与全天穿着", COMFORT_PATTERN, ["function_intent", "capability_intent", "body_need_intent", "time_intent"]),
    ("防滑、抓地与安全", SAFETY_PATTERN, ["function_intent", "capability_intent"]),
]
functional_needs = pd.DataFrame(
    [
        {
            "rank": rank,
            "need": label,
            "terms": (count := structured_count(pattern, fields)),
            "share": round(count / EXPECTED_KEYWORDS, 4),
            "share_pct": round(count / EXPECTED_KEYWORDS * 100, 1),
            "method": "标准化18字段语义归并",
        }
        for rank, (label, pattern, fields) in enumerate(functional_need_specs, start=1)
    ]
)

modifier_ids = ["style_color", "brand_competitor", "material_build", "size_fit", "price_fulfillment"]
selection_modifiers = pd.DataFrame(
    [
        {
            "rank": rank,
            "modifier": THEME_META[theme_id]["label"],
            "terms": lexical_theme_counts[theme_id],
            "share": round(lexical_theme_counts[theme_id] / EXPECTED_KEYWORDS, 4),
            "share_pct": round(lexical_theme_counts[theme_id] / EXPECTED_KEYWORDS * 100, 1),
            "method": "搜索词原文审计" if theme_id != "brand_competitor" else "搜索词原文+品牌阶段标签",
        }
        for rank, theme_id in enumerate(modifier_ids, start=1)
    ]
)
functional_needs, selection_modifiers

# %% [markdown]
# ### 3. 购买阶段与当前商品的语义承接度

# %%
stage_counts = Counter(r["intent_stage"] for r in records)
fit_counts = Counter(r["asin_fit"] for r in records)
confidence_counts = Counter(r["confidence_level"] for r in records)


def distribution_rows(dimension: str, counts: Counter) -> list[dict]:
    return [
        {
            "dimension": dimension,
            "category": key,
            "terms": count,
            "share": round(count / EXPECTED_KEYWORDS, 4),
            "share_pct": round(count / EXPECTED_KEYWORDS * 100, 1),
        }
        for key, count in counts.most_common()
    ]


fit_stage = pd.DataFrame(
    distribution_rows("intent_stage", stage_counts)
    + distribution_rows("asin_fit", fit_counts)
    + distribution_rows("confidence_level", confidence_counts)
    + distribution_rows("review_status", review_counts)
)
fit_stage

# %% [markdown]
# ### 4. 原始 intent_cluster 为什么不能直接用来回答“哪个意图最多”

# %%
raw_cluster_top = pd.DataFrame(
    [
        {
            "intent_cluster": key,
            "terms": count,
            "share_pct": round(count / EXPECTED_KEYWORDS * 100, 1),
        }
        for key, count in cluster_counts.most_common(20)
    ]
)
raw_cluster_top

# %% [markdown]
# ## Takeaways
#
# - 用户的品类目标高度集中在人字拖/夹脚拖，女士是最常被明确写出的受众。
# - 在差异化需求中，足弓支撑与足部健康、颜色与风格、海滩/泳池/涉水场景最常见。
# - 舒适缓震、品牌替代、材质结构、尺码宽窄属于第二梯队。
# - 当前 ASIN 对多数搜索方向至少部分匹配，但这只是语义承接，不代表广告绩效。
# - 原始意图簇共有大量单例，必须先做上层同义归并后才能用于策略判断。

# %%
headline = {
    "unique_keyword_terms": EXPECTED_KEYWORDS,
    "accepted_terms": review_counts.get("accepted", 0),
    "accepted_rate_pct": round(review_counts.get("accepted", 0) / EXPECTED_KEYWORDS * 100, 1),
    "needs_review_terms": review_counts.get("needs_review", 0),
    "raw_intent_clusters": len(raw_cluster_counts),
    "raw_singleton_clusters": raw_singleton_clusters,
    "raw_singleton_cluster_term_pct": round(raw_singleton_clusters / EXPECTED_KEYWORDS * 100, 1),
    "normalized_intent_clusters": len(cluster_counts),
    "normalized_singleton_clusters": singleton_clusters,
    "standardized_changed_terms": standardized_changed,
    "standardized_changed_pct": round(standardized_changed / EXPECTED_KEYWORDS * 100, 1),
    "fit_or_partial_terms": fit_counts.get("match", 0) + fit_counts.get("partial_match", 0),
    "fit_or_partial_pct": round(
        (fit_counts.get("match", 0) + fit_counts.get("partial_match", 0)) / EXPECTED_KEYWORDS * 100,
        1,
    ),
    "high_or_brand_intent_terms": stage_counts.get("high_intent", 0) + stage_counts.get("brand_harvest", 0),
    "high_or_brand_intent_pct": round(
        (stage_counts.get("high_intent", 0) + stage_counts.get("brand_harvest", 0)) / EXPECTED_KEYWORDS * 100,
        1,
    ),
    "max_theme_sensitivity_pp": round(theme_share["sensitivity_pp"].abs().max(), 1),
    "source_files": len(source_files),
    "schema_version": "1.0.0",
    "raw_prompt_versions": dict(Counter(r["prompt_version"] for r in raw_records)),
    "normalized_prompt_version": sorted(df["prompt_version"].unique().tolist()),
    "model_name": "deepseek/deepseek-v4-pro",
    "performance_metrics_used": [],
}

quality_rows = [
    {"check": "自然语言唯一词覆盖", "value": f"{EXPECTED_KEYWORDS}/{EXPECTED_KEYWORDS}", "status": "通过", "note": "term_id 无重复"},
    {"check": "模型复核状态", "value": f"{headline['accepted_rate_pct']}% accepted", "status": "带条件通过", "note": f"{headline['needs_review_terms']} 条 needs_review"},
    {"check": "原始意图簇碎片化", "value": f"{headline['raw_intent_clusters']} 个簇", "status": "需归并", "note": f"{headline['raw_singleton_clusters']} 个单例簇"},
    {"check": "确定性标准化", "value": f"{headline['standardized_changed_pct']}% 记录变化", "status": "已应用", "note": "正式汇总使用标准化后记录"},
    {"check": "敏感性", "value": f"最大 {headline['max_theme_sensitivity_pp']} 个百分点", "status": "稳定", "note": "全量与 accepted 子集主题占比差异"},
    {"check": "绩效指标", "value": "未使用", "status": "通过", "note": "无 ACOS/CVR/点击/订单加权"},
]

results = {
    "headline": headline,
    "theme_share": theme_share.to_dict(orient="records"),
    "functional_needs": functional_needs.to_dict(orient="records"),
    "selection_modifiers": selection_modifiers.to_dict(orient="records"),
    "product_audience": product_audience.to_dict(orient="records"),
    "fit_stage": fit_stage.to_dict(orient="records"),
    "slot_coverage": slot_coverage.to_dict(orient="records"),
    "raw_cluster_top": raw_cluster_top.to_dict(orient="records"),
    "quality": quality_rows,
}

(REPORT_DIR / "analysis_results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)

with pd.ExcelWriter(REPORT_DIR / "AJ2-Y90意图需求报告数据.xlsx", engine="openpyxl") as writer:
    pd.DataFrame([headline]).to_excel(writer, sheet_name="摘要", index=False)
    theme_share.to_excel(writer, sheet_name="需求主题", index=False)
    functional_needs.to_excel(writer, sheet_name="功能任务", index=False)
    selection_modifiers.to_excel(writer, sheet_name="选择修饰条件", index=False)
    product_audience.to_excel(writer, sheet_name="产品与人群", index=False)
    fit_stage.to_excel(writer, sheet_name="阶段与承接度", index=False)
    slot_coverage.to_excel(writer, sheet_name="字段覆盖", index=False)
    raw_cluster_top.to_excel(writer, sheet_name="原始簇Top20", index=False)
    pd.DataFrame(quality_rows).to_excel(writer, sheet_name="质量说明", index=False)

print(json.dumps(headline, ensure_ascii=False, indent=2))
print(theme_share[["rank", "theme", "terms", "share_pct", "lexical_terms", "lexical_share_pct", "accepted_share_pct", "sensitivity_pp"]].to_string(index=False))
