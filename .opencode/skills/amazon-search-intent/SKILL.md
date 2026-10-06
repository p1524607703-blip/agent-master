---
name: amazon-search-intent
description: Tag Amazon advertising search terms into an auditable 18-field intent taxonomy, validate evidence spans and product fit, and route terms semantically without using ACOS, CVR, clicks, orders, sales, or other performance metrics. Use for AJ2-Y90 search-term classification, DeepSeek batch tagging, critic review, and workbook delivery.
---

# Amazon Search Intent

## Workflow

1. Read `references/taxonomy.md`, `references/record.schema.json`, and the selected product baseline.
2. Accept only search-term text, stable identifiers, and the page-validated product baseline. Never accept performance columns in model input.
3. Split inputs into `keyword`, `asin_target`, and `blank`. Only `keyword` records go to the model.
4. Populate all 18 main fields and the control fields. Use English `snake_case` tags and a Chinese complete sentence for `latent_task`.
5. For every non-empty inferred field, add evidence under `field_evidence`. Use only `explicit`, `page_validated`, or `inferred`; never emit `behavior_validated` in this workflow.
   Keep each rationale to one short clause and never duplicate the same `(field, value, evidence_type)` tuple.
6. Use page fact IDs from the product baseline for product claims. Do not elevate Alexa summaries, price, delivery, return notices, or medical-treatment claims into page evidence.
7. Validate output locally, then submit it to the independent critic. Stop the full run if pilot thresholds fail.

## Hard Constraints

- Do not use or mention ACOS, CVR, CTR, clicks, impressions, orders, sales, ROAS, conversion rate, or advertising performance to infer intent.
- Do not browse Amazon or enrich ASIN-form search terms. Route them to `asin_metadata_pending`.
- Do not invent medical efficacy, waterproofing, quick-dry performance, rating percentages, price, delivery, or inventory facts.
- Preserve brand, size, color, material, and negation evidence as auxiliary keys inside `field_evidence`.
- Treat semantic routing as a hypothesis. `semantic_negative_candidate` is not an automatic negative-keyword instruction.

## Resources

- Taxonomy and evidence rules: `references/taxonomy.md`
- JSON Schema: `references/record.schema.json`
- AJ2-Y90 product baseline: `references/product-B0GKDNPHJM.json`
- Pipeline entry point: `scripts/run_pipeline.py`
- Workbook builder: `scripts/build_workbook.mjs`
