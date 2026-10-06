import Ajv from "ajv";
import { describe, expect, it } from "vitest";
import {
  FOOTWEAR_PROMPT_VERSION,
  SCHEMA_VERSION,
  promptPlanSchema,
  type EvidenceFact,
  type ProductSnapshot
} from "@alexa-auditor/contracts";
import { deterministicPromptPlan, expandAndShufflePrompts, generateFootwearPromptPlan } from "./prompt-builder";

const now = new Date().toISOString();
const fact = (
  id: string,
  field: string,
  value: string,
  sourceText: string,
  sourceSection: EvidenceFact["sourceSection"] = "bullets"
): EvidenceFact => ({ id, field, value, evidenceType: "page_validated", sourceSection, sourceText, confidence: "high", capturedAt: now });

const product: ProductSnapshot = {
  asin: "B0GKDNPHJM", requestedAsin: "B0GKDNPHJM", resolvedAsin: "B0GKDW7BDW", asinAliases: ["B0GKDNPHJM", "B0GKDW7BDW"],
  url: "https://www.amazon.com/dp/B0GKDNPHJM", marketplace: "amazon.com", title: "Joomra Women's Arch Support Flip Flops", brand: "Joomra",
  breadcrumb: [], bullets: [], specifications: { "Outer material": "EVA" }, aPlusText: "", reviewSummary: "", qaText: "",
  stableFacts: [
    fact("type", "product_type", "flip_flops", "Women's arch support flip flops", "title"),
    fact("audience", "audience_intent", "women", "Department: women", "specification"),
    fact("arch", "function_intent", "arch_support", "Ergonomic arch support provides all-day comfort"),
    fact("grip", "capability_intent", "slip_resistant", "Textured outsole provides slip-resistant grip"),
    fact("body", "body_need_intent", "arch_support_need", "Footbed supports an arch support need"),
    fact("event", "event_intent", "daily_wear", "One-piece design for long-term daily wear", "a_plus"),
    fact("location", "location_intent", "beach", "Suitable at the beach", "qa"),
    fact("material", "material", "EVA", "Outer material: EVA", "specification"),
    fact("substitute", "substitute_intent", "casual_sandals", "Casual sandals", "breadcrumb")
  ],
  volatileFacts: [fact("price", "price", "$9.96", "Current price $9.96", "retail")],
  intentProfile: {
    primary_domain: "clothing_shoes_jewelry", secondary_domain: ["sports_outdoors"], product_type: ["flip_flops"], audience_intent: ["women"],
    function_intent: ["arch_support"], capability_intent: ["slip_resistant"], event_intent: ["daily_wear"], location_intent: ["beach"],
    body_need_intent: ["arch_support_need"], time_intent: ["summer"], substitute_intent: ["casual_sandals"], complement_intent: [], latent_task: "", intent_stage: "consideration",
    evidence_type: ["page_validated"], confidence_level: "high", intent_cluster: "womens_arch_support_flip_flops", routing_action: "cluster_route"
  },
  accountLabel: "test", selectorVersion: "fixture-v1", schemaVersion: SCHEMA_VERSION, capturedAt: now
};

describe("footwear V4 dual-track prompt builder", () => {
  it("builds schema-valid smoke, calibration, and full presets", () => {
    const validate = new Ajv({ strict: false }).compile(promptPlanSchema);
    const smoke = generateFootwearPromptPlan(product, "smoke");
    const calibration = generateFootwearPromptPlan(product, "calibration");
    const full = generateFootwearPromptPlan(product, "full");

    expect(smoke.prompts).toHaveLength(5);
    expect(calibration.prompts).toHaveLength(9);
    expect(full.prompts).toHaveLength(11);
    expect(smoke.prompts.filter((item) => item.sessionPolicy === "fresh")).toHaveLength(3);
    expect(smoke.prompts.filter((item) => item.sessionPolicy === "shared_sequence")).toHaveLength(2);
    expect(calibration.prompts.filter((item) => item.sessionPolicy === "fresh")).toHaveLength(5);
    expect(calibration.prompts.filter((item) => item.sessionPolicy === "shared_sequence")).toHaveLength(4);
    expect(full.prompts.filter((item) => item.sessionPolicy === "fresh")).toHaveLength(5);
    expect(full.prompts.filter((item) => item.sessionPolicy === "shared_sequence")).toHaveLength(6);
    expect(full.promptVersion).toBe(FOOTWEAR_PROMPT_VERSION);
    expect(validate(smoke), JSON.stringify(validate.errors)).toBe(true);
    expect(validate(calibration), JSON.stringify(validate.errors)).toBe(true);
    expect(validate(full), JSON.stringify(validate.errors)).toBe(true);
  });

  it("keeps fixed templates generic while dynamically binding page evidence", () => {
    const plan = deterministicPromptPlan(product);
    const direct = plan.find((item) => item.templateId === "footwear.control.primary-function-direct.v4")!;

    expect(plan).toHaveLength(11);
    expect(plan.every((item) => item.enabled)).toBe(true);
    expect(plan.every((item) => !item.promptText.toLowerCase().includes("joomra"))).toBe(true);
    expect(plan.every((item) => !item.promptText.includes(product.asin))).toBe(true);
    expect(plan.filter((item) => item.sessionPolicy === "fresh").every((item) => item.promptText.startsWith("Treat this message as a new independent request."))).toBe(true);
    expect(plan.find((item) => item.templateId === "footwear.progressive.01-category.v4")?.promptText).toContain("without referring to or continuing any prior conversation");
    expect(plan.find((item) => item.templateId === "footwear.progressive.02-alexa-score.v4")?.promptText).not.toContain("new independent request");
    expect(direct.promptText).toContain("arch support");
    expect(direct.requiredTerms).toEqual(expect.arrayContaining(["flip flops", "arch support"]));
    expect(direct.evidenceFactIds).toEqual(expect.arrayContaining(["type", "arch"]));
    expect(direct.testRole).toBe("positive_control");
    expect(direct.scoreEligible).toBe(true);
    expect(direct.expectedMatch).toBe("eligible");
    expect(direct.judgmentCriteria.length).toBeGreaterThan(0);
    const natural = plan.find((item) => item.templateId === "footwear.control.primary-function-natural.v4")!;
    expect(natural.promptText).toContain("arches feel tired and unsupported");
    expect(natural.promptText).not.toContain("arch support");
    expect(natural.evidenceFactIds).toContain("arch");
    expect(natural.slot).toBe(direct.slot);
    const comparison = plan.find((item) => item.templateId === "footwear.control.comparison.v4")!;
    expect(comparison.expression).toBe("comparison");
    expect(comparison.scoreEligible).toBe(true);
    const progressive = plan.filter((item) => item.sessionPolicy === "shared_sequence");
    expect(progressive).toHaveLength(6);
    expect(progressive.every((item) => item.testRole === "diagnostic" && !item.scoreEligible)).toBe(true);
    expect(new Set(progressive.map((item) => item.sessionGroup))).toEqual(new Set(["footwear_progressive_intent"]));
  });

  it("builds a schema-valid Simplified Chinese plan with localized dynamic footwear values", () => {
    const validate = new Ajv({ strict: false }).compile(promptPlanSchema);
    const full = generateFootwearPromptPlan(product, "full", "zh-CN");

    expect(validate(full), JSON.stringify(validate.errors)).toBe(true);
    expect(full.promptLanguage).toBe("zh-CN");
    expect(full.prompts).toHaveLength(11);
    expect(full.prompts.every((item) => /[\u3400-\u9fff]/u.test(item.promptText))).toBe(true);
    expect(full.prompts.every((item) => !item.promptText.toLowerCase().includes("joomra"))).toBe(true);
    expect(full.prompts.every((item) => !item.promptText.includes(product.asin))).toBe(true);
    const normalizedText = (value: string) => value.normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}$]+/gu, " ").replace(/\s+/g, " ").trim();
    expect(full.prompts.every((item) => item.requiredTerms.every((term) => normalizedText(item.promptText).includes(normalizedText(term))))).toBe(true);

    const baseline = full.prompts.find((item) => item.templateId === "footwear.control.category-baseline.v4")!;
    expect(baseline.promptText).toContain("我想购买适合女士日常穿着的人字拖");
    expect(baseline.promptText).toContain("全部候选，不要只做Top5");
    expect(baseline.promptText).toContain("Amazon商品链接");
    expect(baseline.requiredTerms).toEqual(expect.arrayContaining(["女士", "人字拖", "全部候选", "不要只做Top5", "Amazon商品链接", "只依据本条需求回答", "不引用或延续任何先前对话"]));
    expect(baseline.promptText).toContain("请把本条消息视为全新的独立请求");

    const direct = full.prompts.find((item) => item.templateId === "footwear.control.primary-function-direct.v4")!;
    expect(direct.promptText).toContain("足弓支撑");
    expect(direct.requiredTerms).toEqual(expect.arrayContaining(["女士", "人字拖", "足弓支撑"]));
    expect(direct.evidenceFactIds).toEqual(expect.arrayContaining(["type", "arch"]));
    expect(direct.testRole).toBe("positive_control");
    expect(direct.scoreEligible).toBe(true);

    const natural = full.prompts.find((item) => item.templateId === "footwear.control.primary-function-natural.v4")!;
    expect(natural.promptText).toContain("足弓会感到疲劳且缺乏支撑");
    expect(natural.promptText).not.toContain("arch support");

    const negative = full.prompts.find((item) => item.templateId === "footwear.control.negative-category.v4")!;
    expect(negative.promptText).toContain("包头防水徒步靴");
    expect(negative.promptText).toContain("明确排除任何人字拖");

    const progressive = full.prompts.filter((item) => item.sessionPolicy === "shared_sequence");
    expect(progressive.map((item) => item.templateId)).toEqual([
      "footwear.progressive.01-category.v4",
      "footwear.progressive.02-alexa-score.v4",
      "footwear.progressive.03-screening-transparency.v4",
      "footwear.progressive.04-entry-hypotheses.v4",
      "footwear.progressive.05-scene-narrowing.v4",
      "footwear.progressive.06-budget-rescore.v4"
    ]);
    expect(progressive[1].promptText).toContain("权重合计100");
    expect(progressive[1].promptText).toContain("不要再次乘权重");
    expect(progressive[3].promptText).toContain("最多3条自然用户问法");
    expect(progressive[4].promptText).toContain("适合日常穿着");
    expect(progressive[5].promptText).toContain("15美元以内");
    expect(progressive[5].promptText).toContain("沿用P2的同一评分标准复评分");
  });

  it("keeps unknown dynamic labels visible as a safe fallback inside Chinese scaffolding", () => {
    const niche: ProductSnapshot = {
      ...product,
      intentProfile: {
        ...product.intentProfile,
        product_type: ["orthopedic_house_shoes"],
        audience_intent: ["caregivers"]
      },
      stableFacts: [
        ...product.stableFacts.filter((item) => !["type", "audience"].includes(item.id)),
        fact("type-niche", "product_type", "orthopedic_house_shoes", "Orthopedic house shoes", "title"),
        fact("audience-niche", "audience_intent", "caregivers", "Designed for caregivers", "specification")
      ]
    };
    const baseline = deterministicPromptPlan(niche, "smoke", "zh-CN")[0];

    expect(baseline.promptText).toContain("orthopedic house shoes");
    expect(baseline.promptText).toContain("caregivers");
    expect(baseline.promptText).toMatch(/购买.*日常穿着/);
    expect(baseline.evidenceFactIds).toEqual(expect.arrayContaining(["type-niche", "audience-niche"]));
  });

  it("matches Chinese intent labels to Chinese page evidence without losing score eligibility", () => {
    const chineseEvidence: ProductSnapshot = {
      ...product,
      stableFacts: [
        fact("type-zh", "产品类型", "人字拖", "女士足弓支撑人字拖", "title"),
        fact("audience-zh", "适用人群", "女士", "适用人群：女士", "specification"),
        fact("function-zh", "功能意图", "足弓支撑", "符合人体工学的足弓支撑带来全天舒适体验")
      ],
      intentProfile: {
        ...product.intentProfile,
        product_type: ["人字拖"],
        audience_intent: ["女士"],
        function_intent: ["足弓支撑"],
        capability_intent: [],
        body_need_intent: [],
        event_intent: [],
        location_intent: [],
        substitute_intent: []
      }
    };
    const direct = deterministicPromptPlan(chineseEvidence, "smoke", "zh-CN")
      .find((item) => item.templateId === "footwear.control.primary-function-direct.v4")!;

    expect(direct.promptText).toContain("我只考虑女士人字拖，需要明确具备足弓支撑");
    expect(direct.promptText).toContain("无法验证的功能不要推断");
    expect(direct.evidenceFactIds).toEqual(expect.arrayContaining(["type-zh", "function-zh"]));
    expect(direct.testRole).toBe("positive_control");
    expect(direct.scoreEligible).toBe(true);
  });

  it("never promotes a fallback function phrase to scoreable evidence", () => {
    const withoutFunctionIntent: ProductSnapshot = {
      ...product,
      intentProfile: { ...product.intentProfile, function_intent: [] },
      stableFacts: [...product.stableFacts, fact("generic-comfort", "function_intent", "comfortable_fit", "Comfortable fit with support")]
    };
    const controls = deterministicPromptPlan(withoutFunctionIntent)
      .filter((item) => ["footwear.control.primary-function-direct.v4", "footwear.control.primary-function-natural.v4", "footwear.control.comparison.v4"].includes(item.templateId));

    expect(controls).toHaveLength(3);
    expect(controls.every((item) => item.testRole === "diagnostic" && !item.scoreEligible)).toBe(true);
    expect(controls.every((item) => !item.evidenceFactIds.includes("generic-comfort"))).toBe(true);
  });

  it("keeps review-only function claims out of score-eligible controls", () => {
    const reviewOnlyFunction: ProductSnapshot = {
      ...product,
      stableFacts: [
        ...product.stableFacts.filter((item) => !["arch", "body", "type"].includes(item.id)),
        fact("type-clean", "product_type", "flip_flops", "Women's flip flops", "title"),
        fact("review-function", "function_intent", "arch_support", "A reviewer mentions arch support", "review_summary")
      ],
      intentProfile: { ...product.intentProfile, function_intent: ["arch_support"] }
    };
    const direct = deterministicPromptPlan(reviewOnlyFunction).find((item) => item.templateId === "footwear.control.primary-function-direct.v4")!;

    expect(direct.promptText).toContain("arch support");
    expect(direct.evidenceFactIds).not.toContain("review-function");
    expect(direct.testRole).toBe("diagnostic");
    expect(direct.scoreEligible).toBe(false);
  });

  it("defines an explicit, non-scoreable negative control with inverse judgment", () => {
    const negative = deterministicPromptPlan(product, "smoke")[2];
    expect(negative.testRole).toBe("negative_control");
    expect(negative.scoreEligible).toBe(false);
    expect(negative.expectedMatch).toBe("ineligible");
    expect(negative.promptText).toContain("closed-toe waterproof hiking boots");
    expect(negative.promptText).toContain("explicitly exclude all flip flops");
  });

  it("is reproducibly shuffled, preserves metadata, and excludes disabled definitions", () => {
    const plan = deterministicPromptPlan(product);
    plan[0] = { ...plan[0], enabled: false };
    const a = expandAndShufflePrompts(plan, product, "run", "seed", 1);
    const b = expandAndShufflePrompts(plan, product, "run", "seed", 1);

    expect(a.map((item) => item.id)).toEqual(b.map((item) => item.id));
    expect(a).toHaveLength(10);
    expect(a.some((item) => item.templateId === "footwear.control.category-baseline.v4")).toBe(false);
    expect(a.slice(0, 4).every((item) => item.sessionPolicy === "fresh")).toBe(true);
    expect(a.slice(4).map((item) => item.templateId)).toEqual([
      "footwear.progressive.01-category.v4",
      "footwear.progressive.02-alexa-score.v4",
      "footwear.progressive.03-screening-transparency.v4",
      "footwear.progressive.04-entry-hypotheses.v4",
      "footwear.progressive.05-scene-narrowing.v4",
      "footwear.progressive.06-budget-rescore.v4"
    ]);
    expect(a.every((item) => item.revision === 1 && item.editable)).toBe(true);
    expect(a.find((item) => item.testRole === "positive_control")?.judgmentCriteria.length).toBeGreaterThan(0);
    expect(() => expandAndShufflePrompts(plan, product, "run", "seed", 2)).toThrow(/exactly one execution/);
  });

  it("does not add brand or ASIN recognition conversations outside the two capped tracks", () => {
    const plan = deterministicPromptPlan(product, "full", "zh-CN");
    const expanded = expandAndShufflePrompts(plan, product, "run-zh", "seed-zh", 1, "zh-CN");

    expect(expanded).toHaveLength(11);
    expect(expanded.filter((item) => item.sessionPolicy === "fresh")).toHaveLength(5);
    expect(expanded.filter((item) => item.sessionPolicy === "shared_sequence")).toHaveLength(6);
    expect(expanded.every((item) => item.mode !== "aided" && item.testRole !== "aided_recognition")).toBe(true);
    expect(expanded.every((item) => !item.promptText.toLowerCase().includes(product.brand.toLowerCase()))).toBe(true);
    expect(expanded.every((item) => !item.promptText.includes(product.asin))).toBe(true);
  });
});
