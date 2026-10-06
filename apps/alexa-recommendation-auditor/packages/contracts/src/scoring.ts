import type {
  ConversationTurn,
  ExpectedMatch,
  ProbeMetric,
  ProductSnapshot,
  PromptCase,
  RecommendationItem,
  ScoreDimensions,
  ScoreSnapshot,
  TestRole,
  TurnJudgment
} from "./types.js";

const WEIGHTS: Record<keyof ScoreDimensions, number> = {
  inclusion: 0.35,
  rank: 0.25,
  comparison: 0.15,
  evidence: 0.15,
  consistency: 0.1
};

const SCORE_ELIGIBLE_PAGE_SECTIONS = new Set(["title", "specification", "bullets", "a_plus", "breadcrumb"]);

export const SCORING_STANDARDS = {
  standardsVersion: "footwear-judgment-v2",
  formulaVersion: "2.1.0",
  scope: "Observable Alexa recommendation behavior for footwear; never an estimate of Amazon's internal weights.",
  developerCriteria: {
    executable: false,
    rule: "Per-question judgmentCriteria are human review notes. Machine scores are determined only by versioned role, session policy, eligibility, expected-match, page-evidence, the complete parsed result list, rank, comparison, and cross-expression consistency rules below."
  },
  mainScoreEligibility: {
    testRole: "positive_control",
    scoreEligible: true,
    expectedMatch: "eligible",
    pageEvidenceRequired: true,
    completedTurnRequired: true,
    sessionPolicy: "fresh"
  },
  roles: {
    baseline: "Broad category discovery is reported separately and never changes the main score.",
    positive_control: "Only page-evidence-aligned positive controls can contribute to the main score.",
    negative_control: "Measures correct exclusion when the tested product should not satisfy the stated constraint.",
    retail_probe: "Observes price, rating, review, inventory, and delivery sensitivity without judging semantic relevance.",
    aided_recognition: "Measures brand/ASIN recognition separately from blind discovery.",
    diagnostic: "Captures explanatory answers; no inclusion or ranking points are awarded."
  },
  constraintOutcomes: {
    eligible: "Pass only when the tested product appears in the complete parsed Alexa result list; absence is an observed failure, not proof of an internal recall rule.",
    ineligible: "Pass only when the tested product is absent from the complete parsed Alexa result list.",
    neutral: "Observe inclusion and rank without pass/fail.",
    diagnostic_only: "Not applicable to candidate inclusion."
  },
  evidenceOutcomes: {
    pass: "The tested product card's evidence text supports every page evidence fact attached to the prompt.",
    fail: "The tested product card contains evidence text but does not support every attached fact.",
    insufficient_evidence: "The product is included but no attributable card evidence is available, or the prompt lacks valid page evidence.",
    not_applicable: "The product is absent or the prompt does not require product evidence."
  },
  evidenceMatchingRule: {
    source: "Only the tested product card's attributable evidenceText is evaluated; Alexa's free-form explanation is not substituted for card evidence.",
    normalization: "NFKC/lowercase normalization removes punctuation and collapses whitespace before comparison.",
    pass: "A fact passes when its normalized value appears as a phrase, or when at least min(2, fact tokens) and at least 50% of non-stopword tokens from value/sourceText appear in the card evidence.",
    aggregation: "Every evidence fact attached to the prompt must pass; otherwise the evidence outcome is fail or insufficient_evidence."
  },
  reasonCodes: {
    prompt_metadata_missing: "The turn cannot be tied to a versioned prompt definition and is excluded from the main score.",
    prompt_disabled: "The developer disabled this prompt; any historical turn remains visible but is ignored by all metrics.",
    turn_not_completed: "The Alexa turn failed or was skipped and cannot be judged as a completed observation.",
    page_evidence_alignment_invalid: "A declared positive control lacks a complete mapping to current stable page evidence.",
    own_product_in_results: "A parent, selected child, or registered ASIN alias of the tested product appears in the complete parsed result list.",
    own_product_not_in_results: "No registered ASIN alias or conservative title match appears in the complete parsed result list.",
    all_attached_page_evidence_supported: "The attributable tested-product card text supports every attached page fact.",
    attached_page_evidence_not_fully_supported: "At least one attached page fact is not supported by attributable tested-product card text.",
    attributable_evidence_unavailable: "No reliable tested-product card evidence text is available for the evidence judgment."
  },
  probeMetrics: {
    baseline: "Broad discovery inclusion and rank only; no pass/fail and no main-score contribution.",
    negativeControl: "Correct-exclusion pass rate plus accidental inclusion rate.",
    retailProbe: "Current retail-condition inclusion and rank only; no semantic pass/fail.",
    aidedRecognition: "Brand/ASIN recognition pass rate plus explicit card inclusion rate.",
    diagnostic: "Usable-answer completion rate only; no candidate score."
  },
  dimensions: {
    inclusion: { weight: WEIGHTS.inclusion, rule: "Complete-result-list inclusion rate across eligible aligned positive-control turns." },
    rank: { weight: WEIGHTS.rank, rule: "Mean logarithmic rank score: 100 / log2(rank + 1), using every parsed rank." },
    comparison: { weight: WEIGHTS.comparison, rule: "Share of eligible aligned comparison turns where the tested product ranks first." },
    evidence: { weight: WEIGHTS.evidence, rule: "Pass rate among attributable evidence judgments for included tested-product cards." },
    consistency: { weight: WEIGHTS.consistency, rule: "Mean pairwise Jaccard overlap across independent direct and natural-language controls that share the same logical intent slot." }
  },
  precisionGate: {
    minimumCompletedAlignedTurns: 3,
    minimumCompletedAlignedGroups: 2,
    comparisonObservationRequired: true,
    behaviorWhenInsufficient: "Return a qualitative insufficient grade and suppress the numeric total."
  }
} as const;

const clamp = (value: number) => Math.max(0, Math.min(100, value));
const round = (value: number) => Math.round(clamp(value) * 10) / 10;
const mean = (values: number[]) => (values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0);

export function getScoringStandards() {
  return SCORING_STANDARDS;
}

export function normalizeAsin(value: string): string {
  return String(value || "").trim().toUpperCase();
}

export function normalizeTitle(value: string): string {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/[_/]+/g, " ")
    .replace(/[^a-z0-9\p{L}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function ownAsins(product: Pick<ProductSnapshot, "asin" | "requestedAsin" | "resolvedAsin" | "asinAliases">): Set<string> {
  return new Set([product.asin, product.requestedAsin, product.resolvedAsin, ...(product.asinAliases || [])].map((asin) => normalizeAsin(asin || "")).filter(Boolean));
}

export function isOwnProduct(item: RecommendationItem, product: Pick<ProductSnapshot, "asin" | "requestedAsin" | "resolvedAsin" | "asinAliases" | "brand" | "title">): boolean {
  if (normalizeAsin(item.asin) && ownAsins(product).has(normalizeAsin(item.asin))) return true;
  const itemTitle = normalizeTitle(item.title);
  const productBrand = normalizeTitle(product.brand);
  const productTitle = normalizeTitle(product.title);
  if (!itemTitle || !productBrand || !itemTitle.includes(productBrand)) return false;
  const brandTokens = new Set(productBrand.split(" "));
  const discriminators = productTitle.split(" ").filter((token) => token.length > 4 && !brandTokens.has(token));
  return discriminators.slice(0, 8).filter((token) => itemTitle.includes(token)).length >= 2;
}

export function rankValue(rank: number): number {
  if (!Number.isFinite(rank) || rank < 1) return 0;
  return 100 / Math.log2(rank + 1);
}

function jaccard(a: Set<string>, b: Set<string>): number {
  const union = new Set([...a, ...b]);
  if (!union.size) return 1;
  let intersection = 0;
  a.forEach((value) => {
    if (b.has(value)) intersection += 1;
  });
  return intersection / union.size;
}

function wilson(successes: number, trials: number): { lower: number; upper: number } | null {
  if (!trials) return null;
  const z = 1.96;
  const p = successes / trials;
  const denominator = 1 + (z * z) / trials;
  const center = (p + (z * z) / (2 * trials)) / denominator;
  const margin = (z * Math.sqrt((p * (1 - p)) / trials + (z * z) / (4 * trials * trials))) / denominator;
  return { lower: round((center - margin) * 100), upper: round((center + margin) * 100) };
}

const STOP_WORDS = new Set(["about", "after", "also", "amazon", "and", "are", "for", "from", "have", "into", "only", "product", "that", "the", "their", "this", "with", "women", "womens"]);

function evidenceTokens(value: unknown): string[] {
  const values = Array.isArray(value) ? value : [value];
  return values.flatMap((entry) => normalizeTitle(String(entry || "")).split(" "))
    .filter((token) => token.length > 2 && !STOP_WORDS.has(token));
}

function supportsFact(corpus: string, fact: ProductSnapshot["stableFacts"][number]): boolean {
  const normalizedCorpus = normalizeTitle(corpus);
  const values = Array.isArray(fact.value) ? fact.value : [fact.value];
  if (values.some((value) => {
    const phrase = normalizeTitle(String(value || ""));
    return phrase.length > 2 && normalizedCorpus.includes(phrase);
  })) return true;
  const tokens = [...new Set([...evidenceTokens(fact.value), ...evidenceTokens(fact.sourceText)])];
  if (!tokens.length) return false;
  const matches = tokens.filter((token) => normalizedCorpus.includes(token)).length;
  return matches >= Math.min(2, tokens.length) && matches / tokens.length >= 0.5;
}

function promptMap(promptCases: PromptCase[]): Map<string, PromptCase> {
  return new Map(promptCases.map((prompt) => [prompt.id, prompt]));
}

function defaultPrompt(turn: ConversationTurn): PromptCase {
  return {
    id: turn.promptCaseId,
    templateId: "metadata_missing",
    slot: "metadata_missing",
    mode: "blind",
    expression: "direct",
    promptText: turn.promptText,
    testRole: "baseline",
    enabled: false,
    scoreEligible: false,
    hypothesis: "Prompt metadata is unavailable.",
    expectedMatch: "neutral",
    evidenceFactIds: [],
    requiredTerms: [],
    judgmentCriteria: [],
    promptVersion: "unknown",
    sessionPolicy: "fresh",
    generatedBy: "deterministic",
    repeatIndex: 1,
    sequence: 0,
    status: turn.status,
    revision: 1,
    editable: false
  };
}

function isAlignedPositive(prompt: PromptCase, product: ProductSnapshot): boolean {
  if (!prompt.enabled || prompt.sessionPolicy !== "fresh" || prompt.testRole !== "positive_control" || !prompt.scoreEligible || prompt.expectedMatch !== "eligible") return false;
  if (!prompt.evidenceFactIds.length) return false;
  const validIds = new Set(product.stableFacts
    .filter((fact) => SCORE_ELIGIBLE_PAGE_SECTIONS.has(fact.sourceSection))
    .map((fact) => fact.id));
  return prompt.evidenceFactIds.every((id) => validIds.has(id));
}

function expectedOutcome(prompt: PromptCase, included: boolean): TurnJudgment["constraintOutcome"] {
  if (prompt.expectedMatch === "eligible") return included ? "pass" : "fail";
  if (prompt.expectedMatch === "ineligible") return included ? "fail" : "pass";
  if (prompt.expectedMatch === "neutral") return "observe";
  return "not_applicable";
}

function evidenceOutcome(prompt: PromptCase, own: RecommendationItem | undefined, product: ProductSnapshot): TurnJudgment["evidenceOutcome"] {
  if (prompt.expectedMatch !== "eligible" || !own) return "not_applicable";
  const facts = prompt.evidenceFactIds.map((id) => product.stableFacts.find((fact) => fact.id === id)).filter(Boolean) as ProductSnapshot["stableFacts"];
  if (!facts.length || !own.evidenceText.trim()) return "insufficient_evidence";
  return facts.every((fact) => supportsFact(own.evidenceText, fact)) ? "pass" : "fail";
}

export function calculateTurnJudgments(turns: ConversationTurn[], product: ProductSnapshot, promptCases: PromptCase[]): TurnJudgment[] {
  const prompts = promptMap(promptCases);
  return turns.map((turn) => {
    const foundPrompt = prompts.get(turn.promptCaseId);
    const prompt = foundPrompt || defaultPrompt(turn);
    const own = turn.recommendations.find((item) => isOwnProduct(item, product));
    const aligned = isAlignedPositive(prompt, product);
    const reasonCodes: string[] = [];
    if (!foundPrompt) reasonCodes.push("prompt_metadata_missing");
    if (!prompt.enabled) reasonCodes.push("prompt_disabled");
    if (turn.status !== "completed") reasonCodes.push("turn_not_completed");
    if (prompt.scoreEligible && prompt.testRole === "positive_control" && !aligned) reasonCodes.push("page_evidence_alignment_invalid");
    if (own) reasonCodes.push("own_product_in_results");
    else reasonCodes.push("own_product_not_in_results");

    let constraintOutcome: TurnJudgment["constraintOutcome"];
    let judgedEvidence: TurnJudgment["evidenceOutcome"];
    if (!prompt.enabled) {
      constraintOutcome = "not_applicable";
      judgedEvidence = "not_applicable";
    } else if (turn.status !== "completed") {
      constraintOutcome = "insufficient_evidence";
      judgedEvidence = "not_applicable";
    } else if (prompt.testRole === "positive_control" && prompt.expectedMatch === "eligible" && !aligned) {
      constraintOutcome = "insufficient_evidence";
      judgedEvidence = "insufficient_evidence";
    } else {
      constraintOutcome = expectedOutcome(prompt, Boolean(own));
      judgedEvidence = evidenceOutcome(prompt, own, product);
    }
    if (judgedEvidence === "pass") reasonCodes.push("all_attached_page_evidence_supported");
    if (judgedEvidence === "fail") reasonCodes.push("attached_page_evidence_not_fully_supported");
    if (judgedEvidence === "insufficient_evidence") reasonCodes.push("attributable_evidence_unavailable");

    return {
      turnId: turn.id,
      promptCaseId: turn.promptCaseId,
      testRole: prompt.testRole,
      scoreEligible: aligned && turn.status === "completed",
      expectedMatch: prompt.expectedMatch,
      ownIncluded: Boolean(own),
      ownRank: own?.rank ?? null,
      constraintOutcome,
      evidenceOutcome: judgedEvidence,
      reasonCodes
    };
  });
}

function resultSet(turn: ConversationTurn): Set<string> {
  return new Set(turn.recommendations.map((item) => normalizeAsin(item.asin) || normalizeTitle(item.title)).filter(Boolean));
}

function groupKey(prompt: PromptCase): string {
  return prompt.slot || prompt.templateId || prompt.id.replace(/:r\d+$/, "");
}

function consistencyValue(turns: ConversationTurn[], prompts: Map<string, PromptCase>): number {
  const grouped = new Map<string, ConversationTurn[]>();
  turns.forEach((turn) => {
    const prompt = prompts.get(turn.promptCaseId);
    const key = prompt ? groupKey(prompt) : turn.promptCaseId.replace(/:r\d+$/, "");
    grouped.set(key, [...(grouped.get(key) || []), turn]);
  });
  const repeated = [...grouped.values()].filter((group) => group.length >= 2);
  if (!repeated.length) return 0;
  return mean(repeated.map((group) => {
    const sets = group.map(resultSet);
    const pairs: number[] = [];
    for (let index = 0; index < sets.length; index += 1) {
      for (let peer = index + 1; peer < sets.length; peer += 1) pairs.push(jaccard(sets[index], sets[peer]) * 100);
    }
    return mean(pairs);
  }));
}

function responseRecognizesOwnProduct(turn: ConversationTurn, product: ProductSnapshot): boolean {
  if (turn.recommendations.some((item) => isOwnProduct(item, product))) return true;
  const response = normalizeTitle(turn.responseText);
  if (!response) return false;
  if ([...ownAsins(product)].some((asin) => response.includes(asin.toLowerCase()))) return true;
  const brand = normalizeTitle(product.brand);
  const titleTokens = normalizeTitle(product.title).split(" ").filter((token) => token.length > 4 && !brand.includes(token));
  return Boolean(brand && response.includes(brand) && titleTokens.filter((token) => response.includes(token)).length >= 2);
}

function probeMetric(turns: ConversationTurn[], product: ProductSnapshot, judgments: TurnJudgment[], prompts: Map<string, PromptCase>, role: TestRole): ProbeMetric {
  const relevant = turns.filter((turn) => turn.status === "completed"
    && prompts.get(turn.promptCaseId)?.enabled !== false
    && judgments.find((judgment) => judgment.promptCaseId === turn.promptCaseId)?.testRole === role);
  const relevantJudgments = relevant.map((turn) => judgments.find((judgment) => judgment.promptCaseId === turn.promptCaseId)!).filter(Boolean);
  const included = relevantJudgments.filter((judgment) => judgment.ownIncluded);
  const metric: ProbeMetric = {
    sampleSize: relevant.length,
    includedCount: included.length,
    inclusionRate: relevant.length ? round((included.length / relevant.length) * 100) : 0,
    meanRankScore: round(mean(included.map((judgment) => rankValue(judgment.ownRank || 0))))
  };
  if (role === "negative_control") {
    const passes = relevantJudgments.filter((judgment) => judgment.constraintOutcome === "pass").length;
    metric.passCount = passes;
    metric.passRate = relevant.length ? round((passes / relevant.length) * 100) : 0;
  }
  if (role === "aided_recognition") {
    const passes = relevant.filter((turn) => responseRecognizesOwnProduct(turn, product)).length;
    metric.passCount = passes;
    metric.passRate = relevant.length ? round((passes / relevant.length) * 100) : 0;
  }
  if (role === "diagnostic") {
    const passes = relevant.filter((turn) => turn.responseText.trim().length > 0).length;
    metric.passCount = passes;
    metric.passRate = relevant.length ? round((passes / relevant.length) * 100) : 0;
  }
  return metric;
}

export function calculateScore(
  turns: ConversationTurn[],
  product: ProductSnapshot,
  promptCases: PromptCase[] = [],
  expectedPromptGroupsOverride?: number
): ScoreSnapshot {
  const prompts = promptMap(promptCases);
  const judgments = calculateTurnJudgments(turns, product, promptCases);
  const eligibleJudgments = judgments.filter((judgment) => judgment.scoreEligible);
  const eligibleIds = new Set(eligibleJudgments.map((judgment) => judgment.promptCaseId));
  const eligibleTurns = turns.filter((turn) => turn.status === "completed" && eligibleIds.has(turn.promptCaseId));
  const inclusions = eligibleJudgments.filter((judgment) => judgment.ownIncluded).length;
  const inclusion = eligibleJudgments.length ? (inclusions / eligibleJudgments.length) * 100 : 0;
  const rank = mean(eligibleJudgments.map((judgment) => rankValue(judgment.ownRank || 0)));

  const comparisonJudgments = eligibleJudgments.filter((judgment) => prompts.get(judgment.promptCaseId)?.expression === "comparison");
  const comparison = comparisonJudgments.length
    ? mean(comparisonJudgments.map((judgment) => judgment.ownRank === 1 ? 100 : 0))
    : 0;
  const attributableEvidence = eligibleJudgments.filter((judgment) => judgment.evidenceOutcome === "pass" || judgment.evidenceOutcome === "fail");
  const evidence = attributableEvidence.length
    ? (attributableEvidence.filter((judgment) => judgment.evidenceOutcome === "pass").length / attributableEvidence.length) * 100
    : 0;
  const consistency = consistencyValue(eligibleTurns, prompts);

  const plannedEligible = promptCases.filter((prompt) => prompt.enabled && isAlignedPositive(prompt, product));
  const expectedGroups = expectedPromptGroupsOverride ?? new Set(plannedEligible.map(groupKey)).size;
  const completedGroups = new Set(eligibleTurns.map((turn) => {
    const prompt = prompts.get(turn.promptCaseId);
    return prompt ? groupKey(prompt) : turn.promptCaseId;
  })).size;
  const minimumTurns = Math.min(SCORING_STANDARDS.precisionGate.minimumCompletedAlignedTurns, Math.max(1, plannedEligible.length));
  const minimumGroups = Math.min(SCORING_STANDARDS.precisionGate.minimumCompletedAlignedGroups, expectedGroups);
  const sufficient = expectedGroups > 0
    && eligibleTurns.length >= minimumTurns
    && completedGroups >= minimumGroups
    && comparisonJudgments.length > 0
    && attributableEvidence.length > 0;

  const dimensions: ScoreDimensions = {
    inclusion: round(inclusion),
    rank: round(rank),
    comparison: round(comparison),
    evidence: round(evidence),
    consistency: round(consistency)
  };
  const rawTotal = Object.entries(WEIGHTS).reduce((sum, [key, weight]) => sum + dimensions[key as keyof ScoreDimensions] * weight, 0);
  const total = sufficient ? round(rawTotal) : null;
  const grade = total === null ? "insufficient" : total >= 70 ? "strong" : total >= 40 ? "medium" : "weak";
  const warnings: string[] = [];
  if (!sufficient) warnings.push("对齐正向题的有效样本、重复组、比较题或可归属证据不足，暂不显示精确总分");
  if (eligibleTurns.length && consistency < 45) warnings.push("对齐题的重复推荐结果波动较大，可能受到个性化或推荐随机性的影响");
  if (!product.stableFacts.length) warnings.push("商品页面缺少可审计的稳定证据");
  if (turns.some((turn) => !prompts.has(turn.promptCaseId))) warnings.push("部分历史轮次缺少问题元数据，已排除在主推荐指数之外");
  if (promptCases.some((prompt) => prompt.testRole === "positive_control" && prompt.scoreEligible && !isAlignedPositive(prompt, product))) warnings.push("部分正向题缺少有效页面证据映射，已降级为诊断观察");

  return {
    total,
    grade,
    dimensions,
    sampleSize: eligibleTurns.length,
    completedPromptGroups: completedGroups,
    expectedPromptGroups: expectedGroups,
    confidence: wilson(inclusions, eligibleJudgments.length),
    warnings,
    formulaVersion: SCORING_STANDARDS.formulaVersion,
    standardsVersion: SCORING_STANDARDS.standardsVersion,
    judgments,
    probes: {
      baseline: probeMetric(turns, product, judgments, prompts, "baseline"),
      negativeControl: probeMetric(turns, product, judgments, prompts, "negative_control"),
      retailProbe: probeMetric(turns, product, judgments, prompts, "retail_probe"),
      aidedRecognition: probeMetric(turns, product, judgments, prompts, "aided_recognition"),
      diagnostic: probeMetric(turns, product, judgments, prompts, "diagnostic")
    },
    calculatedAt: new Date().toISOString()
  };
}
