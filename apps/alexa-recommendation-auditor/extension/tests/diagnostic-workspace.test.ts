import { describe, expect, it } from "vitest";
import {
  diagnosticWorkspaceAlarmName,
  isDiagnosticWorkspaceAlarm
} from "../src/run/diagnostic-workspace";

describe("diagnostic workspace cleanup alarm", () => {
  it("uses a namespaced persistent alarm per run", () => {
    const name = diagnosticWorkspaceAlarmName("run-123");
    expect(name).toBe("alexa-auditor:diagnostic-workspace:run-123");
    expect(isDiagnosticWorkspaceAlarm(name)).toBe(true);
  });

  it("ignores unrelated Chrome alarms", () => {
    expect(isDiagnosticWorkspaceAlarm("another-extension:alarm")).toBe(false);
    expect(isDiagnosticWorkspaceAlarm("alexa-auditor:diagnostic-workspace:")).toBe(false);
  });
});
