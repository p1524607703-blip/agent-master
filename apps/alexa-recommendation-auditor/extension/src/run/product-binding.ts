import type { ProductSnapshot } from "@alexa-auditor/contracts";

function aliases(product: Pick<ProductSnapshot, "asin" | "requestedAsin" | "resolvedAsin" | "asinAliases">): Set<string> {
  return new Set([product.asin, product.requestedAsin, product.resolvedAsin, ...(product.asinAliases || [])]
    .map((value) => String(value || "").trim().toUpperCase())
    .filter(Boolean));
}

export function sameProductFamily(
  baseline: Pick<ProductSnapshot, "asin" | "requestedAsin" | "resolvedAsin" | "asinAliases">,
  current: Pick<ProductSnapshot, "asin" | "requestedAsin" | "resolvedAsin" | "asinAliases">
): boolean {
  const baselineAliases = aliases(baseline);
  return [...aliases(current)].some((asin) => baselineAliases.has(asin));
}
