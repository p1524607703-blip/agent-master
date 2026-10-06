import type { EvidenceFact, ProductSnapshot } from "@alexa-auditor/contracts";

export const AMAZON_MARKETPLACE_HOSTS = [
  "amazon.com",
  "amazon.co.jp",
  "amazon.de",
  "amazon.fr",
  "amazon.it",
  "amazon.es"
] as const;

export const AMAZON_TAB_QUERY_PATTERNS = AMAZON_MARKETPLACE_HOSTS.map((host) => `https://www.${host}/*`);
export const STUDIO_PRODUCT_CACHE_KEY = "studioAmazonProductContextV2";
export const STUDIO_PRODUCT_CACHE_TTL_MS = 15 * 60 * 1000;

const PDP_PATH_PATTERN = /\/(?:dp|gp\/product)\/([A-Z0-9]{10})(?:[/?]|$)/i;
const PLANNING_EVIDENCE_SECTIONS = new Set<EvidenceFact["sourceSection"]>([
  "title",
  "brand",
  "breadcrumb",
  "bullets",
  "specification",
  "a_plus"
]);
const EXCLUDED_PLANNING_LABEL = /price|deal|coupon|availability|stock|seller|delivery|shipping|customer reviews?|ratings?|preis|lieferung|bewertungen?|kundenrezensionen?|prix|livraison|avis clients?|prezzo|spedizione|recensioni clienti|precio|env[ií]o|valoraciones?|価格|配送|在庫|出品者|カスタマーレビュー|評価/i;
const EXCLUDED_PLANNING_TEXT = /(?:rufus|alexa for shopping|customer question|chat history|shopping assistant|客户问题|用户问题|聊天记录|购物助手)/i;
const EXCLUDED_PLANNING_VALUE = /(?:\b(?:price|deal|coupon|availability|in stock|seller|delivery|shipping|customer reviews?|ratings?)\b|[$€£¥]\s*\d|\d(?:[.,]\d+)?\s*(?:stars?|星))/i;

export type ProductTabCandidate = Pick<chrome.tabs.Tab, "id" | "url" | "lastAccessed" | "active" | "windowId">;

export type StudioProductCache = {
  snapshot: ProductSnapshot;
  cachedAt: string;
  sourceTabId?: number;
};

function supportedHostname(hostname: string): boolean {
  const normalized = hostname.toLowerCase().replace(/^www\./, "");
  return AMAZON_MARKETPLACE_HOSTS.some((host) => host === normalized);
}

export function asinFromAmazonPdpUrl(rawUrl: string): string {
  try {
    const url = new URL(rawUrl);
    if (url.protocol !== "https:" || !supportedHostname(url.hostname)) return "";
    return (url.pathname.match(PDP_PATH_PATTERN)?.[1] || "").toUpperCase();
  } catch {
    return "";
  }
}

export function isSupportedAmazonPdpUrl(rawUrl: string | undefined): rawUrl is string {
  return Boolean(rawUrl && asinFromAmazonPdpUrl(rawUrl));
}

function validTab(candidate: ProductTabCandidate | undefined): candidate is ProductTabCandidate & { id: number; url: string } {
  return Boolean(
    candidate
    && typeof candidate.id === "number"
    && Number.isInteger(candidate.id)
    && candidate.id >= 0
    && isSupportedAmazonPdpUrl(candidate.url)
  );
}

/**
 * Prefer the user's currently active PDP. When the image studio itself is the
 * active tab, select only the most recently accessed PDP; an Amazon home or
 * search page is never an eligible fallback.
 */
export function selectPreferredAmazonProductTab(
  activeTab: ProductTabCandidate | undefined,
  candidates: ProductTabCandidate[],
  preferredWindowId?: number
): ProductTabCandidate & { id: number; url: string } {
  if (validTab(activeTab) && (!Number.isInteger(preferredWindowId) || activeTab.windowId === preferredWindowId)) return activeTab;
  const productTabs = candidates
    .filter(validTab)
    .sort((left, right) => Number(right.lastAccessed || 0) - Number(left.lastAccessed || 0));
  const preferredWindowProduct = Number.isInteger(preferredWindowId)
    ? productTabs.find((tab) => tab.windowId === preferredWindowId)
    : undefined;
  const selected = preferredWindowProduct || productTabs[0];
  if (!selected) {
    throw Object.assign(
      new Error("没有可同步的 Amazon 商品详情页，请先在支持站点打开含 /dp/ASIN 的商品页"),
      { code: "amazon_pdp_not_found" }
    );
  }
  return selected;
}

/** Select only a tab whose marketplace and URL ASIN match the pasted link. */
export function selectAmazonProductTabByUrl(
  requestedUrl: string,
  candidates: ProductTabCandidate[],
  preferredWindowId?: number
): ProductTabCandidate & { id: number; url: string } {
  const requestedAsin = asinFromAmazonPdpUrl(requestedUrl);
  if (!requestedAsin) {
    throw Object.assign(new Error("请提供受支持的 Amazon 商品详情页链接"), { code: "amazon_pdp_url_invalid" });
  }
  const requestedHost = new URL(requestedUrl).hostname.toLowerCase().replace(/^www\./, "");
  const matchingTabs = candidates
    .filter(validTab)
    .filter((tab) => {
      try {
        return asinFromAmazonPdpUrl(tab.url) === requestedAsin
          && new URL(tab.url).hostname.toLowerCase().replace(/^www\./, "") === requestedHost;
      } catch {
        return false;
      }
    })
    .sort((left, right) => Number(right.lastAccessed || 0) - Number(left.lastAccessed || 0));
  const selected = Number.isInteger(preferredWindowId)
    ? matchingTabs.find((tab) => tab.windowId === preferredWindowId) || matchingTabs[0]
    : matchingTabs[0];
  if (!selected) {
    throw Object.assign(
      new Error(`没有找到已打开的目标商品页（${requestedAsin}）。请先在当前 Chrome 窗口打开该链接并等待页面加载完成`),
      { code: "amazon_pdp_target_not_open" }
    );
  }
  return selected;
}

function planningSpecificationAllowed(key: string, value: string): boolean {
  const corpus = `${key} ${value}`;
  return Boolean(key && value)
    && !EXCLUDED_PLANNING_LABEL.test(key)
    && !EXCLUDED_PLANNING_TEXT.test(corpus)
    && !EXCLUDED_PLANNING_VALUE.test(corpus);
}

function canonicalProductUrl(snapshot: ProductSnapshot): string {
  try {
    const source = new URL(snapshot.url);
    const urlAsin = asinFromAmazonPdpUrl(snapshot.url);
    if (!supportedHostname(source.hostname) || !urlAsin || !studioSnapshotMatchesAsin(snapshot, urlAsin)) return "";
    return `${source.origin}/dp/${urlAsin}`;
  } catch {
    return "";
  }
}

function factValueText(value: EvidenceFact["value"]): string {
  return Array.isArray(value) ? value.join(" ") : String(value || "");
}

function planningFactAllowed(fact: EvidenceFact): boolean {
  const corpus = `${fact.field} ${fact.sourceText || ""} ${factValueText(fact.value)}`;
  return PLANNING_EVIDENCE_SECTIONS.has(fact.sourceSection)
    && !EXCLUDED_PLANNING_TEXT.test(corpus)
    && !EXCLUDED_PLANNING_VALUE.test(corpus)
    && (fact.sourceSection !== "specification" || !EXCLUDED_PLANNING_LABEL.test(corpus));
}

function cleanPlanningText(value: unknown): string {
  const result = String(value || "").trim();
  return EXCLUDED_PLANNING_TEXT.test(result) ? "" : result;
}

function cleanPlanningTexts(values: unknown): string[] {
  return Array.isArray(values) ? values.map(cleanPlanningText).filter(Boolean) : [];
}

function cleanAsin(value: unknown): string {
  const asin = String(value || "").trim().toUpperCase();
  return /^[A-Z0-9]{10}$/.test(asin) ? asin : "";
}

function neutralPlanningIntentProfile(): ProductSnapshot["intentProfile"] {
  return {
    primary_domain: "others",
    secondary_domain: [],
    product_type: [],
    audience_intent: [],
    function_intent: [],
    capability_intent: [],
    event_intent: [],
    location_intent: [],
    body_need_intent: [],
    time_intent: [],
    substitute_intent: [],
    complement_intent: [],
    latent_task: "",
    intent_stage: "unknown",
    evidence_type: [],
    confidence_level: "low",
    intent_cluster: "",
    routing_action: "ambiguity_review"
  };
}

/**
 * Produce the planning-only ProductSnapshot sent outside the extension.
 * The allowlist intentionally removes reviews, Q&A, retail state, Rufus text,
 * account labels, and tracking query parameters so they cannot contaminate an
 * image-planning prompt.
 */
export function sanitizeProductSnapshotForStudio(snapshot: ProductSnapshot): ProductSnapshot {
  const specifications = Object.fromEntries(
    Object.entries(snapshot.specifications || {})
      .filter(([key, value]) => planningSpecificationAllowed(String(key), String(value)))
      .slice(0, 50)
  );
  const stableFacts = (snapshot.stableFacts || [])
    .filter(planningFactAllowed);
  const asin = cleanAsin(snapshot.asin);
  const requestedAsin = cleanAsin(snapshot.requestedAsin);
  const resolvedAsin = cleanAsin(snapshot.resolvedAsin);
  const asinAliases = Array.from(new Set([
    asin,
    requestedAsin,
    resolvedAsin,
    ...(snapshot.asinAliases || []).map(cleanAsin)
  ].filter(Boolean)));
  const canonicalUrl = canonicalProductUrl(snapshot);
  let marketplace = "";
  try { marketplace = canonicalUrl ? new URL(canonicalUrl).hostname : ""; } catch { marketplace = ""; }

  return {
    asin,
    ...(requestedAsin ? { requestedAsin } : {}),
    ...(resolvedAsin ? { resolvedAsin } : {}),
    asinAliases,
    url: canonicalUrl,
    marketplace,
    title: cleanPlanningText(snapshot.title),
    brand: cleanPlanningText(snapshot.brand),
    breadcrumb: cleanPlanningTexts(snapshot.breadcrumb),
    bullets: cleanPlanningTexts(snapshot.bullets),
    specifications,
    aPlusText: cleanPlanningText(snapshot.aPlusText),
    stableFacts,
    volatileFacts: [],
    reviewSummary: "",
    qaText: "",
    intentProfile: neutralPlanningIntentProfile(),
    accountLabel: "",
    selectorVersion: String(snapshot.selectorVersion || ""),
    schemaVersion: snapshot.schemaVersion,
    capturedAt: String(snapshot.capturedAt || "")
  };
}

export function isUsableStudioProductSnapshot(snapshot: ProductSnapshot | undefined): snapshot is ProductSnapshot {
  if (!snapshot) return false;
  const asin = String(snapshot.asin || "").toUpperCase();
  const urlAsin = asinFromAmazonPdpUrl(snapshot.url);
  return /^[A-Z0-9]{10}$/.test(asin)
    && Boolean(String(snapshot.title || "").trim())
    && Boolean(urlAsin)
    && studioSnapshotMatchesAsin(snapshot, urlAsin);
}

export function studioSnapshotMatchesAsin(snapshot: ProductSnapshot, asin: string | undefined): boolean {
  if (!asin) return true;
  const expected = asin.toUpperCase();
  const identities = [snapshot.asin, snapshot.requestedAsin, snapshot.resolvedAsin, ...(snapshot.asinAliases || [])]
    .map((value) => String(value || "").toUpperCase())
    .filter((value) => /^[A-Z0-9]{10}$/.test(value));
  return identities.includes(expected);
}

export function cacheAgeMs(cache: StudioProductCache, now = Date.now()): number {
  const cachedAt = Date.parse(cache.cachedAt);
  return Number.isFinite(cachedAt) ? Math.max(0, now - cachedAt) : Number.POSITIVE_INFINITY;
}

export function isFreshStudioProductCache(
  cache: StudioProductCache | undefined,
  now = Date.now(),
  ttlMs = STUDIO_PRODUCT_CACHE_TTL_MS
): cache is StudioProductCache {
  return Boolean(cache && isUsableStudioProductSnapshot(cache.snapshot) && cacheAgeMs(cache, now) <= ttlMs);
}
