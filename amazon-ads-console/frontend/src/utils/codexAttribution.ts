export type Attribution = {
  status:string; capturedAt?:string; startedAt?:string; resetsAt?:number; windowDurationMins?:number;
  usedPercent:number|null; remainingPercent:number|null; confirmedPercent:number|null; unattributedPercent:number|null;
  ownerConfirmedPercent?:number; automaticPercent?:number; concurrentEstimatedPercent?:number; partialConcurrentEstimate?:boolean;
  provisionalPercent?:number;
  batchMonitoring?:{status:string;cutoverAt:string;capturedAt:string;observedEstimatePercent:number;pendingBatchPercent:number;recalculationCount:number;observationSeconds:number;
    latestBatches:{batchId:string;groupId:string;quotaCapturedAt:string;points:number;status:string;revision:number;updatedAt:string;confidence:string;unattributedPercent:number;startedAt:string;throughAt:string;observeUntil:string;waitingDeviceIds:string[]}[]} | null;
  automaticMonitor?:{status:string; capturedAt:string; reason:string; pendingSettlementPercent?:number; waitingDeviceIds?:string[]};
  deviceShares?:{userId:number; deviceId:string; usedPercent:number}[];
  members:{userId:number; usedPercent:number; evidence:{method:string; confirmedAt:string; partialMeasurement?:boolean}[]}[];
}

export function confirmedShare(value:Attribution|undefined, userId:number, fresh:boolean):number|null {
  if (!fresh || value?.status !== 'available') return null
  const row = value.members.find(r=>r.userId===userId)
  return row && Number.isFinite(row.usedPercent) && row.usedPercent >= 0 && row.usedPercent <= 100 ? row.usedPercent : null
}

export function attributionMethod(value:Attribution|undefined, userId:number):string {
  const evidence = value?.members.find(row=>row.userId===userId)?.evidence || []
  const manual = evidence.some(e=>e.method==='owner-confirmed')
  const automatic = evidence.some(e=>e.method.startsWith('observed-exclusive-'))
  const weighted = evidence.some(e=>e.method==='observed-token-weighted-interval')
  const provisional = evidence.some(e=>e.method==='provisional-token-weighted-batch')
  const observed = evidence.some(e=>e.method==='observed-token-weighted-batch')
  if(provisional || observed) return [manual?'本人确认':'',automatic?'单一来源推定':'',weighted?'旧版并发估算':'',provisional?'批次暂估（可自动回算）':'',observed?'观察后估算（仍可修订）':''].filter(Boolean).join('＋')
  if (weighted) return [manual ? '本人确认' : '', automatic ? '单一来源推定' : '', '并发用量估算'].filter(Boolean).join('＋')
  return manual && automatic ? '本人确认＋自动推定' : automatic ? '单一来源自动推定' : manual ? '本人确认归属' : '暂无已归属消耗'
}

export function allocationLabel(value:number|null):string {
  if (value===null || !Number.isFinite(value) || value<0 || value>100) return '—'
  if (value>0 && value<0.0001) return '<0.0001%'
  return `${value.toLocaleString('zh-CN',{minimumFractionDigits:1,maximumFractionDigits:4})}%`
}
