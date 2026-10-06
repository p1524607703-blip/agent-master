import { describe, expect, it } from "vitest";
import { FOOTWEAR_PROMPT_VERSION, type ExperimentRun, type PromptCase } from "@alexa-auditor/contracts";
import { recommendationIndexAction } from "../src/sidepanel/quick-action";

function prompt(status: PromptCase["status"] = "pending"): PromptCase {
  return { id: "p1", templateId: "t1", slot: "control_primary_function", mode: "blind", expression: "direct", repeatIndex: 0, sequence: 1, revision: 1, promptText: "test", hypothesis: "test", expectedMatch: "eligible", testRole: "positive_control", scoreEligible: true, evidenceFactIds: ["title_0"], requiredTerms: [], judgmentCriteria: [], enabled: true, editable: false, generatedBy: "deterministic", promptVersion: FOOTWEAR_PROMPT_VERSION, sessionPolicy: "fresh", sessionGroup: "g1", status };
}

function run(overrides: Partial<ExperimentRun> = {}): ExperimentRun {
  const now = new Date().toISOString();
  return {
    id: "r1", productSnapshotId: "s1", status: "ready", accountLabel: "test", runSeed: "seed", preset: "smoke",
    promptLanguage: "zh-CN", sessionPolicy: "fresh", promptVersion: FOOTWEAR_PROMPT_VERSION, questionPlanRevision: 1,
    questionPlanEditable: false, questionPlanApprovedAt: now, questionPlanLockedAt: now, promptCount: 1, repetitions: 1,
    totalTurns: 1, completedTurns: 0, promptCases: [prompt()], score: null, diagnoses: [], createdAt: now, updatedAt: now,
    ...overrides
  };
}

describe("recommendation index one-click action", () => {
  it("opens an existing completed report", () => {
    expect(recommendationIndexAction(run({ status: "completed", completedTurns: 1, promptCases: [prompt("completed")] }))).toBe("open_report");
  });

  it("continues an executor-error run without regenerating the approved plan", () => {
    expect(recommendationIndexAction(run({ status: "stopped", stopReason: "executor_error" }))).toBe("continue_run");
  });

  it("continues a partially completed automatic sequence", () => {
    expect(recommendationIndexAction(run({ status: "stopped", totalTurns: 2, completedTurns: 1, promptCases: [prompt("completed"), { ...prompt(), id: "p2", templateId: "t2", sequence: 2 }] }))).toBe("continue_run");
  });

  it("regenerates a pending run created with an older prompt template", () => {
    expect(recommendationIndexAction(run({ promptVersion: "footwear-v4.0.0" }))).toBe("prepare_run");
  });

  it("prepares a fresh run when no executable question remains", () => {
    expect(recommendationIndexAction(run({ status: "stopped", completedTurns: 1, promptCases: [prompt("completed")] }))).toBe("prepare_run");
  });
});
