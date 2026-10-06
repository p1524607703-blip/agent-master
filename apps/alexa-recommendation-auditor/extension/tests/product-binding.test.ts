import { describe, expect, it } from "vitest";
import { sameProductFamily } from "../src/run/product-binding";

describe("run product binding", () => {
  it("accepts parent/selected-child aliases of the same product family", () => {
    const baseline = { asin: "B0CHILD001", requestedAsin: "B0PARENT01", resolvedAsin: "B0CHILD001", asinAliases: ["B0PARENT01", "B0CHILD001"] };
    const current = { asin: "B0PARENT01", requestedAsin: "B0PARENT01", resolvedAsin: "B0PARENT01", asinAliases: ["B0PARENT01"] };
    expect(sameProductFamily(baseline, current)).toBe(true);
  });

  it("rejects a different product before Alexa execution", () => {
    expect(sameProductFamily({ asin: "B0PRODUCTA" }, { asin: "B0PRODUCTB" })).toBe(false);
  });
});
