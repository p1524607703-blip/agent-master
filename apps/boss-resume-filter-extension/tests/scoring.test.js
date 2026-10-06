const assert = require("node:assert/strict");
const scoring = require("../src/scoring");

const baseCriteria = {
  enabled: true,
  threshold: 70,
  jobDirection: "鞋类供应链开发",
  minYears: 5,
  education: "大专",
  ageRangeNote: "35-40岁"
};

{
  const result = scoring.evaluateCandidate(
    "候选人 大专 8年鞋类供应链开发经验，熟悉鞋厂开发、供应商开发、面辅料跟进和订单交付。",
    baseCriteria
  );
  assert.equal(result.level, "match");
  assert.ok(result.score >= 70);
  assert.equal(result.extracted.years, 8);
  assert.equal(result.extracted.education, "大专");
  assert.ok(result.flags.some((flag) => flag.includes("未参与评分")));
}

{
  const result = scoring.evaluateCandidate(
    "候选人 本科 3年鞋类供应链开发经验，做过供应商沟通和跟单。",
    baseCriteria
  );
  assert.notEqual(result.level, "match");
  assert.ok(result.reasons.some((reason) => reason.includes("低于要求")));
}

{
  const result = scoring.evaluateCandidate(
    "候选人 大专 7年服装采购经验，熟悉面料供应商和订单跟进。",
    baseCriteria
  );
  assert.notEqual(result.level, "match");
  assert.ok(result.score < baseCriteria.threshold);
  assert.ok(result.reasons.some((reason) => reason.includes("职位方向未匹配")));
}

{
  const warnings = scoring.hasSensitiveCriteria({
    mustKeywords: ["女性", "30岁以下"],
    niceKeywords: [],
    excludeKeywords: []
  });
  assert.ok(warnings.includes("女性"));
  assert.ok(warnings.includes("岁以下"));
}

console.log("scoring tests passed");
