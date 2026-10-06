import { describe, expect, it } from "vitest";
import { resolveSessionStart } from "../src/run/session";

describe("run session isolation", () => {
  it("always starts a fresh session for isolated questions", () => {
    expect(resolveSessionStart({ sessionPolicy: "fresh", templateId: "a" }, "old")).toEqual({
      freshSession: true,
      nextSessionGroup: null
    });
  });

  it("starts the first shared turn fresh and only reuses the same sequence", () => {
    const first = resolveSessionStart({ sessionPolicy: "shared_sequence", sessionGroup: "diagnostic-1", templateId: "a" }, null);
    const second = resolveSessionStart({ sessionPolicy: "shared_sequence", sessionGroup: "diagnostic-1", templateId: "b" }, first.nextSessionGroup);
    const nextGroup = resolveSessionStart({ sessionPolicy: "shared_sequence", sessionGroup: "diagnostic-2", templateId: "c" }, second.nextSessionGroup);

    expect(first.freshSession).toBe(true);
    expect(second.freshSession).toBe(false);
    expect(nextGroup.freshSession).toBe(true);
  });
});
