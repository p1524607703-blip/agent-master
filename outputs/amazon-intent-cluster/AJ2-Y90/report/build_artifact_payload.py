import json
from datetime import datetime, timezone
from pathlib import Path

root = Path.cwd()
report_dir = root / "outputs/amazon-intent-cluster/AJ2-Y90/report"
data = json.loads((report_dir / "analysis_results.json").read_text(encoding="utf-8"))
generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

headline = data["headline"]
product_rows = data["product_audience"]
core_terms = sum(
    row["terms"] for row in product_rows
    if row["dimension"] == "产品类型" and row["category"] in {"夹脚拖/人字拖", "其他凉鞋"}
)
women_terms = next(
    row["terms"] for row in product_rows
    if row["dimension"] == "使用人群" and row["category"] == "女士明确"
)

headline_dataset = [{
    "unique_terms": headline["unique_keyword_terms"],
    "core_product_terms": core_terms,
    "core_product_share": round(core_terms / headline["unique_keyword_terms"], 4),
    "women_terms": women_terms,
    "women_share": round(women_terms / headline["unique_keyword_terms"], 4),
    "support_terms": data["functional_needs"][0]["terms"],
    "support_share": data["functional_needs"][0]["share"],
    "style_terms": data["selection_modifiers"][0]["terms"],
    "style_share": data["selection_modifiers"][0]["share"],
    "accepted_terms": headline["accepted_terms"],
    "accepted_share": round(headline["accepted_terms"] / headline["unique_keyword_terms"], 4),
}]

fit_rows = [row for row in data["fit_stage"] if row["dimension"] == "asin_fit"]
recommendations = [
    {"priority": 1, "area": "SP关键词结构", "action": "基础品类、足弓支撑、湿区场景、颜色款式、竞品品牌分别建组", "reason": "避免不同购物任务在同一广告组中互相稀释"},
    {"priority": 2, "area": "Listing承接", "action": "保留女士、人字拖、足弓支撑、EVA、缓震、防滑等页面已有明示证据", "reason": "最大功能需求是足弓支撑，且页面已有合规证据"},
    {"priority": 3, "area": "场景词控制", "action": "海滩/泳池词单独观察；未获得页面证据前不宣称 waterproof 或 quick-dry", "reason": "湿区意图高，但商品基准未明示防水快干"},
    {"priority": 4, "area": "颜色与变体", "action": "按页面实际颜色承接高频颜色词，不支持颜色转 listing_gap_review", "reason": "颜色与外观是最常见的选择修饰条件"},
    {"priority": 5, "area": "竞品词", "action": "自有品牌词与竞品词拆分；高错配竞品词进入语义否定候选", "reason": "品牌导航与产品功能不是同一种意图"},
    {"priority": 6, "area": "下一轮验证", "action": "叠加搜索量、点击或AMC唯一用户再估算真实需求规模", "reason": "唯一词等权只能说明意图类型覆盖，不能代表用户人数"},
]

source = {
    "id": "source-aj2-intent",
    "label": "AJ2-Y90 全量搜索词意图标签",
    "query": {
        "engine": "python",
        "language": "python",
        "sql": "SELECT COUNT(DISTINCT term_id) AS unique_terms, SUM(CASE WHEN product_family IN ('flip_flop','thong_sandal','other_sandal') THEN 1 ELSE 0 END) AS core_product_terms, SUM(CASE WHEN audience_intent = 'women' THEN 1 ELSE 0 END) AS women_terms, SUM(CASE WHEN support_theme = 1 THEN 1 ELSE 0 END) AS support_terms, SUM(CASE WHEN style_color_theme = 1 THEN 1 ELSE 0 END) AS style_terms FROM aj2_y90_intent_labels WHERE query_kind = 'keyword';",
        "executed_at": generated_at,
        "description": "汇总pilot-0001..0005与full-0001..0115，按term_id去重，并应用run_pipeline.normalize_model_record后进行上层同义归并。",
        "tables_used": [
            "AJ2-Y90/_audit/responses/pilot-0001..0005",
            "AJ2-Y90/_audit/responses/full-0001..0115",
            "AJ2-Y90/_audit/manifests",
        ],
        "filters": [
            "query_kind = keyword",
            "2,394个唯一term_id等权",
            "不使用ACOS、CVR、点击、订单或销售额加权",
            "主题允许一词多标签",
        ],
        "metric_definitions": [
            "意图覆盖率 = 命中主题的唯一term_id数 / 2,394",
            "基础品类覆盖率 = 人字拖、夹趾凉鞋或其他凉鞋同义产品词数 / 2,394",
            "功能任务采用标准化18字段语义归并",
            "颜色、材质、尺码、价格采用搜索词原文审计；品牌同时参考brand_harvest阶段标签",
            "商品承接度仅表示语义match或partial_match，不表示广告转化绩效",
        ],
    },
}

manifest = {
    "version": 1,
    "surface": "report",
    "title": "AJ2-Y90 搜索词意图需求报告",
    "description": "识别用户最常表达的产品、功能、场景与选择条件，并映射到广告和Listing动作。",
    "generatedAt": generated_at,
    "sources": [source],
    "cards": [
        {"id": "card-sample", "dataset": "headline", "sourceId": "source-aj2-intent", "description": "全量自然语言唯一搜索词", "metrics": [{"label": "唯一自然语言词", "field": "unique_terms", "format": "number"}]},
        {"id": "card-core", "dataset": "headline", "sourceId": "source-aj2-intent", "description": "人字拖、夹趾凉鞋与其他凉鞋同义产品类型", "metrics": [{"label": "基础品类覆盖", "field": "core_product_share", "format": "percent"}, {"label": "词数", "field": "core_product_terms", "format": "number"}]},
        {"id": "card-women", "dataset": "headline", "sourceId": "source-aj2-intent", "description": "搜索词或意图标签明确指出女士", "metrics": [{"label": "明确女士受众", "field": "women_share", "format": "percent"}, {"label": "词数", "field": "women_terms", "format": "number"}]},
        {"id": "card-support", "dataset": "headline", "sourceId": "source-aj2-intent", "description": "标准化功能、能力与身体需求槽位归并", "metrics": [{"label": "足弓/足部健康", "field": "support_share", "format": "percent"}, {"label": "词数", "field": "support_terms", "format": "number"}]},
        {"id": "card-style", "dataset": "headline", "sourceId": "source-aj2-intent", "description": "搜索词原文中的颜色与外观风格修饰", "metrics": [{"label": "颜色与外观", "field": "style_share", "format": "percent"}, {"label": "词数", "field": "style_terms", "format": "number"}]},
    ],
    "charts": [
        {
            "id": "chart-functional",
            "title": "功能与使用场景意图覆盖率",
            "subtitle": "足弓支撑/足部健康是最常见功能任务",
            "type": "bar",
            "dataset": "functional_needs",
            "sourceId": "source-aj2-intent",
            "intent": "comparison",
            "encodings": {
                "x": {"field": "need", "type": "nominal", "label": "功能任务"},
                "y": {"field": "share", "type": "quantitative", "aggregate": "none", "format": "percent", "label": "唯一词覆盖率"},
                "tooltip": [{"field": "terms", "type": "quantitative", "format": "number", "label": "词数"}, {"field": "method", "type": "text", "label": "口径"}],
            },
            "layout": "full",
            "maxRows": 10,
        },
        {
            "id": "chart-modifiers",
            "title": "选择修饰条件覆盖率",
            "subtitle": "颜色和外观是最常见的最终选择条件",
            "type": "bar",
            "dataset": "selection_modifiers",
            "sourceId": "source-aj2-intent",
            "intent": "comparison",
            "encodings": {
                "x": {"field": "modifier", "type": "nominal", "label": "选择条件"},
                "y": {"field": "share", "type": "quantitative", "aggregate": "none", "format": "percent", "label": "唯一词覆盖率"},
                "tooltip": [{"field": "terms", "type": "quantitative", "format": "number", "label": "词数"}, {"field": "method", "type": "text", "label": "口径"}],
            },
            "layout": "full",
            "maxRows": 10,
        },
    ],
    "tables": [
        {
            "id": "table-themes",
            "title": "保守显式证据主题明细",
            "subtitle": "同一搜索词可命中多个主题",
            "dataset": "theme_share",
            "sourceId": "source-aj2-intent",
            "defaultSort": {"field": "rank", "direction": "asc"},
            "density": "dense",
            "layout": "full",
            "columns": [
                {"field": "rank", "label": "排名", "type": "number"},
                {"field": "theme", "label": "上层主题", "type": "text"},
                {"field": "terms", "label": "显式词数", "type": "number"},
                {"field": "share", "label": "显式覆盖率", "format": "percent"},
                {"field": "lexical_share_pct", "label": "原文审计%", "type": "number"},
                {"field": "definition", "label": "定义", "type": "text"},
            ],
        },
        {
            "id": "table-fit",
            "title": "标准化后的商品语义承接度",
            "subtitle": "Match与Partial Match合计86.7%，不代表转化效果",
            "dataset": "asin_fit",
            "sourceId": "source-aj2-intent",
            "defaultSort": {"field": "share", "direction": "desc"},
            "density": "dense",
            "layout": "full",
            "columns": [
                {"field": "category", "label": "承接状态", "type": "text"},
                {"field": "terms", "label": "词数", "type": "number"},
                {"field": "share", "label": "占比", "format": "percent"},
            ],
        },
        {
            "id": "table-recommendations",
            "title": "广告与Listing优先动作",
            "dataset": "recommendations",
            "sourceId": "source-aj2-intent",
            "defaultSort": {"field": "priority", "direction": "asc"},
            "density": "spacious",
            "layout": "full",
            "columns": [
                {"field": "priority", "label": "优先级", "type": "number"},
                {"field": "area", "label": "模块", "type": "text"},
                {"field": "action", "label": "动作", "type": "text"},
                {"field": "reason", "label": "原因", "type": "text"},
            ],
        },
    ],
    "blocks": [
        {"id": "title", "type": "markdown", "body": "# AJ2-Y90 搜索词意图需求报告", "layout": "full"},
        {"id": "summary", "type": "markdown", "sourceId": "source-aj2-intent", "body": "## Executive Summary\n\n本次已覆盖全部 **2,394 个唯一自然语言搜索词**。基础购物任务高度集中：**97.4%** 指向人字拖、夹趾凉鞋或其他凉鞋，**65.4%** 明确为女士。功能层面，**足弓支撑与足部健康（26.9%）** 最常见，其次是湿区/涉水场景（17.0%）和舒适缓震（14.5%）；选择层面，**颜色与外观（30.3%）** 是最常见修饰条件。没有任何单一细分功能超过全部词的一半，因此应采用“基础品类收割 + 支撑功能 + 湿区场景 + 颜色款式”的分层广告结构。", "layout": "full"},
        {"id": "metrics", "type": "metric-strip", "cardIds": ["card-sample", "card-core", "card-women", "card-support", "card-style"], "layout": "full"},
        {"id": "functional-heading", "type": "markdown", "sourceId": "source-aj2-intent", "body": "## 用户最想解决什么功能问题\n\n**足弓支撑与足部健康是第一功能任务。** 相关词包含 arch support、orthopedic、plantar fasciitis、foot pain、flat feet 等。湿区场景位居第二，说明用户经常把这类拖鞋放在海滩、泳池、淋浴或其他涉水环境中使用；但页面没有明示 waterproof 或 quick-dry，广告与Listing不能越过证据边界。", "layout": "full"},
        {"id": "functional-chart", "type": "chart", "chartId": "chart-functional", "layout": "full"},
        {"id": "modifier-heading", "type": "markdown", "sourceId": "source-aj2-intent", "body": "## 用户用什么条件做最终选择\n\n**颜色与外观的出现频率高于任何单一功能修饰。** 这意味着商品变体、主图颜色识别和颜色词承接会直接影响召回质量。品牌、材质、尺码是第二梯队；价格与配送词较少，说明这批搜索词更偏向产品与属性表达，而不是纯交易条件。", "layout": "full"},
        {"id": "modifier-chart", "type": "chart", "chartId": "chart-modifiers", "layout": "full"},
        {"id": "theme-heading", "type": "markdown", "body": "## 上层意图主题明细\n\n下表采用更保守的显式证据口径，同时保留原文审计比例作为敏感性参照。原始 intent_cluster 有 1,674 个名称，无法直接用于排名。", "layout": "full"},
        {"id": "themes-table", "type": "table", "tableId": "table-themes", "layout": "full"},
        {"id": "fit-heading", "type": "markdown", "sourceId": "source-aj2-intent", "body": "## 当前商品能承接多少意图\n\n标准化后，**46.9% 为 Match，39.8% 为 Partial Match，合计 86.7%**；13.0% 为 Mismatch。Partial Match主要意味着用户要求了页面未明确支持的颜色、价格、配送、材质、特殊鞋型或防水快干能力。该结果只表示语义承接，不等于广告转化或盈利能力。", "layout": "full"},
        {"id": "fit-table", "type": "table", "tableId": "table-fit", "layout": "full"},
        {"id": "recommend-heading", "type": "markdown", "body": "## Recommended Next Steps\n\n建议先按意图任务拆分广告结构，再补齐页面证据；不要把所有含 flip flops 的词放进同一广告组。", "layout": "full"},
        {"id": "recommend-table", "type": "table", "tableId": "table-recommendations", "layout": "full"},
        {"id": "questions", "type": "markdown", "body": "## Further Questions\n\n- 各颜色意图分别由哪些现有变体承接，哪些属于缺失颜色？\n- 竞品品牌词中，自有品牌 Joomra 与 Archies、FitFlop、Crocs 等竞品各占多少？\n- 哪些足病词属于高风险医疗宣称，只能投放而不能直接写入Listing？\n- 若按展示、点击或AMC唯一用户加权，功能需求排名是否仍然稳定？", "layout": "full"},
        {"id": "caveats", "type": "markdown", "sourceId": "source-aj2-intent", "body": "## Caveats and Assumptions\n\n- 这里统计的是 **唯一搜索词类型**，不是用户人数、搜索量、曝光或点击占比。\n- 主题为多标签，同一词可以同时命中颜色、支撑和涉水场景，因此比例不可相加。\n- 79条记录为 needs_review；剔除后主题占比最大变化仅0.3个百分点。\n- 原始响应混用Prompt 1.0/1.1，本报告已统一应用1.1确定性标准化；85.2%的记录至少一个字段发生控制性变化。\n- 打标和报告均未使用ACOS、CVR、点击、订单、销售额等绩效指标。\n- 商品页不明示治疗足底筋膜炎、防水快干或连续久站时长，这些不得作为已验证卖点。", "layout": "full"},
    ],
}

# Widget assets require complete source provenance, including the materialized
# SQL-equivalent aggregation contract, rather than only a source identifier.
for collection in ("cards", "charts", "tables"):
    for asset in manifest[collection]:
        asset["source"] = source

snapshot = {
    "version": 1,
    "generatedAt": generated_at,
    "status": "ready",
    "datasets": {
        "headline": headline_dataset,
        "functional_needs": data["functional_needs"],
        "selection_modifiers": data["selection_modifiers"],
        "theme_share": data["theme_share"],
        "asin_fit": fit_rows,
        "recommendations": recommendations,
        "quality": data["quality"],
    },
}

payload = {"manifest": manifest, "snapshot": snapshot, "sources": [source], "surface": "report"}
(report_dir / "artifact_payload.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
print(report_dir / "artifact_payload.json")
