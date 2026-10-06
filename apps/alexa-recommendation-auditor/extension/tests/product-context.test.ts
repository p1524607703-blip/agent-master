import { SCHEMA_VERSION, type ProductSnapshot } from "@alexa-auditor/contracts";
import { describe, expect, it } from "vitest";
import {
  AMAZON_MARKETPLACE_HOSTS,
  asinFromAmazonPdpUrl,
  isFreshStudioProductCache,
  isUsableStudioProductSnapshot,
  sanitizeProductSnapshotForStudio,
  selectAmazonProductTabByUrl,
  selectPreferredAmazonProductTab,
  studioSnapshotMatchesAsin,
  STUDIO_PRODUCT_CACHE_TTL_MS
} from "../src/studio/product-context";

function product(overrides: Partial<ProductSnapshot> = {}): ProductSnapshot {
  const capturedAt = "2026-07-19T12:00:00.000Z";
  return {
    asin: "B0GKDNPHJM",
    requestedAsin: "B0GKDNPHJM",
    resolvedAsin: "B0GKDNPHJM",
    asinAliases: ["B0GKDNPHJM"],
    url: "https://www.amazon.com/dp/B0GKDNPHJM/ref=tracking?th=1",
    marketplace: "www.amazon.com",
    title: "Joomra Women's Arch Support Flip Flops",
    brand: "Joomra",
    breadcrumb: ["Women", "Shoes", "Flip-Flops"],
    bullets: ["Lightweight EVA", "Arch support"],
    specifications: {
      Material: "EVA",
      "Customer Reviews": "4.3 out of 5 stars",
      Delivery: "Tomorrow",
      Notes: "Rufus customer question history"
    },
    aPlusText: "One-piece EVA construction",
    reviewSummary: "Customers say this is comfortable",
    qaText: "Can it be used at the beach?",
    stableFacts: [
      { id: "title_0", field: "product_type", value: "flip_flops", evidenceType: "explicit", sourceSection: "title", sourceText: "Joomra flip flops", confidence: "high", capturedAt },
      { id: "spec_0", field: "material", value: "eva", evidenceType: "page_validated", sourceSection: "specification", sourceText: "Material: EVA", confidence: "high", capturedAt },
      { id: "review_0", field: "comfort", value: "comfortable", evidenceType: "page_validated", sourceSection: "review_summary", sourceText: "Customers say comfortable", confidence: "high", capturedAt },
      { id: "rufus_0", field: "chat", value: "history", evidenceType: "page_validated", sourceSection: "bullets", sourceText: "Rufus customer question", confidence: "high", capturedAt }
    ],
    volatileFacts: [
      { id: "retail_0", field: "price", value: "$9.96", evidenceType: "page_validated", sourceSection: "retail", sourceText: "$9.96", confidence: "medium", capturedAt }
    ],
    intentProfile: {
      primary_domain: "clothing_shoes_jewelry",
      secondary_domain: [],
      product_type: ["flip_flops"],
      audience_intent: ["women"],
      function_intent: ["arch_support"],
      capability_intent: ["eva"],
      event_intent: [],
      location_intent: [],
      body_need_intent: [],
      time_intent: [],
      substitute_intent: [],
      complement_intent: [],
      latent_task: "Find women's flip flops",
      intent_stage: "consideration",
      evidence_type: ["explicit"],
      confidence_level: "medium",
      intent_cluster: "women_flip_flops",
      routing_action: "cluster_route"
    },
    accountLabel: "dedicated_test_account",
    selectorVersion: "test",
    schemaVersion: SCHEMA_VERSION,
    capturedAt,
    ...overrides
  };
}

describe("studio Amazon product context", () => {
  it("recognizes PDP URLs on all six supported marketplaces and rejects home/search pages", () => {
    for (const host of AMAZON_MARKETPLACE_HOSTS) {
      expect(asinFromAmazonPdpUrl(`https://www.${host}/dp/B0GKDNPHJM?th=1`)).toBe("B0GKDNPHJM");
      expect(asinFromAmazonPdpUrl(`https://www.${host}/gp/product/B0GKDNPHJM`)).toBe("B0GKDNPHJM");
    }
    expect(asinFromAmazonPdpUrl("https://www.amazon.com/")).toBe("");
    expect(asinFromAmazonPdpUrl("https://www.amazon.com/s?k=flip+flops")).toBe("");
    expect(asinFromAmazonPdpUrl("https://example.com/dp/B0GKDNPHJM")).toBe("");
  });

  it("prefers the current active PDP over a more recently accessed background PDP", () => {
    const active = { id: 7, url: "https://www.amazon.de/dp/B0AAA11111", active: true, windowId: 1, lastAccessed: 10 };
    const recent = { id: 8, url: "https://www.amazon.fr/dp/B0BBB22222", active: false, windowId: 1, lastAccessed: 100 };
    expect(selectPreferredAmazonProductTab(active, [active, recent]).id).toBe(7);
  });

  it("uses the latest PDP when the studio is active and never falls back to an Amazon home page", () => {
    const studio = { id: 1, url: "http://localhost:5173/", active: true, windowId: 1, lastAccessed: 100 };
    const home = { id: 2, url: "https://www.amazon.com/", active: false, windowId: 1, lastAccessed: 99 };
    const olderPdp = { id: 3, url: "https://www.amazon.it/dp/B0AAA11111", active: false, windowId: 1, lastAccessed: 80 };
    const newerPdp = { id: 4, url: "https://www.amazon.es/dp/B0BBB22222", active: false, windowId: 1, lastAccessed: 90 };
    expect(selectPreferredAmazonProductTab(studio, [home, olderPdp, newerPdp], 1).id).toBe(4);
    expect(() => selectPreferredAmazonProductTab(studio, [home], 1)).toThrow(/商品详情页/);
  });

  it("prefers the latest PDP in the request sender window before a newer global PDP", () => {
    const studio = { id: 1, url: "http://localhost:5173/", active: true, windowId: 1, lastAccessed: 100 };
    const senderWindowPdp = { id: 3, url: "https://www.amazon.it/dp/B0AAA11111", active: false, windowId: 1, lastAccessed: 80 };
    const globallyNewerPdp = { id: 4, url: "https://www.amazon.es/dp/B0BBB22222", active: false, windowId: 2, lastAccessed: 90 };

    expect(selectPreferredAmazonProductTab(studio, [senderWindowPdp, globallyNewerPdp], 1).id).toBe(3);
    expect(selectPreferredAmazonProductTab(studio, [senderWindowPdp, globallyNewerPdp], 99).id).toBe(4);
  });

  it("selects an already-open PDP only when marketplace and ASIN match the pasted link", () => {
    const wrongAsin = { id: 2, url: "https://www.amazon.com/dp/B0AAA11111", active: false, windowId: 1, lastAccessed: 99 };
    const wrongMarketplace = { id: 3, url: "https://www.amazon.de/dp/B0GKDNPHJM", active: false, windowId: 1, lastAccessed: 100 };
    const target = { id: 4, url: "https://www.amazon.com/Joomra/dp/B0GKDNPHJM?th=1", active: false, windowId: 1, lastAccessed: 80 };
    const otherWindowTarget = { id: 5, url: "https://www.amazon.com/dp/B0GKDNPHJM", active: false, windowId: 2, lastAccessed: 90 };

    expect(selectAmazonProductTabByUrl(
      "https://www.amazon.com/dp/B0GKDNPHJM",
      [wrongAsin, wrongMarketplace, target, otherWindowTarget],
      1
    ).id).toBe(4);
    expect(() => selectAmazonProductTabByUrl(
      "https://www.amazon.com/dp/B0BBB22222",
      [wrongAsin, target]
    )).toThrow(/目标商品页/);
  });

  it("allows only product planning evidence and strips retail, reviews, Q&A, chat, account and tracking data", () => {
    const source = product();
    source.stableFacts.push({
      id: "value_0",
      field: "detail",
      value: "Rufus price $9.96",
      evidenceType: "page_validated",
      sourceSection: "bullets",
      sourceText: "Product detail",
      confidence: "high",
      capturedAt: source.capturedAt
    });
    source.intentProfile.latent_task = "Rufus customer question history";
    const sanitized = sanitizeProductSnapshotForStudio(source);
    expect(sanitized.url).toBe("https://www.amazon.com/dp/B0GKDNPHJM");
    expect(sanitized.specifications).toEqual({ Material: "EVA" });
    expect(sanitized.stableFacts.map((fact) => fact.id)).toEqual(["title_0", "spec_0"]);
    expect(sanitized.volatileFacts).toEqual([]);
    expect(sanitized.reviewSummary).toBe("");
    expect(sanitized.qaText).toBe("");
    expect(sanitized.accountLabel).toBe("");
    expect(sanitized.intentProfile.latent_task).toBe("");
    expect(sanitized.intentProfile.product_type).toEqual([]);
    expect(JSON.stringify(sanitized)).not.toMatch(/\$9\.96|Tomorrow|Rufus|customer question|dedicated_test_account/);
  });

  it("rejects a snapshot whose source URL ASIN is outside its identity aliases", () => {
    const mismatched = sanitizeProductSnapshotForStudio(product({
      url: "https://www.amazon.com/dp/B0AAA11111?th=1"
    }));

    expect(mismatched.url).toBe("");
    expect(isUsableStudioProductSnapshot(mismatched)).toBe(false);
  });

  it("accepts an explicitly timestamped cache only within the bounded TTL", () => {
    const now = Date.parse("2026-07-19T12:15:00.000Z");
    expect(isFreshStudioProductCache({ snapshot: product(), cachedAt: new Date(now - STUDIO_PRODUCT_CACHE_TTL_MS + 1).toISOString() }, now)).toBe(true);
    expect(isFreshStudioProductCache({ snapshot: product(), cachedAt: new Date(now - STUDIO_PRODUCT_CACHE_TTL_MS - 1).toISOString() }, now)).toBe(false);
    expect(isFreshStudioProductCache({ snapshot: product(), cachedAt: "invalid" }, now)).toBe(false);
  });

  it("allows a fresh cache without a live candidate but rejects a different candidate ASIN", () => {
    const cached = product({ asinAliases: ["B0GKDNPHJM", "B0GKDW7BDW"] });

    expect(studioSnapshotMatchesAsin(cached, undefined)).toBe(true);
    expect(studioSnapshotMatchesAsin(cached, "B0GKDNPHJM")).toBe(true);
    expect(studioSnapshotMatchesAsin(cached, "B0GKDW7BDW")).toBe(true);
    expect(studioSnapshotMatchesAsin(cached, "B0DIFFERENT")).toBe(false);
  });
});
