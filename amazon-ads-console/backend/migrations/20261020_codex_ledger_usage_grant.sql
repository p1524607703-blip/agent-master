-- Explicit owner-run permission change. No schema or business data changes.
-- Runtime can enrich missing usage, not edit identities, times or credentials.
GRANT UPDATE (input_tokens, output_tokens, total_tokens, cached_tokens, reasoning_tokens, completed)
ON codex_ops.model_requests TO amazon_ads_admin;
