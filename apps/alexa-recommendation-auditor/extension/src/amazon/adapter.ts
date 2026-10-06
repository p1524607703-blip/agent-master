import { SCHEMA_VERSION, type EvidenceFact, type IntentProfile, type ProductSnapshot, type RecommendationItem } from "@alexa-auditor/contracts";
import { SELECTOR_VERSION } from "./version";

export { SELECTOR_VERSION } from "./version";

function text(element: Element | null, max = 4000): string {
  return String((element as HTMLElement | null)?.innerText || element?.textContent || "")
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\uFEFF]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, max);
}

function texts(root: ParentNode, selector: string, maxItems = 30): string[] {
  return Array.from(root.querySelectorAll(selector)).map((item) => text(item, 1200)).filter(Boolean).slice(0, maxItems);
}

function deepRoots(root: ParentNode): ParentNode[] {
  const roots: ParentNode[] = [root];
  const seen = new Set<ParentNode>(roots);
  for (let index = 0; index < roots.length; index += 1) {
    const current = roots[index];
    Array.from(current.querySelectorAll("*")).forEach((raw) => {
      const element = raw as HTMLElement;
      if (element.shadowRoot && !seen.has(element.shadowRoot)) {
        seen.add(element.shadowRoot);
        roots.push(element.shadowRoot);
      }
      if (element.tagName === "IFRAME") {
        try {
          const frameDocument = (element as HTMLIFrameElement).contentDocument;
          if (frameDocument && !seen.has(frameDocument)) {
            seen.add(frameDocument);
            roots.push(frameDocument);
          }
        } catch { /* Cross-origin frames remain inaccessible by design. */ }
      }
    });
  }
  return roots;
}

function deepQueryAll(root: ParentNode, selector: string): HTMLElement[] {
  return deepRoots(root).flatMap((candidateRoot) => Array.from(candidateRoot.querySelectorAll(selector)) as HTMLElement[]);
}

function isVisibleElement(element: HTMLElement): boolean {
  if (element.hidden || element.getAttribute("aria-hidden") === "true" || element.getAttribute("aria-disabled") === "true") return false;
  if ((element.tagName === "TEXTAREA" || element.tagName === "INPUT") && (element as HTMLTextAreaElement | HTMLInputElement).disabled) return false;
  const view = element.ownerDocument.defaultView || window;
  let node: HTMLElement | null = element;
  while (node) {
    const style = view.getComputedStyle(node);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return false;
    node = node.parentElement;
  }
  const rect = element.getBoundingClientRect();
  const runningInJsdom = typeof navigator !== "undefined" && /jsdom/i.test(navigator.userAgent);
  return runningInJsdom || rect.width > 0 || rect.height > 0;
}

function accessibleName(element: HTMLElement): string {
  const ownerDocument = element.ownerDocument;
  const labelledByText = (element.getAttribute("aria-labelledby") || "")
    .split(/\s+/)
    .filter(Boolean)
    .map((id) => ownerDocument.getElementById(id)?.textContent || "")
    .join(" ");
  const descendantLabels = Array.from(element.querySelectorAll("img[alt], [aria-label], [title]"))
    .flatMap((node) => [node.getAttribute("alt"), node.getAttribute("aria-label"), node.getAttribute("title")])
    .filter(Boolean)
    .join(" ");
  return [
    text(element, 160),
    element.getAttribute("aria-label"),
    element.getAttribute("title"),
    element.getAttribute("data-testid"),
    labelledByText,
    descendantLabels
  ].filter(Boolean).join(" ").normalize("NFKC").replace(/\s+/g, " ").trim();
}

function isEnabledControl(element: HTMLElement): boolean {
  if (!isVisibleElement(element) || element.getAttribute("aria-disabled") === "true") return false;
  return !("disabled" in element) || !(element as HTMLButtonElement | HTMLInputElement).disabled;
}

function extractAsins(url: string, doc: Document): { requestedAsin: string; resolvedAsin: string; asinAliases: string[] } {
  const requestedAsin = (url.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i)?.[1] || "").toUpperCase();
  const detailText = text(doc.querySelector("#detailBullets_feature_div, #productDetails_detailBullets_sections1, #productDetails_db_sections"), 8000);
  const detailAsins = Array.from(detailText.matchAll(/\bASIN\b\s*[:：]?\s*([A-Z0-9]{10})\b/gi)).map((match) => match[1].toUpperCase());
  const inputCandidates = [
    (doc.querySelector("#ASIN") as HTMLInputElement | null)?.value,
    (doc.querySelector('input[name="ASIN"]') as HTMLInputElement | null)?.value,
    doc.querySelector("#twister_feature_div [data-defaultasin]")?.getAttribute("data-defaultasin"),
    doc.querySelector("#twister_feature_div [data-asin].a-button-selected, #variation_color_name [data-asin].a-button-selected, #variation_size_name [data-asin].a-button-selected")?.getAttribute("data-asin"),
    detailAsins[0]
  ];
  const resolvedAsin = String(inputCandidates.find((value) => /^[A-Z0-9]{10}$/i.test(String(value || ""))) || requestedAsin).toUpperCase();
  const pageAsins = Array.from(doc.querySelectorAll("[data-defaultasin], #twister_feature_div [data-asin]"))
    .flatMap((element) => [element.getAttribute("data-defaultasin"), element.getAttribute("data-asin")])
    .map((value) => String(value || "").toUpperCase())
    .filter((value) => /^[A-Z0-9]{10}$/.test(value));
  const asinAliases = [...new Set([requestedAsin, resolvedAsin, ...detailAsins, ...pageAsins].filter((value) => /^[A-Z0-9]{10}$/.test(value)))];
  return { requestedAsin, resolvedAsin, asinAliases };
}

function valuesFor(all: string, rules: Array<[RegExp, string]>): string[] {
  return [...new Set(rules.filter(([pattern]) => pattern.test(all)).map(([, value]) => value))];
}

function heuristicProfile(title: string, bullets: string[], specifications: Record<string, string>, breadcrumb: string[], aPlusText: string): IntentProfile {
  const all = `${title} ${breadcrumb.join(" ")} ${bullets.join(" ")} ${Object.entries(specifications).flat().join(" ")} ${aPlusText}`.normalize("NFKC").toLowerCase();
  const productType = valuesFor(all, [
    [/flip[ -]?flops?|thong sandals?|人字拖|夹趾拖/, "flip_flops"],
    [/slides?|slide sandals?|一字拖|拖鞋/, "slides"],
    [/loafers?|boat shoes?|deck shoes?|乐福鞋|船鞋/, "loafers"],
    [/slip[ -]?ons?|套脚|一脚蹬/, "slip_on_shoes"],
    [/water shoes?|aqua shoes?|水鞋|涉水鞋/, "water_shoes"],
    [/barefoot|minimalist|赤足鞋|极简鞋/, "barefoot_shoes"],
    [/running shoes?|跑鞋/, "running_shoes"],
    [/walking shoes?|步行鞋|健走鞋/, "walking_shoes"],
    [/sneakers?|tennis shoes?|运动鞋|板鞋/, "sneakers"],
    [/sandals?|凉鞋/, "sandals"],
    [/boots?|靴/, "boots"],
    [/clogs?|洞洞鞋/, "clogs"]
  ]);
  if (!productType.length && /shoe|footwear|鞋/.test(all)) productType.push("shoes");
  if (!productType.length) productType.push("unknown_product");
  const audience = valuesFor(all, [
    [/women(?:'s|s)?|ladies|female|女士|女款|女性/, "women"],
    [/(?:^|\W)men(?:'s|s)?(?:\W|$)|male|男士|男款|男性/, "men"],
    [/kids?|children|toddler|baby|youth|儿童|幼儿|婴儿|童鞋/, "kids"],
    [/unisex|男女通用|中性/, "unisex"]
  ]);
  const functions = valuesFor(all, [
    [/arch support|足弓支撑|足弓承托/, "arch_support"],
    [/slip[ -]?resistant|non[ -]?slip|anti[ -]?slip|防滑|止滑/, "slip_resistant"],
    [/cushion|shock absorb|缓冲|缓震|减震/, "cushioning"],
    [/lightweight|ultralight|超轻|轻量|轻盈/, "lightweight"],
    [/breathable|透气/, "breathable"],
    [/easy to clean|washable|易清洁|可机洗/, "easy_clean"],
    [/waterproof|water resistant|防水/, "waterproof"],
    [/quick[ -]?dry|速干|快干/, "quick_dry"],
    [/wide toe|roomy toe|宽鞋头|宽趾|宽头/, "wide_toe_box"],
    [/traction|grip|抓地/, "traction"],
    [/flexib|柔韧|灵活/, "flexible"],
    [/durab|耐用/, "durable"],
    [/all[ -]?day comfort|全天舒适|久站/, "all_day_comfort"]
  ]);
  const bodyNeeds = valuesFor(all, [
    [/wide feet|wide width|宽脚|宽楦/, "wide_feet"],
    [/flat feet|fallen arches|扁平足|低足弓/, "flat_feet"],
    [/plantar fasciitis|足底筋膜炎/, "plantar_fasciitis"],
    [/heel pain|足跟痛|脚后跟疼/, "heel_pain"],
    [/bunions?|hallux valgus|拇外翻/, "bunions"],
    [/swollen feet|foot swelling|脚肿|足部肿胀/, "foot_swelling"]
  ]);
  const events = valuesFor(all, [
    [/walking|walk|步行|散步/, "walking"],
    [/standing|all day|久站|全天穿/, "long_standing"],
    [/travel|vacation|旅行|旅游|度假/, "travel"],
    [/hiking|徒步/, "hiking"],
    [/running|跑步/, "running"],
    [/workout|training|gym|训练|健身/, "training"],
    [/water activit|swimming|游泳|水上活动/, "water_activities"],
    [/casual|daily wear|日常|休闲/, "daily_casual"]
  ]);
  const locations = valuesFor(all, [
    [/beach|沙滩|海滩/, "beach"],
    [/pool|泳池|游泳池/, "pool"],
    [/bathroom|shower|浴室|淋浴/, "bathroom"],
    [/outdoor|户外/, "outdoors"],
    [/indoor|home|室内|家居/, "indoors"],
    [/river|creek|河流|溪流/, "river"],
    [/workplace|work|工作场所|上班/, "workplace"]
  ]);
  const materials = valuesFor(all, [
    [/\beva\b|ethylene vinyl acetate|乙烯.?醋酸乙烯|eva材质/, "eva"],
    [/leather|皮革|真皮/, "leather"],
    [/canvas|帆布/, "canvas"],
    [/mesh|网眼|网布/, "mesh"],
    [/knit|针织/, "knit"]
  ]);
  const primaryProduct = productType[0];
  return {
    primary_domain: "clothing_shoes_jewelry", secondary_domain: [], product_type: productType, audience_intent: audience,
    function_intent: functions, capability_intent: materials, event_intent: events, location_intent: locations, body_need_intent: bodyNeeds, time_intent: [], substitute_intent: [], complement_intent: [],
    latent_task: `用户正在寻找适合${audience[0] || "目标人群"}、用于${events[0] || locations[0] || "日常穿着"}的${primaryProduct}。`, intent_stage: "consideration", evidence_type: ["explicit", "page_validated"], confidence_level: primaryProduct === "unknown_product" ? "low" : "medium",
    intent_cluster: `${audience[0] || "general"}_${primaryProduct}_${events[0] || functions[0] || "general"}`, routing_action: primaryProduct === "unknown_product" ? "ambiguity_review" : "cluster_route"
  };
}

export function extractProductSnapshot(doc: Document = document, url = location.href): ProductSnapshot {
  const capturedAt = new Date().toISOString();
  const { requestedAsin, resolvedAsin, asinAliases } = extractAsins(url, doc);
  const title = text(doc.querySelector("#productTitle"), 1000);
  const brandRaw = text(doc.querySelector("#bylineInfo"), 300);
  const brand = brandRaw
    .replace(/^(Visit the|Brand:|访问)\s+/i, "")
    .replace(/\s+(Store|商店)$/i, "")
    .trim();
  const breadcrumb = texts(doc, "#wayfinding-breadcrumbs_feature_div a, #wayfinding-breadcrumbs_container a", 20);
  const bullets = texts(doc, "#feature-bullets li .a-list-item, #featurebullets_feature_div li", 20);
  const specifications: Record<string, string> = {};
  Array.from(doc.querySelectorAll("#productDetails_techSpec_section_1 tr, #productDetails_detailBullets_sections1 tr, #prodDetails tr, .a-expander-content table tr")).forEach((row) => {
    const cells = row.querySelectorAll("th, td");
    if (cells.length >= 2) {
      const key = text(cells[0], 200);
      const value = text(cells[1], 800);
      if (key && value && !specifications[key]) specifications[key] = value;
    }
  });
  const aPlusText = text(doc.querySelector("#aplus, #aplus_feature_div"), 12000);
  const reviewSummary = text(doc.querySelector("#customerReviews, #reviewsMedley"), 4000);
  const qaText = text(doc.querySelector("#ask-btf, #ask_feature_div"), 4000);

  const stableFacts: EvidenceFact[] = [];
  const addFact = (field: string, value: string | string[], sourceSection: EvidenceFact["sourceSection"], sourceText: string, index: number) => {
    if (!sourceText) return;
    stableFacts.push({ id: `${sourceSection}_${index}`, field, value, evidenceType: sourceSection === "title" || sourceSection === "brand" ? "explicit" : "page_validated", sourceSection, sourceText, confidence: "high", capturedAt });
  };
  addFact("product_type", title, "title", title, 0);
  addFact("brand", brand, "brand", brandRaw, 0);
  breadcrumb.forEach((value, index) => addFact("primary_domain", value, "breadcrumb", value, index));
  bullets.forEach((value, index) => addFact("page_claim", value, "bullets", value, index));
  Object.entries(specifications).slice(0, 50).forEach(([key, value], index) => addFact(key.toLowerCase().replace(/[^a-z0-9]+/g, "_"), value, "specification", `${key}: ${value}`, index));
  if (aPlusText) addFact("a_plus_claims", aPlusText, "a_plus", aPlusText, 0);
  if (reviewSummary) addFact("review_summary", reviewSummary, "review_summary", reviewSummary, 0);
  if (qaText) addFact("qa", qaText, "qa", qaText, 0);

  const volatileFacts: EvidenceFact[] = [];
  [
    ["price", text(doc.querySelector("#corePriceDisplay_desktop_feature_div .a-offscreen, .priceToPay .a-offscreen, #priceblock_ourprice"), 100)],
    ["availability", text(doc.querySelector("#availability"), 300)],
    ["delivery", text(doc.querySelector("#mir-layout-DELIVERY_BLOCK-slot-PRIMARY_DELIVERY_MESSAGE_LARGE, #deliveryBlockMessage"), 500)]
  ].forEach(([field, value], index) => {
    if (value) volatileFacts.push({ id: `retail_${index}`, field, value, evidenceType: "page_validated", sourceSection: "retail", sourceText: value, confidence: "medium", capturedAt });
  });

  return {
    asin: resolvedAsin || requestedAsin, requestedAsin, resolvedAsin, asinAliases, url, marketplace: new URL(url).hostname, title, brand, breadcrumb, bullets, specifications, aPlusText, reviewSummary, qaText,
    stableFacts, volatileFacts, intentProfile: heuristicProfile(title, bullets, specifications, breadcrumb, aPlusText), accountLabel: "dedicated_test_account", selectorVersion: SELECTOR_VERSION, schemaVersion: SCHEMA_VERSION, capturedAt
  };
}

export function detectSafetyStop(doc: Document = document): string | null {
  const pageText = text(doc.body, 10000).toLowerCase();
  if (/enter the characters you see|captcha|robot check/.test(pageText)) return "captcha";
  if (/too many requests|try again later/.test(pageText)) return "rate_limited";
  if (/sign in to continue|please sign in/.test(pageText)) return "login_required";
  if (/sorry.*something went wrong|page not found/.test(pageText) && !findComposer(doc)) return "selector_drift";
  return null;
}

export function findComposer(doc: Document = document): HTMLTextAreaElement | HTMLInputElement | HTMLElement | null {
  const selectors = [
    'textarea[placeholder*="shopping" i]', 'textarea[aria-label*="shopping" i]', 'textarea[placeholder*="Ask" i]',
    'textarea[placeholder*="购物" i]', 'textarea[aria-label*="购物" i]', 'textarea[placeholder*="询问" i]',
    '[contenteditable="true"][role="textbox"]', '[contenteditable="true"]',
    'input[placeholder*="shopping" i]', 'input[placeholder*="购物" i]', 'textarea'
  ];
  return selectors.flatMap((selector) => deepQueryAll(doc, selector)).find(isVisibleElement) || null;
}

const SUBMIT_CONTROL_SELECTOR = [
  'button[type="submit"]', 'input[type="submit"]',
  'button[aria-label*="send" i]', 'button[aria-label*="submit" i]',
  '[role="button"][aria-label*="send" i]', '[role="button"][aria-label*="submit" i]',
  '[data-testid*="send" i]', '[data-testid*="submit" i]'
].join(", ");

function submitControlFromSurface(surface: ParentNode, allowUnnamedSubmit: boolean): HTMLElement | null {
  const submitName = /(?:^|\b)(?:send|submit)(?:\b|$)|发送|提交/i;
  const candidates = Array.from(surface.querySelectorAll(SUBMIT_CONTROL_SELECTOR)) as HTMLElement[];
  const trusted = candidates.find((candidate) => {
    if (!isEnabledControl(candidate)) return false;
    if (submitName.test(accessibleName(candidate))) return true;
    if (/send|submit/i.test(candidate.getAttribute("data-testid") || "")) return true;
    return allowUnnamedSubmit && candidate.getAttribute("type") === "submit";
  });
  if (trusted) return trusted;

  return (Array.from(surface.querySelectorAll("button, input[type='button'], [role='button']")) as HTMLElement[])
    .find((candidate) => submitName.test(accessibleName(candidate)) && isEnabledControl(candidate)) || null;
}

function composerSubmitSurfaces(composer: HTMLElement): Array<{ surface: ParentNode; allowUnnamedSubmit: boolean }> {
  const surfaces: Array<{ surface: ParentNode; allowUnnamedSubmit: boolean }> = [];
  const seen = new Set<ParentNode>();
  const add = (surface: ParentNode | null | undefined, allowUnnamedSubmit: boolean) => {
    if (!surface || seen.has(surface)) return;
    seen.add(surface);
    surfaces.push({ surface, allowUnnamedSubmit });
  };

  // A submit button without a name is trustworthy only inside the exact form
  // that owns the Rufus composer. Searching the whole Amazon document for the
  // first button[type=submit] can otherwise click the global product-search
  // button and navigate the tab while a prompt is in flight.
  add(composer.closest("form"), true);

  let ancestor = composer.parentElement;
  for (let depth = 0; ancestor && ancestor !== composer.ownerDocument.body && depth < 8; depth += 1) {
    add(ancestor, false);
    ancestor = ancestor.parentElement;
  }

  const root = composer.getRootNode();
  if (root instanceof ShadowRoot) add(root, false);
  return surfaces;
}

export function findSubmitControl(doc: Document = document, composer: HTMLElement | null = findComposer(doc)): HTMLElement | null {
  if (!composer) return null;
  for (const { surface, allowUnnamedSubmit } of composerSubmitSurfaces(composer)) {
    const control = submitControlFromSurface(surface, allowUnnamedSubmit);
    if (control) return control;
  }
  return null;
}

export function submitSurfaceDiagnostics(doc: Document = document, composer: HTMLElement | null = findComposer(doc)): string {
  const controls = deepQueryAll(doc, "button, input[type='submit'], [role='button']");
  const submitLike = controls.filter((control) => /send|submit|发送|提交/i.test(accessibleName(control)) || control.getAttribute("type") === "submit");
  const scopedControls = composer
    ? composerSubmitSurfaces(composer).flatMap(({ surface }) => Array.from(surface.querySelectorAll("button, input[type='submit'], [role='button']")) as HTMLElement[])
    : [];
  return JSON.stringify({
    composerTag: composer?.tagName || "missing",
    composerRole: composer?.getAttribute("role") || "",
    controls: controls.length,
    submitLike: submitLike.length,
    enabledSubmitLike: submitLike.filter(isEnabledControl).length,
    scopedControls: new Set(scopedControls).size,
    names: submitLike.slice(0, 8).map((control) => accessibleName(control).slice(0, 120))
  });
}

export function composerSurfaceDiagnostics(doc: Document = document): string {
  const roots = deepRoots(doc);
  const frames = Array.from(doc.querySelectorAll("iframe")) as HTMLIFrameElement[];
  const accessibleFrames = frames.filter((frame) => {
    try { return Boolean(frame.contentDocument); } catch { return false; }
  }).length;
  return JSON.stringify({
    roots: roots.length,
    shadowRoots: roots.filter((root) => "host" in root).length,
    frames: frames.length,
    accessibleFrames,
    textareas: deepQueryAll(doc, "textarea").length,
    contentEditables: deepQueryAll(doc, '[contenteditable="true"]').length
  });
}

export function findAlexaPanel(doc: Document = document): HTMLElement {
  const composer = findComposer(doc);
  let node = composer?.parentElement || null;
  let outermostCandidate: HTMLElement | null = null;
  while (node && node !== doc.body) {
    const rect = node.getBoundingClientRect();
    const viewportWidth = doc.defaultView?.innerWidth || window.innerWidth;
    if (rect.height > 350 && rect.width > 250 && rect.width < viewportWidth * 0.6) outermostCandidate = node;
    node = node.parentElement;
  }
  if (outermostCandidate) return outermostCandidate;
  return deepQueryAll(doc, '[aria-label*="Alexa" i], [data-testid*="alexa" i], [aria-label*="Rufus" i], [data-testid*="rufus" i]')[0] || doc.body;
}

const ALEXA_GENERATING_MARKERS = [
  "rufus 目前正在生成回复",
  "rufus 正在生成回复",
  "rufus is currently generating a response",
  "rufus is generating a response"
];

const ALEXA_COMPLETED_MARKERS = [
  "rufus 已完成生成回复",
  "rufus 已完成回复",
  "rufus has completed generating a response",
  "rufus completed generating a response"
];

function lastMarkerIndex(value: string, markers: string[]): number {
  return markers.reduce((latest, marker) => Math.max(latest, value.lastIndexOf(marker)), -1);
}

export function inspectAlexaConversationText(value: string): {
  generating: boolean;
  completionCount: number;
  hasConversation: boolean;
} {
  const normalized = String(value || "").normalize("NFKC").replace(/\s+/g, " ").toLowerCase();
  const lastGenerating = lastMarkerIndex(normalized, ALEXA_GENERATING_MARKERS);
  const lastCompleted = lastMarkerIndex(normalized, ALEXA_COMPLETED_MARKERS);
  const completionCount = ALEXA_COMPLETED_MARKERS.reduce((count, marker) => {
    let offset = 0;
    let next = normalized.indexOf(marker, offset);
    while (next >= 0) {
      count += 1;
      offset = next + marker.length;
      next = normalized.indexOf(marker, offset);
    }
    return count;
  }, 0);
  const hasQuestion = /(?:customer|user) question|客户问题|用户问题/.test(normalized);
  return {
    generating: lastGenerating >= 0 && lastGenerating > lastCompleted,
    completionCount,
    hasConversation: hasQuestion || lastGenerating >= 0 || lastCompleted >= 0
  };
}

export function inspectAlexaConversation(doc: Document = document) {
  return inspectAlexaConversationText(text(findAlexaPanel(doc), 50000));
}

export function isPristineAlexaConversationText(value: string): boolean {
  const normalized = String(value || "").normalize("NFKC").replace(/\s+/g, " ").toLowerCase();
  if (inspectAlexaConversationText(normalized).hasConversation) return false;
  return /welcome back|欢迎回来|what can i help|我能帮上什么忙|我今天能帮你什么|ask a shopping question|询问购物问题/.test(normalized);
}

export function isAlexaResponseCandidate(input: {
  previousText: string;
  currentText: string;
  promptText: string;
  sawGenerating: boolean;
  elapsedMs: number;
}): boolean {
  const previousState = inspectAlexaConversationText(input.previousText);
  const currentState = inspectAlexaConversationText(input.currentText);
  if (currentState.generating) return false;
  const minimumGrowth = input.promptText.normalize("NFKC").replace(/\s+/g, " ").trim().length + 20;
  const completionAdvanced = currentState.completionCount > previousState.completionCount;
  return input.currentText !== input.previousText
    && input.currentText.length > input.previousText.length + minimumGrowth
    && (input.sawGenerating || completionAdvanced || input.elapsedMs > 8000);
}

function asinFromHref(href: string): string {
  const variants = [href];
  try { variants.push(decodeURIComponent(href)); } catch { /* keep the original URL */ }
  for (const value of variants) {
    const match = value.match(/\/(?:dp|gp\/product)\/([A-Z0-9]{10})/i)
      || value.match(/[?&](?:asin|pd_rd_i|creativeASIN)=([A-Z0-9]{10})/i);
    if (match?.[1]) return match[1].toUpperCase();
  }
  return "";
}

export function parseAlexaResponse(doc: Document = document): {
  responseText: string;
  recommendations: RecommendationItem[];
  extractionDiagnostics: { responseChars: number; domLinkCount: number; asinCount: number; textOnlyCount: number };
} {
  const panel = findAlexaPanel(doc);
  const responseText = text(panel, 50000).slice(-20000);
  const links = Array.from(panel.querySelectorAll("a[href]")) as HTMLAnchorElement[];
  const seen = new Set<string>();
  const candidates: Array<RecommendationItem & { position: number }> = [];
  const addCandidate = (asin: string, title: string, url: string, card: HTMLElement | null, position: number) => {
    const normalizedTitle = title.normalize("NFKC").replace(/\s+/g, " ").trim();
    const key = asin || normalizedTitle.toLowerCase();
    if (!key || seen.has(key) || candidates.length >= 100) return;
    const cardText = text(card, 2200);
    if (!normalizedTitle) return;
    seen.add(key);
    candidates.push({
      asin, title: normalizedTitle, brand: normalizedTitle.split(/\s+/)[0] || "", rank: 0, url,
      priceText: cardText.match(/\$\s?\d+(?:\.\d{2})?/)?.[0] || "", ratingText: cardText.match(/\d(?:\.\d)?\s*(?:out of 5|stars?)/i)?.[0] || "",
      reviewCountText: cardText.match(/\([\d,]+\)/)?.[0] || "", sponsored: /sponsored/i.test(cardText),
      deliveryText: cardText.match(/(?:FREE delivery|delivery)[^.\n]*/i)?.[0] || "", evidenceText: cardText, position
    });
  };
  links.forEach((link) => {
    const asin = asinFromHref(link.href);
    if (!asin) return;
    const card = (link.closest("article, li, [role='listitem'], [data-asin], .a-cardui, div[class*='card']") || link.parentElement) as HTMLElement | null;
    const title = text(card?.querySelector("h2, h3, h4, [class*='title']") || link, 500)
      || link.getAttribute("aria-label")
      || link.getAttribute("title")
      || "";
    const position = responseText.indexOf(title);
    addCandidate(asin, title, link.href, card, position < 0 ? Number.MAX_SAFE_INTEGER : position);
  });
  Array.from(panel.querySelectorAll("[data-asin]")).forEach((raw) => {
    const element = raw as HTMLElement;
    const asin = String(element.getAttribute("data-asin") || "").toUpperCase();
    if (!/^[A-Z0-9]{10}$/.test(asin)) return;
    const title = text(element.querySelector("h2, h3, h4, [class*='title'], a[aria-label]"), 500);
    const href = (element.querySelector("a[href]") as HTMLAnchorElement | null)?.href || `https://www.amazon.com/dp/${asin}`;
    const position = responseText.indexOf(title);
    addCandidate(asin, title, href, element, position < 0 ? Number.MAX_SAFE_INTEGER : position);
  });

  Array.from(panel.querySelectorAll("button, [role='button']")).forEach((raw) => {
    const button = raw as HTMLElement;
    if (!/add to cart|加入购物车|添加到购物车/i.test(text(button, 120))) return;
    const card = (button.closest("article, li, [role='listitem'], [data-asin], .a-cardui, div[class*='card']") || button.parentElement?.parentElement) as HTMLElement | null;
    if (!card) return;
    const titleElement = card.querySelector("h2, h3, h4, [class*='title'], a[aria-label], [role='heading']");
    const title = text(titleElement, 500);
    if (!title || /add to cart|加入购物车|添加到购物车/i.test(title)) return;
    const link = card.querySelector("a[href]") as HTMLAnchorElement | null;
    const asin = String(card.getAttribute("data-asin") || asinFromHref(link?.href || "")).toUpperCase();
    const position = responseText.indexOf(title);
    addCandidate(/^[A-Z0-9]{10}$/.test(asin) ? asin : "", title, link?.href || "", card, position < 0 ? Number.MAX_SAFE_INTEGER : position);
  });

  const currentTitle = text(doc.querySelector("#productTitle"), 1000);
  const currentBrand = text(doc.querySelector("#bylineInfo"), 300).replace(/^(Visit the|Brand:|访问)\s+/i, "").replace(/\s+(Store|商店)$/i, "").trim();
  const normalizedResponse = responseText.toLowerCase();
  const titleTokens = currentTitle.toLowerCase().split(/\s+/).filter((token) => token.length > 4);
  const currentMentioned = currentTitle && (
    normalizedResponse.includes(currentTitle.toLowerCase())
    || Boolean(currentBrand && normalizedResponse.includes(currentBrand.toLowerCase()) && titleTokens.filter((token) => normalizedResponse.includes(token)).length >= 2)
  );
  if (currentMentioned) {
    const asins = extractAsins(doc.location?.href || location.href, doc);
    const position = normalizedResponse.indexOf(currentTitle.toLowerCase());
    addCandidate(asins.resolvedAsin || asins.requestedAsin, currentTitle, doc.location?.href || location.href, doc.querySelector("#centerCol") as HTMLElement | null, position < 0 ? 0 : position);
  }

  const recommendations = candidates
    .sort((a, b) => a.position - b.position)
    .map(({ position: _position, ...item }, index) => ({ ...item, rank: index + 1 }));
  return {
    responseText,
    recommendations,
    extractionDiagnostics: {
      responseChars: responseText.length,
      domLinkCount: links.length,
      asinCount: recommendations.filter((item) => Boolean(item.asin)).length,
      textOnlyCount: recommendations.filter((item) => !item.asin).length
    }
  };
}

export function maskPii(doc: Document = document): () => void {
  const selectors = ["#nav-global-location-popover-link", "#nav-link-accountList-nav-line-1", "#glow-ingress-line2", "[data-testid*='address']"];
  const changed: Array<{ element: HTMLElement; filter: string }> = [];
  selectors.forEach((selector) => doc.querySelectorAll(selector).forEach((raw) => {
    const element = raw as HTMLElement;
    changed.push({ element, filter: element.style.filter });
    element.style.filter = "blur(8px)";
  }));
  return () => changed.forEach(({ element, filter }) => { element.style.filter = filter; });
}

export function clickByText(root: ParentNode, pattern: RegExp): boolean {
  const candidates = deepQueryAll(root, "button, [role='button'], a");
  const target = candidates.find((item) => {
    if (!pattern.test(accessibleName(item))) return false;
    return isEnabledControl(item);
  });
  target?.click();
  return Boolean(target);
}
