export const DIAGNOSTIC_WORKSPACE_ALARM_PREFIX = "alexa-auditor:diagnostic-workspace:";

export function diagnosticWorkspaceAlarmName(runId: string): string {
  return `${DIAGNOSTIC_WORKSPACE_ALARM_PREFIX}${runId}`;
}

export function isDiagnosticWorkspaceAlarm(name: string): boolean {
  return name.startsWith(DIAGNOSTIC_WORKSPACE_ALARM_PREFIX)
    && name.length > DIAGNOSTIC_WORKSPACE_ALARM_PREFIX.length;
}
