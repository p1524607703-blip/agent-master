import { BadRequestException, ConflictException } from "@nestjs/common";
import { describe, expect, it, vi } from "vitest";
import { FOOTWEAR_PROMPT_VERSION, SCHEMA_VERSION, type ConversationTurn, type ExperimentRun, type ProductSnapshot, type PromptCase } from "@alexa-auditor/contracts";
import { RunsService } from "./runs.service";

const now = new Date().toISOString();

const product: ProductSnapshot = {
  id: "product-1",
  asin: "B0TEST0001",
  requestedAsin: "B0TEST0001",
  resolvedAsin: "B0TEST0002",
  asinAliases: ["B0TEST0001", "B0TEST0002"],
  url: "https://www.amazon.com/dp/B0TEST0001",
  marketplace: "amazon.com",
  title: "Acme Women's Arch Support Flip Flops",
  brand: "Acme",
  breadcrumb: ["Shoes", "Flip-Flops"],
  bullets: ["Arch support for everyday comfort"],
  specifications: { Department: "Women" },
  aPlusText: "",
  reviewSummary: "",
  qaText: "",
  stableFacts: [
    { id: "fact-type", field: "product_type", value: "flip_flops", evidenceType: "page_validated", sourceSection: "title", sourceText: "Women's flip flops", confidence: "high", capturedAt: now },
    { id: "fact-arch", field: "function_intent", value: "arch_support", evidenceType: "page_validated", sourceSection: "bullets", sourceText: "Arch support", confidence: "high", capturedAt: now },
    { id: "fact-review", field: "body_need_intent", value: "wide_feet", evidenceType: "page_validated", sourceSection: "review_summary", sourceText: "A reviewer mentions wide feet", confidence: "medium", capturedAt: now }
  ],
  volatileFacts: [],
  intentProfile: {
    primary_domain: "clothing_shoes_jewelry", secondary_domain: [], product_type: ["flip_flops"], audience_intent: ["women"],
    function_intent: ["arch_support"], capability_intent: [], event_intent: [], location_intent: [], body_need_intent: [],
    time_intent: [], substitute_intent: [], complement_intent: [], latent_task: "find supportive flip flops", intent_stage: "consideration",
    evidence_type: ["page_validated"], confidence_level: "high", intent_cluster: "supportive_flip_flops", routing_action: "cluster_route"
  },
  accountLabel: "test-account",
  selectorVersion: "fixture-v1",
  schemaVersion: SCHEMA_VERSION,
  capturedAt: now
};

function prompt(overrides: Partial<PromptCase> = {}): PromptCase {
  return {
    id: "prompt-1", templateId: "template-1", enabled: true, slot: "function", mode: "blind", expression: "direct",
    promptText: "Recommend five women's flip flops with arch support.", testRole: "positive_control", scoreEligible: true,
    hypothesis: "Page-backed arch support should make the product eligible.", expectedMatch: "eligible",
    evidenceFactIds: ["fact-type", "fact-arch"], requiredTerms: ["women's", "flip flops", "arch support"],
    judgmentCriteria: ["Record complete-list inclusion and rank."], promptVersion: FOOTWEAR_PROMPT_VERSION, sessionPolicy: "fresh",
    generatedBy: "deterministic", repeatIndex: 1, sequence: 1, status: "pending", revision: 1, editable: true,
    ...overrides
  };
}

function run(promptCases: PromptCase[], overrides: Partial<ExperimentRun> = {}): ExperimentRun {
  return {
    id: "run-1", productSnapshotId: "product-1", status: "draft", accountLabel: "test-account", runSeed: "seed",
    preset: "calibration", promptLanguage: "en-US", sessionPolicy: "fresh", promptVersion: FOOTWEAR_PROMPT_VERSION,
    questionPlanRevision: 1, questionPlanEditable: true, promptCount: 1, repetitions: 1, totalTurns: promptCases.filter((item) => item.enabled).length,
    completedTurns: 0, promptCases, score: null, diagnoses: [], createdAt: now, updatedAt: now,
    ...overrides
  };
}

function harness(currentRun: ExperimentRun) {
  let runClaimed = false;
  let promptClaimed = false;
  let completedIncrements = 0;
  const turns = new Map<string, unknown>();
  const events: any[] = [];
  const promptUpdates: any[] = [];
  const claimWhere: any[] = [];
  const prisma: any = {
    experimentRun: {
      create: vi.fn(async ({ data }: any) => ({ id: "draft-run", promptVersion: FOOTWEAR_PROMPT_VERSION, ...data })),
      updateMany: vi.fn(async ({ data }: any) => {
        if (data.status === "running") {
          if (runClaimed) return { count: 0 };
          runClaimed = true;
        }
        return { count: 1 };
      }),
      update: vi.fn(async ({ data }: any) => {
        if (data.completedTurns?.increment) completedIncrements += data.completedTurns.increment;
        return {};
      })
    },
    promptCase: {
      create: vi.fn(async ({ data }: any) => data),
      updateMany: vi.fn(async ({ where, data }: any) => {
        promptUpdates.push({ where, data });
        if (data.status === "running") {
          claimWhere.push(where);
          if (promptClaimed) return { count: 0 };
          promptClaimed = true;
        }
        return { count: 1 };
      }),
      update: vi.fn(async () => ({}))
    },
    conversationTurn: {
      findUnique: vi.fn(async ({ where }: any) => turns.get(where.promptCaseId) || null),
      create: vi.fn(async ({ data }: any) => {
        turns.set(data.promptCaseId, data);
        return data;
      }),
      update: vi.fn(async () => ({}))
    },
    runEvent: {
      create: vi.fn(async ({ data }: any) => {
        events.push(data);
        return data;
      })
    },
    $transaction: vi.fn(async (value: any) => typeof value === "function" ? value(prisma) : Promise.all(value))
  };
  const products = { get: vi.fn(async () => product) };
  const deepseek = {
    enabled: false,
    transportStatus: { mode: "hermes_only", configured: false },
    generatePromptPlanWithAudit: vi.fn(async (_product: unknown, fallback: PromptCase[]) => ({
      prompts: fallback,
      audit: { status: "deterministic_only", model: "hermes-agent" }
    })),
    diagnose: vi.fn(async (_report: unknown, fallback: unknown) => fallback),
    getLastModelInvocation: vi.fn(() => null)
  };
  const eventBus = { emit: vi.fn() };
  const service = new RunsService(prisma, products as any, deepseek as any, eventBus as any);
  vi.spyOn(service, "get").mockImplementation(async () => currentRun);
  return { service, prisma, deepseek, turns, events, promptUpdates, claimWhere, completedIncrements: () => completedIncrements };
}

describe("RunsService execution gates", () => {
  it("correlates Hermes question generation with the draft run, product and template versions", async () => {
    const current = run([prompt()]);
    const { service, deepseek } = harness(current);

    await service.create({
      productSnapshotId: "product-1",
      accountLabel: "test-account",
      preset: "smoke",
      repetitions: 1,
      runSeed: "fixed-seed"
    });

    const [passedProduct, fallback, context] = deepseek.generatePromptPlanWithAudit.mock.calls[0];
    expect(passedProduct).toBe(product);
    expect(fallback).toHaveLength(5);
    expect(context).toMatchObject({
      runId: "draft-run",
      productSnapshotId: "product-1",
      productAsin: "B0TEST0002",
      schemaVersion: SCHEMA_VERSION,
      promptVersion: FOOTWEAR_PROMPT_VERSION,
      templateIds: fallback.map((item: PromptCase) => item.templateId)
    });
    expect(context.requestId).toMatch(/^[a-f0-9]{32}$/);
  });

  it("propagates Simplified Chinese through deterministic generation, Hermes context, and audit events", async () => {
    const current = run([prompt()]);
    const { service, prisma, deepseek, events } = harness(current);

    await service.create({
      productSnapshotId: "product-1",
      accountLabel: "test-account",
      preset: "smoke",
      promptLanguage: "zh-CN",
      repetitions: 1,
      runSeed: "fixed-zh-seed"
    });

    const [, fallback, context] = deepseek.generatePromptPlanWithAudit.mock.calls[0];
    expect(context.promptLanguage).toBe("zh-CN");
    expect(fallback).toHaveLength(5);
    expect(fallback.every((item: PromptCase) => /[\u3400-\u9fff]/u.test(item.promptText))).toBe(true);
    expect(prisma.experimentRun.create).toHaveBeenCalledWith(expect.objectContaining({
      data: expect.objectContaining({ promptLanguage: "zh-CN" })
    }));
    const generated = JSON.parse(events.find((event) => event.type === "question_plan_generated").payloadJson);
    expect(generated.promptLanguage).toBe("zh-CN");
    expect(generated.questions.every((item: PromptCase) => /[\u3400-\u9fff]/u.test(item.promptText))).toBe(true);
  });

  it("starts a locked plan with an atomic compare-and-swap", async () => {
    const current = run([prompt()], { status: "ready", questionPlanEditable: false, questionPlanApprovedAt: now, questionPlanLockedAt: now });
    const { service, events } = harness(current);

    const results = await Promise.allSettled([service.start(current.id), service.start(current.id)]);

    expect(results.filter((result) => result.status === "fulfilled")).toHaveLength(1);
    const rejection = results.find((result) => result.status === "rejected") as PromiseRejectedResult;
    expect(rejection.reason).toBeInstanceOf(ConflictException);
    expect(events.filter((event) => event.type === "run_started")).toHaveLength(1);
  });

  it("rejects a pending run created with an older prompt template", async () => {
    const current = run([prompt({ promptVersion: "footwear-v4.0.0" })], {
      status: "ready",
      promptVersion: "footwear-v4.0.0",
      questionPlanEditable: false,
      questionPlanApprovedAt: now,
      questionPlanLockedAt: now
    });
    const { service } = harness(current);

    await expect(service.start(current.id)).rejects.toThrow(`问题集版本 footwear-v4.0.0 已过期，请使用 ${FOOTWEAR_PROMPT_VERSION} 重新生成问题集`);
  });

  it.each([
    { enabled: false, status: "pending" as const },
    { enabled: true, status: "skipped" as const }
  ])("rejects disabled or non-pending prompt turns: %o", async (state) => {
    const current = run([prompt(state)], { status: "running" });
    const { service, completedIncrements } = harness(current);

    await expect(service.addTurn(current.id, completedTurn(current.promptCases[0].id))).rejects.toBeInstanceOf(BadRequestException);
    expect(completedIncrements()).toBe(0);
  });

  it("claims enabled+pending exactly once and makes duplicate submission idempotent", async () => {
    const current = run([prompt()], { status: "running", totalTurns: 2 });
    const { service, claimWhere, completedIncrements } = harness(current);
    vi.spyOn(service, "report").mockResolvedValue({ score: null } as any);

    await service.addTurn(current.id, completedTurn(current.promptCases[0].id));
    await service.addTurn(current.id, completedTurn(current.promptCases[0].id));

    expect(claimWhere).toEqual([{ id: "prompt-1", runId: "run-1", enabled: true, status: "pending" }]);
    expect(completedIncrements()).toBe(1);
  });

  it.each(["context_isolation_failed", "response_timeout"])("stops the run after executor integrity error %s", async (errorCode) => {
    const current = run([prompt()], { status: "running", totalTurns: 2 });
    const { service } = harness(current);
    const stop = vi.spyOn(service, "stop").mockResolvedValue({ ...current, status: "stopped" });

    await service.addTurn(current.id, {
      ...completedTurn(current.promptCases[0].id),
      status: "failed",
      errorCode,
      errorMessage: "integrity guard"
    });

    expect(stop).toHaveBeenCalledWith(current.id, `safety_stop:${errorCode}`);
  });

  it("refuses approval when the enabled plan has no evidence-aligned positive score case", async () => {
    const baseline = prompt({ testRole: "baseline", scoreEligible: false, expectedMatch: "neutral" });
    const current = run([baseline]);
    const { service } = harness(current);

    await expect(service.approveQuestionPlan(current.id, { expectedRevision: 1 })).rejects.toThrow(/正向计分题/);
  });

  it("allows the smoke preset to run as diagnostic-only when the page has no aligned score case", async () => {
    const baseline = prompt({ testRole: "baseline", scoreEligible: false, expectedMatch: "neutral" });
    const current = run([baseline], { preset: "smoke" });
    const { service, events } = harness(current);

    await expect(service.approveQuestionPlan(current.id, { expectedRevision: 1 })).resolves.toBe(current);
    const audit = JSON.parse(events.find((event) => event.type === "question_plan_approved").payloadJson);
    expect(audit.diagnosticOnly).toBe(true);
  });

  it("prevents developer edits from creating more than five independent conversations", async () => {
    const controls = Array.from({ length: 5 }, (_, index) => prompt({
      id: `fresh-${index + 1}`,
      templateId: `fresh-template-${index + 1}`,
      sequence: index + 1
    }));
    const progressive = prompt({
      id: "progressive-1",
      templateId: "progressive-template-1",
      sequence: 6,
      testRole: "diagnostic",
      scoreEligible: false,
      expectedMatch: "diagnostic_only",
      evidenceFactIds: [],
      sessionPolicy: "shared_sequence",
      sessionGroup: "footwear_progressive_intent"
    });
    const current = run([...controls, progressive]);
    const { service } = harness(current);

    await expect(service.updatePrompt(current.id, progressive.id, {
      expectedRevision: 1,
      changeReason: "Move this prompt into an independent session.",
      sessionPolicy: "fresh",
      sessionGroup: null
    })).rejects.toThrow(/最多只能启用5个问题/);
  });

  it("revalidates score evidence and rejects review-only facts at approval", async () => {
    const reviewBacked = prompt({ evidenceFactIds: ["fact-review"] });
    const current = run([reviewBacked]);
    const { service } = harness(current);

    await expect(service.approveQuestionPlan(current.id, { expectedRevision: 1 })).rejects.toThrow(/稳定证据/);
  });

  it("rejects semantic no-op edits even when array order changes", async () => {
    const selected = prompt({ evidenceFactIds: ["fact-type", "fact-arch"] });
    const current = run([selected]);
    const { service } = harness(current);

    await expect(service.updatePrompt(current.id, selected.id, {
      expectedRevision: 1,
      changeReason: "Only reorder metadata",
      evidenceFactIds: ["fact-arch", "fact-type"]
    })).rejects.toThrow(/没有检测到/);
  });

  it("writes audit after-state from the exact persisted clear operation", async () => {
    const selected = prompt({ sessionPolicy: "shared_sequence", sessionGroup: "sequence-a" });
    const current = run([selected]);
    const { service, events, promptUpdates } = harness(current);

    await service.updatePrompt(current.id, selected.id, {
      expectedRevision: 1,
      changeReason: "Move this prompt back to an isolated session",
      sessionPolicy: "fresh",
      sessionGroup: null
    });

    const stored = promptUpdates.find((entry) => entry.where.templateId === selected.templateId)?.data;
    expect(stored.sessionGroup).toBeNull();
    expect(stored.rewriteReason).toBe("Move this prompt back to an isolated session");
    const audit = JSON.parse(events.find((event) => event.type === "question_plan_updated").payloadJson);
    expect(audit.after.sessionGroup).toBeUndefined();
    expect(audit.after.rewriteReason).toBe(stored.rewriteReason);
  });
});

function completedTurn(promptCaseId: string): ConversationTurn {
  return {
    runId: "run-1", promptCaseId, promptText: "prompt", responseText: "answer", recommendations: [],
    selectorVersion: "fixture-v1", status: "completed", capturedAt: now
  };
}
