import type { PromptCase } from "@alexa-auditor/contracts";

export function resolveSessionStart(
  prompt: Pick<PromptCase, "sessionPolicy" | "sessionGroup" | "templateId">,
  activeSessionGroup: string | null
): { freshSession: boolean; nextSessionGroup: string | null } {
  if (prompt.sessionPolicy !== "shared_sequence") {
    return { freshSession: true, nextSessionGroup: null };
  }
  const group = prompt.sessionGroup || prompt.templateId;
  return { freshSession: group !== activeSessionGroup, nextSessionGroup: group };
}
