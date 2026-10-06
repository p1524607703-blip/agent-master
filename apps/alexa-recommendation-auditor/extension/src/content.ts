import { clickByText, composerSurfaceDiagnostics, detectSafetyStop, extractProductSnapshot, findAlexaPanel, findComposer, findSubmitControl, inspectAlexaConversation, inspectAlexaConversationText, isAlexaResponseCandidate, isPristineAlexaConversationText, maskPii, parseAlexaResponse, SELECTOR_VERSION, submitSurfaceDiagnostics } from "./amazon/adapter";
import { sanitizeProductSnapshotForStudio } from "./studio/product-context";

let restorePii: (() => void) | null = null;
let submittedInCurrentDocument = false;

function setComposerValue(composer: HTMLElement, value: string) {
  const view = composer.ownerDocument.defaultView || window;
  composer.dispatchEvent(new view.InputEvent("beforeinput", { bubbles: true, cancelable: true, inputType: "insertText", data: value }));
  if (composer.tagName === "TEXTAREA" || composer.tagName === "INPUT") {
    const prototype = composer.tagName === "TEXTAREA" ? view.HTMLTextAreaElement.prototype : view.HTMLInputElement.prototype;
    const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set;
    setter?.call(composer, value);
  } else {
    composer.textContent = value;
  }
  composer.dispatchEvent(new view.InputEvent("input", { bubbles: true, inputType: "insertText", data: value }));
  composer.dispatchEvent(new view.Event("change", { bubbles: true }));
}

async function waitForSubmitControl(composer: HTMLElement, timeoutMs = 5000): Promise<HTMLElement | null> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const control = findSubmitControl(composer.ownerDocument, composer);
    if (control) return control;
    await wait(200);
  }
  return null;
}

async function wait(ms: number) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForComposer(timeoutMs = 12000): Promise<HTMLElement> {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    const safety = detectSafetyStop();
    if (safety) throw Object.assign(new Error(`Safety stop: ${safety}`), { code: safety });
    const composer = findComposer();
    if (composer) return composer;
    await wait(300);
  }
  throw Object.assign(new Error(`Alexa输入框未出现 ${composerSurfaceDiagnostics()}`), { code: "selector_drift" });
}

async function openAlexaPanelIfNeeded(): Promise<boolean> {
  if (findComposer()) return false;
  const opened = clickByText(document, /open alexa panel|打开 alexa 面板|alexa for shopping|alexa 购物/i);
  if (!opened) return false;
  await waitForComposer();
  return true;
}

async function waitForResponse(previousText: string, promptText: string, timeoutMs = 90000) {
  const started = Date.now();
  let last = "";
  let stableSince = 0;
  let sawGenerating = false;
  while (Date.now() - started < timeoutMs) {
    const safety = detectSafetyStop();
    if (safety) throw Object.assign(new Error(`Safety stop: ${safety}`), { code: safety });
    const current = parseAlexaResponse();
    const state = inspectAlexaConversationText(current.responseText);
    if (state.generating) {
      sawGenerating = true;
      last = "";
      stableSince = 0;
      await wait(500);
      continue;
    }
    if (isAlexaResponseCandidate({
      previousText,
      currentText: current.responseText,
      promptText,
      sawGenerating,
      elapsedMs: Date.now() - started
    })) {
      if (current.responseText === last) {
        if (!stableSince) stableSince = Date.now();
        if (Date.now() - stableSince > 3000) return current;
      } else {
        last = current.responseText;
        stableSince = Date.now();
      }
    }
    await wait(500);
  }
  throw Object.assign(new Error("等待Alexa回答超时"), { code: "response_timeout" });
}

async function waitForCleanConversation(timeoutMs = 6000): Promise<void> {
  const started = Date.now();
  let cleanSince = 0;
  while (Date.now() - started < timeoutMs) {
    const responseText = parseAlexaResponse().responseText;
    if (isPristineAlexaConversationText(responseText)) {
      if (!cleanSince) cleanSince = Date.now();
      if (Date.now() - cleanSince >= 600) return;
    } else {
      cleanSince = 0;
    }
    await wait(250);
  }
  throw Object.assign(new Error("Alexa新会话仍包含上一题内容，已停止以避免上下文污染"), { code: "context_isolation_failed" });
}

async function ensureFreshConversation(): Promise<void> {
  await openAlexaPanelIfNeeded();
  // Rufus can hydrate account-backed conversation history shortly after the
  // composer first appears. Give it one short settle window before deciding
  // that a welcome surface is truly pristine.
  await wait(900);
  const currentText = parseAlexaResponse().responseText;
  if (!inspectAlexaConversation().hasConversation && isPristineAlexaConversationText(currentText)) {
    submittedInCurrentDocument = false;
    return;
  }

  const newChatPattern = /^new chat$|^new conversation$|^新对话$|^新聊天$/i;
  const panel = findAlexaPanel();
  let created = clickByText(panel, newChatPattern);
  if (!created) {
    const openedMenu = clickByText(panel, /^more options$|^更多选项$|^更多操作$/i);
    if (openedMenu) {
      await wait(350);
      created = clickByText(document, newChatPattern);
    }
  }
  if (!created) {
    throw Object.assign(new Error("无法证明当前Alexa会话为空，且无法创建新的Alexa会话，已停止以避免上下文污染"), { code: "context_isolation_failed" });
  }
  submittedInCurrentDocument = false;
  await waitForCleanConversation();
}

async function runPrompt(promptText: string, freshSession = true) {
  const safety = detectSafetyStop();
  if (safety) throw Object.assign(new Error(`Safety stop: ${safety}`), { code: safety });
  if (freshSession) {
    await ensureFreshConversation();
  }
  const composer = await waitForComposer();
  const before = parseAlexaResponse().responseText;
  composer.focus();
  setComposerValue(composer, promptText);
  let submitControl = await waitForSubmitControl(composer);
  if (!submitControl) {
    // Some Rufus builds enable the submit control only after a second input
    // notification. Re-assert the value once, then fail with diagnostics
    // instead of pretending that an untrusted Enter key was accepted.
    setComposerValue(composer, promptText);
    submitControl = await waitForSubmitControl(composer, 2500);
  }
  if (!submitControl) {
    throw Object.assign(new Error(`无法找到已启用的Alexa发送按钮 ${submitSurfaceDiagnostics(composer.ownerDocument, composer)}`), { code: "selector_drift" });
  }
  submitControl.click();
  submittedInCurrentDocument = true;
  return waitForResponse(before, promptText);
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message?.type === "AUDITOR_PING") {
    sendResponse({ ok: true, selectorVersion: SELECTOR_VERSION });
    return false;
  }
  if (message?.type === "AUDITOR_EXTRACT_PRODUCT") {
    try { sendResponse({ ok: true, snapshot: extractProductSnapshot() }); } catch (error) { sendResponse({ ok: false, error: (error as Error).message }); }
    return false;
  }
  if (message?.type === "AUDITOR_EXTRACT_STUDIO_PRODUCT") {
    try {
      sendResponse({ ok: true, snapshot: sanitizeProductSnapshotForStudio(extractProductSnapshot()) });
    } catch (error) {
      sendResponse({ ok: false, error: (error as Error).message });
    }
    return false;
  }
  if (message?.type === "AUDITOR_RUN_PROMPT") {
    runPrompt(String(message.promptText || ""), message.freshSession !== false)
      .then((result) => sendResponse({ ok: true, ...result, selectorVersion: SELECTOR_VERSION }))
      .catch((error) => sendResponse({ ok: false, error: (error as Error).message, errorCode: (error as { code?: string }).code || "unknown", selectorVersion: SELECTOR_VERSION }));
    return true;
  }
  if (message?.type === "AUDITOR_MASK_PII") {
    restorePii?.();
    restorePii = maskPii();
    sendResponse({ ok: true });
    return false;
  }
  if (message?.type === "AUDITOR_UNMASK_PII") {
    restorePii?.();
    restorePii = null;
    sendResponse({ ok: true });
    return false;
  }
  return false;
});
