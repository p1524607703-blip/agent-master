import { describe, expect, it } from "vitest";
import type { PromptCase } from "@alexa-auditor/contracts";
import {
  isPromptDraftDirty,
  newPromptDraft,
  normalizePromptDraftText,
  syncPromptDrafts
} from "../src/sidepanel/prompt-drafts";

const prompt = (templateId: string, promptText: string): PromptCase => ({
  id: `${templateId}:r1`, templateId, slot: templateId, mode: "blind", expression: "direct", promptText,
  testRole: "positive_control", enabled: true, scoreEligible: true, hypothesis: "test", expectedMatch: "eligible",
  evidenceFactIds: ["fact"], requiredTerms: [], judgmentCriteria: [], promptVersion: "test", sessionPolicy: "fresh",
  generatedBy: "deterministic", repeatIndex: 1, sequence: 1, status: "pending", revision: 1, editable: true
});

describe("developer question drafts", () => {
  it("preserves an unsaved draft when another template updates the server revision", () => {
    const drafts = { a: newPromptDraft(prompt("a", "Original A")), b: newPromptDraft(prompt("b", "Original B")) };
    drafts.b.promptText = "Unsaved B";
    syncPromptDrafts(drafts, [prompt("a", "Saved A"), prompt("b", "Original B")]);
    expect(drafts.a.promptText).toBe("Saved A");
    expect(drafts.b.promptText).toBe("Unsaved B");
    expect(isPromptDraftDirty(drafts.b)).toBe(true);
  });

  it("marks a just-saved draft clean when the server now matches it", () => {
    const drafts = { a: newPromptDraft(prompt("a", "Original A")) };
    drafts.a.promptText = "Saved A";
    syncPromptDrafts(drafts, [prompt("a", "Saved A")]);
    expect(isPromptDraftDirty(drafts.a)).toBe(false);
    expect(drafts.a.changeReason).toBe("");
  });

  it("uses the same NFKC and whitespace normalization as the server", () => {
    const draft = newPromptDraft(prompt("a", "请列出女士 人字拖,但不要出现徒步靴。"));
    draft.promptText = "  请列出女士\n人字拖，但不要出现徒步靴。  ";

    expect(normalizePromptDraftText(draft.promptText)).toBe("请列出女士 人字拖,但不要出现徒步靴。");
    expect(isPromptDraftDirty(draft)).toBe(false);
  });

  it("clears a saved draft when the server returns normalized text", () => {
    const drafts = { a: newPromptDraft(prompt("a", "原始问题")) };
    drafts.a.promptText = "  保存后的\n问题  ";

    syncPromptDrafts(drafts, [prompt("a", "保存后的 问题")]);

    expect(drafts.a.promptText).toBe("保存后的 问题");
    expect(isPromptDraftDirty(drafts.a)).toBe(false);
  });
});
