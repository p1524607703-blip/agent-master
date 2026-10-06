import { BadRequestException, ConflictException, Inject, Injectable, NotFoundException } from "@nestjs/common";
import { createHash, randomBytes } from "node:crypto";
import { mkdir, writeFile } from "node:fs/promises";
import { resolve, sep } from "node:path";
import {
  calculateScore,
  EXPECTED_MATCHES,
  FOOTWEAR_PROMPT_VERSION,
  SCHEMA_VERSION,
  getScoringStandards,
  JUDGMENT_STANDARDS_VERSION,
  SESSION_POLICIES,
  TEST_ROLES,
  type AuditActor,
  type ApproveQuestionPlanRequest,
  type ConversationTurn,
  type CreateRunRequest,
  type Diagnosis,
  type ExperimentRun,
  type ProductSnapshot,
  type PromptCase,
  type PromptCaseDefinition,
  type RecommendationItem,
  type RunAuditEvent,
  type RunReport,
  type ScoreSnapshot,
  type UpdatePromptCaseRequest
} from "@alexa-auditor/contracts";
import { PrismaService } from "../prisma.service";
import { ProductsService } from "../products/products.service";
import { DeepSeekService } from "../deepseek/deepseek.service";
import { parseJson, stringifyJson } from "../common/json";
import { deterministicPromptPlan, expandAndShufflePrompts, FOOTWEAR_PRESET_COUNTS } from "./prompt-builder";
import {
  validateApproveQuestionPlanRequest,
  validateCreateRunRequest,
  validateUpdatePromptCaseRequest
} from "./request-validation";
import { RunEventsService } from "./run-events.service";

class PromptClaimConflict extends Error {}

const SCORE_ELIGIBLE_EVIDENCE_SECTIONS = new Set<ProductSnapshot["stableFacts"][number]["sourceSection"]>([
  "title",
  "specification",
  "bullets",
  "a_plus",
  "breadcrumb"
]);

@Injectable()
export class RunsService {
  private readonly artifactRoot = resolve(process.cwd(), process.env.ARTIFACT_DIR || "./artifacts");

  constructor(
    @Inject(PrismaService) private readonly prisma: PrismaService,
    @Inject(ProductsService) private readonly products: ProductsService,
    @Inject(DeepSeekService) private readonly deepseek: DeepSeekService,
    @Inject(RunEventsService) private readonly events: RunEventsService
  ) {}

  async create(input: CreateRunRequest): Promise<ExperimentRun> {
    validateCreateRunRequest(input);
    const product = await this.products.get(input.productSnapshotId);
    if (!product) throw new NotFoundException("商品快照不存在");
    const preset = input.preset || "calibration";
    const promptLanguage = input.promptLanguage || "en-US";
    const presetCount = FOOTWEAR_PRESET_COUNTS[preset];
    const promptCount = Math.min(presetCount, input.promptCount ?? presetCount);
    const repetitions = 1;
    const runSeed = String(input.runSeed || randomBytes(8).toString("hex"));
    const draft = await this.prisma.experimentRun.create({
      data: {
        productSnapshotId: input.productSnapshotId, status: "draft", accountLabel: String(input.accountLabel || product.accountLabel), runSeed,
        preset, promptLanguage, sessionPolicy: "fresh", promptVersion: FOOTWEAR_PROMPT_VERSION,
        promptCount, repetitions, totalTurns: 0, judgmentStandardsVersion: JUDGMENT_STANDARDS_VERSION
      }
    });
    const fallback = deterministicPromptPlan(product, preset, promptLanguage).slice(0, promptCount);
    const generated = await this.deepseek.generatePromptPlanWithAudit(product, fallback, {
      requestId: randomBytes(16).toString("hex"),
      runId: draft.id,
      productSnapshotId: input.productSnapshotId,
      productAsin: product.resolvedAsin || product.asin,
      schemaVersion: SCHEMA_VERSION,
      promptVersion: fallback[0]?.promptVersion || draft.promptVersion,
      promptLanguage,
      templateIds: fallback.map((item) => item.templateId)
    });
    const plan = generated.prompts.slice(0, promptCount);
    assertPlanTrackLimits(plan);
    const promptCases = expandAndShufflePrompts(plan, product, draft.id, runSeed, repetitions, promptLanguage);
    const generatedByDeepSeek = generated.audit.status === "rewritten";
    const planPayload = {
      action: generatedByDeepSeek ? "deepseek_rewritten" : "generated",
      toRevision: 1,
      modelEnabled: this.deepseek.enabled,
      modelTransport: this.deepseek.transportStatus,
      modelAudit: generated.audit,
      promptLanguage,
      promptVersion: plan[0]?.promptVersion || draft.promptVersion,
      questions: [...new Map(promptCases.map((item) => [item.templateId, item])).values()].map((item) => auditPrompt(item))
    };
    await this.prisma.$transaction([
      ...promptCases.map((item) => this.prisma.promptCase.create({ data: itemToDb(item, draft.id) })),
      this.prisma.experimentRun.update({
        where: { id: draft.id },
        data: { status: "draft", promptVersion: plan[0]?.promptVersion || draft.promptVersion, totalTurns: promptCases.filter((item) => item.enabled).length }
      }),
      this.prisma.runEvent.create({ data: { runId: draft.id, type: "question_plan_generated", actor: generatedByDeepSeek ? "deepseek" : "system", payloadJson: stringifyJson(planPayload) } }),
      this.prisma.runEvent.create({ data: { runId: draft.id, type: "run_created", actor: "system", payloadJson: stringifyJson({ promptCount, repetitions, totalTurns: promptCases.length, promptLanguage, modelEnabled: this.deepseek.enabled, modelTransport: this.deepseek.transportStatus }) } })
    ]);
    this.events.emit(draft.id, "question_plan_generated", planPayload);
    this.events.emit(draft.id, "run_created", { runId: draft.id, totalTurns: promptCases.length });
    return this.get(draft.id);
  }

  async get(id: string): Promise<ExperimentRun> {
    const run = await this.prisma.experimentRun.findUnique({ where: { id }, include: { promptCases: { orderBy: { sequence: "asc" } } } });
    if (!run) throw new NotFoundException("测试运行不存在");
    return mapRun(run);
  }

  async updatePrompt(id: string, promptCaseId: string, input: UpdatePromptCaseRequest): Promise<ExperimentRun> {
    validateUpdatePromptCaseRequest(input);
    const run = await this.get(id);
    if (!run.questionPlanEditable || !["draft", "ready"].includes(run.status)) {
      throw new BadRequestException("问题集已经锁定或运行已开始，不能再编辑");
    }
    if (input.expectedRevision !== run.questionPlanRevision) {
      throw new ConflictException(`问题集版本已变化，当前版本为 ${run.questionPlanRevision}`);
    }
    const selected = run.promptCases.find((item) => item.id === promptCaseId);
    if (!selected) throw new NotFoundException("问题不属于当前运行");
    const group = run.promptCases.filter((item) => item.templateId === selected.templateId);
    const product = await this.products.get(run.productSnapshotId);
    if (!product) throw new NotFoundException("商品快照不存在");

    const promptText = input.promptText === undefined ? selected.promptText : cleanPrompt(input.promptText);
    const testRole = input.testRole || selected.testRole;
    const scoreEligible = input.scoreEligible === undefined ? selected.scoreEligible : input.scoreEligible;
    const expectedMatch = input.expectedMatch || selected.expectedMatch;
    const evidenceFactIds = input.evidenceFactIds === undefined ? selected.evidenceFactIds : uniqueStrings(input.evidenceFactIds, 30);
    const requiredTerms = input.requiredTerms === undefined ? selected.requiredTerms : uniqueStrings(input.requiredTerms, 20);
    const judgmentCriteria = input.judgmentCriteria === undefined ? selected.judgmentCriteria : uniqueStrings(input.judgmentCriteria, 12);
    const enabled = input.enabled === undefined ? selected.enabled : input.enabled;
    const sessionPolicy = input.sessionPolicy || selected.sessionPolicy;
    const sessionGroup = input.sessionGroup === undefined ? selected.sessionGroup : String(input.sessionGroup || "").trim() || undefined;
    const hypothesis = input.hypothesis === undefined ? selected.hypothesis : String(input.hypothesis || "").trim().slice(0, 1000);
    const changeReason = String(input.changeReason || "").trim().slice(0, 1000);
    const candidate: PromptCaseDefinition = {
      ...selected,
      promptText,
      testRole,
      enabled,
      scoreEligible,
      hypothesis,
      expectedMatch,
      evidenceFactIds,
      requiredTerms,
      judgmentCriteria,
      sessionPolicy,
      sessionGroup
    };
    assertPromptInvariant(candidate, product);
    assertPlanTrackLimits([...new Map(run.promptCases.map((item) => [
      item.templateId,
      item.templateId === selected.templateId ? candidate : item
    ])).values()]);
    if (!hasPromptContentChange(selected, candidate)) {
      throw new BadRequestException("没有检测到可保存的问题集调整");
    }

    const nextRevision = run.questionPlanRevision + 1;
    const currentEnabledInGroup = group.filter((item) => item.enabled).length;
    const nextTotalTurns = Math.max(0, run.totalTurns - currentEnabledInGroup + (enabled ? group.length : 0));
    const before = auditPrompt(selected);
    const after: PromptCaseDefinition = {
      ...candidate,
      sessionGroup,
      generatedBy: "developer_edit",
      originalPromptText: selected.originalPromptText || selected.promptText,
      rewriteReason: changeReason
    };
    const promptUpdate = {
      promptText,
      testRole,
      enabled,
      scoreEligible,
      hypothesis,
      expectedMatch,
      evidenceFactIdsJson: stringifyJson(evidenceFactIds),
      requiredTermsJson: stringifyJson(requiredTerms),
      judgmentCriteriaJson: stringifyJson(judgmentCriteria),
      sessionPolicy,
      sessionGroup: sessionGroup || null,
      generatedBy: "developer_edit",
      originalPromptText: selected.originalPromptText || selected.promptText,
      rewriteReason: changeReason,
      revision: { increment: 1 }
    } as const;
    const eventPayload = {
      action: "developer_updated",
      fromRevision: run.questionPlanRevision,
      toRevision: nextRevision,
      changeReason,
      templateId: selected.templateId,
      affectedPromptCaseIds: group.map((item) => item.id),
      afterRevision: selected.revision + 1,
      before,
      after: auditPrompt(after)
    };
    await this.prisma.$transaction(async (tx) => {
      const revisionLock = await tx.experimentRun.updateMany({
        where: { id, questionPlanRevision: run.questionPlanRevision, questionPlanEditable: true },
        data: {
          status: "draft",
          questionPlanRevision: nextRevision,
          questionPlanApprovedAt: null,
          questionPlanLockedAt: null,
          totalTurns: nextTotalTurns
        }
      });
      if (revisionLock.count !== 1) throw new ConflictException("问题集已被其他编辑更新，请刷新后重试");
      await tx.promptCase.updateMany({ where: { runId: id, templateId: selected.templateId }, data: promptUpdate });
      await tx.runEvent.create({
        data: { runId: id, type: "question_plan_updated", actor: "developer", promptCaseId: selected.id, payloadJson: stringifyJson(eventPayload) }
      });
    });
    this.events.emit(id, "question_plan_updated", eventPayload);
    return this.get(id);
  }

  async approveQuestionPlan(id: string, input: ApproveQuestionPlanRequest): Promise<ExperimentRun> {
    validateApproveQuestionPlanRequest(input);
    const run = await this.get(id);
    if (!run.questionPlanEditable || !["draft", "ready"].includes(run.status)) {
      throw new BadRequestException("问题集已经锁定或运行已开始");
    }
    if (input.expectedRevision !== run.questionPlanRevision) {
      throw new ConflictException(`问题集版本已变化，当前版本为 ${run.questionPlanRevision}`);
    }
    const enabled = run.promptCases.filter((item) => item.enabled);
    if (!enabled.length) throw new BadRequestException("至少启用一个问题模板后才能批准运行");
    if (enabled.some((item) => item.status !== "pending")) {
      throw new BadRequestException("启用的问题包含非pending状态，不能批准为新的问题集");
    }
    const product = await this.products.get(run.productSnapshotId);
    if (!product) throw new NotFoundException("商品快照不存在");
    const uniqueEnabled = [...new Map(enabled.map((item) => [item.templateId, item])).values()];
    uniqueEnabled.forEach((item) => assertPromptInvariant(item, product));
    assertPlanTrackLimits(uniqueEnabled);
    const validFactIds = new Set(product.stableFacts
      .filter((fact) => SCORE_ELIGIBLE_EVIDENCE_SECTIONS.has(fact.sourceSection))
      .map((fact) => fact.id));
    const alignedPositive = uniqueEnabled.some((item) => item.sessionPolicy === "fresh"
      && item.testRole === "positive_control"
      && item.scoreEligible
      && item.expectedMatch === "eligible"
      && item.evidenceFactIds.length > 0
      && item.evidenceFactIds.every((factId) => validFactIds.has(factId)));
    const diagnosticOnly = !alignedPositive;
    if (diagnosticOnly && run.preset !== "smoke") {
      throw new BadRequestException("当前启用题没有任何页面证据对齐的正向计分题，无法生成推荐指数");
    }
    const approvedAt = new Date();
    const eventPayload = {
      action: "approved",
      toRevision: run.questionPlanRevision,
      note: String(input.note || "").slice(0, 1000),
      enabledTemplates: [...new Set(enabled.map((item) => item.templateId))],
      disabledTemplates: [...new Set(run.promptCases.filter((item) => !item.enabled).map((item) => item.templateId))],
      totalTurns: enabled.length,
      diagnosticOnly
    };
    await this.prisma.$transaction(async (tx) => {
      const revisionLock = await tx.experimentRun.updateMany({
        where: { id, questionPlanRevision: run.questionPlanRevision, questionPlanEditable: true },
        data: {
          status: "ready",
          questionPlanEditable: false,
          questionPlanApprovedAt: approvedAt,
          questionPlanLockedAt: approvedAt,
          totalTurns: enabled.length
        }
      });
      if (revisionLock.count !== 1) throw new ConflictException("问题集已被更新，请刷新后重新审核");
      await tx.promptCase.updateMany({ where: { runId: id }, data: { editable: false } });
      await tx.promptCase.updateMany({ where: { runId: id, enabled: false, status: "pending" }, data: { status: "skipped" } });
      await tx.runEvent.create({ data: { runId: id, type: "question_plan_approved", actor: "developer", payloadJson: stringifyJson(eventPayload) } });
    });
    this.events.emit(id, "question_plan_approved", eventPayload);
    return this.get(id);
  }

  async start(id: string): Promise<ExperimentRun> {
    const run = await this.get(id);
    if (!["ready", "stopped"].includes(run.status)) throw new BadRequestException(`当前状态不能开始测试: ${run.status}`);
    if (run.promptVersion !== FOOTWEAR_PROMPT_VERSION) {
      throw new BadRequestException(`问题集版本 ${run.promptVersion} 已过期，请使用 ${FOOTWEAR_PROMPT_VERSION} 重新生成问题集`);
    }
    if (!run.questionPlanApprovedAt || run.questionPlanEditable) throw new BadRequestException("必须先由开发者审核并锁定问题集");
    if (!run.promptCases.some((item) => item.enabled && item.status === "pending")) {
      throw new BadRequestException("没有可执行的pending问题，不能开始或恢复测试");
    }
    const eventPayload = { resumed: run.status === "stopped", questionPlanRevision: run.questionPlanRevision };
    await this.prisma.$transaction(async (tx) => {
      const claimed = await tx.experimentRun.updateMany({
        where: {
          id,
          status: run.status,
          questionPlanRevision: run.questionPlanRevision,
          questionPlanEditable: false,
          questionPlanApprovedAt: { not: null }
        },
        data: { status: "running", stopReason: null, questionPlanEditable: false }
      });
      if (claimed.count !== 1) throw new ConflictException("运行已由其他客户端启动或状态已经变化");
      await tx.promptCase.updateMany({ where: { runId: id }, data: { editable: false } });
      await tx.runEvent.create({ data: { runId: id, type: "run_started", actor: "system", payloadJson: stringifyJson(eventPayload) } });
    });
    this.events.emit(id, "run_started", eventPayload);
    return this.get(id);
  }

  async stop(id: string, reason = "user_requested"): Promise<ExperimentRun> {
    await this.get(id);
    await this.prisma.experimentRun.update({ where: { id }, data: { status: "stopped", stopReason: reason } });
    await this.addEvent(id, "run_stopped", { reason });
    return this.get(id);
  }

  async addTurn(id: string, input: ConversationTurn): Promise<ExperimentRun> {
    const run = await this.get(id);
    if (run.status !== "running") throw new BadRequestException(`运行未处于可写状态: ${run.status}`);
    if (!input || typeof input !== "object" || typeof input.promptCaseId !== "string" || !input.promptCaseId.trim()) {
      throw new BadRequestException("轮次必须包含有效的promptCaseId");
    }
    const prompt = run.promptCases.find((item) => item.id === input.promptCaseId);
    if (!prompt) throw new BadRequestException("问题不属于当前运行");
    const existing = await this.prisma.conversationTurn.findUnique({ where: { promptCaseId: prompt.id } });
    if (existing) return this.get(id);
    if (!prompt.enabled || prompt.status !== "pending") {
      throw new BadRequestException("只能提交已启用且处于pending状态的问题");
    }
    if (!["completed", "failed"].includes(String(input.status))) {
      throw new BadRequestException("轮次状态必须是completed或failed");
    }
    const capturedAt = new Date(input.capturedAt || Date.now());
    if (Number.isNaN(capturedAt.getTime())) throw new BadRequestException("capturedAt不是有效时间");
    const recommendations = sanitizeRecommendations(input.recommendations);
    const status = input.status === "completed" ? "completed" : "failed";
    let screenshotPath: string | null = null;
    try {
      await this.prisma.$transaction(async (tx) => {
        const claimed = await tx.promptCase.updateMany({
          where: { id: prompt.id, runId: id, enabled: true, status: "pending" },
          data: { status: "running" }
        });
        if (claimed.count !== 1) throw new PromptClaimConflict();
        // Save only after the database claim succeeds. A concurrent duplicate
        // must never overwrite the authoritative screenshot on disk.
        screenshotPath = await this.saveScreenshot(id, prompt.id, input.screenshotDataUrl);
        await tx.conversationTurn.create({
          data: {
            runId: id, promptCaseId: prompt.id, promptText: prompt.promptText, responseText: String(input.responseText || "").slice(0, 50000),
            recommendationsJson: stringifyJson(recommendations), screenshotPath, selectorVersion: String(input.selectorVersion || "unknown"), status,
            errorCode: input.errorCode || null, errorMessage: input.errorMessage?.slice(0, 2000) || null, capturedAt
          }
        });
        await tx.promptCase.update({ where: { id: prompt.id }, data: { status } });
        await tx.experimentRun.update({ where: { id }, data: { completedTurns: { increment: 1 } } });
      });
    } catch (error) {
      if (error instanceof PromptClaimConflict) {
        const committed = await this.prisma.conversationTurn.findUnique({ where: { promptCaseId: prompt.id } });
        if (committed) return this.get(id);
        throw new ConflictException("问题已被其他执行器领取或状态已经变化");
      }
      throw error;
    }
    await this.addEvent(id, "turn_recorded", {
      promptCaseId: prompt.id,
      promptVersion: prompt.promptVersion,
      testRole: prompt.testRole,
      status,
      recommendationCount: recommendations.length,
      extractionDiagnostics: input.extractionDiagnostics || {
        responseChars: String(input.responseText || "").length,
        domLinkCount: 0,
        asinCount: recommendations.filter((item) => Boolean(item.asin)).length,
        textOnlyCount: recommendations.filter((item) => !item.asin).length
      },
      screenshot: screenshotPath
        ? { status: "captured", path: screenshotPath }
        : { status: "failed", error: String(input.screenshotError || "capture_not_available").slice(0, 1000) }
    }, "extension", prompt.id);

    if (["captcha", "rate_limited", "forbidden", "login_required", "selector_drift", "context_isolation_failed", "response_timeout"].includes(String(input.errorCode))) {
      return this.stop(id, `safety_stop:${input.errorCode}`);
    }

    const report = await this.report(id);
    const judgment = report.score?.judgments.find((item) => item.promptCaseId === prompt.id);
    await this.prisma.$transaction([
      this.prisma.experimentRun.update({ where: { id }, data: { scoreJson: stringifyJson(report.score) } }),
      this.prisma.conversationTurn.update({
        where: { promptCaseId: prompt.id },
        data: { judgmentJson: judgment ? stringifyJson(judgment) : null, judgmentVersion: judgment ? JUDGMENT_STANDARDS_VERSION : null }
      })
    ]);
    if (judgment) {
      await this.addEvent(id, "turn_judged", judgment, "system", prompt.id);
    }
    await this.addEvent(id, "score_recalculated", scoreAuditSummary(report.score), "system", prompt.id);
    const latest = await this.get(id);
    if (latest.completedTurns >= latest.totalTurns) {
      const fallback = deterministicDiagnoses(report);
      const diagnoses = await this.deepseek.diagnose({ ...report, score: report.score }, fallback, {
        requestId: randomBytes(16).toString("hex"),
        runId: id,
        productSnapshotId: run.productSnapshotId,
        productAsin: report.product.resolvedAsin || report.product.asin,
        schemaVersion: SCHEMA_VERSION,
        promptVersion: run.promptVersion
      });
      const modelAudit = this.deepseek.getLastModelInvocation("run_diagnosis", id);
      await this.prisma.experimentRun.update({ where: { id }, data: { status: "completed", diagnosisJson: stringifyJson(diagnoses) } });
      if (modelAudit) await this.addEvent(id, "model_diagnosis_completed", modelAudit, modelAudit.status === "succeeded" ? "deepseek" : "system");
      await this.addEvent(id, "run_completed", { score: report.score, diagnosisCount: diagnoses.length, modelAudit });
    }
    return this.get(id);
  }

  async report(id: string): Promise<RunReport> {
    const record = await this.prisma.experimentRun.findUnique({
      where: { id },
      include: {
        productSnapshot: true,
        promptCases: { orderBy: { sequence: "asc" } },
        turns: { orderBy: { capturedAt: "asc" } },
        events: { orderBy: { createdAt: "asc" } }
      }
    });
    if (!record) throw new NotFoundException("测试运行不存在");
    const product = { ...parseJson<ProductSnapshot>(record.productSnapshot.snapshotJson, {} as ProductSnapshot), id: record.productSnapshot.id };
    const turns = record.turns.map(mapTurn);
    const run = mapRun(record);
    const score = turns.length ? calculateScore(turns, product, run.promptCases) : parseJson<ScoreSnapshot | null>(record.scoreJson, null);
    const diagnoses = parseJson<Diagnosis[]>(record.diagnosisJson, []);
    const auditEvents = record.events.map(mapAuditEvent);
    return { run: { ...run, score, diagnoses }, product, turns, score, diagnoses, auditEvents };
  }

  scoringStandards() {
    return getScoringStandards();
  }

  async audit(id: string): Promise<{ runId: string; standards: ReturnType<typeof getScoringStandards>; events: RunAuditEvent[] }> {
    await this.get(id);
    const events = await this.prisma.runEvent.findMany({ where: { runId: id }, orderBy: { createdAt: "asc" } });
    return { runId: id, standards: getScoringStandards(), events: events.map(mapAuditEvent) };
  }

  async artifactPath(runId: string, name: string): Promise<string> {
    const path = resolve(this.artifactRoot, runId, name);
    const expectedPrefix = `${resolve(this.artifactRoot, runId)}${sep}`;
    if (!path.startsWith(expectedPrefix)) throw new BadRequestException("非法文件路径");
    return path;
  }

  private async saveScreenshot(runId: string, promptId: string, dataUrl?: string): Promise<string | null> {
    if (!dataUrl) return null;
    const match = /^data:image\/(png|jpeg);base64,([A-Za-z0-9+/=]+)$/.exec(dataUrl);
    if (!match) throw new BadRequestException("截图格式必须为PNG或JPEG data URL");
    const buffer = Buffer.from(match[2], "base64");
    if (buffer.length > 8 * 1024 * 1024) throw new BadRequestException("单张截图不能超过8MB");
    const directory = resolve(this.artifactRoot, runId);
    await mkdir(directory, { recursive: true, mode: 0o700 });
    const digest = createHash("sha256").update(promptId).digest("hex").slice(0, 16);
    const name = `${digest}.${match[1] === "jpeg" ? "jpg" : "png"}`;
    await writeFile(resolve(directory, name), buffer, { mode: 0o600 });
    return name;
  }

  private async addEvent(runId: string, type: string, payload: unknown, actor: AuditActor = "system", promptCaseId?: string) {
    await this.prisma.runEvent.create({ data: { runId, type, actor, promptCaseId: promptCaseId || null, payloadJson: stringifyJson(payload) } });
    this.events.emit(runId, type, payload);
  }
}

function itemToDb(item: PromptCase, runId: string) {
  return {
    id: item.id, runId, templateId: item.templateId, slot: item.slot, mode: item.mode, expression: item.expression, promptText: item.promptText,
    testRole: item.testRole, enabled: item.enabled, scoreEligible: item.scoreEligible, hypothesis: item.hypothesis, expectedMatch: item.expectedMatch,
    evidenceFactIdsJson: stringifyJson(item.evidenceFactIds), requiredTermsJson: stringifyJson(item.requiredTerms),
    judgmentCriteriaJson: stringifyJson(item.judgmentCriteria), promptVersion: item.promptVersion, sessionPolicy: item.sessionPolicy,
    sessionGroup: item.sessionGroup || null, generatedBy: item.generatedBy, originalPromptText: item.originalPromptText || null,
    rewriteReason: item.rewriteReason || null, repeatIndex: item.repeatIndex, sequence: item.sequence, status: item.status,
    revision: item.revision, editable: item.editable
  };
}

function mapRun(run: any): ExperimentRun {
  return {
    id: run.id, productSnapshotId: run.productSnapshotId, status: run.status, accountLabel: run.accountLabel, runSeed: run.runSeed,
    preset: run.preset || "calibration", promptLanguage: run.promptLanguage || "en-US", sessionPolicy: run.sessionPolicy || "fresh",
    promptVersion: run.promptVersion || FOOTWEAR_PROMPT_VERSION, questionPlanRevision: run.questionPlanRevision || 1,
    questionPlanEditable: run.questionPlanEditable !== false,
    questionPlanApprovedAt: run.questionPlanApprovedAt ? new Date(run.questionPlanApprovedAt).toISOString() : undefined,
    questionPlanLockedAt: run.questionPlanLockedAt ? new Date(run.questionPlanLockedAt).toISOString() : undefined,
    promptCount: run.promptCount, repetitions: run.repetitions, totalTurns: run.totalTurns, completedTurns: run.completedTurns,
    promptCases: (run.promptCases || []).map(mapPromptCase),
    score: parseJson(run.scoreJson, null), diagnoses: parseJson(run.diagnosisJson, []), stopReason: run.stopReason || undefined,
    createdAt: new Date(run.createdAt).toISOString(), updatedAt: new Date(run.updatedAt).toISOString()
  };
}

function mapPromptCase(item: any): PromptCase {
  return {
    id: item.id, templateId: item.templateId || "legacy", slot: item.slot, mode: item.mode, expression: item.expression, promptText: item.promptText,
    testRole: item.testRole || "baseline", enabled: item.enabled !== false, scoreEligible: Boolean(item.scoreEligible), hypothesis: item.hypothesis || "",
    expectedMatch: item.expectedMatch || "neutral", evidenceFactIds: parseJson<string[]>(item.evidenceFactIdsJson, []),
    requiredTerms: parseJson<string[]>(item.requiredTermsJson, []), judgmentCriteria: parseJson<string[]>(item.judgmentCriteriaJson, []),
    promptVersion: item.promptVersion || "legacy", sessionPolicy: item.sessionPolicy || "fresh", sessionGroup: item.sessionGroup || undefined,
    generatedBy: item.generatedBy || "deterministic", originalPromptText: item.originalPromptText || undefined, rewriteReason: item.rewriteReason || undefined,
    repeatIndex: item.repeatIndex, sequence: item.sequence, status: item.status, revision: item.revision || 1,
    editable: item.editable !== false, updatedAt: item.updatedAt ? new Date(item.updatedAt).toISOString() : undefined
  };
}

function mapAuditEvent(event: any): RunAuditEvent {
  return {
    id: event.id,
    runId: event.runId,
    type: event.type,
    actor: event.actor || "system",
    promptCaseId: event.promptCaseId || undefined,
    payload: parseJson(event.payloadJson, {}),
    createdAt: new Date(event.createdAt).toISOString()
  };
}

function auditPrompt(item: PromptCaseDefinition | PromptCase) {
  return {
    templateId: item.templateId,
    slot: item.slot,
    promptText: item.promptText,
    originalPromptText: item.originalPromptText,
    rewriteReason: item.rewriteReason,
    generatedBy: item.generatedBy,
    promptVersion: item.promptVersion,
    testRole: item.testRole,
    enabled: item.enabled,
    scoreEligible: item.scoreEligible,
    hypothesis: item.hypothesis,
    expectedMatch: item.expectedMatch,
    evidenceFactIds: item.evidenceFactIds,
    requiredTerms: item.requiredTerms,
    judgmentCriteria: item.judgmentCriteria,
    sessionPolicy: item.sessionPolicy,
    sessionGroup: item.sessionGroup
  };
}

function scoreAuditSummary(score: ScoreSnapshot | null) {
  if (!score) return { status: "not_available", standardsVersion: JUDGMENT_STANDARDS_VERSION };
  return {
    status: score.total === null ? "insufficient" : "scored",
    total: score.total,
    grade: score.grade,
    dimensions: score.dimensions,
    mainSampleSize: score.sampleSize,
    completedPromptGroups: score.completedPromptGroups,
    probes: score.probes,
    formulaVersion: score.formulaVersion,
    standardsVersion: score.standardsVersion,
    warnings: score.warnings
  };
}

function cleanPrompt(value: unknown): string {
  const prompt = String(value || "").normalize("NFKC").replace(/\s+/g, " ").trim();
  if (prompt.length < 5 || prompt.length > 800) throw new BadRequestException("问题长度必须在5到800字符之间");
  return prompt;
}

function uniqueStrings(value: unknown, max: number): string[] {
  if (!Array.isArray(value)) throw new BadRequestException("题目元数据必须为数组");
  return [...new Set(value.map((item) => String(item || "").trim()).filter(Boolean))].slice(0, max);
}

function normalizedPrompt(value: string): string {
  return String(value || "").normalize("NFKC").toLowerCase().replace(/_/g, " ").replace(/[^a-z0-9$\p{L}]+/gu, " ").replace(/\s+/g, " ").trim();
}

function leaksProductIdentity(promptText: string, product: ProductSnapshot): boolean {
  const prompt = normalizedPrompt(promptText);
  const identities = [
    product.asin,
    product.requestedAsin || "",
    product.resolvedAsin || "",
    ...(product.asinAliases || []),
    ...(product.brand.length > 3 ? [product.brand] : [])
  ].map(normalizedPrompt).filter((value) => value.length > 3);
  return identities.some((identity) => prompt.includes(identity));
}

function assertPromptInvariant(prompt: PromptCaseDefinition | PromptCase, product: ProductSnapshot): void {
  cleanPrompt(prompt.promptText);
  if (!(TEST_ROLES as readonly string[]).includes(prompt.testRole)) {
    throw new BadRequestException("testRole不是允许的枚举值");
  }
  if (!(EXPECTED_MATCHES as readonly string[]).includes(prompt.expectedMatch)) {
    throw new BadRequestException("expectedMatch不是允许的枚举值");
  }
  if (!(SESSION_POLICIES as readonly string[]).includes(prompt.sessionPolicy)) {
    throw new BadRequestException("sessionPolicy不是允许的枚举值");
  }
  if (!["blind", "aided", "diagnostic"].includes(prompt.mode)) {
    throw new BadRequestException("mode不是允许的枚举值");
  }
  if (!["direct", "natural_language", "task", "comparison", "conflict"].includes(prompt.expression)) {
    throw new BadRequestException("expression不是允许的枚举值");
  }
  if (!String(prompt.hypothesis || "").trim()) {
    throw new BadRequestException("hypothesis不能为空");
  }
  if (!Array.isArray(prompt.requiredTerms) || !prompt.requiredTerms.length) {
    throw new BadRequestException("requiredTerms至少包含一个必保留条件");
  }
  if (!Array.isArray(prompt.judgmentCriteria) || !prompt.judgmentCriteria.length) {
    throw new BadRequestException("judgmentCriteria至少包含一条判断标准");
  }
  const normalizedText = normalizedPrompt(prompt.promptText);
  const missingTerms = prompt.requiredTerms.filter((term) => {
    const required = normalizedPrompt(term);
    return required && !normalizedText.includes(required);
  });
  if (missingTerms.length) {
    throw new BadRequestException(`问题文本遗漏必须保留条件: ${missingTerms.join(", ")}`);
  }
  if (prompt.mode === "blind" && leaksProductIdentity(prompt.promptText, product)) {
    throw new BadRequestException("盲测问题不能包含我方品牌或ASIN");
  }
  if (prompt.sessionPolicy === "shared_sequence" && !String(prompt.sessionGroup || "").trim()) {
    throw new BadRequestException("连续会话问题必须指定sessionGroup");
  }

  const stableFacts = new Map(product.stableFacts.map((fact) => [fact.id, fact]));
  const unknownEvidence = prompt.evidenceFactIds.filter((factId) => !stableFacts.has(factId));
  if (unknownEvidence.length) {
    throw new BadRequestException(`问题引用了不存在的商品证据: ${unknownEvidence.join(", ")}`);
  }
  if (prompt.scoreEligible) {
    if (prompt.sessionPolicy !== "fresh") {
      throw new BadRequestException("主推荐指数只允许使用独立新会话对照题");
    }
    if (prompt.testRole !== "positive_control" || prompt.expectedMatch !== "eligible") {
      throw new BadRequestException("计分题必须是expectedMatch=eligible的positive_control");
    }
    if (!prompt.evidenceFactIds.length) {
      throw new BadRequestException("计分题必须绑定页面证据");
    }
    const unsupported = prompt.evidenceFactIds.filter((factId) => {
      const fact = stableFacts.get(factId);
      return !fact || !SCORE_ELIGIBLE_EVIDENCE_SECTIONS.has(fact.sourceSection);
    });
    if (unsupported.length) {
      throw new BadRequestException("计分题只能绑定标题、规格、五点、A+或类目路径中的稳定证据");
    }
  }
  if (prompt.testRole === "negative_control"
    && (prompt.scoreEligible || prompt.expectedMatch !== "ineligible")) {
    throw new BadRequestException("负控制题必须不计分且expectedMatch=ineligible");
  }
  if (["diagnostic", "aided_recognition"].includes(prompt.testRole) && prompt.scoreEligible) {
    throw new BadRequestException("诊断题和辅助认知题不能计入主推荐指数");
  }
}

function assertPlanTrackLimits(prompts: Array<PromptCaseDefinition | PromptCase>): void {
  const enabled = prompts.filter((item) => item.enabled);
  const fresh = enabled.filter((item) => item.sessionPolicy === "fresh");
  if (fresh.length > 5) {
    throw new BadRequestException("独立新会话对照组最多只能启用5个问题");
  }
  const progressive = enabled.filter((item) => item.sessionPolicy === "shared_sequence");
  const groups = new Map<string, Array<PromptCaseDefinition | PromptCase>>();
  progressive.forEach((item) => {
    const group = String(item.sessionGroup || "").trim();
    groups.set(group, [...(groups.get(group) || []), item]);
  });
  if (groups.size > 1) {
    throw new BadRequestException("每个商品只能启用一个单会话递进组");
  }
  if ([...groups.values()].some((items) => items.length > 6)) {
    throw new BadRequestException("单一对话框递进组最多只能启用6个问题");
  }
}

function hasPromptContentChange(before: PromptCaseDefinition | PromptCase, after: PromptCaseDefinition | PromptCase): boolean {
  const normalizeGroup = (value?: string) => String(value || "").trim() || undefined;
  const normalizedArray = (value: string[]) => [...new Set(value.map((item) => item.trim()))].sort();
  const editableSnapshot = (item: PromptCaseDefinition | PromptCase) => ({
    promptText: item.promptText,
    testRole: item.testRole,
    enabled: item.enabled,
    scoreEligible: item.scoreEligible,
    hypothesis: item.hypothesis,
    expectedMatch: item.expectedMatch,
    evidenceFactIds: normalizedArray(item.evidenceFactIds),
    requiredTerms: normalizedArray(item.requiredTerms),
    judgmentCriteria: normalizedArray(item.judgmentCriteria),
    sessionPolicy: item.sessionPolicy,
    sessionGroup: normalizeGroup(item.sessionGroup)
  });
  return JSON.stringify(editableSnapshot(before)) !== JSON.stringify(editableSnapshot(after));
}

function mapTurn(turn: any): ConversationTurn {
  return {
    id: turn.id, runId: turn.runId, promptCaseId: turn.promptCaseId, promptText: turn.promptText, responseText: turn.responseText,
    recommendations: parseJson<RecommendationItem[]>(turn.recommendationsJson, []), screenshotPath: turn.screenshotPath || undefined,
    selectorVersion: turn.selectorVersion, status: turn.status, errorCode: turn.errorCode || undefined, errorMessage: turn.errorMessage || undefined,
    capturedAt: new Date(turn.capturedAt).toISOString()
  };
}

function sanitizeRecommendations(input: unknown): RecommendationItem[] {
  if (!Array.isArray(input)) return [];
  const seen = new Set<string>();
  return input.slice(0, 100).flatMap((raw, index) => {
    if (!raw || typeof raw !== "object") return [];
    const item = raw as Partial<RecommendationItem>;
    const asin = String(item.asin || "").toUpperCase().slice(0, 10);
    const title = String(item.title || "").replace(/\s+/g, " ").trim().slice(0, 500);
    const key = asin || title.toLowerCase();
    if (!key || seen.has(key)) return [];
    seen.add(key);
    return [{
      asin, title, brand: String(item.brand || "").slice(0, 120), rank: Math.max(1, Math.min(100, Number(item.rank || index + 1))),
      url: String(item.url || "").slice(0, 1500), priceText: String(item.priceText || "").slice(0, 100), ratingText: String(item.ratingText || "").slice(0, 100),
      reviewCountText: String(item.reviewCountText || "").slice(0, 100), sponsored: Boolean(item.sponsored), deliveryText: String(item.deliveryText || "").slice(0, 300), evidenceText: String(item.evidenceText || "").slice(0, 1000)
    }];
  }).slice(0, 100);
}

function deterministicDiagnoses(report: RunReport): Diagnosis[] {
  const diagnoses: Diagnosis[] = [];
  const score = report.score;
  const turnsByPrompt = new Map(report.turns.map((turn) => [turn.promptCaseId, turn]));
  const alignedJudgments = score?.judgments.filter((judgment) => judgment.scoreEligible) || [];
  const alignedTurnIds = alignedJudgments.map((judgment) => turnsByPrompt.get(judgment.promptCaseId)?.id || "").filter(Boolean);
  const missedTurnIds = alignedJudgments.filter((judgment) => !judgment.ownIncluded).map((judgment) => turnsByPrompt.get(judgment.promptCaseId)?.id || "").filter(Boolean);
  if (score && score.sampleSize > 0 && score.dimensions.inclusion < 30) diagnoses.push({ category: "recall_gap", severity: "high", observation: "我方商品很少进入页面证据对齐的正向题完整返回列表。", supportingTurnIds: missedTurnIds.slice(0, 10), evidenceFactIds: [], inference: "当前可观察结果显示正向对齐题召回不足，但不能证明Amazon内部使用了特定权重。", recommendedAction: "优先检查标题、五点和规格是否明确承接这些正向题对应的品类、受众与功能证据。" });
  if (score && score.sampleSize > 0 && score.dimensions.evidence < 45) diagnoses.push({ category: "intent_evidence_gap", severity: "medium", observation: "Alexa商品卡片对正向题所绑定页面证据的明确承接较弱。", supportingTurnIds: alignedTurnIds.slice(0, 8), evidenceFactIds: report.product.stableFacts.map((fact) => fact.id).slice(0, 12), inference: "Alexa可能缺少可明确引用的页面证据，或测试问题与页面卖点不一致。", recommendedAction: "把已验证的功能、场景和人群表达放入可索引的标题、Bullet和规格字段。" });
  if (score && score.sampleSize >= 6 && score.dimensions.consistency < 45) diagnoses.push({ category: "personalization_noise", severity: "medium", observation: "相同正向意图的重复推荐重合率较低。", supportingTurnIds: alignedTurnIds.slice(0, 10), evidenceFactIds: [], inference: "结果可能受到推荐波动、账户个性化或实时零售信号影响。", recommendedAction: "增加重复次数、固定测试账户标签，并分时段复测。" });
  if (score?.probes.negativeControl.sampleSize && (score.probes.negativeControl.passRate || 0) < 80) diagnoses.push({ category: "attribute_conflict", severity: "medium", observation: "我方商品在部分明确不兼容的鞋类负控制题中仍进入完整返回列表。", supportingTurnIds: score.judgments.filter((judgment) => judgment.testRole === "negative_control" && judgment.constraintOutcome === "fail").map((judgment) => turnsByPrompt.get(judgment.promptCaseId)?.id || "").filter(Boolean).slice(0, 8), evidenceFactIds: [], inference: "这是可观察的错误入选现象，不能单独归因于页面或Amazon内部算法。", recommendedAction: "检查Alexa返回卡片的商品身份与类目解析，并复测负控制条件。" });
  if (score?.probes.aidedRecognition.sampleSize && (score.probes.aidedRecognition.passRate || 0) < 50) diagnoses.push({ category: "product_recognition", severity: "medium", observation: "明确提供品牌或ASIN后，Alexa仍未稳定识别我方商品家族。", supportingTurnIds: score.judgments.filter((judgment) => judgment.testRole === "aided_recognition").map((judgment) => turnsByPrompt.get(judgment.promptCaseId)?.id || "").filter(Boolean).slice(0, 8), evidenceFactIds: [], inference: "商品身份解析可能不稳定；辅助识别结果不代表盲测召回能力。", recommendedAction: "核对父体、已选子体和ASIN别名映射，并单独复测辅助识别题。" });
  if (!diagnoses.length) diagnoses.push({ category: "unknown", severity: "low", observation: "当前结果未出现单一、稳定的不推荐原因。", supportingTurnIds: [], evidenceFactIds: [], inference: "仅凭黑盒对话无法确认内部排序原因。", recommendedAction: "结合意图簇拆分结果，继续进行小规模受控测试。" });
  return diagnoses;
}
