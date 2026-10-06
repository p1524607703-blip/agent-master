import type {
  ApproveQuestionPlanRequest,
  CreateRunRequest,
  ExperimentRun,
  ProductSnapshot,
  RunAuditEvent,
  UpdatePromptCaseRequest
} from "@alexa-auditor/contracts";

export class AuditorApi {
  constructor(public serverUrl: string, public token: string) {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.serverUrl}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}), ...(init.headers || {}) }
    });
    if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
    return response.json() as Promise<T>;
  }

  health() {
    return this.request<{
      ok: boolean;
      authRequired: boolean;
      pairingRequired: boolean;
      authMode: "disabled" | "pairing";
      version: string;
      modelTransport?: {
        mode: "hermes_only";
        configured: boolean;
        reachable: boolean;
        dashboardUrl: string;
        requestedModel: string;
        reason?: string;
      };
    }>("/api/v1/health");
  }

  pair(code: string) {
    return this.request<{ token: string }>("/api/v1/pair", { method: "POST", body: JSON.stringify({ code }) });
  }

  createSnapshot(snapshot: ProductSnapshot) {
    return this.request<ProductSnapshot>("/api/v1/product-snapshots", { method: "POST", body: JSON.stringify(snapshot) });
  }

  getSnapshot(id: string) {
    return this.request<ProductSnapshot>(`/api/v1/product-snapshots/${id}`);
  }

  createRun(input: CreateRunRequest) {
    return this.request<ExperimentRun>("/api/v1/runs", { method: "POST", body: JSON.stringify(input) });
  }

  getRun(id: string) {
    return this.request<ExperimentRun>(`/api/v1/runs/${id}`);
  }

  updatePrompt(runId: string, promptCaseId: string, input: UpdatePromptCaseRequest) {
    return this.request<ExperimentRun>(`/api/v1/runs/${runId}/prompts/${encodeURIComponent(promptCaseId)}`, {
      method: "PATCH",
      body: JSON.stringify(input)
    });
  }

  approveQuestionPlan(runId: string, input: ApproveQuestionPlanRequest) {
    return this.request<ExperimentRun>(`/api/v1/runs/${runId}/question-plan/approve`, {
      method: "POST",
      body: JSON.stringify(input)
    });
  }

  getAudit(runId: string) {
    return this.request<{ runId: string; standards: Record<string, unknown>; events: RunAuditEvent[] }>(`/api/v1/runs/${runId}/audit`);
  }

  getScoringStandards() {
    return this.request<Record<string, unknown>>("/api/v1/runs/scoring-standards");
  }
}
