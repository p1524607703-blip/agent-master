const MODEL = "deepseek-v4-pro";
const MAX_BODY_BYTES = 128 * 1024;
const MAX_MESSAGE_COUNT = 6;
const MAX_MESSAGE_CHARS = 100_000;
const HEALTH_TIMEOUT_MS = 5_000;
const COMPLETION_TIMEOUT_MS = 95_000;

type ChatRole = "system" | "user";

interface ChatMessage {
  role: ChatRole;
  content: string;
}

interface SafeChatPayload {
  model: typeof MODEL;
  stream: false;
  messages: ChatMessage[];
  tools: [];
  temperature: 0;
}

function jsonResponse(
  status: number,
  code: string,
  message: string,
  requestId: string,
): Response {
  return Response.json(
    {
      error: {
        code,
        message,
        requestId,
      },
    },
    {
      status,
      headers: {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    },
  );
}

function pathFromParams(value: string | string[] | undefined): string {
  if (Array.isArray(value)) return value.join("/");
  return value ?? "";
}

async function readLimitedJson(request: Request): Promise<unknown> {
  const declaredLength = Number(request.headers.get("Content-Length") ?? 0);
  if (Number.isFinite(declaredLength) && declaredLength > MAX_BODY_BYTES) {
    throw Object.assign(new Error("请求体超过128KB限制"), {
      code: "PAYLOAD_TOO_LARGE",
      status: 413,
    });
  }

  if (!request.body) {
    throw Object.assign(new Error("请求体为空"), {
      code: "INVALID_REQUEST",
      status: 400,
    });
  }

  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let received = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    received += value.byteLength;
    if (received > MAX_BODY_BYTES) {
      await reader.cancel("payload too large");
      throw Object.assign(new Error("请求体超过128KB限制"), {
        code: "PAYLOAD_TOO_LARGE",
        status: 413,
      });
    }
    chunks.push(value);
  }

  const merged = new Uint8Array(received);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.byteLength;
  }

  try {
    return JSON.parse(new TextDecoder().decode(merged));
  } catch {
    throw Object.assign(new Error("请求体不是有效JSON"), {
      code: "INVALID_JSON",
      status: 400,
    });
  }
}

function safeChatPayload(value: unknown): SafeChatPayload {
  if (!value || typeof value !== "object") {
    throw Object.assign(new Error("请求结构无效"), {
      code: "INVALID_REQUEST",
      status: 400,
    });
  }

  const payload = value as Record<string, unknown>;
  if (payload.model !== MODEL) {
    throw Object.assign(new Error(`只允许模型${MODEL}`), {
      code: "MODEL_NOT_ALLOWED",
      status: 400,
    });
  }
  if (payload.stream !== false) {
    throw Object.assign(new Error("只允许非流式请求"), {
      code: "STREAM_NOT_ALLOWED",
      status: 400,
    });
  }
  if (!Array.isArray(payload.tools) || payload.tools.length !== 0) {
    throw Object.assign(new Error("不允许工具调用"), {
      code: "TOOLS_NOT_ALLOWED",
      status: 400,
    });
  }
  if (
    !Array.isArray(payload.messages) ||
    payload.messages.length < 2 ||
    payload.messages.length > MAX_MESSAGE_COUNT
  ) {
    throw Object.assign(new Error("消息数量不符合限制"), {
      code: "INVALID_MESSAGES",
      status: 400,
    });
  }

  let totalChars = 0;
  const messages: ChatMessage[] = payload.messages.map((item) => {
    if (!item || typeof item !== "object") {
      throw Object.assign(new Error("消息结构无效"), {
        code: "INVALID_MESSAGES",
        status: 400,
      });
    }
    const message = item as Record<string, unknown>;
    if (
      (message.role !== "system" && message.role !== "user") ||
      typeof message.content !== "string" ||
      message.content.length === 0
    ) {
      throw Object.assign(new Error("只允许system和user文本消息"), {
        code: "INVALID_MESSAGES",
        status: 400,
      });
    }
    totalChars += message.content.length;
    return {
      role: message.role,
      content: message.content,
    };
  });

  if (totalChars > MAX_MESSAGE_CHARS) {
    throw Object.assign(new Error("消息内容超过限制"), {
      code: "PAYLOAD_TOO_LARGE",
      status: 413,
    });
  }

  return {
    model: MODEL,
    stream: false,
    messages,
    tools: [],
    temperature: 0,
  };
}

function upstreamUrl(originValue: string, path: string): URL {
  let origin: URL;
  try {
    origin = new URL(originValue);
  } catch {
    throw Object.assign(new Error("Hermes源站地址配置无效"), {
      code: "HERMES_NOT_CONFIGURED",
      status: 503,
    });
  }

  const isLocal =
    origin.hostname === "127.0.0.1" || origin.hostname === "localhost";
  if (
    origin.protocol !== "https:" &&
    !(isLocal && origin.protocol === "http:")
  ) {
    throw Object.assign(new Error("Hermes远程源站必须使用HTTPS"), {
      code: "HERMES_NOT_CONFIGURED",
      status: 503,
    });
  }

  origin.pathname = `${origin.pathname.replace(/\/$/, "")}/${path}`;
  origin.search = "";
  origin.hash = "";
  return origin;
}

function accessHeaders(env: Env, origin: URL): Headers {
  const headers = new Headers();
  const isLocal =
    origin.hostname === "127.0.0.1" || origin.hostname === "localhost";
  if (isLocal) return headers;

  if (!env.CF_ACCESS_CLIENT_ID || !env.CF_ACCESS_CLIENT_SECRET) {
    throw Object.assign(new Error("Cloudflare Access服务凭证尚未配置"), {
      code: "ACCESS_NOT_CONFIGURED",
      status: 503,
    });
  }
  headers.set("CF-Access-Client-Id", env.CF_ACCESS_CLIENT_ID);
  headers.set("CF-Access-Client-Secret", env.CF_ACCESS_CLIENT_SECRET);
  return headers;
}

function safeResponse(upstream: Response, requestId: string): Response {
  const headers = new Headers({
    "Cache-Control": "no-store",
    "Content-Type":
      upstream.headers.get("Content-Type") ?? "application/json; charset=utf-8",
    "X-Content-Type-Options": "nosniff",
    "X-Request-Id": requestId,
  });
  const sessionId = upstream.headers.get("X-Hermes-Session-Id");
  if (sessionId) headers.set("X-Hermes-Session-Id", sessionId);
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers,
  });
}

export const onRequest: PagesFunction<Env, "path"> = async (context) => {
  const requestId = crypto.randomUUID();
  const path = pathFromParams(context.params.path);
  const isHealth = path === "health" && context.request.method === "GET";
  const isCompletion =
    path === "v1/chat/completions" && context.request.method === "POST";

  if (!isHealth && !isCompletion) {
    return jsonResponse(404, "NOT_FOUND", "接口不存在", requestId);
  }

  try {
    const origin = upstreamUrl(context.env.HERMES_ORIGIN, path);
    const headers = accessHeaders(context.env, origin);
    let body: string | undefined;
    let timeout = HEALTH_TIMEOUT_MS;

    if (isCompletion) {
      const payload = safeChatPayload(await readLimitedJson(context.request));
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(payload);
      timeout = COMPLETION_TIMEOUT_MS;
    }

    const startedAt = Date.now();
    const upstream = await fetch(origin, {
      method: context.request.method,
      headers,
      body,
      redirect: "manual",
      signal: AbortSignal.timeout(timeout),
    });

    console.log(
      JSON.stringify({
        event: "hermes_proxy",
        requestId,
        path,
        status: upstream.status,
        durationMs: Date.now() - startedAt,
      }),
    );
    return safeResponse(upstream, requestId);
  } catch (error) {
    const details =
      error && typeof error === "object"
        ? (error as { code?: unknown; status?: unknown; message?: unknown })
        : {};
    const status =
      typeof details.status === "number" ? details.status : 503;
    const code =
      typeof details.code === "string"
        ? details.code
        : error instanceof DOMException && error.name === "TimeoutError"
          ? "HERMES_TIMEOUT"
          : "HERMES_UNAVAILABLE";
    const message =
      typeof details.message === "string"
        ? details.message
        : "Hermes当前不可用";

    console.error(
      JSON.stringify({
        event: "hermes_proxy_error",
        requestId,
        path,
        status,
        code,
      }),
    );
    return jsonResponse(status, code, message, requestId);
  }
};
