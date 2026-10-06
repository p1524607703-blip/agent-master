import {
  EXPECTED_MATCHES,
  PRIMARY_DOMAINS,
  PROMPT_GENERATORS,
  PROMPT_LANGUAGES,
  RUN_PRESETS,
  SCHEMA_VERSION,
  SESSION_POLICIES,
  TEST_ROLES
} from "./types.js";

export const promptCaseDefinitionSchema = {
  type: "object",
  additionalProperties: false,
  required: [
    "templateId",
    "enabled",
    "slot",
    "mode",
    "expression",
    "promptText",
    "testRole",
    "scoreEligible",
    "hypothesis",
    "expectedMatch",
    "evidenceFactIds",
    "requiredTerms",
    "judgmentCriteria",
    "promptVersion",
    "sessionPolicy",
    "generatedBy"
  ],
  properties: {
    templateId: { type: "string", pattern: "^[a-z0-9][a-z0-9._-]{1,95}$" },
    enabled: { type: "boolean" },
    slot: { type: "string", minLength: 2, maxLength: 64 },
    mode: { enum: ["blind", "aided", "diagnostic"] },
    expression: { enum: ["direct", "natural_language", "task", "comparison", "conflict"] },
    promptText: { type: "string", minLength: 5, maxLength: 800 },
    testRole: { enum: TEST_ROLES },
    scoreEligible: { type: "boolean" },
    hypothesis: { type: "string", minLength: 3, maxLength: 1000 },
    expectedMatch: { enum: EXPECTED_MATCHES },
    evidenceFactIds: {
      type: "array",
      maxItems: 30,
      uniqueItems: true,
      items: { type: "string", minLength: 1, maxLength: 128 }
    },
    requiredTerms: {
      type: "array",
      minItems: 1,
      maxItems: 20,
      uniqueItems: true,
      items: { type: "string", minLength: 1, maxLength: 120 }
    },
    judgmentCriteria: {
      type: "array",
      minItems: 1,
      maxItems: 12,
      uniqueItems: true,
      items: { type: "string", minLength: 3, maxLength: 500 }
    },
    promptVersion: { type: "string", pattern: "^[a-z0-9][a-z0-9._-]{2,63}$" },
    sessionPolicy: { enum: SESSION_POLICIES },
    sessionGroup: { type: "string", minLength: 1, maxLength: 64 },
    generatedBy: { enum: PROMPT_GENERATORS },
    originalPromptText: { type: "string", minLength: 5, maxLength: 800 },
    rewriteReason: { type: "string", minLength: 3, maxLength: 1000 }
  },
  allOf: [
    {
      if: { properties: { scoreEligible: { const: true } }, required: ["scoreEligible"] },
      then: { properties: { testRole: { const: "positive_control" }, expectedMatch: { const: "eligible" } } }
    },
    {
      if: { properties: { testRole: { const: "negative_control" } }, required: ["testRole"] },
      then: { properties: { scoreEligible: { const: false }, expectedMatch: { const: "ineligible" } } }
    },
    {
      if: { properties: { sessionPolicy: { const: "shared_sequence" } }, required: ["sessionPolicy"] },
      then: { required: ["sessionGroup"] }
    },
    {
      if: { properties: { generatedBy: { const: "deepseek_rewrite" } }, required: ["generatedBy"] },
      then: { required: ["originalPromptText", "rewriteReason"] }
    }
  ]
} as const;

export const promptPlanSchema = {
  $id: "alexa-auditor-prompt-plan-v2",
  type: "object",
  additionalProperties: false,
  required: ["schemaVersion", "promptVersion", "preset", "promptLanguage", "sessionPolicy", "prompts"],
  properties: {
    schemaVersion: { const: SCHEMA_VERSION },
    promptVersion: { type: "string", pattern: "^[a-z0-9][a-z0-9._-]{2,63}$" },
    preset: { enum: RUN_PRESETS },
    promptLanguage: { enum: PROMPT_LANGUAGES },
    sessionPolicy: { enum: SESSION_POLICIES },
    prompts: {
      type: "array",
      minItems: 1,
      maxItems: 60,
      items: promptCaseDefinitionSchema
    }
  }
} as const;

export const intentProfileSchema = {
  $id: "alexa-auditor-intent-profile-v1",
  type: "object",
  additionalProperties: false,
  required: [
    "primary_domain", "secondary_domain", "product_type", "audience_intent", "function_intent",
    "capability_intent", "event_intent", "location_intent", "body_need_intent", "time_intent",
    "substitute_intent", "complement_intent", "latent_task", "intent_stage", "evidence_type",
    "confidence_level", "intent_cluster", "routing_action"
  ],
  properties: {
    primary_domain: { enum: PRIMARY_DOMAINS },
    secondary_domain: { type: "array", items: { type: "string" } },
    product_type: { type: "array", items: { type: "string" } },
    audience_intent: { type: "array", items: { type: "string" } },
    function_intent: { type: "array", items: { type: "string" } },
    capability_intent: { type: "array", items: { type: "string" } },
    event_intent: { type: "array", items: { type: "string" } },
    location_intent: { type: "array", items: { type: "string" } },
    body_need_intent: { type: "array", items: { type: "string" } },
    time_intent: { type: "array", items: { type: "string" } },
    substitute_intent: { type: "array", items: { type: "string" } },
    complement_intent: { type: "array", items: { type: "string" } },
    latent_task: { type: "string" },
    intent_stage: { enum: ["exploration", "consideration", "high_intent", "brand_harvest", "unknown"] },
    evidence_type: { type: "array", items: { enum: ["explicit", "page_validated", "inferred"] }, uniqueItems: true },
    confidence_level: { enum: ["high", "medium", "low"] },
    intent_cluster: { type: "string" },
    routing_action: { enum: ["cluster_route", "listing_gap_review", "ambiguity_review", "semantic_negative_candidate", "performance_observation"] }
  }
} as const;
