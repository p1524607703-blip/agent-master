import { afterEach, describe, expect, it, vi } from "vitest";
import { HermesTransportError, HermesTransportService } from "./hermes-transport.service";

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("HermesTransportService", () => {
  it("uses the installed Hermes OpenAI-compatible API without private context headers", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642/");
    vi.stubEnv("HERMES_API_KEY", "local-hermes-key");
    vi.stubEnv("HERMES_MODEL", "hermes-agent");
    vi.stubEnv("DEEPSEEK_API_KEY", "ignored-deepseek-key");
    vi.stubEnv("DEEPSEEK_BASE_URL", "https://ignored.invalid");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "X-Hermes-Session-Id": "chat-session-1" }),
      json: async () => ({
        model: "hermes-agent",
        choices: [{ message: { content: "{\"ok\":true}" } }],
        usage: { prompt_tokens: 5, completion_tokens: 2, total_tokens: 7 }
      })
    });
    vi.stubGlobal("fetch", fetchMock);
    const service = new HermesTransportService();

    const result = await service.jsonCompletion<{ ok: boolean }>([
      { role: "system", content: "Return JSON." },
      { role: "user", content: "{\"task\":\"test\",\"audit_context\":{\"request_id\":\"request-1\"}}" }
    ], {
      operation: "question_rewrite",
      requestId: "request-1",
      runId: "run-1"
    });

    expect(result.value).toEqual({ ok: true });
    expect(result.metadata).toMatchObject({
      transport: "hermes_agent",
      requestId: "request-1",
      sessionId: "chat-session-1",
      requestedModel: "hermes-agent",
      responseModel: "hermes-agent",
      usage: { promptTokens: 5, completionTokens: 2, totalTokens: 7 }
    });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8642/v1/chat/completions");
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe("Bearer local-hermes-key");
    expect(Object.keys(headers).some((name) => name.toLowerCase().startsWith("x-hermes"))).toBe(false);
    const body = JSON.parse(String(init.body));
    expect(body).toMatchObject({ model: "hermes-agent", stream: false });
    expect(body.metadata).toBeUndefined();
  });

  it("does not authenticate with any DEEPSEEK variable", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    vi.stubEnv("HERMES_API_KEY", "");
    vi.stubEnv("DEEPSEEK_API_KEY", "must-not-be-forwarded");
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers(),
      json: async () => ({ choices: [{ message: { content: "{\"ok\":true}" } }] })
    });
    vi.stubGlobal("fetch", fetchMock);

    await new HermesTransportService().jsonCompletion([{ role: "user", content: "test" }], {
      operation: "intent_profile_refinement",
      requestId: "request-2"
    });

    const headers = fetchMock.mock.calls[0][1].headers as Record<string, string>;
    expect(headers.Authorization).toBeUndefined();
    expect(JSON.stringify(fetchMock.mock.calls[0])).not.toContain("must-not-be-forwarded");
  });

  it("returns bounded reason codes for unavailable and invalid responses", async () => {
    vi.stubEnv("HERMES_API_URL", "http://127.0.0.1:8642");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network detail")));
    const unavailable = new HermesTransportService();

    await expect(unavailable.jsonCompletion([{ role: "user", content: "test" }], {
      operation: "intent_profile_refinement"
    })).rejects.toMatchObject<HermesTransportError>({ code: "hermes_unavailable" });

    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      headers: new Headers({ "x-hermes-session-id": "failed-session" }),
      json: async () => ({
        choices: [{ message: { content: "not-json" } }],
        usage: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 }
      })
    }));
    const invalid = new HermesTransportService();
    await expect(invalid.jsonCompletion([{ role: "user", content: "test" }], {
      operation: "run_diagnosis"
    })).rejects.toMatchObject<HermesTransportError>({
      code: "hermes_invalid_model_json",
      metadata: {
        operation: "run_diagnosis",
        sessionId: "failed-session",
        usage: { promptTokens: 0, completionTokens: 0, totalTokens: 0 }
      }
    });
  });
});
