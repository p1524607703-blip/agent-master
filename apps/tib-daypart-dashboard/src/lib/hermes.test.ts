import { afterEach, describe, expect, it, vi } from "vitest";
import type { CampaignRow } from "@/types";
import {
  checkHermes,
  isHermesReviewV1,
  reviewWithHermes,
} from "./hermes";

const validReview = {
  campaignId: "1001",
  finalQuadrant: "lowTibHighRoas",
  candidateLevel: "正式候选",
  actionEligible: true,
  reasons: ["样本充分"],
  referenceCampaignIds: ["1002"],
  risks: ["可能内部迁移"],
  nextAnalysis: ["观察同日承接"],
  reviewedAt: "2026-08-04T00:00:00.000Z",
} as const;

const campaign = {
  campaignId: "1001",
  campaignName: "DD1-S81-test",
  productLine: "DD1-S81",
  adType: "Sponsored Products",
  tib: 0.5,
  tibBand: "low",
  roas: 5,
  cpc: 1.26,
  cvr: 0.12,
  clicks: 100,
  purchases: 12,
  spend: 126,
  activeDays: 7,
  purchaseDays: 5,
  maxDailyOrderConcentration: 0.3,
  matureFactShare: 1,
  targetRoas: 4,
  rawQuadrant: "lowTibHighRoas",
  candidateLevel: "正式候选",
  gates: [],
  medianLastActiveHour: 10,
  lastActiveDistribution: { "10": 4 },
  sameDayHandoffDays: 3,
  actionEligible: true,
} as unknown as CampaignRow;

const evidence = {
  campaign,
  productLine: {
    productLine: "DD1-S81",
    campaignIds: ["1001", "1002"],
    impressions: 1000,
    clicks: 100,
    spend: 126,
    purchases: 12,
    adSales: 630,
    roas: 5,
    acos: 0.2,
    cpc: 1.26,
    cvr: 0.12,
    weightedTib: 0.5,
    calendarDays: 14,
    matureDays: 14,
    activeDays: 7,
    clickDays: 7,
    purchaseDays: 5,
    maxDailyOrderConcentration: 0.3,
    matureFactShare: 1,
  },
  viewMode: "decision" as const,
  window: { start: "2026-07-14", end: "2026-07-27" },
};

afterEach(() => vi.unstubAllGlobals());

describe("Hermes governance", () => {
  it("validates HermesReviewV1", () => {
    expect(isHermesReviewV1(validReview)).toBe(true);
    expect(isHermesReviewV1({ ...validReview, reasons: "bad" })).toBe(false);
  });

  it("returns a validated review through the same-origin Hermes path", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response("ok", { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            model: "deepseek-v4-pro",
            choices: [{ message: { content: JSON.stringify(validReview) } }],
            usage: { total_tokens: 123 },
          }),
          {
            status: 200,
            headers: { "X-Hermes-Session-Id": "session-1" },
          },
        ),
      );
    vi.stubGlobal("fetch", fetchMock);
    const result = await reviewWithHermes(evidence);
    expect(result.status).toBe("success");
    expect(result.hermesSessionId).toBe("session-1");
    expect(result.review?.campaignId).toBe("1001");
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/hermes/v1/chat/completions",
    );
  });

  it("keeps deterministic rules when Hermes returns 402", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response("ok", { status: 200 }))
        .mockResolvedValueOnce(new Response("quota", { status: 402 })),
    );
    const result = await reviewWithHermes(evidence);
    expect(result.status).toBe("error");
    expect(result.errorCode).toBe("HTTP_402");
    expect(result.review).toBeUndefined();
  });

  it("fails closed after two non-JSON responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response("ok", { status: 200 }))
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ choices: [{ message: { content: "not json" } }] }),
            { status: 200 },
          ),
        )
        .mockResolvedValueOnce(
          new Response(
            JSON.stringify({ choices: [{ message: { content: "still bad" } }] }),
            { status: 200 },
          ),
        ),
    );
    const result = await reviewWithHermes(evidence);
    expect(result.status).toBe("error");
    expect(result.errorCode).toBe("SCHEMA_INVALID");
    expect(result.review).toBeUndefined();
  });

  it("reports an unavailable health endpoint without fabricating output", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    await expect(checkHermes()).resolves.toEqual({
      ok: false,
      message: "offline",
    });
  });
});
