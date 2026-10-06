import { describe, expect, it } from "vitest";
import {
  decisionWindow,
  maturityStatus,
  observationWindow,
  parseFlexibleDate,
} from "./dates";

const now = new Date("2026-08-04T18:00:00Z");
const timezone = "America/Los_Angeles";

describe("date contracts", () => {
  it("parses Chinese, ISO and slash dates", () => {
    expect(parseFlexibleDate("2026年7月22日")).toBe("2026-07-22");
    expect(parseFlexibleDate("2026-7-22")).toBe("2026-07-22");
    expect(parseFlexibleDate("2026/07/22")).toBe("2026-07-22");
  });

  it("locks Seller SP on D-8 and 14-day products on D-15", () => {
    expect(maturityStatus("2026-07-27", "SP", timezone, now)).toBe("mature");
    expect(maturityStatus("2026-07-28", "SP", timezone, now)).toBe(
      "backfilling",
    );
    expect(maturityStatus("2026-07-20", "SB", timezone, now)).toBe("mature");
    expect(maturityStatus("2026-07-21", "SD", timezone, now)).toBe(
      "backfilling",
    );
    expect(maturityStatus("2026-08-03", "SP", timezone, now)).toBe(
      "processing",
    );
  });

  it("builds the two fixed 14-day windows", () => {
    expect(observationWindow(timezone, now)).toMatchObject({
      start: "2026-07-20",
      end: "2026-08-02",
    });
    expect(decisionWindow("SP", timezone, now)).toMatchObject({
      start: "2026-07-14",
      end: "2026-07-27",
    });
    expect(decisionWindow("SB", timezone, now)).toMatchObject({
      start: "2026-07-07",
      end: "2026-07-20",
    });
  });
});
