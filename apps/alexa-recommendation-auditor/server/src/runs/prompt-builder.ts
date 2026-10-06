import { createHash } from "node:crypto";
import {
  FOOTWEAR_PROMPT_VERSION,
  SCHEMA_VERSION,
  type EvidenceFact,
  type GeneratedPromptPlan,
  type ProductSnapshot,
  type PromptCase,
  type PromptCaseDefinition,
  type PromptLanguage,
  type RunPreset
} from "@alexa-auditor/contracts";

export const FOOTWEAR_PRESET_COUNTS: Record<RunPreset, number> = { smoke: 5, calibration: 9, full: 11 };
const PROGRESSIVE_SESSION_GROUP = "footwear_progressive_intent";
const PRESET_TEMPLATE_IDS: Record<RunPreset, string[]> = {
  smoke: [
    "footwear.control.category-baseline.v4",
    "footwear.control.primary-function-direct.v4",
    "footwear.control.negative-category.v4",
    "footwear.progressive.01-category.v4",
    "footwear.progressive.02-alexa-score.v4"
  ],
  calibration: [
    "footwear.control.category-baseline.v4",
    "footwear.control.primary-function-direct.v4",
    "footwear.control.primary-function-natural.v4",
    "footwear.control.comparison.v4",
    "footwear.control.negative-category.v4",
    "footwear.progressive.01-category.v4",
    "footwear.progressive.02-alexa-score.v4",
    "footwear.progressive.03-screening-transparency.v4",
    "footwear.progressive.04-entry-hypotheses.v4"
  ],
  full: [
    "footwear.control.category-baseline.v4",
    "footwear.control.primary-function-direct.v4",
    "footwear.control.primary-function-natural.v4",
    "footwear.control.comparison.v4",
    "footwear.control.negative-category.v4",
    "footwear.progressive.01-category.v4",
    "footwear.progressive.02-alexa-score.v4",
    "footwear.progressive.03-screening-transparency.v4",
    "footwear.progressive.04-entry-hypotheses.v4",
    "footwear.progressive.05-scene-narrowing.v4",
    "footwear.progressive.06-budget-rescore.v4"
  ]
};
const SOURCE_PRIORITY: Record<EvidenceFact["sourceSection"], number> = {
  title: 0,
  specification: 1,
  bullets: 2,
  a_plus: 3,
  breadcrumb: 4,
  qa: 5,
  brand: 6,
  review_summary: 7,
  retail: 8
};

// Only seller-controlled PDP sections can make a dynamic condition eligible
// for the main recommendation score. Reviews and Q&A remain visible as
// supporting/diagnostic evidence, but cannot promote a claim to product fact.
const SCORE_ELIGIBLE_EVIDENCE_SECTIONS = new Set<EvidenceFact["sourceSection"]>([
  "title",
  "specification",
  "bullets",
  "a_plus",
  "breadcrumb"
]);

interface SupportedValue {
  text: string;
  rawText: string;
  evidenceFactIds: string[];
  supported: boolean;
}

interface DefinitionInput {
  templateId: string;
  slot: string;
  mode?: PromptCaseDefinition["mode"];
  expression: PromptCaseDefinition["expression"];
  promptText: string;
  testRole: PromptCaseDefinition["testRole"];
  scoreEligible: boolean;
  hypothesis: string;
  expectedMatch: PromptCaseDefinition["expectedMatch"];
  evidenceFactIds?: string[];
  requiredTerms: string[];
  judgmentCriteria: string[];
  sessionPolicy?: PromptCaseDefinition["sessionPolicy"];
  sessionGroup?: string;
}

function phrase(value: unknown, fallback: string): string {
  const result = String(value || "")
    .replace(/_/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return result || fallback;
}

function normalized(value: unknown): string {
  return phrase(value, "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/[^\p{L}\p{N}$]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function semanticKey(value: unknown): string {
  return String(value || "")
    .normalize("NFKC")
    .toLowerCase()
    .replace(/_/g, " ")
    .replace(/[^\p{L}\p{N}$]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const ZH_DYNAMIC_VALUES: Record<string, string> = {
  shoes: "鞋",
  shoe: "鞋",
  footwear: "鞋",
  "flip flops": "人字拖",
  "flip flop": "人字拖",
  slides: "一字拖",
  slide: "一字拖",
  loafers: "乐福鞋",
  loafer: "乐福鞋",
  "slip on shoes": "一脚蹬鞋",
  "slip ons": "一脚蹬鞋",
  "water shoes": "水鞋",
  "barefoot shoes": "赤足鞋",
  "running shoes": "跑鞋",
  "walking shoes": "步行鞋",
  sneakers: "运动鞋",
  sandals: "凉鞋",
  sandal: "凉鞋",
  boots: "靴子",
  boot: "靴子",
  clogs: "洞洞鞋",
  women: "女士",
  womens: "女士",
  men: "男士",
  mens: "男士",
  adults: "成人",
  kids: "儿童",
  children: "儿童",
  toddler: "幼儿",
  baby: "婴幼儿",
  youth: "青少年",
  unisex: "男女通用",
  "arch support": "足弓支撑",
  "supportive footbed": "支撑型鞋床",
  "everyday comfort": "日常舒适",
  "comfortable fit": "舒适合脚",
  "slip resistant": "防滑",
  "non slip": "防滑",
  cushioning: "缓震",
  cushion: "缓震",
  "shock absorption": "减震",
  "memory foam": "记忆海绵",
  lightweight: "轻量",
  breathable: "透气",
  "easy clean": "易清洁",
  waterproof: "防水",
  "water resistant": "防泼水",
  "quick dry": "速干",
  "wide toe box": "宽鞋头",
  "zero drop": "零落差",
  barefoot: "赤足",
  minimalist: "极简",
  traction: "抓地力",
  flexible: "柔韧",
  durable: "耐用",
  "all day comfort": "全天舒适",
  "arch support need": "足弓支撑需求",
  "wide feet": "宽脚",
  "flat feet": "扁平足",
  "heel pain": "足跟不适",
  bunions: "拇外翻",
  "foot swelling": "足部肿胀",
  "daily wear": "日常穿着",
  "daily casual": "日常休闲",
  "daily walking": "日常步行",
  walking: "步行",
  "long standing": "长时间站立",
  travel: "旅行",
  hiking: "徒步",
  running: "跑步",
  training: "训练",
  "water activities": "水上活动",
  beach: "沙滩",
  pool: "泳池",
  bathroom: "浴室",
  outdoors: "户外",
  indoors: "室内",
  river: "河流或溪流",
  workplace: "工作场所",
  city: "城市环境",
  "home and outdoors": "居家和户外环境",
  "casual sandals": "休闲凉鞋",
  "casual footwear": "休闲鞋",
  "casual sneakers": "休闲运动鞋",
  eva: "EVA",
  "ethylene vinyl acetate eva": "EVA",
  leather: "皮革",
  canvas: "帆布",
  mesh: "网布",
  knit: "针织",
  "easy care construction": "易打理结构"
};

function localizedPhrase(value: unknown, fallback: string, language: PromptLanguage): string {
  const raw = phrase(value, fallback);
  if (language !== "zh-CN") return raw;
  return ZH_DYNAMIC_VALUES[semanticKey(raw)] || raw;
}

function unique(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function pluralFootwear(value: string, language: PromptLanguage): string {
  if (language === "zh-CN") return localizedPhrase(value, "鞋", language);
  const clean = phrase(value, "shoes");
  if (/\b(shoes|boots|sandals|sneakers|loafers|flip flops|slides|flats|footwear)\b$/i.test(clean)) return clean;
  if (/shoe$/i.test(clean)) return `${clean}s`;
  if (/(s|x|z|ch|sh)$/i.test(clean)) return `${clean}es`;
  return `${clean}s`;
}

function implicitFunctionNeed(value: string, language: PromptLanguage): string {
  const key = semanticKey(value);
  const intent =
    /arch support|supportive footbed|足弓/.test(key) ? "arch" :
    /cushion|shock|impact|padded|缓震|缓冲/.test(key) ? "cushion" :
    /slip|grip|traction|防滑|抓地/.test(key) ? "grip" :
    /wide|toe room|roomy|宽鞋头|宽趾/.test(key) ? "wide" :
    /breath|ventilat|透气/.test(key) ? "breathable" :
    /lightweight|light weight|轻量|轻盈/.test(key) ? "lightweight" :
    /quick dry|waterproof|water resistant|速干|防水/.test(key) ? "wet" :
    /flex|柔韧|灵活/.test(key) ? "flexible" :
    /durab|long lasting|耐用/.test(key) ? "durable" :
    /easy clean|washable|易清洁|可清洗/.test(key) ? "clean" :
    "comfort";
  if (language === "zh-CN") {
    return {
      arch: "穿几小时后，我的足弓会感到疲劳且缺乏支撑",
      cushion: "在硬地面活动几小时后，我的脚会感到酸痛",
      grip: "我担心在光滑或潮湿的地面上站不稳",
      wide: "我的脚趾容易受挤压，需要更多伸展空间",
      breathable: "长时间穿着时，我的脚容易发热",
      lightweight: "较重的鞋会让日常穿着更容易疲劳",
      wet: "我经常在干湿环境之间活动，不希望鞋长时间湿着",
      flexible: "僵硬的鞋会限制我的自然步态",
      durable: "我需要一双能承受频繁日常使用的鞋",
      clean: "日常使用后，我需要容易清洁的鞋",
      comfort: "日常穿着几小时后，我的脚容易感到不适"
    }[intent];
  }
  return {
    arch: "My arches feel tired and unsupported after a few hours",
    cushion: "Hard surfaces leave my feet sore after a few hours",
    grip: "I worry about losing my footing on smooth or damp surfaces",
    wide: "My toes feel squeezed and need more room to spread",
    breathable: "My feet become hot during extended wear",
    lightweight: "Heavy footwear makes everyday wear feel tiring",
    wet: "I move between wet and dry areas and do not want footwear to stay soggy",
    flexible: "Stiff footwear restricts my natural steps",
    durable: "I need footwear that holds up to frequent everyday use",
    clean: "I need footwear that is simple to clean after regular use",
    comfort: "My feet become uncomfortable after a few hours of everyday wear"
  }[intent];
}

function factContent(fact: EvidenceFact): string {
  return normalized(`${fact.field} ${Array.isArray(fact.value) ? fact.value.join(" ") : fact.value} ${fact.sourceText}`);
}

function evidenceFor(snapshot: ProductSnapshot, values: string[], fieldHints: string[]): string[] {
  const candidates = values.map(normalized).filter(Boolean);
  const hints = fieldHints.map(normalized).filter(Boolean);
  return snapshot.stableFacts
    .filter((fact) => {
      if (!SCORE_ELIGIBLE_EVIDENCE_SECTIONS.has(fact.sourceSection)) return false;
      const content = factContent(fact);
      const valueMatch = candidates.some((candidate) => {
        if (content.includes(candidate)) return true;
        const tokens = candidate.split(" ").filter((token) => token.length > 2);
        return tokens.length > 0 && tokens.every((token) => content.includes(token));
      });
      // Field hints may rank an already matching fact, but never turn a generic
      // "support" or "comfort" mention into evidence for an absent attribute.
      return valueMatch;
    })
    .sort((a, b) => {
      const aField = normalized(a.field);
      const bField = normalized(b.field);
      const aHint = hints.some((hint) => aField.includes(hint)) ? 0 : 1;
      const bHint = hints.some((hint) => bField.includes(hint)) ? 0 : 1;
      return aHint - bHint || SOURCE_PRIORITY[a.sourceSection] - SOURCE_PRIORITY[b.sourceSection];
    })
    .map((fact) => fact.id)
    .filter(Boolean)
    .slice(0, 4);
}

function selectProfileValue(
  snapshot: ProductSnapshot,
  values: string[],
  fallback: string,
  fieldHints: string[],
  language: PromptLanguage
): SupportedValue {
  const declaredValues = values.map((value) => phrase(value, "")).filter(Boolean);
  const rawText = phrase(declaredValues[0], fallback);
  const text = localizedPhrase(rawText, fallback, language);
  // A fallback phrase keeps the question grammatical; it is never promoted to
  // a scoreable product claim when the intent profile has no value for the slot.
  const evidenceFactIds = declaredValues.length ? evidenceFor(snapshot, declaredValues, fieldHints) : [];
  return { text, rawText, evidenceFactIds, supported: evidenceFactIds.length > 0 };
}

function selectMaterial(snapshot: ProductSnapshot, language: PromptLanguage): SupportedValue {
  const specification = Object.entries(snapshot.specifications).find(([key, value]) =>
    /(material|construction|upper|outer|sole)/i.test(key) && Boolean(value)
  );
  const rawText = phrase(specification?.[1], "easy-care construction");
  const text = localizedPhrase(rawText, language === "zh-CN" ? "易打理结构" : "easy-care construction", language);
  const evidenceFactIds = evidenceFor(snapshot, [rawText], ["material", "construction", "upper", "outer", "sole"]);
  return { text, rawText, evidenceFactIds, supported: evidenceFactIds.length > 0 };
}

function oppositeFootwear(type: string, language: PromptLanguage): string {
  const value = normalized(type);
  const opposite =
    /flip flop|sandal|slide|open toe/.test(value) ? "closed-toe waterproof hiking boots" :
    /boot/.test(value) ? "open-toe beach sandals" :
    /running|trail|athletic|sneaker|trainer/.test(value) ? "formal leather dress loafers" :
    /loafer|slip on|moccasin/.test(value) ? "lace-up trail-running shoes" :
    /dress|oxford|derby/.test(value) ? "technical trail-running shoes" :
    "steel-toe waterproof work boots";
  if (language !== "zh-CN") return opposite;
  return {
    "closed-toe waterproof hiking boots": "包头防水徒步靴",
    "open-toe beach sandals": "露趾沙滩凉鞋",
    "formal leather dress loafers": "正装皮质乐福鞋",
    "lace-up trail-running shoes": "系带越野跑鞋",
    "technical trail-running shoes": "专业越野跑鞋",
    "steel-toe waterproof work boots": "钢包头防水工作靴"
  }[opposite];
}

function standardBudgetCeiling(snapshot: ProductSnapshot, language: PromptLanguage): string {
  const priceFact = snapshot.volatileFacts.find((fact) => normalized(fact.field).includes("price"));
  const numericPrice = Number.parseFloat(String(priceFact?.value || priceFact?.sourceText || "").replace(/[^0-9.]/g, ""));
  const ceiling = !Number.isFinite(numericPrice) ? 25
    : numericPrice <= 10 ? 15
      : numericPrice <= 20 ? 25
        : numericPrice <= 35 ? 40
          : numericPrice <= 50 ? 60
            : Math.ceil(numericPrice / 25) * 25;
  return language === "zh-CN" ? `${ceiling}美元以内` : `$${ceiling} or less`;
}

function positiveMetadata(selection: SupportedValue, type: SupportedValue) {
  const evidenceFactIds = unique([...type.evidenceFactIds, ...selection.evidenceFactIds]);
  const supported = type.supported && selection.supported;
  return {
    testRole: (supported ? "positive_control" : "diagnostic") as PromptCaseDefinition["testRole"],
    scoreEligible: supported,
    expectedMatch: (supported ? "eligible" : "diagnostic_only") as PromptCaseDefinition["expectedMatch"],
    evidenceFactIds
  };
}

function definition(input: DefinitionInput): PromptCaseDefinition {
  return {
    enabled: true,
    templateId: input.templateId,
    slot: input.slot,
    mode: input.mode || "blind",
    expression: input.expression,
    promptText: input.promptText,
    testRole: input.testRole,
    scoreEligible: input.scoreEligible,
    hypothesis: input.hypothesis,
    expectedMatch: input.expectedMatch,
    evidenceFactIds: unique(input.evidenceFactIds || []),
    requiredTerms: unique(input.requiredTerms.map((term) => phrase(term, ""))),
    judgmentCriteria: input.judgmentCriteria,
    promptVersion: FOOTWEAR_PROMPT_VERSION,
    sessionPolicy: input.sessionPolicy || "fresh",
    ...(input.sessionGroup ? { sessionGroup: input.sessionGroup } : {}),
    generatedBy: "deterministic"
  };
}

function eligibleCriteria(attribute: string): string[] {
  return [
    "我方任一ASIN别名进入Alexa完整返回列表，记为一次召回命中。",
    `Alexa回答或商品卡片必须明确承接“${attribute}”，否则只记召回、不记意图证据命中。`,
    "按首次出现位置记录排名；赞助标识、价格、评分和配送仅作为观察字段，不改变本题意图判断。"
  ];
}

function buildAllFootwearCases(snapshot: ProductSnapshot, promptLanguage: PromptLanguage): PromptCaseDefinition[] {
  const zh = promptLanguage === "zh-CN";
  const profile = snapshot.intentProfile;
  const declaredProductTypes = profile.product_type.filter((value) => !/^unknown(?:_| )product$/i.test(value));
  const type = selectProfileValue(snapshot, declaredProductTypes, zh ? "鞋" : "shoes", ["product type", "category", "title", "breadcrumb"], promptLanguage);
  type.text = pluralFootwear(type.text, promptLanguage);
  const audience = selectProfileValue(snapshot, profile.audience_intent, zh ? "成人" : "adults", ["audience", "department", "gender"], promptLanguage);
  const primaryFunction = selectProfileValue(snapshot, profile.function_intent, zh ? "日常舒适" : "everyday comfort", ["function", "feature", "support", "comfort"], promptLanguage);
  const implicitPrimaryNeed = implicitFunctionNeed(primaryFunction.rawText, promptLanguage);
  const capability = selectProfileValue(snapshot, profile.capability_intent, primaryFunction.rawText, ["capability", "feature", "performance"], promptLanguage);
  const event = selectProfileValue(snapshot, profile.event_intent, zh ? "日常穿着" : "daily wear", ["event", "activity", "occasion", "use"], promptLanguage);
  const location = selectProfileValue(snapshot, profile.location_intent, zh ? "居家和户外环境" : "home and outdoors", ["location", "place", "environment", "use"], promptLanguage);
  const material = selectMaterial(snapshot, promptLanguage);
  const currentPageProduct = zh ? "当前页面商品" : "the current-page product";
  const candidateTerm = zh ? "候选" : "candidates";
  const everyCandidateTerm = zh ? "全部候选" : "every candidate";
  const notTopFiveTerm = zh ? "不要只做Top5" : "not just a Top 5";
  const amazonLinkTerm = zh ? "Amazon商品链接" : "Amazon product link";
  const budgetCeiling = standardBudgetCeiling(snapshot, promptLanguage);
  const typeAndAudienceEvidence = unique([...type.evidenceFactIds, ...audience.evidenceFactIds]);
  const fnMeta = positiveMetadata(primaryFunction, type);
  const capabilityMeta = positiveMetadata(capability, type);
  const eventMeta = positiveMetadata(event, type);
  const locationMeta = positiveMetadata(location, type);
  const negativeType = oppositeFootwear(type.rawText, promptLanguage);
  const scene = eventMeta.scoreEligible ? event : locationMeta.scoreEligible ? location : event;
  const sceneEvidence = unique([...type.evidenceFactIds, ...scene.evidenceFactIds]);
  const progressiveBase = {
    mode: "diagnostic" as const,
    testRole: "diagnostic" as const,
    scoreEligible: false,
    expectedMatch: "diagnostic_only" as const,
    sessionPolicy: "shared_sequence" as const,
    sessionGroup: PROGRESSIVE_SESSION_GROUP
  };

  const cases: PromptCaseDefinition[] = [
    definition({
      templateId: "footwear.control.category-baseline.v4", slot: "control_category_baseline", expression: "direct",
      promptText: zh
        ? `我想购买适合${audience.text}日常穿着的${type.text}。请列出本轮实际建议我了解的全部候选，不要只做Top5。按自然推荐顺序，每个商品只写一行：商品名｜当前价格｜Amazon商品链接。候选池规模或价格无法确认时，请直接写“无法确认”。`
        : `I want ${audience.text} ${type.text} for everyday wear. List every candidate you actually recommend in this turn, not just a Top 5. In natural recommendation order, use one line per item: product name | current price | Amazon product link. If the candidate-pool size or price cannot be verified, say "unable to verify".`,
      testRole: "baseline", scoreEligible: false,
      hypothesis: "Alexa can identify the broad footwear category and produce a comparable result list without being given the tested brand or ASIN.",
      expectedMatch: "neutral", evidenceFactIds: typeAndAudienceEvidence,
      requiredTerms: [audience.text, type.text, everyCandidateTerm, notTopFiveTerm, amazonLinkTerm],
      judgmentCriteria: ["记录Alexa完整返回列表及顺序，作为后续正向条件题的类别基线。", "本题不计入主推荐指数，也不因我方商品缺席而判定失败。"]
    }),
    definition({
      templateId: "footwear.control.primary-function-direct.v4", slot: "control_primary_function", expression: "direct",
      promptText: zh
        ? `我只考虑${audience.text}${type.text}，需要明确具备${primaryFunction.text}。请列出本轮实际符合条件的全部候选，不要只做Top5。每项只写一行：商品名｜支持该功能的公开证据｜主要限制｜当前价格｜Amazon商品链接。无法验证的功能不要推断。`
        : `I am only considering ${audience.text} ${type.text} that clearly have ${primaryFunction.text}. List every candidate that actually qualifies in this turn, not just a Top 5. Use one line per item: product name | public evidence for the feature | main limitation | current price | Amazon product link. Do not infer a feature that cannot be verified.`,
      ...fnMeta,
      hypothesis: `If the page explicitly supports ${primaryFunction.text}, the tested footwear should be eligible for a direct attribute request.`,
      requiredTerms: [audience.text, type.text, primaryFunction.text, everyCandidateTerm, notTopFiveTerm, amazonLinkTerm], judgmentCriteria: eligibleCriteria(primaryFunction.text)
    }),
    definition({
      templateId: "footwear.control.primary-function-natural.v4", slot: "control_primary_function", expression: "natural_language",
      promptText: zh
        ? `${implicitPrimaryNeed}。我只考虑${audience.text}${type.text}，并且需要适合日常较长时间穿着。请列出本轮实际建议的全部候选，不要只做Top5。每项只写一行：商品名｜为什么适合这个实际需求｜主要不确定性｜当前价格｜Amazon商品链接。`
        : `${implicitPrimaryNeed}. I am only considering ${audience.text} ${type.text} suitable for extended everyday wear. List every candidate you actually recommend in this turn, not just a Top 5. Use one line per item: product name | why it fits this practical need | main uncertainty | current price | Amazon product link.`,
      ...fnMeta,
      hypothesis: `Alexa maps a natural-language discomfort statement to the page-evidenced ${primaryFunction.text} attribute.`,
      requiredTerms: [implicitPrimaryNeed, audience.text, type.text, everyCandidateTerm, notTopFiveTerm, amazonLinkTerm], judgmentCriteria: eligibleCriteria(primaryFunction.text)
    }),
    definition({
      templateId: "footwear.control.comparison.v4", slot: "control_comparison", expression: "comparison",
      promptText: zh
        ? `请比较本轮最相关的全部候选，仅限${audience.text}${type.text}，并说明它们在${primaryFunction.text}方面的表现，不要只做Top5。按你认为的自然优先顺序，每项只写一行：商品名｜相对优势｜相对限制｜公开商品证据｜Amazon商品链接。请把页面事实、评论信息和你的推断分开；证据不足时写“未知”。`
        : `Compare every candidate from this turn that is a relevant ${audience.text} ${type.text} option on ${primaryFunction.text}, not just a Top 5. In your natural priority order, use one line per item: product name | relative advantage | relative limitation | public product evidence | Amazon product link. Separate page facts, review information, and your inference; write "unknown" when evidence is insufficient.`,
      ...fnMeta,
      hypothesis: `The tested footwear remains competitive when Alexa compares candidates on the page-evidenced ${primaryFunction.text} attribute.`,
      requiredTerms: [audience.text, type.text, primaryFunction.text, everyCandidateTerm, notTopFiveTerm, amazonLinkTerm],
      judgmentCriteria: ["记录我方商品是否进入比较名单及其相对名次。", "只有可归属到具体商品卡片且与页面一致的功能证据才记为证据命中。", "Alexa的解释属于自述，不能单独证明Amazon内部排序原因。"]
    }),
    definition({
      templateId: "footwear.control.negative-category.v4", slot: "control_negative_category", expression: "direct",
      promptText: zh
        ? `我只考虑${audience.text}${negativeType}，明确排除任何${type.text}。请列出本轮实际建议的全部候选，每项只写商品名和Amazon商品链接。`
        : `I am only considering ${audience.text} ${negativeType} and explicitly exclude all ${type.text}. List every candidate you actually recommend in this turn, using only the product name and Amazon product link for each item.`,
      testRole: "negative_control", scoreEligible: false,
      hypothesis: "A product should be excluded when the requested footwear category explicitly conflicts with its evidenced product type.",
      expectedMatch: "ineligible", evidenceFactIds: type.evidenceFactIds,
      requiredTerms: [audience.text, negativeType, type.text, everyCandidateTerm, amazonLinkTerm],
      judgmentCriteria: ["我方全部ASIN别名均未进入完整返回列表，记为正确排除。", "若我方商品进入完整返回列表，记为负控制失败并标记类别冲突。", "负控制不与正向题的进入率混算。"]
    }),
    definition({
      templateId: "footwear.progressive.01-category.v4", slot: "progressive_01_category", expression: "direct",
      promptText: zh
        ? `我想购买适合${audience.text}日常穿着的${type.text}。先列出你本轮实际建议我了解的全部候选，不要只做Top5。按自然推荐顺序，每项只写一行：商品名｜当前价格｜Amazon商品链接。`
        : `I want ${audience.text} ${type.text} for everyday wear. First list every candidate you actually recommend in this turn, not just a Top 5. In natural recommendation order, use one line per item: product name | current price | Amazon product link.`,
      ...progressiveBase,
      hypothesis: "The first turn establishes a broad footwear candidate set for a single-session progressive diagnosis.",
      evidenceFactIds: typeAndAudienceEvidence,
      requiredTerms: [audience.text, type.text, everyCandidateTerm, notTopFiveTerm, amazonLinkTerm],
      judgmentCriteria: ["保存初始完整候选列表、顺序和商品链接，作为本递进会话的比较基线。", "本题只建立上下文，不计入主推荐指数。"]
    }),
    definition({
      templateId: "footwear.progressive.02-alexa-score.v4", slot: "progressive_02_alexa_score", expression: "comparison",
      promptText: zh
        ? `针对上一轮全部候选，并把${currentPageProduct}作为一个普通对照项，请先说明你会从哪些维度判断推荐程度，最多6个维度，并让权重合计100。然后按同一套标准给每个候选一个0到100的推荐指数。每个维度直接给0到该维度权重的加权分，总分只能由各维度分数相加，不要再次乘权重。请区分页面事实、评论证据和推断；没有证据的维度标记“未知”，不要编造比例或样本量，也不要因为它是当前页面商品而优先。`
        : `For every candidate from the previous turn, and with ${currentPageProduct} included only as an ordinary comparison item, first state up to six dimensions you use to judge recommendation strength and make their weights total 100. Then give every candidate a 0-to-100 recommendation index using the same standard. For each dimension, assign the already-weighted score from zero to that dimension's weight; the total must be only the sum of those dimension scores, with no second multiplication by weight. Separate page facts, review evidence, and inference; mark unsupported dimensions "unknown", do not invent percentages or sample sizes, and do not prioritize the current-page product because it is on the page.`,
      ...progressiveBase,
      hypothesis: "Alexa exposes a consistent diagnostic recommendation rubric and applies it to the natural candidate set plus the current-page product without page-position favoritism or arithmetic double-weighting.",
      evidenceFactIds: fnMeta.evidenceFactIds,
      requiredTerms: [currentPageProduct, zh ? "权重合计100" : "weights total 100", zh ? "不要再次乘权重" : "no second multiplication by weight", zh ? "未知" : "unknown"],
      judgmentCriteria: ["保存Alexa声明的维度、权重、逐维加权分和总分；权重必须合计100，总分必须等于逐维分之和。", "检查上一轮全部候选是否都被评分，以及当前页面商品是否只作为普通对照项。", "Alexa自评分只作诊断，不进入代码主推荐指数；编造比例、样本量或内部排序原因应标记为不可靠。"]
    }),
    definition({
      templateId: "footwear.progressive.03-screening-transparency.v4", slot: "progressive_03_screening_transparency", expression: "natural_language",
      promptText: zh
        ? `这些候选是怎样进入本轮推荐的？请分别说明你实际能够确认的候选数量、使用了哪些可见信息、哪些筛选过程无法确认。不要估算Amazon全站商品总量，也不要把评分、销量、广告或历史行为说成确定的内部排序规则。`
        : `How did these candidates enter this turn's recommendations? Separately state the candidate count you can actually confirm, which visible information you used, and which screening processes you cannot confirm. Do not estimate Amazon's total catalog size or describe ratings, sales, advertising, or history as confirmed internal ranking rules.`,
      ...progressiveBase,
      hypothesis: "Alexa distinguishes observable recommendation evidence from unknown candidate-pool and internal-ranking mechanisms.",
      evidenceFactIds: typeAndAudienceEvidence, requiredTerms: [candidateTerm],
      judgmentCriteria: ["记录Alexa能够确认的候选数量与信息来源。", "若Alexa估算全站候选池、虚构内部权重或把广告/历史行为说成已知规则，标记为机制臆测。", "本题只评估透明度，不把Alexa自述当作Amazon官方机制。"]
    }),
    definition({
      templateId: "footwear.progressive.04-entry-hypotheses.v4", slot: "progressive_04_entry_hypotheses", expression: "task",
      promptText: zh
        ? `假设用户第一次咨询这个品类，并且不使用品牌词或ASIN。根据${currentPageProduct}当前可核验的商品事实，哪些真实需求、使用场景、预算条件和属性组合会使它有资格成为合理候选？请生成最多3条自然用户问法，并为每条标出所依据的页面证据。不要声称这些词一定会提高Amazon内部排序；它们只是下一步需要用新会话验证的测试假设。`
        : `Assume a user is asking about this category for the first time without using a brand name or ASIN. Based on verifiable facts for ${currentPageProduct}, which real needs, use cases, budget conditions, and attribute combinations would make it eligible as a reasonable candidate? Generate at most three natural user questions and identify the page evidence behind each one. Do not claim these words will improve Amazon's internal ranking; they are only test hypotheses for later validation in fresh sessions.`,
      ...progressiveBase,
      hypothesis: "Alexa can produce evidence-bound, brand-free entry-condition hypotheses that are suitable for later fresh-session testing without presenting them as internal ranking rules.",
      evidenceFactIds: unique([...fnMeta.evidenceFactIds, ...sceneEvidence, ...capabilityMeta.evidenceFactIds, ...material.evidenceFactIds]),
      requiredTerms: [currentPageProduct, zh ? "最多3条自然用户问法" : "at most three natural user questions", zh ? "页面证据" : "page evidence", zh ? "新会话" : "fresh sessions"],
      judgmentCriteria: ["最多保留3条不含品牌和ASIN的自然问法。", "每条问法必须绑定具体页面证据ID或明确标记证据不足。", "建议问法、证据和生成理由进入Hermes及运行日志；只有后续新会话实际结果才能验证。"]
    }),
    definition({
      templateId: "footwear.progressive.05-scene-narrowing.v4", slot: "progressive_05_scene_narrowing", expression: "task",
      promptText: zh
        ? `如果需求进一步限定为适合${scene.text}的${audience.text}${type.text}，请列出你本轮会推荐的全部候选，不要只做Top5。每项只写一行：商品名｜进入理由｜替换条件｜当前价格｜Amazon商品链接。请标出相对第一轮新增、保留和退出的商品；只陈述可见证据，不推断Amazon内部权重。`
        : `If the need is narrowed to ${audience.text} ${type.text} suitable for ${scene.text}, list every candidate you would recommend in this turn, not just a Top 5. Use one line per item: product name | entry reason | replacement condition | current price | Amazon product link. Mark products added, retained, or removed relative to the first turn; state only visible evidence and do not infer Amazon's internal weights.`,
      ...progressiveBase,
      hypothesis: `Alexa narrows the original candidate set for the page-evidenced scene (${scene.text}) while preserving the strict footwear category and exposing candidate-set changes.`,
      evidenceFactIds: unique([...typeAndAudienceEvidence, ...sceneEvidence]),
      requiredTerms: [scene.text, audience.text, type.text, everyCandidateTerm, notTopFiveTerm, amazonLinkTerm],
      judgmentCriteria: ["记录相对P1新增、保留和退出的全部候选及链接。", "进入理由和替换条件必须来自可见证据；页面未证明的场景适配应标记未知。", "不得把候选变化解释为Amazon内部权重变化。"]
    }),
    definition({
      templateId: "footwear.progressive.06-budget-rescore.v4", slot: "progressive_06_budget_rescore", expression: "comparison",
      promptText: zh
        ? `在保留${scene.text}和${primaryFunction.text}要求的前提下，把预算进一步限制为${budgetCeiling}。请重新列出本轮全部候选，并沿用P2的同一评分标准复评分。每项只写一行：商品名｜推荐指数｜进入或退出原因｜已知风险｜当前价格｜Amazon商品链接。请特别标出${currentPageProduct}是新增、保留还是退出；不要因为低价自动优先，也不要把历史偏好或内部排序当作已知事实。`
        : `Keep the ${scene.text} and ${primaryFunction.text} requirements, but narrow the budget to ${budgetCeiling}. Relist every candidate in this turn and rescore them with the exact same standard from P2. Use one line per item: product name | recommendation index | entry or exit reason | known risk | current price | Amazon product link. Explicitly mark whether ${currentPageProduct} is added, retained, or removed; do not automatically prioritize low price or treat historical preferences or internal ranking as known facts.`,
      ...progressiveBase,
      hypothesis: `Alexa consistently reapplies its P2 rubric after adding the locked ${budgetCeiling} budget constraint and reports whether the current-page product enters naturally under scene-plus-price conditions.`,
      evidenceFactIds: unique([...fnMeta.evidenceFactIds, ...sceneEvidence]),
      requiredTerms: [scene.text, primaryFunction.text, budgetCeiling, currentPageProduct, everyCandidateTerm, amazonLinkTerm, zh ? "沿用P2的同一评分标准复评分" : "same standard from P2"],
      judgmentCriteria: ["预算上限必须由运行前页面价格带确定，执行中不得根据Alexa结果临时改写。", "记录全部候选的新增、保留、退出、风险、链接和P2同口径复评分。", "低价不能自动等于高推荐；Alexa自评分和历史偏好解释均不进入代码主指数。"]
    })
  ];

  const isolationText = zh
    ? "请把本条消息视为全新的独立请求，只依据本条需求回答，不引用或延续任何先前对话。"
    : "Treat this message as a new independent request. Answer only from the requirements in this message, without referring to or continuing any prior conversation. ";
  const isolationRequiredTerms = zh
    ? ["只依据本条需求回答", "不引用或延续任何先前对话"]
    : ["new independent request", "without referring to or continuing any prior conversation"];

  return cases.map((item) => {
    const startsNewConversation = item.sessionPolicy === "fresh" || item.templateId === "footwear.progressive.01-category.v4";
    if (!startsNewConversation) return item;
    return {
      ...item,
      promptText: `${isolationText}${item.promptText}`,
      requiredTerms: unique([...item.requiredTerms, ...isolationRequiredTerms])
    };
  });
}

export function generateFootwearPromptPlan(
  product: ProductSnapshot,
  preset: RunPreset = "full",
  promptLanguage: PromptLanguage = "en-US"
): GeneratedPromptPlan {
  const all = buildAllFootwearCases(product, promptLanguage);
  const selectedIds = new Set(PRESET_TEMPLATE_IDS[preset]);
  return {
    schemaVersion: SCHEMA_VERSION,
    promptVersion: FOOTWEAR_PROMPT_VERSION,
    preset,
    promptLanguage,
    sessionPolicy: "fresh",
    prompts: all.filter((item) => selectedIds.has(item.templateId))
  };
}

/** Backward-compatible array API used by RunsService. */
export function deterministicPromptPlan(
  product: ProductSnapshot,
  preset: RunPreset = "full",
  promptLanguage: PromptLanguage = "en-US"
): PromptCaseDefinition[] {
  return generateFootwearPromptPlan(product, preset, promptLanguage).prompts;
}

function seededNumber(seed: string, value: string): number {
  return Number.parseInt(createHash("sha256").update(`${seed}:${value}`).digest("hex").slice(0, 12), 16);
}

export function expandAndShufflePrompts(
  plan: PromptCaseDefinition[],
  _product: ProductSnapshot,
  runId: string,
  runSeed: string,
  repetitions: number,
  _promptLanguage: PromptLanguage = "en-US"
): PromptCase[] {
  if (repetitions !== 1) throw new Error("footwear-v4 requires exactly one execution per question template");
  const enabledPlan = plan.filter((item) => item.enabled);
  const expanded = enabledPlan.map((item): PromptCase => ({
    ...item,
    id: `${item.mode}:${runId}:${item.templateId}:r1`,
    repeatIndex: 1,
    sequence: 0,
    status: "pending",
    revision: 1,
    editable: true
  }));
  const independentControls = expanded
    .filter((item) => item.sessionPolicy === "fresh")
    .sort((a, b) => seededNumber(runSeed, a.id) - seededNumber(runSeed, b.id));
  const progressive = expanded
    .filter((item) => item.sessionPolicy === "shared_sequence")
    .sort((a, b) => enabledPlan.findIndex((item) => item.templateId === a.templateId)
      - enabledPlan.findIndex((item) => item.templateId === b.templateId));
  return [...independentControls, ...progressive].map((item, index) => ({ ...item, sequence: index + 1 }));
}
