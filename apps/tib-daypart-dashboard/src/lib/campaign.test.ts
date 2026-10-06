import { describe, expect, it } from "vitest";
import { parseCampaignName } from "./campaign";

describe("parseCampaignName", () => {
  it.each([
    ["DD1- S81-手动广泛", "DD1", "S81", "DD1-S81"],
    ["DD1－S81－手动广泛", "DD1", "S81", "DD1-S81"],
    ["YS1-S881 视频推荐词精准", "YS1", "S881", "YS1-S881"],
    ["XM2 - S75 - 手动wide广泛", "XM2", "S75", "XM2-S75"],
    ["XH1 W8K21-提高和降低-词", "XH1", "W8K21", "XH1-W8K21"],
    ["LB1-W87男 自动", "LB1", "W87", "LB1-W87"],
  ])("normalizes %s", (name, operator, product, productLine) => {
    const result = parseCampaignName(name);
    expect(result).toMatchObject({
      operator,
      product,
      productLine,
      recognized: true,
    });
  });

  it("routes malformed names into the exception group", () => {
    expect(parseCampaignName("品牌词广告").recognized).toBe(false);
    expect(parseCampaignName("品牌词广告").productLine).toBe("未识别");
  });
});
