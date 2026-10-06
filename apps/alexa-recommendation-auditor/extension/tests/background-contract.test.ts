import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

describe("background Chrome API contract", () => {
  it("does not use tabs.get in the automatic executor", () => {
    const source = readFileSync(new URL("../src/background/index.ts", import.meta.url), "utf8");

    // The executor already owns a validated workspace tab/window pair. Using
    // tabs.get here previously caused Chrome to reject a stale or malformed
    // invocation before the first question could be submitted.
    expect(source).not.toMatch(/chrome\.tabs\.get\s*\(/);
  });

  it("never creates a separate Chrome window for the execution workspace", () => {
    const source = readFileSync(new URL("../src/run/workspace.ts", import.meta.url), "utf8");

    expect(source).not.toMatch(/(?:chrome|api)\.windows\.(?:create|remove)\s*\(/);
    expect(source).toContain("active: false");
  });

  it("does not blindly replay a prompt after an ambiguous message-channel failure", () => {
    const source = readFileSync(new URL("../src/background/index.ts", import.meta.url), "utf8");

    expect(source).toContain("failure.retryableBeforeDelivery");
    expect(source).toContain("throw contentMessageError(error)");
  });

  it("uses a persistent Chrome alarm to clean a temporarily preserved error workspace", () => {
    const source = readFileSync(new URL("../src/background/index.ts", import.meta.url), "utf8");
    const manifest = readFileSync(new URL("../manifest.json", import.meta.url), "utf8");

    expect(source).toContain("chrome.alarms.create");
    expect(source).toContain("chrome.alarms.onAlarm.addListener");
    expect(JSON.parse(manifest).permissions).toContain("alarms");
  });

  it("injects the collector only on the six supported Amazon marketplaces", () => {
    const manifest = JSON.parse(readFileSync(new URL("../manifest.json", import.meta.url), "utf8"));
    const amazonMatches = manifest.content_scripts[0].matches;
    expect(amazonMatches).toEqual([
      "https://www.amazon.com/*",
      "https://www.amazon.co.jp/*",
      "https://www.amazon.de/*",
      "https://www.amazon.fr/*",
      "https://www.amazon.it/*",
      "https://www.amazon.es/*"
    ]);
    expect(manifest.host_permissions).toEqual(expect.arrayContaining(amazonMatches));
  });

  it("keeps image-studio requests on a dedicated planning-only message path", () => {
    const background = readFileSync(new URL("../src/background/index.ts", import.meta.url), "utf8");
    const bridge = readFileSync(new URL("../src/studio-bridge.ts", import.meta.url), "utf8");

    expect(bridge).toContain("GET_STUDIO_AMAZON_PRODUCT_CONTEXT");
    expect(background).toContain("sanitizeProductSnapshotForStudio");
    expect(background).toContain("sender.tab?.windowId");
    expect(background).toContain("selectAmazonProductTabByUrl");
    expect(background).toContain("studioSnapshotMatchesAsin");
    expect(background).toContain("amazon_product_cache_asin_mismatch");
    expect(background).toContain("cached: false");
    expect(background).toContain("cached: true");
  });
});
