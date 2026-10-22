export type ActivityState = 'active' | 'recent' | 'idle' | 'unknown' | 'revoked'
export type ActivityDevice = {
  activityStatus?: ActivityState
  activeRequests?: number
  lastActivityAt?: string | null
  revoked: boolean
}

export function activityState(device: ActivityDevice, serverNow: number, fresh: boolean, recentSeconds = 300): ActivityState {
  if (device.revoked) return 'revoked'
  if (!fresh || !Number.isFinite(serverNow) || !device.activityStatus || device.activityStatus === 'unknown') return 'unknown'
  if (device.activityStatus === 'active' && (device.activeRequests ?? 0) > 0) return 'active'
  if (!device.lastActivityAt) return 'idle'
  const age = serverNow - Date.parse(device.lastActivityAt)
  if (!Number.isFinite(age) || age < -30000) return 'unknown'
  return age <= recentSeconds * 1000 ? 'recent' : 'idle'
}

export const activityLabels: Record<ActivityState, string> = {
  active: '正在使用', recent: '最近活跃', idle: '暂无近期请求', unknown: '状态待确认', revoked: '已停用',
}
