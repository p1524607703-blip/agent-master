import Ajv from "ajv";
import { describe, expect, it } from "vitest";
import {
  FOOTWEAR_PROMPT_VERSION,
  SCHEMA_VERSION,
  promptPlanSchema,
  type GeneratedPromptPlan,
  type PromptLanguage,
  type PromptCaseDefinition
} from "./index.js";

const prompt: PromptCaseDefinition = {
  templateId: "footwear.category.baseline",
  enabled: true,
  slot: "category_baseline",
  mode: "blind",
  expression: "direct",
  promptText: "Recommend five women's walking shoes for everyday use.",
  testRole: "baseline",
  scoreEligible: false,
  hypothesis: "A broad category question measures discovery without proving attribute alignment.",
  expectedMatch: "neutral",
  evidenceFactIds: ["fact-product-type"],
  requiredTerms: ["women's", "walking shoes"],
  judgmentCriteria: ["Record inclusion and rank as an observational baseline; do not add it to the main score."],
  promptVersion: FOOTWEAR_PROMPT_VERSION,
  sessionPolicy: "fresh",
  generatedBy: "deterministic"
};

function plan(prompts: PromptCaseDefinition[] = [prompt], promptLanguage: PromptLanguage = "en-US"): GeneratedPromptPlan {
  return {
    schemaVersion: SCHEMA_VERSION,
    promptVersion: FOOTWEAR_PROMPT_VERSION,
    preset: "smoke",
    promptLanguage,
    sessionPolicy: "fresh",
    prompts
  };
}

describe("promptPlanSchema", () => {
  const validate = new Ajv({ allErrors: true, strict: false }).compile(promptPlanSchema);

  it("accepts preset-sized footwear plans instead of requiring the legacy 15 questions", () => {
    expect(validate(plan([prompt, { ...prompt, templateId: "footwear.attribute.positive", slot: "attribute_positive" }, { ...prompt, templateId: "footwear.attribute.negative", slot: "attribute_negative" }]))).toBe(true);
    expect(validate(plan([{ ...prompt, enabled: false }]))).toBe(true);
  });

  it("accepts Simplified Chinese as a controlled question language", () => {
    const chinesePrompt = {
      ...prompt,
      promptText: "请推荐五款适合女士日常穿着的健走鞋。",
      requiredTerms: ["女士", "健走鞋"]
    };
    expect(validate(plan([chinesePrompt], "zh-CN")), JSON.stringify(validate.errors)).toBe(true);
  });

  it("requires audit and judgment metadata on every generated question", () => {
    const missingMetadata = structuredClone(plan()) as unknown as { prompts: Array<Record<string, unknown>> };
    delete missingMetadata.prompts[0].hypothesis;
    delete missingMetadata.prompts[0].judgmentCriteria;
    delete missingMetadata.prompts[0].enabled;
    expect(validate(missingMetadata)).toBe(false);
  });

  it("rejects unknown presets and score-role values", () => {
    const invalid = structuredClone(plan()) as unknown as { preset: string; prompts: Array<Record<string, unknown>> };
    invalid.preset = "legacy-15";
    invalid.prompts[0].testRole = "marketing_claim";
    expect(validate(invalid)).toBe(false);
  });

  it("keeps main-score eligibility and negative controls semantically consistent", () => {
    expect(validate(plan([{ ...prompt, scoreEligible: true }]))).toBe(false);
    expect(validate(plan([{ ...prompt, testRole: "negative_control", expectedMatch: "eligible" }]))).toBe(false);
    expect(validate(plan([{ ...prompt, testRole: "positive_control", scoreEligible: true, expectedMatch: "eligible" }]))).toBe(true);
  });

  it("requires sequence and rewrite audit metadata when those policies are used", () => {
    expect(validate(plan([{ ...prompt, sessionPolicy: "shared_sequence" }]))).toBe(false);
    expect(validate(plan([{ ...prompt, generatedBy: "deepseek_rewrite" }]))).toBe(false);
    expect(validate(plan([{
      ...prompt,
      sessionPolicy: "shared_sequence",
      sessionGroup: "fit_follow_up",
      generatedBy: "deepseek_rewrite",
      originalPromptText: prompt.promptText,
      rewriteReason: "Improved natural phrasing while retaining the test anchors."
    }]))).toBe(true);
  });
});
