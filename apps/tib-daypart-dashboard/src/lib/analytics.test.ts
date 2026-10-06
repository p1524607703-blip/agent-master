import { describe, expect, it } from "vitest";
import {
  hourlySummary,
  mergeTimeWindows,
  rowsForView,
  summarizeRows,
} from "./analytics";
import type { HourMetric, Thresholds } from "@/types";

const thresholds: Thresholds = {
  minClicks: 30,
  minPurchases: 3,
  minActiveDays: 5,
  efficiencyDelta: 0.1,
};

function row(
  hour: number,
  spend: number,
  sales: number,
  clicks = 40,
  purchases = 4,
): HourMetric {
  return {
    hour,
    campaignId: "1",
    campaignName: "DD1-S81-test",
    operator: "DD1",
    product: "S81",
    productLine: "DD1-S81",
    adType: "SP",
    currency: "USD",
    impressions: 1000,
    viewableImpressions: 0,
    clicks,
    spend,
    purchases,
    adSales: sales,
    sourceRows: 1,
  };
}

describe("analytics", () => {
  it("uses ratio-of-sums formulas", () => {
    const summary = summarizeRows([row(1, 10, 40), row(2, 20, 20)]);
    expect(summary.roas).toBeCloseTo(2);
    expect(summary.acos).toBeCloseTo(0.5);
    expect(summary.cpc).toBeCloseTo(30 / 80);
    expect(summary.cvr).toBeCloseTo(8 / 80);
  });

  it("marks zero-spend ROAS as not calculable", () => {
    expect(summarizeRows([row(1, 0, 0)]).roas).toBeNull();
  });

  it("keeps processing spend visible but excludes it from ROAS", () => {
    const mature = {
      ...row(1, 10, 20),
      maturityStatus: "mature" as const,
    };
    const processing = {
      ...row(2, 100, 1_000),
      maturityStatus: "processing" as const,
    };
    const summary = summarizeRows(
      rowsForView([mature, processing], "observation"),
    );
    expect(summary.spend).toBe(110);
    expect(summary.adSales).toBe(20);
    expect(summary.roas).toBeCloseTo(2);
  });

  it("classifies efficient, inefficient and insufficient hours", () => {
    const result = hourlySummary(
      [row(8, 10, 60), row(9, 10, 10), row(10, 10, 30, 2, 0)],
      thresholds,
      false,
    );
    expect(result[8]?.classification).toBe("efficient");
    expect(result[9]?.classification).toBe("inefficient");
    expect(result[10]?.classification).toBe("insufficient");
  });

  it("merges adjacent classes and keeps isolated hours", () => {
    const result = hourlySummary(
      [row(8, 10, 60), row(9, 10, 60), row(10, 10, 10)],
      thresholds,
      false,
    );
    const windows = mergeTimeWindows(result);
    const efficient = windows.find(
      (window) => window.classification === "efficient",
    );
    expect(efficient).toMatchObject({ start: 8, end: 9, isolated: false });
  });
});
