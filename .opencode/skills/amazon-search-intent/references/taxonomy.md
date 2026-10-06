# AJ2-Y90 intent taxonomy

## Main fields

All machine tags use English `snake_case`. Array fields are JSON arrays.

1. `primary_domain`: one COSMO-style product domain.
2. `secondary_domain`: zero or more activity/context domains.
3. `product_type`: requested product class, not every noun in the query.
4. `audience_intent`: intended wearer or buyer.
5. `function_intent`: problem the user wants solved.
6. `capability_intent`: capability the product must provide.
7. `event_intent`: activity or event.
8. `location_intent`: place of use.
9. `body_need_intent`: foot/body condition or fit need.
10. `time_intent`: season, duration, or temporal condition.
11. `substitute_intent`: product role or substitute.
12. `complement_intent`: product commonly used together with the requested item.
13. `latent_task`: one complete Chinese sentence explaining who needs what for which task and constraints.
14. `intent_stage`: `exploration`, `consideration`, `high_intent`, `brand_harvest`, or `unknown`.
15. `evidence_type`: unique list drawn from `explicit`, `page_validated`, `inferred`.
16. `confidence_level`: `high`, `medium`, or `low`.
17. `intent_cluster`: concise reusable semantic cluster.
18. `routing_action`: one allowed semantic action.

## Evidence rules

- `explicit`: the search term itself states the value. `source_span` must be copied verbatim from the term.
- `page_validated`: the product baseline supports product fit; cite a baseline fact ID.
- `inferred`: commonsense interpretation. State the reasoning and lower confidence when alternatives are plausible.
- `behavior_validated` is forbidden because no behavioral or performance data enters the model.
- Brand, price, color, size, material, and negation are auxiliary keys in `field_evidence`, not extra main fields.

## Product-fit rules

- `match`: requested product, audience, and hard constraints are explicitly supported by the baseline.
- `partial_match`: core product is plausible, but one or more constraints are unsupported or only partially aligned.
- `mismatch`: product class, audience, or a hard constraint conflicts with the baseline.
- `unknown`: the query is too ambiguous to compare.
- `not_applicable`: used for ASIN targets and blanks.

## Routing rules

- `cluster_route`: clear semantic match suitable for an intent cluster.
- `listing_gap_review`: plausible demand, but requested evidence is absent from the product baseline.
- `ambiguity_review`: multiple reasonable interpretations or insufficient query detail.
- `semantic_negative_candidate`: clear semantic mismatch; requires later human/performance review before negation.
- `performance_observation`: semantically plausible but should be evaluated later using performance data outside this model.
- `asin_metadata_pending`: ASIN-form query, no enrichment performed.
- `blank_skip`: empty query.

