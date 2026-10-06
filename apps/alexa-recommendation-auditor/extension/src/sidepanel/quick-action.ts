import { FOOTWEAR_PROMPT_VERSION, type ExperimentRun } from "@alexa-auditor/contracts";

export type RecommendationIndexAction = "open_report" | "continue_run" | "prepare_run";

export function recommendationIndexAction(run: ExperimentRun | null): RecommendationIndexAction {
  if (run?.status === "completed" && run.completedTurns > 0) return "open_report";
  if (run && run.promptVersion !== FOOTWEAR_PROMPT_VERSION) return "prepare_run";
  const hasPending = Boolean(run?.promptCases.some((item) => item.enabled && item.status === "pending"));
  if (run && hasPending && ["ready", "stopped", "running"].includes(run.status)) return "continue_run";
  return "prepare_run";
}
