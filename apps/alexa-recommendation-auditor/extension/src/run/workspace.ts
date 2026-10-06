export const AMAZON_HOME = "https://www.amazon.com/";

export type ExecutionWorkspace = {
  tabId: number;
  windowId: number;
  mode: "background_tab";
};

type WorkspaceChrome = Pick<typeof chrome, "tabs">;

function validChromeId(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function validTab(tab: chrome.tabs.Tab | undefined): tab is chrome.tabs.Tab & { id: number; windowId: number } {
  return validChromeId(tab?.id) && validChromeId(tab?.windowId);
}

/** Create an inactive Amazon tab in the current Chrome window. */
export async function createExecutionWorkspace(api: WorkspaceChrome = chrome): Promise<ExecutionWorkspace> {
  const tab = await api.tabs.create({ url: AMAZON_HOME, active: false });
  if (!validTab(tab)) throw new Error("无法创建后台 Amazon 测试标签页");
  return { tabId: tab.id, windowId: tab.windowId, mode: "background_tab" };
}

export function freshNavigationProperties(workspace: ExecutionWorkspace): chrome.tabs.UpdateProperties {
  return {
    url: AMAZON_HOME,
    active: false
  };
}

export function canCaptureWorkspace(_workspace: ExecutionWorkspace): boolean {
  // captureVisibleTab depends on a transient activeTab grant from a user
  // gesture. Background runs intentionally have no such gesture and must
  // never capture whichever window happens to be in the foreground.
  return false;
}

export async function disposeExecutionWorkspace(workspace: ExecutionWorkspace, api: WorkspaceChrome = chrome): Promise<void> {
  await api.tabs.remove(workspace.tabId).catch(() => undefined);
}
