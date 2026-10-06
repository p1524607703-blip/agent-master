import { describe, expect, it } from "vitest";
import { cleanCell, parseNumber, parsePercent, parseTib } from "./parse";

describe("CSV cleaning", () => {
  it("unwraps Excel text identifiers", () => {
    expect(cleanCell('="68847927758065"')).toBe("68847927758065");
  });

  it("parses currency, comma and percentages", () => {
    expect(parseNumber("US$1,234.56")).toBeCloseTo(1234.56);
    expect(parsePercent("12.5%")).toBeCloseTo(0.125);
    expect(parseTib("100")).toBe(1);
    expect(parseTib("72.5%")).toBeCloseTo(0.725);
  });
});
