import { describe, expect, it, vi } from "vitest";
import {
  AMAZON_HOME,
  canCaptureWorkspace,
  createExecutionWorkspace,
  disposeExecutionWorkspace,
  freshNavigationProperties
} from "../src/run/workspace";

describe("background execution workspace", () => {
  it("uses one inactive tab in the current window and never creates a new window", async () => {
    const removeTab = vi.fn().mockResolvedValue(undefined);
    const createWindow = vi.fn();
    const api = {
      windows: {
        create: createWindow,
        remove: vi.fn()
      },
      tabs: {
        create: vi.fn().mockResolvedValue({ id: 33, windowId: 4 }),
        query: vi.fn(),
        remove: removeTab
      }
    } as unknown as Pick<typeof chrome, "tabs">;

    const workspace = await createExecutionWorkspace(api);
    expect(createWindow).not.toHaveBeenCalled();
    expect(api.tabs.create).toHaveBeenCalledWith({ url: AMAZON_HOME, active: false });
    expect(workspace).toEqual({ tabId: 33, windowId: 4, mode: "background_tab" });
    expect(freshNavigationProperties(workspace)).toEqual({ url: AMAZON_HOME, active: false });
    expect(canCaptureWorkspace(workspace)).toBe(false);

    await disposeExecutionWorkspace(workspace, api);
    expect(removeTab).toHaveBeenCalledWith(33);
  });

  it("rejects a malformed background tab instead of touching any existing tab", async () => {
    const api = {
      tabs: {
        create: vi.fn().mockResolvedValue({ id: undefined, windowId: 4 }),
        query: vi.fn(),
        remove: vi.fn()
      }
    } as unknown as Pick<typeof chrome, "tabs">;

    await expect(createExecutionWorkspace(api)).rejects.toThrow("无法创建后台 Amazon 测试标签页");
    expect(api.tabs.remove).not.toHaveBeenCalled();
  });
});
