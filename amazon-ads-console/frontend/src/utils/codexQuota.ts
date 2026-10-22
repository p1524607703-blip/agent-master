export type QuotaWindow = { usedPercent:number; remainingPercent:number; windowDurationMins:number; resetsAt:number }
export type AccountQuota = { status:string; capturedAt?:string; primary:QuotaWindow|null; secondary:QuotaWindow|null; planType?:string|null; accountTotalTokens?:number|null; tokenTotalScope?:string }

// primary/secondary are positions, not stable meanings across subscription plans.
export function quotaDisplay(quota:AccountQuota|undefined, now:number, overviewStale:boolean) {
  const age = now - Date.parse(quota?.capturedAt || '')
  const fresh = !overviewStale && quota?.status === 'available' && Number.isFinite(age) && age >= -30000 && age <= 300000
  const windows = fresh ? (['primary','secondary'] as const).flatMap(key => {
    const w = quota?.[key]
    if (!w || !Number.isFinite(w.remainingPercent) || w.remainingPercent < 0 || w.remainingPercent > 100 ||
      !Number.isInteger(w.windowDurationMins) || w.windowDurationMins <= 0 || !Number.isInteger(w.resetsAt) || w.resetsAt <= 0 || !Number.isFinite(new Date(w.resetsAt*1000).getTime())) return []
    const title = w.windowDurationMins === 300 ? '5小时额度' : w.windowDurationMins === 10080 ? '每周额度' : `${w.windowDurationMins}分钟额度`
    return [{key, title, ...w}]
  }) : []
  const messages:Record<string,string> = {unconfigured:'尚未接入', unavailable:'读取失败', stale:'数据过期'}
  const state = fresh ? windows.length ? '采集正常' : '官方未返回可展示窗口' :
    overviewStale || quota?.status === 'available' ? '数据过期或连接中断' : messages[quota?.status || 'unconfigured'] || '读取失败'
  return {fresh, windows, state}
}
