import { describe, expect, it } from "vitest";
import {
  calculateScore,
  calculateTurnJudgments,
  isOwnProduct,
  rankValue,
  SCHEMA_VERSION,
  type ConversationTurn,
  type ExpectedMatch,
  type ProductSnapshot,
  type PromptCase,
  type TestRole
} from "./index.js";

const product: ProductSnapshot = {
  asin: "B0PARENT01",
  requestedAsin: "B0PARENT01",
  resolvedAsin: "B0CHILD001",
  asinAliases: ["B0PARENT01", "B0CHILD001"],
  url: "https://www.amazon.com/dp/B0PARENT01",
  marketplace: "amazon.com",
  title: "Joomra Women's Arch Support Flip Flops",
  brand: "Joomra",
  breadcrumb: [], bullets: [], specifications: {}, aPlusText: "", reviewSummary: "", qaText: "",
  stableFacts: [{ id: "arch", field: "function_intent", value: "arch_support", evidenceType: "page_validated", sourceSection: "bullets", sourceText: "Ergonomic arch support", confidence: "high", capturedAt: new Date().toISOString() }],
  volatileFacts: [],
  intentProfile: {
    primary_domain: "clothing_shoes_jewelry", secondary_domain: [], product_type: ["flip_flops"], audience_intent: ["women"],
    function_intent: ["arch_support"], capability_intent: [], event_intent: [], location_intent: [], body_need_intent: [], time_intent: [], substitute_intent: [], complement_intent: [], latent_task: "女士寻找有足弓支撑的人字拖。", intent_stage: "consideration", evidence_type: ["page_validated"], confidence_level: "high", intent_cluster: "womens_arch_support_flip_flops", routing_action: "cluster_route"
  },
  accountLabel: "test", selectorVersion: "fixture-v1", schemaVersion: SCHEMA_VERSION, capturedAt: new Date().toISOString()
};

function prompt(
  id: string,
  testRole: TestRole = "positive_control",
  expectedMatch: ExpectedMatch = "eligible",
  scoreEligible = testRole === "positive_control",
  expression: PromptCase["expression"] = "direct"
): PromptCase {
  const repeatMatch = /:r(\d+)$/.exec(id);
  return {
    id,
    templateId: id.replace(/:r\d+$/, ""),
    slot: id.replace(/:r\d+$/, ""),
    mode: testRole === "aided_recognition" ? "aided" : testRole === "diagnostic" ? "diagnostic" : "blind",
    expression,
    promptText: "women arch support flip flops",
    enabled: true,
    testRole,
    scoreEligible,
    hypothesis: "The tested product is aligned with explicit page evidence.",
    expectedMatch,
    evidenceFactIds: scoreEligible ? ["arch"] : [],
    requiredTerms: ["arch support"],
    judgmentCriteria: ["Observe whether the product enters the complete result list."],
    promptVersion: "footwear-v1",
    sessionPolicy: "fresh",
    generatedBy: "deterministic",
    repeatIndex: Number(repeatMatch?.[1] || 1),
    sequence: 1,
    status: "pending",
    revision: 1,
    editable: true
  };
}

function turn(promptCase: PromptCase, rank: number, responseText = ""): ConversationTurn {
  return {
    runId: "run", promptCaseId: promptCase.id, promptText: promptCase.promptText, responseText,
    recommendations: rank ? [{ asin: product.resolvedAsin!, title: product.title, brand: product.brand, rank, url: product.url, priceText: "", ratingText: "", reviewCountText: "", sponsored: false, deliveryText: "", evidenceText: "ergonomic arch support" }] : [],
    selectorVersion: "fixture-v1", status: "completed", capturedAt: new Date().toISOString()
  };
}

function alignedFixture() {
  const prompts = Array.from({ length: 5 }, (_, group) => Array.from({ length: 2 }, (_, repeat) =>
    prompt(`aligned_${group}:r${repeat + 1}`, "positive_control", "eligible", true, group === 4 ? "comparison" : "direct")
  )).flat();
  const turns = prompts.map((item, index) => turn(item, (index % 5) + 1));
  return { prompts, turns };
}

describe("scoring", () => {
  it("matches parent and selected child ASIN aliases before fuzzy title", () => {
    const child = { ...turn(prompt("alias:r1"), 1).recommendations[0], asin: "B0CHILD001", title: "unrelated card title" };
    expect(isOwnProduct(child, product)).toBe(true);
  });

  it("gives rank one the maximum rank value", () => {
    expect(rankValue(1)).toBe(100);
    expect(rankValue(6)).toBeGreaterThan(0);
    expect(rankValue(0)).toBe(0);
  });

  it("scores only page-aligned positive controls", () => {
    const fixture = alignedFixture();
    const baseline = prompt("baseline:r1", "baseline", "neutral", false);
    const retail = prompt("retail:r1", "retail_probe", "neutral", false);
    const score = calculateScore([...fixture.turns, turn(baseline, 0), turn(retail, 1)], product, [...fixture.prompts, baseline, retail]);
    expect(score.total).not.toBeNull();
    expect(score.sampleSize).toBe(10);
    expect(score.probes.baseline.sampleSize).toBe(1);
    expect(score.probes.retailProbe.includedCount).toBe(1);
    expect(score.formulaVersion).toBe("2.1.0");
    expect(score.standardsVersion).toBe("footwear-judgment-v2");
  });

  it("keeps exclusion, aided recognition, and diagnostic outcomes outside the main score", () => {
    const fixture = alignedFixture();
    const negative = prompt("negative:r1", "negative_control", "ineligible", false);
    const aided = prompt("aided:r1", "aided_recognition", "neutral", false);
    const diagnostic = prompt("diagnostic:r1", "diagnostic", "diagnostic_only", false);
    const score = calculateScore(
      [...fixture.turns, turn(negative, 0), turn(aided, 0, "Joomra B0CHILD001 is recognized."), turn(diagnostic, 0, "The evidence is inconclusive.")],
      product,
      [...fixture.prompts, negative, aided, diagnostic]
    );
    expect(score.sampleSize).toBe(10);
    expect(score.probes.negativeControl.passRate).toBe(100);
    expect(score.probes.aidedRecognition.passRate).toBe(100);
    expect(score.probes.diagnostic.passRate).toBe(100);
  });

  it("scores the capped independent control set and excludes shared progressive turns", () => {
    const direct = { ...prompt("control-direct:r1"), slot: "control_primary_function" };
    const natural = { ...prompt("control-natural:r1"), slot: "control_primary_function", expression: "natural_language" as const };
    const comparison = { ...prompt("control-comparison:r1", "positive_control", "eligible", true, "comparison"), slot: "control_comparison" };
    const progressive = {
      ...prompt("progressive:r1"),
      sessionPolicy: "shared_sequence" as const,
      sessionGroup: "footwear_progressive_intent"
    };
    const score = calculateScore(
      [turn(direct, 1), turn(natural, 2), turn(comparison, 1), turn(progressive, 1)],
      product,
      [direct, natural, comparison, progressive]
    );

    expect(score.sampleSize).toBe(3);
    expect(score.expectedPromptGroups).toBe(2);
    expect(score.dimensions.consistency).toBeGreaterThan(0);
    expect(score.total).not.toBeNull();
    expect(score.judgments.find((item) => item.promptCaseId === progressive.id)?.scoreEligible).toBe(false);
  });

  it("records transparent constraint and evidence judgments", () => {
    const caseItem = prompt("evidence:r1");
    const judgment = calculateTurnJudgments([turn(caseItem, 2)], product, [caseItem])[0];
    expect(judgment).toMatchObject({
      scoreEligible: true,
      ownIncluded: true,
      ownRank: 2,
      constraintOutcome: "pass",
      evidenceOutcome: "pass"
    });
    expect(judgment.reasonCodes).toContain("all_attached_page_evidence_supported");
  });

  it("excludes a declared positive control when its page evidence mapping is invalid", () => {
    const invalid = { ...prompt("invalid:r1"), evidenceFactIds: ["missing-fact"] };
    const score = calculateScore([turn(invalid, 1)], product, [invalid]);
    expect(score.sampleSize).toBe(0);
    expect(score.total).toBeNull();
    expect(score.judgments[0].constraintOutcome).toBe("insufficient_evidence");
    expect(score.judgments[0].reasonCodes).toContain("page_evidence_alignment_invalid");
  });

  it("does not treat a review-only claim as score-eligible page evidence", () => {
    const reviewProduct: ProductSnapshot = {
      ...product,
      stableFacts: [{ ...product.stableFacts[0], id: "review-wide", value: "wide_feet", sourceSection: "review_summary", sourceText: "One reviewer says it fits wide feet" }]
    };
    const reviewPrompt = { ...prompt("review:r1"), evidenceFactIds: ["review-wide"] };
    const score = calculateScore([turn(reviewPrompt, 1)], reviewProduct, [reviewPrompt]);
    expect(score.sampleSize).toBe(0);
    expect(score.judgments[0].reasonCodes).toContain("page_evidence_alignment_invalid");
  });

  it("does not silently score historical turns without prompt metadata", () => {
    const orphan = turn(prompt("orphan:r1"), 1);
    const score = calculateScore([orphan], product, []);
    expect(score.total).toBeNull();
    expect(score.sampleSize).toBe(0);
    expect(score.judgments[0].reasonCodes).toContain("prompt_metadata_missing");
  });

  it("ignores disabled prompts in both the main score and probe samples", () => {
    const disabledPositive = { ...prompt("disabled-positive:r1"), enabled: false };
    const disabledBaseline = { ...prompt("disabled-baseline:r1", "baseline", "neutral", false), enabled: false };
    const score = calculateScore([turn(disabledPositive, 1), turn(disabledBaseline, 1)], product, [disabledPositive, disabledBaseline]);
    expect(score.sampleSize).toBe(0);
    expect(score.expectedPromptGroups).toBe(0);
    expect(score.probes.baseline.sampleSize).toBe(0);
    expect(score.judgments.every((judgment) => judgment.reasonCodes.includes("prompt_disabled"))).toBe(true);
  });

  it("suppresses precision for an otherwise aligned but undersized sample", () => {
    const one = prompt("one:r1");
    expect(calculateScore([turn(one, 1)], product, [one]).total).toBeNull();
  });
});
