export type Attribution = {
  status:string; capturedAt?:string; startedAt?:string; resetsAt?:number; windowDurationMins?:number;
  usedPercent:number|null; remainingPercent:number|null; confirmedPercent:number|null; unattributedPercent:number|null;
  ownerConfirmedPercent?:number; automaticPercent?:number;
  automaticMonitor?:{status:string; capturedAt:string; reason:string};
  deviceShares?:{userId:number; deviceId:string; usedPercent:number}[];
  members:{userId:number; usedPercent:number; evidence:{method:string; confirmedAt:string}[]}[];
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
  return manual && automatic ? '本人确认＋自动推定' : automatic ? '单一来源自动推定' : manual ? '本人确认归属' : '暂无已归属消耗'
}
