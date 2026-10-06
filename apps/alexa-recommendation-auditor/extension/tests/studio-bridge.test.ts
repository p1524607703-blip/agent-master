// @vitest-environment jsdom
// @vitest-environment-options {"url":"http://localhost:5173/"}
import { afterEach, describe, expect, it, vi } from "vitest";
import { isAllowedStudioPage } from "../src/studio-bridge";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("amazon-image-studio page bridge", () => {
  it("registers only on the known local ports or the fixed GitHub Pages project path", () => {
    expect(isAllowedStudioPage("http://localhost:5173/")).toBe(true);
    expect(isAllowedStudioPage("http://127.0.0.1:4173/")).toBe(true);
    expect(isAllowedStudioPage("https://ali-aria.github.io/amazon-image-studio/")).toBe(true);
    expect(isAllowedStudioPage("http://localhost:5173/unrelated")).toBe(false);
    expect(isAllowedStudioPage("http://localhost:3000/")).toBe(false);
    expect(isAllowedStudioPage("https://ali-aria.github.io/unrelated/")).toBe(false);
  });

  it("forwards an authorized same-page request to the extension background", async () => {
    const sendMessage = vi.fn().mockResolvedValue({ ok: true, snapshot: { asin: "B0GKDNPHJM" } });
    vi.stubGlobal("chrome", { runtime: { sendMessage } });
    const postMessage = vi.spyOn(window, "postMessage").mockImplementation(() => undefined);

    window.dispatchEvent(new MessageEvent("message", {
      source: window,
      origin: window.location.origin,
      data: {
        source: "amazon-image-studio",
        type: "REQUEST_AMAZON_PRODUCT_CONTEXT",
        requestId: "request-1",
        productUrl: "https://www.amazon.com/dp/B0GKDNPHJM",
        asin: "B0GKDNPHJM"
      }
    }));
    await Promise.resolve();
    await Promise.resolve();

    expect(sendMessage).toHaveBeenCalledWith({
      type: "GET_STUDIO_AMAZON_PRODUCT_CONTEXT",
      requestId: "request-1",
      productUrl: "https://www.amazon.com/dp/B0GKDNPHJM",
      asin: "B0GKDNPHJM"
    });
    expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({
      source: "alexa-recommendation-auditor",
      type: "AMAZON_PRODUCT_CONTEXT_RESPONSE",
      requestId: "request-1",
      ok: true
    }), window.location.origin);
  });

  it("ignores requests from a different origin", async () => {
    const sendMessage = vi.fn();
    vi.stubGlobal("chrome", { runtime: { sendMessage } });
    window.dispatchEvent(new MessageEvent("message", {
      source: window,
      origin: "https://example.com",
      data: {
        source: "amazon-image-studio",
        type: "REQUEST_AMAZON_PRODUCT_CONTEXT",
        requestId: "request-2",
        productUrl: "https://www.amazon.com/dp/B0GKDNPHJM"
      }
    }));
    await Promise.resolve();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("ignores malformed request IDs instead of opening a background channel", async () => {
    const sendMessage = vi.fn();
    vi.stubGlobal("chrome", { runtime: { sendMessage } });
    window.dispatchEvent(new MessageEvent("message", {
      source: window,
      origin: window.location.origin,
      data: {
        source: "amazon-image-studio",
        type: "REQUEST_AMAZON_PRODUCT_CONTEXT",
        requestId: "bad request id with spaces"
      }
    }));
    await Promise.resolve();
    expect(sendMessage).not.toHaveBeenCalled();
  });

  it("keeps the page request ID authoritative when the background returns a mismatched ID", async () => {
    const sendMessage = vi.fn().mockResolvedValue({ ok: true, requestId: "wrong-id", snapshot: { asin: "B0GKDNPHJM" } });
    vi.stubGlobal("chrome", { runtime: { sendMessage } });
    const postMessage = vi.spyOn(window, "postMessage").mockImplementation(() => undefined);

    window.dispatchEvent(new MessageEvent("message", {
      source: window,
      origin: window.location.origin,
      data: {
        source: "amazon-image-studio",
        type: "REQUEST_AMAZON_PRODUCT_CONTEXT",
        requestId: "request-authoritative",
        productUrl: "https://www.amazon.com/dp/B0GKDNPHJM"
      }
    }));
    await Promise.resolve();
    await Promise.resolve();

    expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({
      requestId: "request-authoritative",
      ok: true
    }), window.location.origin);
  });

  it("returns an actionable reload error when an old background listener answers with nothing", async () => {
    const sendMessage = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("chrome", { runtime: { sendMessage } });
    const postMessage = vi.spyOn(window, "postMessage").mockImplementation(() => undefined);

    window.dispatchEvent(new MessageEvent("message", {
      source: window,
      origin: window.location.origin,
      data: {
        source: "amazon-image-studio",
        type: "REQUEST_AMAZON_PRODUCT_CONTEXT",
        requestId: "request-empty",
        productUrl: "https://www.amazon.com/dp/B0GKDNPHJM"
      }
    }));
    await Promise.resolve();
    await Promise.resolve();

    expect(postMessage).toHaveBeenCalledWith(expect.objectContaining({
      ok: false,
      errorCode: "extension_background_unavailable",
      error: expect.stringContaining("重新加载")
    }), window.location.origin);
  });
});
