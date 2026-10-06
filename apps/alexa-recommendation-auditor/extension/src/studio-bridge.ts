const REQUEST_SOURCE = "amazon-image-studio";
const RESPONSE_SOURCE = "alexa-recommendation-auditor";
const LOCAL_STUDIO_PORTS = new Set(["4173", "5173"]);

type StudioRequest = {
  source?: string;
  type?: string;
  requestId?: string;
  productUrl?: string;
  asin?: string;
};

function validRequestId(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(value);
}

export function isAllowedStudioPage(rawUrl: string): boolean {
  try {
    const url = new URL(rawUrl);
    if (url.protocol === "http:" && (url.hostname === "localhost" || url.hostname === "127.0.0.1")) {
      return LOCAL_STUDIO_PORTS.has(url.port) && url.pathname === "/";
    }
    return url.origin === "https://ali-aria.github.io"
      && (url.pathname === "/amazon-image-studio" || url.pathname.startsWith("/amazon-image-studio/"));
  } catch {
    return false;
  }
}

function handleStudioRequest(event: MessageEvent<StudioRequest>): void {
  if (event.source !== window || event.origin !== window.location.origin) return;
  const request = event.data;
  if (request?.source !== REQUEST_SOURCE || request.type !== "REQUEST_AMAZON_PRODUCT_CONTEXT" || !validRequestId(request.requestId)) return;

  if (typeof request.productUrl !== "string" || request.productUrl.length > 2048) return;
  chrome.runtime.sendMessage({
    type: "GET_STUDIO_AMAZON_PRODUCT_CONTEXT",
    requestId: request.requestId,
    productUrl: request.productUrl,
    asin: request.asin
  })
    .then((result) => {
      const response = result && typeof result === "object"
        ? result
        : {
            ok: false,
            error: "扩展后台没有响应。请在 chrome://extensions 重新加载“Alexa 商品推荐诊断”后刷新工作台",
            errorCode: "extension_background_unavailable"
          };
      window.postMessage({
        source: RESPONSE_SOURCE,
        type: "AMAZON_PRODUCT_CONTEXT_RESPONSE",
        ...response,
        requestId: request.requestId
      }, window.location.origin);
    })
    .catch((error) => {
      window.postMessage({
        source: RESPONSE_SOURCE,
        type: "AMAZON_PRODUCT_CONTEXT_RESPONSE",
        requestId: request.requestId,
        ok: false,
        error: (error as Error).message || String(error),
        errorCode: "extension_message_failed"
      }, window.location.origin);
    });
}

if (isAllowedStudioPage(window.location.href)) {
  window.addEventListener("message", handleStudioRequest);
}
