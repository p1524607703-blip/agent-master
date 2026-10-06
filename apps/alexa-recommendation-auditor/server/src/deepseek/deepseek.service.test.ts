import { afterEach, describe, expect, it, vi } from "vitest";
import {
  FOOTWEAR_PROMPT_VERSION,
  SCHEMA_VERSION,
  type EvidenceFact,
  type ProductSnapshot,
  type PromptCaseDefinition
} from "@alexa-auditor/contracts";
import { deterministicPromptPlan } from "../runs/prompt-builder";
import { HermesTransportService } from "../hermes/hermes-transport.service";
import { DeepSeekService } from "./deepseek.service";

const now = new Date().toISOString();
const fact = (id: string, field: string, value: string, sourceText: string): EvidenceFact => ({
  id, field, value, evidenceType: "page_validated", sourceSection: "bullets", sourceText, confidence: "high", capturedAt: now
});

const product: ProductSnapshot = {
  asin: "B012345678", url: "https://www.amazon.com/dp/B012345678", marketplace: "amazon.com",
  title: "Example Women's Comfort Walking Shoes", brand: "ExampleBrand", breadcrumb: [], bullets: [],
  specifications: { Material: "mesh" }, aPlusText: "", reviewSummary: "", qaText: "",
  stableFacts: [
    fact("type", "product_type", "walking_shoes", "Women's walking shoes"),
    fact("audience", "audience_intent", "women", "Designed for women"),
    fact("function", "function_intent", "cushioning", "Cushioning for daily comfort"),
    fact("capability", "capability_intent", "breathable", "Breathable mesh upper"),
    fact("body", "body_need_intent", "comfortable_fit", "Comfortable fit"),
    fact("event", "event_intent", "daily_walking", "For daily walking"),
    fact("location", "location_intent", "city", "City walking"),
    fact("material", "material", "mesh", "Mesh material"),
    fact("substitute", "substitute_intent", "casual_sneakers", "Alternative to casual sneakers")
  ], volatileFacts: [],
  intentProfile: {
    primary_domain: "clothing_shoes_jewelry", secondary_domain: [], product_type: ["walking_shoes"], audience_intent: ["women"],
    function_intent: ["cushioning"], capability_intent: ["breathable"], event_intent: ["daily_walking"], location_intent: ["city"],
    body_need_intent: ["comfortable_fit"], time_intent: [], substitute_intent: ["casual_sneakers"], complement_intent: [], latent_task: "", intent_stage: "consideration",
    evidence_type: ["page_validated"], confidence_level: "high", intent_cluster: "walking_shoes", routing_action: "cluster_route"
  }, accountLabel: "test", selectorVersion: "fixture", schemaVersion: SCHEMA_VERSION, capturedAt: now
};

function responseFor(plan: PromptCaseDefinition[], mutate?: (item: PromptCaseDefinition, index: number) => string) {
  return {
    schemaVersion: SCHEMA_VERSION,
    promptVersion: FOOTWEAR_PROMPT_VERSION,
    rewrites: plan.map((item, index) => ({
      templateId: item.templateId,
      promptText: mutate?.(item, index) || item.promptText,
      rewriteReason: index === 0 ? "Improves natural phrasing while retaining the case specification." : "The deterministic wording is already clear."
    }))
  };
}

function mockCompletion(payload: unknown) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    headers: new Headers({ "x-hermes-session-id": "hermes-session-test" }),
    json: async () => ({
      model: "hermes-agent",
      choices: [{ message: { content: JSON.stringify(payload) } }],
      usage: { prompt_tokens: 100, completion_tokens: 20, total_tokens: 120 }
    }),
    text: async () => ""
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("DeepSeek controlled footwear prompt rewrite", () => {
  it("accepts prompt-text-only rewrites and emits a developer audit with scoring rules", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke");
    const safeRewrite = "Treat this message as a new independent request. Answer only from the requirements in this message, without referring to or continuing any prior conversation. Please help me find women walking shoes for everyday wear. List every candidate you actually recommend in this turn, not just a Top 5. In natural recommendation order, use one line per item: product name | current price | Amazon product link. If the candidate-pool size or price cannot be verified, say \"unable to verify\".";
    const payload = responseFor(plan, (item, index) => index === 0
      ? safeRewrite
      : item.promptText);
    const fetchMock = mockCompletion(payload);
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan, {
      requestId: "request-1",
      runId: "run-1",
      productSnapshotId: "product-1",
      productAsin: product.asin,
      schemaVersion: SCHEMA_VERSION,
      promptVersion: FOOTWEAR_PROMPT_VERSION,
      templateIds: plan.map((item) => item.templateId)
    });

    expect(prompts[0].promptText).toBe(safeRewrite);
    expect(prompts[0].generatedBy).toBe("deepseek_rewrite");
    expect(prompts[0].originalPromptText).toBe(plan[0].promptText);
    expect(prompts[0].hypothesis).toBe(plan[0].hypothesis);
    expect(prompts[0].evidenceFactIds).toEqual(plan[0].evidenceFactIds);
    expect(prompts[0].judgmentCriteria).toEqual(plan[0].judgmentCriteria);
    expect(audit.status).toBe("rewritten");
    expect(audit).toMatchObject({
      transport: "hermes_agent",
      requestId: "request-1",
      hermesSessionId: "hermes-session-test",
      model: "hermes-agent",
      usage: { promptTokens: 100, completionTokens: 20, totalTokens: 120 }
    });
    expect(audit.summary).toEqual({ caseCount: 5, rewrittenCount: 1, scoreEligibleCount: 1 });
    expect(audit.cases[0]).toMatchObject({
      templateId: plan[0].templateId,
      originalPromptText: plan[0].promptText,
      finalPromptText: prompts[0].promptText,
      judgmentCriteria: plan[0].judgmentCriteria,
      changed: true
    });
    expect(service.getPromptGenerationAudit()).toEqual(audit);

    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    const userPayload = JSON.parse(requestBody.messages[1].content);
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:8642/v1/chat/completions");
    expect(requestBody).toMatchObject({ model: "hermes-agent", stream: false });
    expect(requestBody.metadata).toBeUndefined();
    expect(userPayload.audit_context).toEqual({
      operation: "question_rewrite",
      request_id: "request-1",
      run_id: "run-1",
      product_snapshot_id: "product-1",
      product_asin: product.asin,
      schema_version: SCHEMA_VERSION,
      prompt_version: FOOTWEAR_PROMPT_VERSION,
      template_ids: plan.map((item) => item.templateId)
    });
    expect(userPayload.cases[0]).toMatchObject({
      templateId: plan[0].templateId,
      testRole: plan[0].testRole,
      expectedMatch: plan[0].expectedMatch,
      judgmentCriteria: plan[0].judgmentCriteria
    });
  });

  it("rejects a rewrite that removes a required footwear term and falls back atomically", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke");
    mockCompletion(responseFor(plan, (item, index) => index === 1 ? "Recommend five comfortable products." : item.promptText));
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan);

    expect(prompts).toEqual(plan);
    expect(audit.status).toBe("fallback");
    expect(audit.fallbackReason).toContain("removed required term");
    expect(audit.summary.rewrittenCount).toBe(0);
  });

  it("keeps Simplified Chinese rewrites in-language and audits the selected language", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke", "zh-CN");
    const fetchMock = mockCompletion(responseFor(plan, (item, index) => index === 0
      ? `请帮我${item.promptText.replace(/^请/u, "")}`
      : item.promptText));
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan, {
      requestId: "request-zh",
      promptLanguage: "zh-CN"
    });

    expect(prompts[0].promptText).toMatch(/^请帮我/u);
    expect(prompts.every((item) => /[\u3400-\u9fff]/u.test(item.promptText))).toBe(true);
    expect(audit).toMatchObject({ status: "rewritten", promptLanguage: "zh-CN" });

    const requestBody = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(requestBody.messages[0].content).toContain("Simplified Chinese");
    expect(JSON.parse(requestBody.messages[1].content).promptLanguage).toBe("zh-CN");
  });

  it("rejects a Simplified Chinese rewrite that removes a required term", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke", "zh-CN");
    const requiredTerm = plan[1].requiredTerms.at(-1)!;
    mockCompletion(responseFor(plan, (item, index) => index === 1
      ? item.promptText.replace(requiredTerm, "")
      : item.promptText));
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan, {
      promptLanguage: "zh-CN"
    });

    expect(prompts).toEqual(plan);
    expect(audit.status).toBe("fallback");
    expect(audit.fallbackReason).toContain("removed required term");
    expect(audit.fallbackReason).toContain(requiredTerm);
  });

  it("rejects unapproved shopping actions added to a Simplified Chinese blind question", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke", "zh-CN");
    mockCompletion(responseFor(plan, (item, index) => index === 0
      ? `${item.promptText} 并把第一款加入购物车。`
      : item.promptText));
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan, {
      promptLanguage: "zh-CN"
    });

    expect(prompts).toEqual(plan);
    expect(audit.status).toBe("fallback");
    expect(audit.fallbackReason).toContain("prohibited constraint or action");
  });

  it("rejects brand leakage in blind questions", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke");
    mockCompletion(responseFor(plan, (item, index) => index === 0 ? `${item.promptText} Include ExampleBrand.` : item.promptText));
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan);

    expect(prompts).toEqual(plan);
    expect(audit.status).toBe("fallback");
    expect(audit.fallbackReason).toContain("leaked the tested product identity");
  });

  it("records deterministic questions and judgment criteria when Hermes is disabled", async () => {
    vi.stubEnv("HERMES_API_URL", "");
    vi.stubEnv("DEEPSEEK_API_KEY", "must-be-ignored");
    vi.stubEnv("DEEPSEEK_BASE_URL", "https://should-never-be-called.invalid");
    const plan = deterministicPromptPlan(product, "smoke");
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan);

    expect(prompts).toEqual(plan);
    expect(audit.status).toBe("deterministic_only");
    expect(audit.fallbackReason).toBe("hermes_not_configured");
    expect(audit.cases.every((item) => item.judgmentCriteria.length > 0)).toBe(true);
    expect(audit.summary.caseCount).toBe(5);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("routes intent refinement through Hermes with an auditable request context", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const fetchMock = mockCompletion(product.intentProfile);
    const service = new DeepSeekService(new HermesTransportService());

    await expect(service.refineIntentProfile(product, {
      requestId: "intent-request",
      productAsin: product.asin,
      schemaVersion: SCHEMA_VERSION
    })).resolves.toEqual(product.intentProfile);

    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(JSON.parse(body.messages[1].content).audit_context).toEqual({
      operation: "intent_profile_refinement",
      request_id: "intent-request",
      product_asin: product.asin,
      schema_version: SCHEMA_VERSION
    });
    expect(service.getLastModelInvocation("intent_profile_refinement")).toMatchObject({
      status: "succeeded",
      hermesSessionId: "hermes-session-test",
      requestId: "intent-request"
    });
  });

  it("routes run diagnosis through Hermes and records run correlation", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const diagnosis = {
      category: "unknown",
      severity: "low",
      observation: "No stable gap.",
      supportingTurnIds: [],
      evidenceFactIds: [],
      inference: "Evidence is insufficient.",
      recommendedAction: "Collect more samples."
    } as const;
    const fetchMock = mockCompletion({ diagnoses: [diagnosis] });
    const service = new DeepSeekService(new HermesTransportService());

    const result = await service.diagnose({
      run: { id: "run-diagnosis", productSnapshotId: "product-1", promptVersion: "footwear-v4.0.0" },
      product: { ...product, id: "product-1" },
      turns: [],
      score: null,
      diagnoses: [],
      auditEvents: []
    } as any, [diagnosis as any], { requestId: "diagnosis-request", runId: "run-diagnosis" });

    expect(result).toEqual([diagnosis]);
    const body = JSON.parse(fetchMock.mock.calls[0][1].body as string);
    expect(JSON.parse(body.messages[1].content).audit_context).toMatchObject({
      operation: "run_diagnosis",
      request_id: "diagnosis-request",
      run_id: "run-diagnosis",
      product_snapshot_id: "product-1",
      product_asin: product.asin
    });
    expect(service.getLastModelInvocation("run_diagnosis", "run-diagnosis")).toMatchObject({ status: "succeeded" });
  });

  it("falls back with a sanitized Hermes status code and never exposes an upstream body", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      headers: new Headers(),
      text: async () => "Bearer sk-secret-should-not-enter-audit"
    }));
    const service = new DeepSeekService(new HermesTransportService());

    const { prompts, audit } = await service.generatePromptPlanWithAudit(product, plan, { requestId: "failed-request" });

    expect(prompts).toEqual(plan);
    expect(audit).toMatchObject({ status: "fallback", fallbackReason: "hermes_http_503", requestId: "failed-request" });
    expect(JSON.stringify(audit)).not.toContain("sk-secret");
  });

  it("keeps Hermes session telemetry when a 200 response contains a non-JSON provider error", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    const plan = deterministicPromptPlan(product, "smoke");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "x-hermes-session-id": "api-balance-failure" }),
      json: async () => ({
        model: "hermes-agent",
        choices: [{ message: { content: "API call failed after 3 retries: HTTP 402: Insufficient Balance" } }],
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
      })
    }));
    const service = new DeepSeekService(new HermesTransportService());

    const { audit } = await service.generatePromptPlanWithAudit(product, plan, { requestId: "balance-request" });

    expect(audit).toMatchObject({
      status: "fallback",
      fallbackReason: "hermes_upstream_insufficient_balance",
      hermesSessionId: "api-balance-failure",
      usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 }
    });
    expect(JSON.stringify(audit)).not.toContain("Insufficient Balance");
  });
});
