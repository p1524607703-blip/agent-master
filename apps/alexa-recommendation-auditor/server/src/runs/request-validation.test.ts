import { BadRequestException } from "@nestjs/common";
import { describe, expect, it } from "vitest";
import {
  validateApproveQuestionPlanRequest,
  validateCreateRunRequest,
  validateUpdatePromptCaseRequest
} from "./request-validation";

const validCreateRequest = () => ({
  productSnapshotId: "snapshot-1",
  accountLabel: "development-account",
  preset: "smoke",
  promptLanguage: "en-US",
  sessionPolicy: "fresh",
  promptCount: 3,
  repetitions: 1,
  runSeed: "stable-seed"
});

const validUpdateRequest = () => ({
  expectedRevision: 1,
  changeReason: "Align the question with the approved footwear evidence.",
  enabled: true,
  scoreEligible: true,
  promptText: "Recommend five women's walking shoes with arch support.",
  hypothesis: "The product should be eligible for an arch-support footwear query.",
  testRole: "positive_control",
  expectedMatch: "eligible",
  evidenceFactIds: ["fact-arch-support"],
  requiredTerms: ["walking shoes", "arch support"],
  judgmentCriteria: ["The tested ASIN appears in the top five recommendations."],
  sessionPolicy: "fresh",
  sessionGroup: null
});

function expectBadRequest(action: () => void) {
  expect(action).toThrow(BadRequestException);
}

describe("validateCreateRunRequest", () => {
  it("accepts a valid create request", () => {
    expect(() => validateCreateRunRequest(validCreateRequest())).not.toThrow();
  });

  it("accepts Simplified Chinese question generation", () => {
    expect(() => validateCreateRunRequest({
      ...validCreateRequest(),
      promptLanguage: "zh-CN"
    })).not.toThrow();
  });

  it.each([
    ["promptCount", 1.5],
    ["repetitions", 2.5]
  ])("rejects a non-integer %s", (field, value) => {
    expectBadRequest(() => validateCreateRunRequest({
      ...validCreateRequest(),
      [field]: value
    }));
  });

  it("rejects repeated executions because the dual-track design runs every template once", () => {
    expectBadRequest(() => validateCreateRunRequest({
      ...validCreateRequest(),
      repetitions: 2
    }));
  });

  it.each([
    ["preset", "unbounded"],
    ["promptLanguage", "zh-TW"],
    ["sessionPolicy", "reuse_everything"]
  ])("rejects an unsupported %s enum value", (field, value) => {
    expectBadRequest(() => validateCreateRunRequest({
      ...validCreateRequest(),
      [field]: value
    }));
  });
});

describe("validateUpdatePromptCaseRequest", () => {
  it("accepts a valid update request", () => {
    expect(() => validateUpdatePromptCaseRequest(validUpdateRequest())).not.toThrow();
  });

  it.each([
    ["enabled", "true"],
    ["scoreEligible", "false"]
  ])("rejects a string Boolean for %s", (field, value) => {
    expectBadRequest(() => validateUpdatePromptCaseRequest({
      ...validUpdateRequest(),
      [field]: value
    }));
  });

  it("rejects a non-integer expectedRevision", () => {
    expectBadRequest(() => validateUpdatePromptCaseRequest({
      ...validUpdateRequest(),
      expectedRevision: 1.25
    }));
  });

  it.each([
    ["testRole", "primary"],
    ["expectedMatch", "maybe"],
    ["sessionPolicy", "shared_forever"]
  ])("rejects an unsupported %s enum value", (field, value) => {
    expectBadRequest(() => validateUpdatePromptCaseRequest({
      ...validUpdateRequest(),
      [field]: value
    }));
  });

  it.each(["requiredTerms", "judgmentCriteria"])("rejects an empty %s array", (field) => {
    expectBadRequest(() => validateUpdatePromptCaseRequest({
      ...validUpdateRequest(),
      [field]: []
    }));
  });
});

describe("validateApproveQuestionPlanRequest", () => {
  it("accepts a valid approval request", () => {
    expect(() => validateApproveQuestionPlanRequest({
      expectedRevision: 4,
      note: "Reviewed against the product evidence baseline."
    })).not.toThrow();
  });

  it.each([1.5, 0, "2"])("rejects invalid expectedRevision %j", (expectedRevision) => {
    expectBadRequest(() => validateApproveQuestionPlanRequest({ expectedRevision }));
  });
});
