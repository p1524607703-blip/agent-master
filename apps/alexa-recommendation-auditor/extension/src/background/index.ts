import type { ConversationTurn, ExperimentRun, ProductSnapshot } from "@alexa-auditor/contracts";
import { SELECTOR_VERSION } from "../amazon/version";
import { diagnosticWorkspaceAlarmName, isDiagnosticWorkspaceAlarm } from "../run/diagnostic-workspace";
import { EXECUTOR_BUILD, EXECUTOR_PROTOCOL_VERSION } from "../run/executor-protocol";
import { classifyContentMessageFailure, contentMessageError } from "../run/message-delivery";
import { resolveSessionStart } from "../run/session";
import {
  canCaptureWorkspace,
  createExecutionWorkspace,
  disposeExecutionWorkspace,
  freshNavigationProperties,
  type ExecutionWorkspace
} from "../run/workspace";
import {
  AMAZON_TAB_QUERY_PATTERNS,
  asinFromAmazonPdpUrl,
  cacheAgeMs,
  isFreshStudioProductCache,
  isUsableStudioProductSnapshot,
  sanitizeProductSnapshotForStudio,
  selectAmazonProductTabByUrl,
  selectPreferredAmazonProductTab,
  studioSnapshotMatchesAsin,
  STUDIO_PRODUCT_CACHE_KEY,
  type StudioProductCache
} from "../studio/product-context";

const DEFAULT_SERVER = "http://127.0.0.1:4318";
const activeExecutions = new Map<string, { stopped: boolean; workspace?: ExecutionWorkspace }>();

async function scheduleDiagnosticWorkspaceCleanup(runId: string, workspace: ExecutionWorkspace): Promise<void> {
  const alarmName = diagnosticWorkspaceAlarmName(runId);
  await chrome.storage.local.set({ [alarmName]: workspace });
  await chrome.alarms.create(alarmName, { delayInMinutes: 1 });
}

chrome.alarms.onAlarm.addListener((alarm) => {
  if (!isDiagnosticWorkspaceAlarm(alarm.name)) return;
  void chrome.storage.local.get(alarm.name)
    .then(async (stored) => {
      const workspace = stored[alarm.name] as ExecutionWorkspace | undefined;
      if (workspace) await disposeExecutionWorkspace(workspace);
    })
    .finally(() => chrome.storage.local.remove(alarm.name));
});

chrome.runtime.onInstalled.addListener(() => {
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => undefined);
});

async function latestAmazonProductTab(preferredWindowId?: number): Promise<chrome.tabs.Tab & { id: number; url: string }> {
  const activeQuery: chrome.tabs.QueryInfo = Number.isInteger(preferredWindowId)
    ? { active: true, windowId: preferredWindowId }
    : { active: true, currentWindow: true };
  const [[active], tabs] = await Promise.all([
    chrome.tabs.query(activeQuery),
    chrome.tabs.query({ url: AMAZON_TAB_QUERY_PATTERNS })
  ]);
  return selectPreferredAmazonProductTab(active, tabs, preferredWindowId) as chrome.tabs.Tab & { id: number; url: string };
}

async function amazonProductTabForLink(
  productUrl: string,
  preferredWindowId?: number
): Promise<chrome.tabs.Tab & { id: number; url: string }> {
  const tabs = await chrome.tabs.query({ url: AMAZON_TAB_QUERY_PATTERNS });
  return selectAmazonProductTabByUrl(productUrl, tabs, preferredWindowId) as chrome.tabs.Tab & { id: number; url: string };
}

async function extractLatestProductContext(): Promise<{ snapshot: ProductSnapshot; tabId: number }> {
  const tab = await latestAmazonProductTab();
  const result = await sendTab<{ ok: boolean; snapshot?: ProductSnapshot; error?: string }>(tab.id, { type: "AUDITOR_EXTRACT_PRODUCT" });
  if (!result.ok || !result.snapshot) throw new Error(result.error || "读取最近使用的 Amazon 商品页失败");
  await chrome.storage.local.set({ latestAmazonProductContext: result.snapshot });
  return { snapshot: result.snapshot, tabId: tab.id };
}

function errorDetails(error: unknown): { error: string; errorCode: string } {
  const value = error instanceof Error ? error : new Error(String(error));
  return {
    error: value.message || "读取 Amazon 商品详情页失败",
    errorCode: String((value as Error & { code?: string }).code || "amazon_product_context_failed")
  };
}

function validStudioRequestId(value: unknown): value is string {
  return typeof value === "string" && /^[A-Za-z0-9._:-]{1,128}$/.test(value);
}

async function extractStudioProductContext(requestId: string, productUrl: string, preferredWindowId?: number): Promise<{
  ok: true;
  requestId: string;
  snapshot: ProductSnapshot;
  tabId: number;
  cached: false;
}> {
  const candidateAsin = asinFromAmazonPdpUrl(productUrl);
  if (!candidateAsin) {
    throw Object.assign(new Error("工作台提供的 Amazon 商品链接无效"), {
      code: "amazon_pdp_url_invalid",
      candidateUrl: productUrl
    });
  }
  let tab: chrome.tabs.Tab & { id: number; url: string };
  try {
    tab = await amazonProductTabForLink(productUrl, preferredWindowId);
  } catch (error) {
    throw Object.assign(error instanceof Error ? error : new Error(String(error)), {
      candidateAsin,
      candidateUrl: productUrl
    });
  }
  try {
    const result = await sendTab<{ ok: boolean; snapshot?: ProductSnapshot; error?: string }>(
      tab.id,
      { type: "AUDITOR_EXTRACT_STUDIO_PRODUCT" }
    );
    if (!result.ok || !result.snapshot) {
      throw Object.assign(new Error(result.error || "Amazon 商品详情页没有返回商品数据"), { code: "amazon_pdp_extract_failed" });
    }
    const snapshot = sanitizeProductSnapshotForStudio(result.snapshot);
    if (!isUsableStudioProductSnapshot(snapshot) || !studioSnapshotMatchesAsin(snapshot, candidateAsin)) {
      throw Object.assign(new Error("当前商品页的标题或 ASIN 尚未加载完成，已拒绝同步以避免串商品"), { code: "amazon_pdp_invalid" });
    }
    const cache: StudioProductCache = {
      snapshot,
      cachedAt: new Date().toISOString(),
      sourceTabId: tab.id
    };
    await chrome.storage.local.set({ [STUDIO_PRODUCT_CACHE_KEY]: cache }).catch(() => undefined);
    return { ok: true, requestId, snapshot, tabId: tab.id, cached: false };
  } catch (error) {
    const details = errorDetails(error);
    throw Object.assign(new Error(details.error), {
      code: details.errorCode,
      candidateAsin,
      candidateUrl: tab.url
    });
  }
}

async function cachedStudioProductContext(requestId: string, liveError: unknown): Promise<{
  ok: true;
  requestId: string;
  snapshot: ProductSnapshot;
  cached: true;
  warning: string;
  cacheAgeMs: number;
}> {
  const stored = await chrome.storage.local.get(STUDIO_PRODUCT_CACHE_KEY).catch(() => ({})) as Record<string, unknown>;
  const storedCache = stored[STUDIO_PRODUCT_CACHE_KEY] as StudioProductCache | undefined;
  const cache = storedCache
    ? { ...storedCache, snapshot: sanitizeProductSnapshotForStudio(storedCache.snapshot) }
    : undefined;
  const details = errorDetails(liveError);
  const candidateAsin = String((liveError as { candidateAsin?: string } | undefined)?.candidateAsin || "").toUpperCase();
  if (!isFreshStudioProductCache(cache)) {
    const age = cache ? cacheAgeMs(cache) : Number.POSITIVE_INFINITY;
    const expired = cache
      ? `；最近缓存已过期（${Number.isFinite(age) ? `${Math.round(age / 60000)} 分钟前` : "缓存时间无效"}）`
      : "";
    throw Object.assign(new Error(`${details.error}${expired}`), {
      code: cache ? "amazon_product_cache_expired" : details.errorCode
    });
  }
  if (candidateAsin && !studioSnapshotMatchesAsin(cache.snapshot, candidateAsin)) {
    throw Object.assign(
      new Error(`${details.error}；当前候选 ASIN ${candidateAsin} 与缓存商品 ${cache.snapshot.asin} 不一致，已拒绝跨商品回退`),
      { code: "amazon_product_cache_asin_mismatch" }
    );
  }
  const age = cacheAgeMs(cache);
  return {
    ok: true,
    requestId,
    snapshot: cache.snapshot,
    cached: true,
    warning: `${details.error}；已改用 ${Math.max(1, Math.round(age / 60000))} 分钟前的商品页缓存，请核对 ASIN 后再生成策划`,
    cacheAgeMs: age
  };
}

async function sendTab<T>(tabId: number, message: unknown): Promise<T> {
  try {
    return await chrome.tabs.sendMessage(tabId, message) as T;
  } catch (error) {
    const failure = classifyContentMessageFailure(error);
    // Injection + replay is safe only when Chrome proves that no listener
    // received the original message. A closed async channel is ambiguous: the
    // Rufus send button may already have been clicked, so replaying would ask
    // the same question twice and contaminate the experiment.
    if (!failure.retryableBeforeDelivery) throw contentMessageError(error);
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    try {
      return await chrome.tabs.sendMessage(tabId, message) as T;
    } catch (retryError) {
      throw contentMessageError(retryError);
    }
  }
}

function requireChromeId(value: unknown, label: string): number {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 0) {
    throw Object.assign(new Error(`后台工作区${label}无效，请重新加载扩展后重试`), { code: "workspace_invalid" });
  }
  return value;
}

async function navigateTabAndWait(
  tabId: number,
  properties: chrome.tabs.UpdateProperties,
  timeoutMs = 30000
): Promise<chrome.tabs.Tab> {
  const safeTabId = requireChromeId(tabId, "标签页ID");
  return new Promise((resolve, reject) => {
    let settled = false;
    const cleanup = () => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      clearTimeout(timeout);
    };
    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      cleanup();
      callback();
    };
    const isReady = (tab: chrome.tabs.Tab) => (
      tab.status === "complete" && Boolean(tab.url?.startsWith("https://www.amazon.com/"))
    );
    const onUpdated = (updatedTabId: number, changeInfo: { status?: string }, tab: chrome.tabs.Tab) => {
      if (updatedTabId !== safeTabId) return;
      if (changeInfo.status === "complete" && isReady(tab)) finish(() => resolve(tab));
    };
    const timeout = setTimeout(() => {
      finish(() => reject(Object.assign(new Error("等待Amazon首页加载超时"), { code: "selector_drift" })));
    }, timeoutMs);

    // Register before navigation so a very fast Amazon response cannot be
    // missed. The returned Tab also covers the no-navigation/same-URL case.
    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.update(safeTabId, properties)
      .then((tab) => {
        if (tab && isReady(tab)) finish(() => resolve(tab));
      })
      .catch((error) => finish(() => reject(error)));
  });
}

async function reloadTabAndWait(tabId: number, timeoutMs = 30000): Promise<chrome.tabs.Tab> {
  const safeTabId = requireChromeId(tabId, "标签页ID");
  return new Promise((resolve, reject) => {
    let sawLoading = false;
    let settled = false;
    const cleanup = () => {
      chrome.tabs.onUpdated.removeListener(onUpdated);
      clearTimeout(timeout);
    };
    const finish = (callback: () => void) => {
      if (settled) return;
      settled = true;
      cleanup();
      callback();
    };
    const onUpdated = (updatedTabId: number, changeInfo: { status?: string }, tab: chrome.tabs.Tab) => {
      if (updatedTabId !== safeTabId) return;
      if (changeInfo.status === "loading") sawLoading = true;
      if (sawLoading && changeInfo.status === "complete" && tab.url?.startsWith("https://www.amazon.com/")) {
        finish(() => resolve(tab));
      }
    };
    const timeout = setTimeout(() => {
      finish(() => reject(Object.assign(new Error("强制刷新Amazon首页超时"), { code: "selector_drift" })));
    }, timeoutMs);
    chrome.tabs.onUpdated.addListener(onUpdated);
    chrome.tabs.reload(safeTabId, { bypassCache: true }).catch((error) => {
      finish(() => reject(error));
    });
  });
}

async function verifyCurrentContentScript(tabId: number): Promise<void> {
  const result = await sendTab<{ ok?: boolean; selectorVersion?: string }>(tabId, { type: "AUDITOR_PING" });
  if (!result?.ok || result.selectorVersion !== SELECTOR_VERSION) {
    throw Object.assign(
      new Error(`Amazon页面脚本版本不一致：期望 ${SELECTOR_VERSION}，实际 ${result?.selectorVersion || "unknown"}`),
      { code: "selector_drift" }
    );
  }
}

async function prepareFreshAmazonHome(workspace: ExecutionWorkspace): Promise<chrome.tabs.Tab> {
  await navigateTabAndWait(workspace.tabId, freshNavigationProperties(workspace));
  // Chrome may restore the Amazon home document from BFCache after the
  // extension has been reloaded. A hard reload guarantees that the current
  // manifest content script owns the new test session before Rufus is opened.
  const tab = await reloadTabAndWait(workspace.tabId);
  await new Promise((resolve) => setTimeout(resolve, 900));
  await verifyCurrentContentScript(workspace.tabId);
  return tab;
}

async function api<T>(serverUrl: string, token: string, path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${serverUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}), ...(init.headers || {}) }
  });
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json() as Promise<T>;
}

async function captureMasked(workspace: ExecutionWorkspace): Promise<string | undefined> {
  if (!canCaptureWorkspace(workspace)) {
    throw new Error("background_tab_screenshot_skipped");
  }
  const tabId = requireChromeId(workspace.tabId, "标签页ID");
  const windowId = requireChromeId(workspace.windowId, "窗口ID");
  await sendTab(tabId, { type: "AUDITOR_MASK_PII" });
  try {
    return await chrome.tabs.captureVisibleTab(windowId, { format: "jpeg", quality: 72 });
  } finally {
    await sendTab(tabId, { type: "AUDITOR_UNMASK_PII" }).catch(() => undefined);
  }
}

async function captureMaskedWithRetry(workspace: ExecutionWorkspace): Promise<{ dataUrl?: string; error?: string }> {
  if (!canCaptureWorkspace(workspace)) {
    return { error: "background_mode_screenshot_skipped" };
  }
  let lastError = "";
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const dataUrl = await captureMasked(workspace);
      if (dataUrl) return { dataUrl };
      lastError = "capture_returned_empty";
    } catch (error) {
      lastError = (error as Error).message || String(error);
    }
    if (attempt === 0) await new Promise((resolve) => setTimeout(resolve, 400));
  }
  return { error: lastError || "capture_failed" };
}

function postProgress(port: chrome.runtime.Port, message: Record<string, unknown>): void {
  try {
    port.postMessage(message);
  } catch {
    // The side panel is only a monitor. Closing it, switching tabs, or
    // re-opening it must never abort the background experiment.
  }
}

async function executeRun(port: chrome.runtime.Port, options: { run: ExperimentRun; serverUrl: string; token: string; minIntervalMs?: number }) {
  const { run, serverUrl, token } = options;
  if (activeExecutions.has(run.id)) throw new Error("该测试已经在运行");
  const state: { stopped: boolean; workspace?: ExecutionWorkspace; preserveWorkspaceForDiagnostics?: boolean } = { stopped: false };
  activeExecutions.set(run.id, state);
  let failures = 0;
  let phase = "workspace_create";
  try {
    const workspace = await createExecutionWorkspace();
    state.workspace = workspace;
    phase = "run_fetch";
    const authoritative = await api<ExperimentRun>(serverUrl, token, `/api/v1/runs/${run.id}`);
    phase = "run_start";
    let current = authoritative.status === "running"
      ? authoritative
      : await api<ExperimentRun>(serverUrl, token, `/api/v1/runs/${run.id}/start`, { method: "POST", body: "{}" });
    postProgress(port, {
      type: authoritative.status === "running" ? "RUN_RESUMED" : "RUN_STARTED",
      runId: run.id,
      run: current,
      workspaceMode: workspace.mode,
      executorBuild: EXECUTOR_BUILD
    });
    const pending = current.promptCases.filter((item) => item.enabled && item.status === "pending");
    if (!pending.length) throw new Error("没有可继续执行的pending问题");
    const completedBeforeResume = current.completedTurns;
    let activeSessionGroup: string | null = null;
    for (let index = 0; index < pending.length; index += 1) {
      const prompt = pending[index];
      if (state.stopped) break;
      const sessionStart = resolveSessionStart(prompt, activeSessionGroup);
      const freshSession = sessionStart.freshSession;
      activeSessionGroup = sessionStart.nextSessionGroup;
      if (freshSession) {
        phase = `prepare_session:${prompt.id}`;
        await prepareFreshAmazonHome(workspace);
      }
      postProgress(port, { type: "TURN_STARTED", runId: run.id, prompt, index: completedBeforeResume + index + 1, total: current.totalTurns });
      phase = `submit_prompt:${prompt.id}`;
      const result = await sendTab<{
        ok: boolean;
        responseText?: string;
        recommendations?: ConversationTurn["recommendations"];
        extractionDiagnostics?: ConversationTurn["extractionDiagnostics"];
        selectorVersion?: string;
        error?: string;
        errorCode?: string;
      }>(workspace.tabId, {
        type: "AUDITOR_RUN_PROMPT", promptText: prompt.promptText, freshSession
      });
      if (state.stopped) break;
      phase = `capture_result:${prompt.id}`;
      const screenshot = await captureMaskedWithRetry(workspace);
      if (state.stopped) break;
      const turn: ConversationTurn = {
        runId: run.id,
        promptCaseId: prompt.id,
        promptText: prompt.promptText,
        responseText: result.responseText || "",
        recommendations: result.recommendations || [],
        screenshotDataUrl: screenshot.dataUrl,
        screenshotError: screenshot.error,
        extractionDiagnostics: result.extractionDiagnostics,
        selectorVersion: result.selectorVersion || "unknown",
        status: result.ok ? "completed" : "failed",
        errorCode: result.errorCode,
        errorMessage: result.error,
        capturedAt: new Date().toISOString()
      };
      phase = `record_turn:${prompt.id}`;
      current = await api<ExperimentRun>(serverUrl, token, `/api/v1/runs/${run.id}/turns`, { method: "POST", body: JSON.stringify(turn) });
      postProgress(port, { type: "TURN_RECORDED", runId: run.id, run: current, prompt, result });
      if (!result.ok) failures += 1; else failures = 0;
      if (["captcha", "rate_limited", "forbidden", "login_required", "selector_drift", "context_isolation_failed", "response_timeout"].includes(String(result.errorCode)) || failures >= 3 || current.status === "stopped") break;
      if (index < pending.length - 1) {
        phase = `between_turns:${prompt.id}`;
        await new Promise((resolve) => setTimeout(resolve, Math.max(12000, Number(options.minIntervalMs || 12000))));
      }
    }
    phase = "run_finalize";
    const final = await api<ExperimentRun>(serverUrl, token, `/api/v1/runs/${run.id}`);
    postProgress(port, { type: "RUN_FINISHED", runId: run.id, run: final });
  } catch (error) {
    const original = error instanceof Error ? error : new Error(String(error));
    const errorCode = (original as Error & { code?: string }).code;
    if (state.workspace && ["message_channel_closed", "message_target_gone"].includes(String(errorCode))) {
      // Keep the background diagnostic tab around briefly instead of making
      // it appear to vanish. This lets the operator verify whether a
      // prompt reached Rufus without sending it again.
      state.preserveWorkspaceForDiagnostics = true;
    }
    throw Object.assign(
      new Error(`[${phase}] ${original.message} · executor ${EXECUTOR_BUILD}`),
      { code: errorCode }
    );
  } finally {
    if (state.workspace && state.preserveWorkspaceForDiagnostics) {
      await scheduleDiagnosticWorkspaceCleanup(run.id, state.workspace);
    } else if (state.workspace) {
      await disposeExecutionWorkspace(state.workspace);
    }
    activeExecutions.delete(run.id);
  }
}

chrome.runtime.onConnect.addListener((port) => {
  if (port.name !== "alexa-auditor") return;
  port.onMessage.addListener((message) => {
    if (message?.type === "EXECUTE_RUN") {
      if (message.protocolVersion !== EXECUTOR_PROTOCOL_VERSION || message.sidepanelBuild !== EXECUTOR_BUILD) {
        postProgress(port, {
          type: "RUN_ERROR",
          runId: message.run?.id,
          error: `扩展前后台协议不一致，请在 chrome://extensions 重新加载扩展 · executor ${EXECUTOR_BUILD}`
        });
        return;
      }
      executeRun(port, message).catch(async (error) => {
        let stoppedRun: ExperimentRun | undefined;
        try {
          stoppedRun = await api<ExperimentRun>(message.serverUrl || DEFAULT_SERVER, message.token, `/api/v1/runs/${message.run.id}/stop`, {
            method: "POST",
            body: JSON.stringify({ reason: "executor_error" })
          });
        } catch {
          // The server may already have safety-stopped the run. Preserve the
          // original execution error and let the sidepanel offer a manual stop.
        }
        postProgress(port, { type: "RUN_ERROR", runId: message.run.id, error: (error as Error).message, ...(stoppedRun ? { run: stoppedRun } : {}) });
      });
    }
    if (message?.type === "STOP_RUN") {
      const state = activeExecutions.get(String(message.runId));
      if (state) state.stopped = true;
      api(message.serverUrl || DEFAULT_SERVER, message.token, `/api/v1/runs/${message.runId}/stop`, { method: "POST", body: JSON.stringify({ reason: "user_requested" }) })
        .then((run) => postProgress(port, { type: "RUN_FINISHED", runId: message.runId, run }))
        .catch((error) => postProgress(port, { type: "RUN_ERROR", runId: message.runId, error: (error as Error).message }));
    }
  });
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "GET_EXECUTOR_INFO") {
    sendResponse({ ok: true, executorBuild: EXECUTOR_BUILD, protocolVersion: EXECUTOR_PROTOCOL_VERSION });
    return false;
  }
  if (message?.type === "GET_ACTIVE_PRODUCT") {
    latestAmazonProductTab()
      .then(async (tab) => {
        const result = await sendTab<{ ok: boolean; snapshot?: ProductSnapshot; error?: string }>(tab.id, { type: "AUDITOR_EXTRACT_PRODUCT" });
        return { ...result, tabId: tab.id };
      })
      .then(sendResponse)
      .catch((error) => sendResponse({ ok: false, error: (error as Error).message }));
    return true;
  }
  if (message?.type === "GET_LATEST_AMAZON_PRODUCT_CONTEXT") {
    extractLatestProductContext()
      .then((result) => sendResponse({ ok: true, ...result }))
      .catch(async (error) => {
        const saved = await chrome.storage.local.get("latestAmazonProductContext").catch(() => ({})) as { latestAmazonProductContext?: ProductSnapshot };
        if (saved.latestAmazonProductContext) {
          sendResponse({ ok: true, snapshot: saved.latestAmazonProductContext, cached: true, warning: (error as Error).message });
          return;
        }
        sendResponse({ ok: false, error: (error as Error).message });
      });
    return true;
  }
  if (message?.type === "GET_STUDIO_AMAZON_PRODUCT_CONTEXT") {
    const requestId = message.requestId;
    if (!validStudioRequestId(requestId)) {
      sendResponse({
        ok: false,
        requestId: typeof requestId === "string" ? requestId : "",
        error: "工作台请求ID无效，请刷新工作台后重试",
        errorCode: "invalid_request_id"
      });
      return false;
    }
    const preferredWindowId = typeof sender.tab?.windowId === "number"
      && Number.isInteger(sender.tab.windowId)
      && sender.tab.windowId >= 0
      ? sender.tab.windowId
      : undefined;
    extractStudioProductContext(requestId, String(message.productUrl || ""), preferredWindowId)
      .then(sendResponse)
      .catch(async (liveError) => {
        try {
          sendResponse(await cachedStudioProductContext(requestId, liveError));
        } catch (cacheError) {
          sendResponse({ ok: false, requestId, ...errorDetails(cacheError) });
        }
      });
    return true;
  }
  if (message?.type === "OPEN_REPORT") {
    chrome.tabs.create({ url: `${message.serverUrl || DEFAULT_SERVER}/reports/${message.runId}` }).then(() => sendResponse({ ok: true }));
    return true;
  }
  if (message?.type === "GET_EXECUTION_STATUS") {
    sendResponse({
      active: activeExecutions.has(String(message.runId || "")),
      executorBuild: EXECUTOR_BUILD,
      protocolVersion: EXECUTOR_PROTOCOL_VERSION
    });
    return false;
  }
  return false;
});
