import type { CampaignIdentity } from "@/types";
import { canonicalText } from "./parse";

export interface ParsedCampaignName {
  canonicalName: string;
  operator: string;
  product: string;
  productLine: string;
  recognized: boolean;
}

export function parseCampaignName(name: string): ParsedCampaignName {
  const canonicalName = canonicalText(name);
  const match = canonicalName.match(
    /^([A-Za-z]{1,8}\d+)(?:-|\s)+([A-Za-z]+\d+[A-Za-z0-9]*)/,
  );
  if (!match) {
    return {
      canonicalName,
      operator: "未识别",
      product: "未识别",
      productLine: "未识别",
      recognized: false,
    };
  }
  const operator = (match[1] ?? "").toUpperCase();
  const product = (match[2] ?? "").toUpperCase();
  return {
    canonicalName,
    operator,
    product,
    productLine: `${operator}-${product}`,
    recognized: true,
  };
}

export function campaignKey(
  identity: Pick<CampaignIdentity, "campaignId" | "canonicalName">,
): string {
  return identity.campaignId || identity.canonicalName.toLowerCase();
}
