import fs from "node:fs";
import Papa from "papaparse";
import { describe, expect, it } from "vitest";
import { importAdRows, importTibRows, mergeHourlyFacts } from "./importer";
import type { CsvRow } from "./parse";

describe("report import", () => {
  it("aggregates duplicate campaign-hour rows and joins normalized names", () => {
    const ad = importAdRows([
      {
        日期: "2026年7月22日",
        "广告主账户 ID": '="account-1"',
        小时: "8",
        广告活动编号: '="123"',
        广告活动名称: "DD1- S81-手动广泛",
        广告产品: "Sponsored Products",
        预算货币: "USD",
        展示量: "100",
        点击量: "10",
        总成本: "5",
        购买量: "1",
        销售额: "20",
      },
      {
        日期: "2026/07/22",
        "广告主账户 ID": '="account-1"',
        小时: "8",
        广告活动编号: '="123"',
        广告活动名称: "DD1- S81-手动广泛",
        广告产品: "Sponsored Products",
        预算货币: "USD",
        展示量: "50",
        点击量: "5",
        总成本: "2",
        购买量: "1",
        销售额: "10",
      },
    ]);
    const tib = importTibRows([
      {
        广告活动名称: "DD1－S81－手动广泛",
        平均预算内活跃时间: "75",
        广告活动预算金额: "US$35.00",
      },
    ]);
    expect(ad.hourly).toHaveLength(1);
    expect(ad.hourly[0]).toMatchObject({
      campaignId: "123",
      productLine: "DD1-S81",
      date: "2026-07-22",
      advertiserAccountId: "account-1",
      impressions: 150,
      clicks: 15,
      spend: 7,
      purchases: 2,
      adSales: 30,
    });
    expect(tib.byName.get("dd1-s81-手动广泛")?.tib).toBeCloseTo(0.75);
    expect(ad.period).toMatchObject({
      start: "2026-07-22",
      end: "2026-07-22",
      source: "dateColumn",
    });
    expect(tib.period.source).toBe("none");
  });

  it("parses the current Chuanpeng report schema when the files are available", () => {
    const base =
      "/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号";
    const adPath = `${base}/小时级广告活动7.22-8.2.csv`;
    const tibPath = `${base}/川鹏TIB分析全量30天.csv`;
    if (!fs.existsSync(adPath) || !fs.existsSync(tibPath)) return;
    const parse = (path: string) =>
      Papa.parse<CsvRow>(fs.readFileSync(path, "utf8"), {
        header: true,
        skipEmptyLines: "greedy",
        transformHeader: (value) => value.replace(/^\uFEFF/, "").trim(),
      }).data;
    const ad = importAdRows(parse(adPath));
    const tib = importTibRows(parse(tibPath));
    expect(ad.rows).toBeGreaterThan(10_000);
    expect(ad.hourly.length).toBeGreaterThan(100_000);
    expect(ad.identities.size).toBeGreaterThan(100);
    expect(ad.rejected).toBe(0);
    expect(tib.rows).toBeGreaterThan(200);
    expect(tib.byName.size).toBeGreaterThan(200);
    expect(ad.period.start).toBe("2026-07-22");
    expect(ad.period.end).toBe("2026-08-02");
    expect(tib.period.source).toBe("none");
    const selected = ad.hourly.filter(
      (row) =>
        row.campaignName === "DD1- S81-手动广泛whitin shoes for men",
    );
    const totals = selected.reduce(
      (sum, row) => {
        sum.clicks += row.clicks;
        sum.spend += row.spend;
        sum.purchases += row.purchases;
        sum.sales += row.adSales;
        return sum;
      },
      { clicks: 0, spend: 0, purchases: 0, sales: 0 },
    );
    expect(totals.clicks).toBe(2893);
    expect(totals.purchases).toBe(407);
    expect(totals.spend).toBeCloseTo(3658.51, 2);
    expect(totals.sales).toBeCloseTo(16649.79, 2);
    expect(totals.spend / totals.clicks).toBeCloseTo(1.2646, 4);
  }, 20_000);

  it("rejects hourly data without an explicit date field", () => {
    expect(() =>
      importAdRows([
        {
          小时: "8",
          广告活动编号: "1",
          广告活动名称: "DD1-S81-test",
        },
      ]),
    ).toThrow(/不会从文件名推断日期/);
  });

  it("overwrites backfilling facts but locks mature conflicts", () => {
    const backfill = importAdRows(
      [
        {
          日期: "2026-07-30",
          小时: "8",
          广告活动编号: "1",
          广告活动名称: "DD1-S81-test",
          广告产品: "Sponsored Products",
          点击量: "30",
          总成本: "10",
          购买量: "12",
          销售额: "50",
        },
      ],
      "America/Los_Angeles",
      "2026-08-01T00:00:00.000Z",
    ).hourly[0]!;
    const incoming = { ...backfill, purchases: 15, adSales: 65 };
    const updated = mergeHourlyFacts(
      [backfill],
      [incoming],
      "America/Los_Angeles",
      "2026-08-02T00:00:00.000Z",
    );
    expect(updated.updated).toBe(1);
    expect(updated.changes[0]).toMatchObject({
      previousPurchases: 12,
      incomingPurchases: 15,
    });
    expect(updated.facts[0]?.purchases).toBe(15);

    const mature = {
      ...backfill,
      date: "2026-07-22",
      uniqueKey: backfill.uniqueKey.replace("2026-07-30", "2026-07-22"),
      maturityStatus: "mature" as const,
      lockedAt: "2026-08-01T00:00:00.000Z",
    };
    const conflict = mergeHourlyFacts(
      [mature],
      [{ ...mature, purchases: 17, adSales: 75 }],
      "America/Los_Angeles",
      "2026-08-04T00:00:00.000Z",
    );
    expect(conflict.lockedSkipped).toBe(1);
    expect(conflict.conflicts).toHaveLength(1);
    expect(conflict.facts[0]?.purchases).toBe(12);
  });
});
