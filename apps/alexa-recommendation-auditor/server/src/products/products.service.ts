import { BadRequestException, Inject, Injectable } from "@nestjs/common";
import { randomUUID } from "node:crypto";
import { SCHEMA_VERSION, type EvidenceFact, type IntentProfile, type ProductSnapshot } from "@alexa-auditor/contracts";
import { PrismaService } from "../prisma.service";
import { DeepSeekService } from "../deepseek/deepseek.service";
import { parseJson } from "../common/json";

function emptyProfile(snapshot: Pick<ProductSnapshot, "title" | "brand">): IntentProfile {
  const title = snapshot.title.toLowerCase();
  const productType = title.includes("flip flop") ? ["flip_flops"] : title.includes("shoe") ? ["shoes"] : ["unknown_product"];
  const audience = title.includes("women") ? ["women"] : title.includes("men") ? ["men"] : [];
  return {
    primary_domain: "clothing_shoes_jewelry",
    secondary_domain: [], product_type: productType, audience_intent: audience,
    function_intent: [], capability_intent: [], event_intent: [], location_intent: [], body_need_intent: [], time_intent: [], substitute_intent: [], complement_intent: [],
    latent_task: `用户正在寻找符合页面明示属性的${productType[0]}。`, intent_stage: "consideration", evidence_type: ["explicit"], confidence_level: "low",
    intent_cluster: `${audience[0] || "general"}_${productType[0]}`, routing_action: "ambiguity_review"
  };
}

@Injectable()
export class ProductsService {
  constructor(
    @Inject(PrismaService) private readonly prisma: PrismaService,
    @Inject(DeepSeekService) private readonly deepseek: DeepSeekService
  ) {}

  async create(input: Partial<ProductSnapshot>): Promise<ProductSnapshot> {
    const requestedAsin = validAsin(input.requestedAsin) || validAsin(input.asin);
    const resolvedAsin = validAsin(input.resolvedAsin) || validAsin(input.asin) || requestedAsin;
    const asinAliases = [...new Set([requestedAsin, resolvedAsin, ...(Array.isArray(input.asinAliases) ? input.asinAliases.map(validAsin) : [])].filter(Boolean))];
    const asin = resolvedAsin || requestedAsin;
    const title = String(input.title || "").trim();
    if (!/^B0[A-Z0-9]{8}$/.test(asin) && !/^[A-Z0-9]{10}$/.test(asin)) throw new BadRequestException("无法从当前页面确认有效ASIN");
    if (!title) throw new BadRequestException("当前页面未读取到商品标题");
    const capturedAt = input.capturedAt || new Date().toISOString();
    const snapshot: ProductSnapshot = {
      asin,
      requestedAsin,
      resolvedAsin,
      asinAliases,
      url: String(input.url || ""),
      marketplace: String(input.marketplace || "amazon.com"),
      title,
      brand: String(input.brand || "").trim(),
      breadcrumb: Array.isArray(input.breadcrumb) ? input.breadcrumb.map(String).slice(0, 20) : [],
      bullets: Array.isArray(input.bullets) ? input.bullets.map(String).slice(0, 20) : [],
      specifications: input.specifications && typeof input.specifications === "object" ? input.specifications as Record<string, string> : {},
      aPlusText: String(input.aPlusText || "").slice(0, 12000),
      reviewSummary: String(input.reviewSummary || "").slice(0, 4000),
      qaText: String(input.qaText || "").slice(0, 4000),
      stableFacts: sanitizeFacts(input.stableFacts, capturedAt, false),
      volatileFacts: sanitizeFacts(input.volatileFacts, capturedAt, true),
      intentProfile: input.intentProfile || emptyProfile({ title, brand: String(input.brand || "") }),
      accountLabel: String(input.accountLabel || "dedicated_test_account").slice(0, 80),
      selectorVersion: String(input.selectorVersion || "amazon-us-v1"),
      schemaVersion: SCHEMA_VERSION,
      capturedAt
    };
    snapshot.intentProfile = await this.deepseek.refineIntentProfile(snapshot, {
      requestId: randomUUID(),
      productAsin: resolvedAsin || asin,
      schemaVersion: SCHEMA_VERSION
    });
    const record = await this.prisma.productSnapshot.create({
      data: {
        asin,
        requestedAsin: requestedAsin || null,
        resolvedAsin: resolvedAsin || null,
        asinAliasesJson: JSON.stringify(asinAliases),
        title,
        brand: snapshot.brand,
        accountLabel: snapshot.accountLabel,
        selectorVersion: snapshot.selectorVersion,
        schemaVersion: snapshot.schemaVersion,
        snapshotJson: JSON.stringify(snapshot),
        capturedAt: new Date(capturedAt)
      }
    });
    return { ...snapshot, id: record.id };
  }

  async get(id: string): Promise<ProductSnapshot | null> {
    const record = await this.prisma.productSnapshot.findUnique({ where: { id } });
    return record ? { ...parseJson<ProductSnapshot>(record.snapshotJson, {} as ProductSnapshot), id: record.id } : null;
  }
}

function validAsin(value: unknown): string {
  const asin = String(value || "").trim().toUpperCase();
  return /^[A-Z0-9]{10}$/.test(asin) ? asin : "";
}

function sanitizeFacts(input: unknown, capturedAt: string, volatile: boolean): EvidenceFact[] {
  if (!Array.isArray(input)) return [];
  const allowedSections = new Set(volatile ? ["retail"] : ["title", "brand", "breadcrumb", "bullets", "specification", "a_plus", "review_summary", "qa"]);
  return input.flatMap((raw, index) => {
    if (!raw || typeof raw !== "object") return [];
    const fact = raw as Partial<EvidenceFact>;
    if (!allowedSections.has(String(fact.sourceSection))) return [];
    const sourceText = String(fact.sourceText || "").replace(/\s+/g, " ").trim().slice(0, 1000);
    if (!sourceText) return [];
    return [{
      id: String(fact.id || `${volatile ? "volatile" : "stable"}_${index}`), field: String(fact.field || "unknown"), value: Array.isArray(fact.value) ? fact.value.map(String) : String(fact.value || ""),
      evidenceType: fact.evidenceType === "inferred" ? "inferred" : fact.evidenceType === "explicit" ? "explicit" : "page_validated",
      sourceSection: fact.sourceSection as EvidenceFact["sourceSection"], sourceText,
      confidence: fact.confidence === "low" ? "low" : fact.confidence === "medium" ? "medium" : "high", capturedAt
    }];
  });
}
