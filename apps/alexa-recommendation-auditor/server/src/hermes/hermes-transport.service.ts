import { Injectable } from "@nestjs/common";
import { randomUUID } from "node:crypto";

export type HermesOperation = "intent_profile_refinement" | "question_rewrite" | "run_diagnosis";

export interface HermesMessage {
  role: "system" | "user";
  content: string;
}

export interface HermesRequestContext {
  operation: HermesOperation;
  requestId?: string;
  runId?: string;
  productSnapshotId?: string;
  productAsin?: string;
  schemaVersion?: string;
  promptVersion?: string;
  templateIds?: string[];
}

export interface HermesUsage {
  promptTokens?: number;
  completionTokens?: number;
  totalTokens?: number;
}

export interface HermesCompletionMetadata {
  transport: "hermes_agent";
  operation: HermesOperation;
  requestId: string;
  sessionId?: string;
  usage?: HermesUsage;
  latencyMs?: number;
  requestedModel: string;
  responseModel?: string;
}

export interface HermesCompletion<T> {
  value: T;
  metadata: HermesCompletionMetadata;
}

export interface HermesTransportStatus {
  mode: "hermes_only";
  configured: boolean;
  endpoint: string | null;
  dashboardUrl: string;
  requestedModel: string;
  timeoutMs: number;
}

interface HermesResponsePayload {
  model?: unknown;
  choices?: Array<{ message?: { content?: string } }>;
  usage?: {
    prompt_tokens?: unknown;
    completion_tokens?: unknown;
    total_tokens?: unknown;
  };
}

export class HermesTransportError extends Error {
  constructor(
    public readonly code: string,
    public readonly metadata?: HermesCompletionMetadata
  ) {
    super(code);
    this.name = "HermesTransportError";
  }
}

function cleanHeader(value: unknown, maxLength = 500): string {
  return String(value || "").replace(/[\r\n]/g, " ").trim().slice(0, maxLength);
}

function finiteNonNegative(value: unknown): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed >= 0 ? parsed : undefined;
}

function usageFrom(payload: HermesResponsePayload): HermesUsage | undefined {
  const usage = {
    promptTokens: finiteNonNegative(payload.usage?.prompt_tokens),
    completionTokens: finiteNonNegative(payload.usage?.completion_tokens),
    totalTokens: finiteNonNegative(payload.usage?.total_tokens)
  };
  return Object.values(usage).some((value) => value !== undefined) ? usage : undefined;
}

@Injectable()
export class HermesTransportService {
  private readonly gatewayUrl = (
    process.env.HERMES_API_URL === undefined
      ? "http://127.0.0.1:8642"
      : String(process.env.HERMES_API_URL).trim()
  ).replace(/\/+$/, "");
  private readonly gatewayToken = String(process.env.HERMES_API_KEY || "").trim();
  private readonly dashboardUrl = String(process.env.HERMES_DASHBOARD_URL || "http://127.0.0.1:9119").trim();
  readonly modelName = cleanHeader(process.env.HERMES_MODEL || "hermes-agent", 120);
  private readonly timeoutMs = Math.max(1_000, Math.min(180_000, Number(process.env.HERMES_TIMEOUT_MS || 120_000)));

  get enabled(): boolean {
    return Boolean(this.gatewayUrl);
  }

  get status(): HermesTransportStatus {
    return {
      mode: "hermes_only" as const,
      configured: this.enabled,
      endpoint: this.gatewayUrl ? `${this.gatewayUrl}/v1/chat/completions` : null,
      dashboardUrl: this.dashboardUrl,
      requestedModel: this.modelName,
      timeoutMs: this.timeoutMs
    };
  }

  async health(): Promise<HermesTransportStatus & { reachable: boolean; reason?: string }> {
    const status = this.status;
    if (!this.enabled) return { ...status, reachable: false, reason: "hermes_not_configured" };
    const timeout = new AbortController();
    const timer = setTimeout(() => timeout.abort(), Math.min(this.timeoutMs, 2_000));
    try {
      const response = await fetch(`${this.gatewayUrl}/health`, {
        headers: this.gatewayToken ? { Authorization: `Bearer ${this.gatewayToken}` } : {},
        signal: timeout.signal
      });
      return response.ok
        ? { ...status, reachable: true }
        : { ...status, reachable: false, reason: `hermes_health_${response.status}` };
    } catch {
      return { ...status, reachable: false, reason: "hermes_unavailable" };
    } finally {
      clearTimeout(timer);
    }
  }

  async jsonCompletion<T>(
    messages: HermesMessage[],
    context: HermesRequestContext,
    signal?: AbortSignal
  ): Promise<HermesCompletion<T>> {
    if (!this.enabled) throw new HermesTransportError("hermes_not_configured");
    const requestId = cleanHeader(context.requestId || randomUUID(), 128);
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(this.gatewayToken ? { Authorization: `Bearer ${this.gatewayToken}` } : {})
    };

    const timeout = new AbortController();
    const timer = setTimeout(() => timeout.abort("hermes_timeout"), this.timeoutMs);
    const combinedSignal = signal ? AbortSignal.any([signal, timeout.signal]) : timeout.signal;
    const startedAt = Date.now();
    try {
      let response: Response;
      try {
        response = await fetch(`${this.gatewayUrl}/v1/chat/completions`, {
          method: "POST",
          headers,
          body: JSON.stringify({
            model: this.modelName,
            messages,
            temperature: 0,
            top_p: 0.2,
            response_format: { type: "json_object" },
            stream: false
          }),
          signal: combinedSignal
        });
      } catch (error) {
        if (timeout.signal.aborted) throw new HermesTransportError("hermes_timeout");
        if (signal?.aborted) throw new HermesTransportError("request_aborted");
        throw new HermesTransportError("hermes_unavailable");
      }
      if (!response.ok) {
        const status = Math.max(0, Math.min(999, Number(response.status || 0)));
        if (status >= 500) throw new HermesTransportError(`hermes_http_${status}`);
        if (status === 408 || status === 429) throw new HermesTransportError(`hermes_http_${status}`);
        throw new HermesTransportError(`hermes_rejected_${status}`);
      }

      let payload: HermesResponsePayload;
      try {
        payload = await response.json() as HermesResponsePayload;
      } catch {
        throw new HermesTransportError("hermes_invalid_response");
      }
      const content = payload.choices?.[0]?.message?.content;
      const sessionId = cleanHeader(response.headers?.get?.("x-hermes-session-id"), 128) || undefined;
      const responseModel = cleanHeader(payload.model, 120) || undefined;
      const metadata: HermesCompletionMetadata = {
        transport: "hermes_agent",
        operation: context.operation,
        requestId,
        ...(sessionId ? { sessionId } : {}),
        ...(usageFrom(payload) ? { usage: usageFrom(payload) } : {}),
        latencyMs: Math.max(0, Date.now() - startedAt),
        requestedModel: this.modelName,
        ...(responseModel ? { responseModel } : {})
      };
      if (!content) throw new HermesTransportError("hermes_empty_response", metadata);
      const trimmedContent = content.trim();
      if (!/^[{[]/.test(trimmedContent)) {
        if (/\bHTTP\s*402\b/i.test(trimmedContent) || /\binsufficient balance\b/i.test(trimmedContent)) {
          throw new HermesTransportError("hermes_upstream_insufficient_balance", metadata);
        }
        if (/^API call failed\b/i.test(trimmedContent)) {
          throw new HermesTransportError("hermes_upstream_failure", metadata);
        }
      }
      let value: T;
      try {
        value = JSON.parse(trimmedContent) as T;
      } catch {
        throw new HermesTransportError("hermes_invalid_model_json", metadata);
      }
      return {
        value,
        metadata
      };
    } finally {
      clearTimeout(timer);
    }
  }
}
