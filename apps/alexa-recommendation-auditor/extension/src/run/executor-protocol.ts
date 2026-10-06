export const EXECUTOR_PROTOCOL_VERSION = 2;
export const EXECUTOR_BUILD = "2026.07.17-no-window-prompt-isolation.1";

export type ExecutorInfo = {
  ok?: boolean;
  protocolVersion?: number;
  executorBuild?: string;
};

export function executorCompatibilityError(info: ExecutorInfo | null | undefined): string {
  if (
    info?.ok === true
    && info.protocolVersion === EXECUTOR_PROTOCOL_VERSION
    && info.executorBuild === EXECUTOR_BUILD
  ) return "";

  const actual = info?.executorBuild
    ? `${info.executorBuild} / protocol ${info.protocolVersion ?? "unknown"}`
    : "旧版或无响应的 service worker";
  return `扩展前后台版本不一致（当前后台：${actual}；需要：${EXECUTOR_BUILD} / protocol ${EXECUTOR_PROTOCOL_VERSION}）。请在 chrome://extensions 重新加载从 extension/dist 安装的扩展后再试。`;
}
