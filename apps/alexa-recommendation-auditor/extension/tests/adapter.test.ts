// @vitest-environment jsdom
import { beforeEach, describe, expect, it } from "vitest";
import { clickByText, detectSafetyStop, extractProductSnapshot, findAlexaPanel, findComposer, findSubmitControl, inspectAlexaConversationText, isAlexaResponseCandidate, isPristineAlexaConversationText, parseAlexaResponse, submitSurfaceDiagnostics } from "../src/amazon/adapter";

describe("Amazon adapter", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="nav-link-accountList-nav-line-1">Hello, Test User</div>
      <span id="productTitle">Joomra Women's Arch Support Flip Flops</span>
      <input id="ASIN" value="B0GKDW7BDW" />
      <a id="bylineInfo">Visit the Joomra Store</a>
      <div id="wayfinding-breadcrumbs_feature_div"><a>Clothing, Shoes & Jewelry</a><a>Women's Sandals</a></div>
      <div id="feature-bullets"><li><span class="a-list-item">Ergonomic arch support for all-day comfort</span></li><li><span class="a-list-item">Deep textured slip-resistant outsole</span></li></div>
      <table id="productDetails_techSpec_section_1"><tr><th>Outer material</th><td>EVA</td></tr><tr><th>Closure type</th><td>Slip On</td></tr></table>
      <div id="corePriceDisplay_desktop_feature_div"><span class="a-offscreen">$9.96</span></div>
    `;
  });

  it("extracts PDP evidence while separating volatile retail facts", () => {
    const snapshot = extractProductSnapshot(document, "https://www.amazon.com/dp/B0GKDNPHJM?th=1");
    expect(snapshot.asin).toBe("B0GKDW7BDW");
    expect(snapshot.requestedAsin).toBe("B0GKDNPHJM");
    expect(snapshot.resolvedAsin).toBe("B0GKDW7BDW");
    expect(snapshot.asinAliases).toEqual(["B0GKDNPHJM", "B0GKDW7BDW"]);
    expect(snapshot.brand).toBe("Joomra");
    expect(snapshot.specifications["Outer material"]).toBe("EVA");
    expect(snapshot.stableFacts.some((fact) => fact.sourceText.includes("arch support"))).toBe(true);
    expect(snapshot.volatileFacts.some((fact) => fact.field === "price")).toBe(true);
  });

  it("maps translated footwear evidence into generic intent slots", () => {
    document.body.innerHTML = `
      <span id="productTitle">女士足弓支撑人字拖鞋</span>
      <a id="bylineInfo">访问 Joomra 商店</a>
      <div id="wayfinding-breadcrumbs_feature_div"><a>鞋</a><a>女士凉鞋</a></div>
      <div id="feature-bullets">
        <li><span class="a-list-item">符合人体工学的足弓支撑，全天舒适</span></li>
        <li><span class="a-list-item">深纹理防滑鞋底，超轻透气</span></li>
      </div>
    `;
    const snapshot = extractProductSnapshot(document, "https://www.amazon.com/dp/B0GKDNPHJM");
    expect(snapshot.brand).toBe("Joomra");
    expect(snapshot.intentProfile.product_type).toContain("flip_flops");
    expect(snapshot.intentProfile.audience_intent).toContain("women");
    expect(snapshot.intentProfile.function_intent).toEqual(expect.arrayContaining(["arch_support", "slip_resistant", "lightweight", "breathable"]));
  });

  it("parses every unique linked product card instead of truncating at five", () => {
    document.body.innerHTML += `
      <aside aria-label="Alexa for Shopping">
        <textarea placeholder="Ask a shopping question"></textarea>
        <div class="card"><h3>Product One</h3><a href="https://www.amazon.com/dp/B0AAA11111">Product One</a><span>$20.00 4.7 out of 5 stars (123)</span></div>
        <div class="card"><h3>Product Two</h3><a href="https://www.amazon.com/dp/B0BBB22222">Product Two</a><span>$30.00</span></div>
        <div class="card"><h3>Product Three</h3><a href="https://www.amazon.com/dp/B0CCC33333">Product Three</a></div>
        <div class="card"><h3>Product Four</h3><a href="https://www.amazon.com/dp/B0DDD44444">Product Four</a></div>
        <div class="card"><h3>Product Five</h3><a href="https://www.amazon.com/dp/B0EEE55555">Product Five</a></div>
        <div class="card"><h3>Product Six</h3><a href="https://www.amazon.com/dp/B0FFF66666">Product Six</a></div>
      </aside>`;
    const result = parseAlexaResponse(document);
    expect(result.recommendations).toHaveLength(6);
    expect(result.recommendations[0].asin).toBe("B0AAA11111");
    expect(result.recommendations[0].rank).toBe(1);
    expect(result.recommendations[5].asin).toBe("B0FFF66666");
    expect(result.extractionDiagnostics.asinCount).toBe(6);
  });

  it("keeps a text-only recommendation when a visible card has no ASIN link", () => {
    document.body.innerHTML += `
      <aside aria-label="Alexa for Shopping">
        <textarea placeholder="Ask a shopping question"></textarea>
        <div class="card">
          <h3>Unlinked Product</h3>
          <button>Add to cart</button>
        </div>
      </aside>`;
    const result = parseAlexaResponse(document);
    expect(result.recommendations).toHaveLength(1);
    expect(result.recommendations[0]).toMatchObject({ asin: "", title: "Unlinked Product", rank: 1 });
    expect(result.extractionDiagnostics.textOnlyCount).toBe(1);
  });

  it("detects CAPTCHA as a hard safety stop", () => {
    document.body.innerHTML = "<main>Enter the characters you see below</main>";
    expect(detectSafetyStop(document)).toBe("captcha");
  });

  it("keeps a response unsettled while the latest Rufus lifecycle marker is generating", () => {
    expect(inspectAlexaConversationText("Customer question hello Rufus 目前正在生成回复")).toMatchObject({
      generating: true,
      completionCount: 0,
      hasConversation: true
    });
  });

  it("recognizes completion only when it follows the active generating marker", () => {
    const state = inspectAlexaConversationText("Customer question hello Rufus 目前正在生成回复 answer Rufus 已完成生成回复");
    expect(state.generating).toBe(false);
    expect(state.completionCount).toBe(1);
    expect(state.hasConversation).toBe(true);
  });

  it("treats the welcome composer as a clean fresh conversation", () => {
    expect(inspectAlexaConversationText("Welcome back. What can I help with? Ask a shopping question")).toEqual({
      generating: false,
      completionCount: 0,
      hasConversation: false
    });
    expect(isPristineAlexaConversationText("欢迎回来，我今天能帮你什么？询问购物问题")).toBe(true);
  });

  it("detects prior English and Chinese customer turns as contaminated fresh-session state", () => {
    expect(inspectAlexaConversationText("Customer question Find shoes").hasConversation).toBe(true);
    expect(inspectAlexaConversationText("客户问题 推荐几双鞋").hasConversation).toBe(true);
    expect(isPristineAlexaConversationText("欢迎回来 客户问题 推荐几双鞋")).toBe(false);
  });

  it("uses the outer Rufus panel so the header More options control remains in reset scope", () => {
    document.body.innerHTML = `
      <aside id="outer-panel" aria-label="Alexa for Shopping">
        <button aria-label="More options"></button>
        <section id="inner-chat"><textarea aria-label="Ask a shopping question"></textarea></section>
      </aside>
    `;
    const outer = document.querySelector("#outer-panel") as HTMLElement;
    const inner = document.querySelector("#inner-chat") as HTMLElement;
    outer.getBoundingClientRect = () => ({ width: 420, height: 800, top: 0, right: 420, bottom: 800, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    inner.getBoundingClientRect = () => ({ width: 380, height: 600, top: 150, right: 400, bottom: 750, left: 20, x: 20, y: 150, toJSON: () => ({}) });

    expect(findAlexaPanel(document)).toBe(outer);
  });

  it("never accepts the echoed prompt plus an active generating announcement as a completed answer", () => {
    expect(isAlexaResponseCandidate({
      previousText: "Welcome back",
      currentText: "Welcome back Customer question Find shoes Rufus 目前正在生成回复",
      promptText: "Find shoes",
      sawGenerating: true,
      elapsedMs: 15000
    })).toBe(false);
  });

  it("accepts a stable-sized answer after a new completion marker", () => {
    expect(isAlexaResponseCandidate({
      previousText: "Welcome back",
      currentText: "Welcome back Customer question Find shoes Here are three suitable products with public evidence. Rufus 已完成生成回复",
      promptText: "Find shoes",
      sawGenerating: true,
      elapsedMs: 5000
    })).toBe(true);
  });

  it("does not use the marker-free fallback before the minimum delay", () => {
    expect(isAlexaResponseCandidate({
      previousText: "Welcome back",
      currentText: "Welcome back Find shoes Here are three suitable products with public evidence.",
      promptText: "Find shoes",
      sawGenerating: false,
      elapsedMs: 3000
    })).toBe(false);
  });

  it("finds the translated Rufus shopping composer", () => {
    document.body.innerHTML = `<textarea aria-label="询问购物问题"></textarea>`;
    expect(findComposer(document)).toBe(document.querySelector("textarea"));
  });

  it("finds a Rufus composer inside an open shadow root", () => {
    document.body.innerHTML = `<div id="rufus-host"></div>`;
    const host = document.querySelector("#rufus-host") as HTMLElement;
    const root = host.attachShadow({ mode: "open" });
    root.innerHTML = `<textarea aria-label="询问购物问题"></textarea>`;
    expect(findComposer(document)).toBe(root.querySelector("textarea"));
  });

  it("ignores hidden New chat controls and clicks the visible control only", () => {
    document.body.innerHTML = `
      <button style="display:none">New chat</button>
      <button id="visible-new-chat">New chat</button>
    `;
    let hiddenClicks = 0;
    let visibleClicks = 0;
    document.querySelector("button")?.addEventListener("click", () => { hiddenClicks += 1; });
    const visible = document.querySelector("#visible-new-chat") as HTMLButtonElement;
    visible.getBoundingClientRect = () => ({ width: 100, height: 40, top: 0, right: 100, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    visible.addEventListener("click", () => { visibleClicks += 1; });

    expect(clickByText(document, /^new chat$/i)).toBe(true);
    expect(hiddenClicks).toBe(0);
    expect(visibleClicks).toBe(1);
  });

  it("matches visible controls by accessible name when they have no inner text", () => {
    document.body.innerHTML = `<button id="alexa-trigger" aria-label="Open Alexa panel"></button>`;
    const trigger = document.querySelector("#alexa-trigger") as HTMLButtonElement;
    trigger.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    let clicks = 0;
    trigger.addEventListener("click", () => { clicks += 1; });

    expect(clickByText(document, /open alexa panel/i)).toBe(true);
    expect(clicks).toBe(1);
  });

  it("matches visible controls when a child image supplies the accessible name", () => {
    document.body.innerHTML = `<button id="alexa-trigger"><img alt="Open Alexa panel"></button>`;
    const trigger = document.querySelector("#alexa-trigger") as HTMLButtonElement;
    trigger.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    let clicks = 0;
    trigger.addEventListener("click", () => { clicks += 1; });

    expect(clickByText(document, /open alexa panel/i)).toBe(true);
    expect(clicks).toBe(1);
  });

  it("finds an icon-only Rufus submit control by its submit type", () => {
    document.body.innerHTML = `
      <form>
        <textarea aria-label="Ask a shopping question"></textarea>
        <button id="attachment" type="button" aria-label="Add attachment"></button>
        <button id="submit" type="submit"><svg></svg></button>
      </form>
    `;
    const submit = document.querySelector("#submit") as HTMLButtonElement;
    submit.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    expect(findSubmitControl(document, document.querySelector("textarea"))).toBe(submit);
  });

  it("never mistakes the Amazon search submit button for the Rufus submit button", () => {
    document.body.innerHTML = `
      <header>
        <form id="amazon-search"><input aria-label="Search Amazon"><button id="amazon-search-submit" type="submit"></button></form>
      </header>
      <aside aria-label="Alexa for Shopping">
        <form id="rufus-chat">
          <textarea aria-label="Ask a shopping question"></textarea>
          <button id="rufus-submit" type="submit"><svg></svg></button>
        </form>
      </aside>
    `;
    const globalSubmit = document.querySelector("#amazon-search-submit") as HTMLButtonElement;
    const rufusSubmit = document.querySelector("#rufus-submit") as HTMLButtonElement;
    for (const button of [globalSubmit, rufusSubmit]) {
      button.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    }

    expect(findSubmitControl(document, document.querySelector("textarea"))).toBe(rufusSubmit);
  });

  it("does not accept an unrelated unnamed submit button when the composer has no form", () => {
    document.body.innerHTML = `
      <header><button id="amazon-search-submit" type="submit"></button></header>
      <aside aria-label="Alexa for Shopping">
        <textarea aria-label="Ask a shopping question"></textarea>
        <button id="rufus-submit" type="button" aria-label="Send message"></button>
      </aside>
    `;
    const globalSubmit = document.querySelector("#amazon-search-submit") as HTMLButtonElement;
    const rufusSubmit = document.querySelector("#rufus-submit") as HTMLButtonElement;
    for (const button of [globalSubmit, rufusSubmit]) {
      button.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    }

    expect(findSubmitControl(document, document.querySelector("textarea"))).toBe(rufusSubmit);
  });

  it("keeps submit lookup inside the composer shadow root", () => {
    document.body.innerHTML = `
      <form id="amazon-search"><button id="amazon-search-submit" type="submit"></button></form>
      <div id="rufus-host"></div>
    `;
    const globalSubmit = document.querySelector("#amazon-search-submit") as HTMLButtonElement;
    globalSubmit.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    const root = (document.querySelector("#rufus-host") as HTMLElement).attachShadow({ mode: "open" });
    root.innerHTML = `
      <form>
        <textarea aria-label="Ask a shopping question"></textarea>
        <button id="rufus-submit" type="submit"></button>
      </form>
    `;
    const composer = root.querySelector("textarea") as HTMLTextAreaElement;
    const rufusSubmit = root.querySelector("#rufus-submit") as HTMLButtonElement;
    rufusSubmit.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });

    expect(findSubmitControl(document, composer)).toBe(rufusSubmit);
  });

  it("keeps submit lookup inside an accessible same-origin frame", () => {
    document.body.innerHTML = `
      <form id="amazon-search"><button id="amazon-search-submit" type="submit"></button></form>
      <iframe id="rufus-frame"></iframe>
    `;
    const frame = document.querySelector("#rufus-frame") as HTMLIFrameElement;
    frame.contentDocument!.body.innerHTML = `
      <form>
        <textarea aria-label="Ask a shopping question"></textarea>
        <button id="rufus-submit" type="submit"></button>
      </form>
    `;
    const composer = frame.contentDocument!.querySelector("textarea") as HTMLTextAreaElement;
    const rufusSubmit = frame.contentDocument!.querySelector("#rufus-submit") as HTMLButtonElement;

    expect(findComposer(document)).toBe(composer);
    expect(findSubmitControl(document, composer)).toBe(rufusSubmit);
  });

  it("ignores disabled submit controls and exposes diagnostics", () => {
    document.body.innerHTML = `
      <textarea aria-label="Ask a shopping question"></textarea>
      <button type="submit" disabled aria-label="Submit"></button>
    `;
    const submit = document.querySelector("button") as HTMLButtonElement;
    submit.getBoundingClientRect = () => ({ width: 40, height: 40, top: 0, right: 40, bottom: 40, left: 0, x: 0, y: 0, toJSON: () => ({}) });
    expect(findSubmitControl(document, document.querySelector("textarea"))).toBeNull();
    expect(submitSurfaceDiagnostics(document, document.querySelector("textarea"))).toContain('"enabledSubmitLike":0');
  });
});
