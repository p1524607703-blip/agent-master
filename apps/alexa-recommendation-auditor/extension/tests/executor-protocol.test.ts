import { describe, expect, it } from "vitest";
import {
  EXECUTOR_BUILD,
  EXECUTOR_PROTOCOL_VERSION,
  executorCompatibilityError
} from "../src/run/executor-protocol";

describe("executor protocol handshake", () => {
  it("accepts the matching background build", () => {
    expect(executorCompatibilityError({
      ok: true,
      executorBuild: EXECUTOR_BUILD,
      protocolVersion: EXECUTOR_PROTOCOL_VERSION
    })).toBe("");
  });

  it("rejects an old worker that does not answer the handshake", () => {
    expect(executorCompatibilityError(null)).toContain("旧版或无响应的 service worker");
  });

  it("rejects a mixed sidepanel/background build", () => {
    const message = executorCompatibilityError({ ok: true, executorBuild: "old-build", protocolVersion: 1 });
    expect(message).toContain("扩展前后台版本不一致");
    expect(message).toContain(EXECUTOR_BUILD);
  });
});
