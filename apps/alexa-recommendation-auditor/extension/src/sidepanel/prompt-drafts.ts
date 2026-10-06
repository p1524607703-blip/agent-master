import type { PromptCase } from "@alexa-auditor/contracts";

export interface PromptDraft {
  promptText: string;
  enabled: boolean;
  changeReason: string;
  serverPromptText: string;
  serverEnabled: boolean;
}

export function normalizePromptDraftText(value: string): string {
  return String(value || "").normalize("NFKC").replace(/\s+/g, " ").trim();
}

export function newPromptDraft(prompt: PromptCase): PromptDraft {
  return {
    promptText: prompt.promptText,
    enabled: prompt.enabled,
    changeReason: "",
    serverPromptText: prompt.promptText,
    serverEnabled: prompt.enabled
  };
}

export function isPromptDraftDirty(draft: PromptDraft | undefined): boolean {
  return Boolean(draft && (
    normalizePromptDraftText(draft.promptText) !== normalizePromptDraftText(draft.serverPromptText)
    || draft.enabled !== draft.serverEnabled
  ));
}

export function syncPromptDrafts(
  drafts: Record<string, PromptDraft>,
  prompts: PromptCase[],
  resetAll = false
): void {
  const active = new Set(prompts.map((prompt) => prompt.templateId));
  Object.keys(drafts).forEach((templateId) => {
    if (resetAll || !active.has(templateId)) delete drafts[templateId];
  });
  prompts.forEach((prompt) => {
    const draft = drafts[prompt.templateId];
    const serverNowMatchesDraft = draft
      ? normalizePromptDraftText(draft.promptText) === normalizePromptDraftText(prompt.promptText)
        && draft.enabled === prompt.enabled
      : false;
    if (!draft || !isPromptDraftDirty(draft) || serverNowMatchesDraft) {
      drafts[prompt.templateId] = newPromptDraft(prompt);
    }
  });
}
