import { BadRequestException } from "@nestjs/common";
import {
  EXPECTED_MATCHES,
  PROMPT_LANGUAGES,
  RUN_PRESETS,
  SESSION_POLICIES,
  TEST_ROLES,
  type ApproveQuestionPlanRequest,
  type CreateRunRequest,
  type UpdatePromptCaseRequest
} from "@alexa-auditor/contracts";

const presetSet = new Set<string>(RUN_PRESETS);
const languageSet = new Set<string>(PROMPT_LANGUAGES);
const sessionPolicySet = new Set<string>(SESSION_POLICIES);
const testRoleSet = new Set<string>(TEST_ROLES);
const expectedMatchSet = new Set<string>(EXPECTED_MATCHES);

function record(value: unknown, label: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new BadRequestException(`${label}必须是JSON对象`);
  }
  return value as Record<string, unknown>;
}

function optionalEnum(value: unknown, allowed: Set<string>, label: string) {
  if (value !== undefined && (typeof value !== "string" || !allowed.has(value))) {
    throw new BadRequestException(`${label}不是允许的枚举值`);
  }
}

function optionalBoolean(value: unknown, label: string) {
  if (value !== undefined && typeof value !== "boolean") {
    throw new BadRequestException(`${label}必须是Boolean，不能使用字符串或数字代替`);
  }
}

function optionalString(value: unknown, label: string, max: number, allowNull = false) {
  if (value === undefined || (allowNull && value === null)) return;
  if (typeof value !== "string" || value.length > max) {
    throw new BadRequestException(`${label}必须是长度不超过${max}的字符串`);
  }
}

function optionalStringArray(value: unknown, label: string, maxItems: number, maxLength: number, minItems = 0) {
  if (value === undefined) return;
  if (!Array.isArray(value) || value.length < minItems || value.length > maxItems
    || value.some((item) => typeof item !== "string" || !item.trim() || item.length > maxLength)) {
    throw new BadRequestException(`${label}必须是${minItems}-${maxItems}个非空字符串组成的数组`);
  }
}

function requiredPositiveInteger(value: unknown, label: string) {
  if (!Number.isInteger(value) || Number(value) < 1) {
    throw new BadRequestException(`${label}必须是正整数`);
  }
}

function optionalInteger(value: unknown, label: string, min: number, max: number) {
  if (value !== undefined && (!Number.isInteger(value) || Number(value) < min || Number(value) > max)) {
    throw new BadRequestException(`${label}必须是${min}-${max}之间的整数`);
  }
}

export function validateCreateRunRequest(input: unknown): asserts input is CreateRunRequest {
  const body = record(input, "创建运行参数");
  if (typeof body.productSnapshotId !== "string" || !body.productSnapshotId.trim() || body.productSnapshotId.length > 128) {
    throw new BadRequestException("productSnapshotId必须是非空字符串");
  }
  if (typeof body.accountLabel !== "string" || !body.accountLabel.trim() || body.accountLabel.length > 80) {
    throw new BadRequestException("accountLabel必须是1-80字符的字符串");
  }
  optionalEnum(body.preset, presetSet, "preset");
  optionalEnum(body.promptLanguage, languageSet, "promptLanguage");
  optionalEnum(body.sessionPolicy, sessionPolicySet, "sessionPolicy");
  optionalInteger(body.promptCount, "promptCount", 1, 11);
  optionalInteger(body.repetitions, "repetitions", 1, 1);
  optionalString(body.runSeed, "runSeed", 128);
}

export function validateUpdatePromptCaseRequest(input: unknown): asserts input is UpdatePromptCaseRequest {
  const body = record(input, "问题调整参数");
  requiredPositiveInteger(body.expectedRevision, "expectedRevision");
  if (typeof body.changeReason !== "string" || body.changeReason.trim().length < 3 || body.changeReason.length > 1000) {
    throw new BadRequestException("changeReason必须是3-1000字符的字符串");
  }
  optionalBoolean(body.enabled, "enabled");
  optionalBoolean(body.scoreEligible, "scoreEligible");
  optionalString(body.promptText, "promptText", 800);
  optionalString(body.hypothesis, "hypothesis", 1000);
  optionalEnum(body.testRole, testRoleSet, "testRole");
  optionalEnum(body.expectedMatch, expectedMatchSet, "expectedMatch");
  optionalStringArray(body.evidenceFactIds, "evidenceFactIds", 30, 128);
  optionalStringArray(body.requiredTerms, "requiredTerms", 20, 120, 1);
  optionalStringArray(body.judgmentCriteria, "judgmentCriteria", 12, 500, 1);
  optionalEnum(body.sessionPolicy, sessionPolicySet, "sessionPolicy");
  optionalString(body.sessionGroup, "sessionGroup", 64, true);
}

export function validateApproveQuestionPlanRequest(input: unknown): asserts input is ApproveQuestionPlanRequest {
  const body = record(input, "问题集审批参数");
  requiredPositiveInteger(body.expectedRevision, "expectedRevision");
  optionalString(body.note, "note", 1000);
}
