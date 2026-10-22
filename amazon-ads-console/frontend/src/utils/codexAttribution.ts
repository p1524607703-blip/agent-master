export type Attribution = {
  status:string; capturedAt?:string; startedAt?:string; resetsAt?:number; windowDurationMins?:number;
  usedPercent:number|null; remainingPercent:number|null; confirmedPercent:number|null; unattributedPercent:number|null;
  members:{userId:number; usedPercent:number; evidence:{method:string; confirmedAt:string}[]}[];
}

export function confirmedShare(value:Attribution|undefined, userId:number, fresh:boolean):number|null {
  if (!fresh || value?.status !== 'available') return null
  const row = value.members.find(r=>r.userId===userId)
  return row && Number.isFinite(row.usedPercent) && row.usedPercent >= 0 && row.usedPercent <= 100 ? row.usedPercent : null
}
