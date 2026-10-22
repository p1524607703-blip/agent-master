"""Observed activity attribution with explicitly estimated concurrent quota allocation.

A quota counter is rounded and account-wide. Carry all candidate sources until it
moves, retaining a 30-minute overlap warning for delayed reporting. Concurrent
sources use observed interval Token weights; gaps and corrections remain unallocated. This cannot cover unmonitored clients.
"""
import asyncio
import fcntl
import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.core.config import settings
from app.services.auth import _connect
from app.services.codex_attribution import current_window, private_json, host_usage
from app.services.codex_quota import snapshot
from app.services.codex_telemetry import spool_dir, flush_events

MAX_GAP = 300
REPORTING_GUARD = 1800


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.timestamp()


def matches(entry, window, plan):
    return (entry.get('resetsAt'), entry.get('windowDurationMins'), entry.get('planType')) == (window['resetsAt'], window['windowDurationMins'], plan)


def atomic(path, value):
    path = Path(path)
    payload = json.dumps(value, separators=(',', ':')).encode()
    if len(payload) > 65536:
        raise ValueError('attribution document full; preserve audit and stop')
    fd, tmp = tempfile.mkstemp(prefix=path.name+'.', dir=str(path.parent))
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload); stream.flush(); os.fsync(stream.fileno())
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def proportional_points(points, weights):
    """Allocate integer micro-percentage points with deterministic largest remainders."""
    unit = Decimal('0.000001')
    micros = int((points/unit).to_integral_value(rounding='ROUND_DOWN'))
    total = sum(weights.values())
    base = {did:micros*weight//total for did,weight in weights.items()}
    remainder = micros-sum(base.values())
    order = sorted(weights, key=lambda did: (-(micros*weights[did] % total), did))
    for did in order[:remainder]:
        base[did] += 1
    return {did:Decimal(amount)*unit for did,amount in base.items()}


def advance(document, sample):
    """Observed Tokens remain exact; concurrent quota shares are explicitly estimated.

    Consume only new official points and new counter differences. Previously
    confirmed/inferred history is never redistributed. A pending batch waits for an active
    source's first measurable result, independently of later quota changes.
    """
    document = json.loads(json.dumps(document))
    window, plan = sample['window'], sample['planType']
    at, used = sample['capturedAt'], Decimal(str(window['usedPercent']))
    identity = [window['resetsAt'], window['windowDurationMins'], plan]
    state = document.get('autoState') or {}
    same = state.get('window') == identity
    if same and state.get('capturedAt') and stamp(at) <= stamp(state['capturedAt']):
        return document
    if not same:
        state = {'window':identity, 'usedPercent':float(used), 'boundaryAt':sample['startedAt'],
                 'sources':{}, 'candidates':[], 'blocked':False}
    if not sample['healthy']:
        state['blocked'] = True
        document['autoState'] = state
        document['monitor'] = {'status':'paused', 'capturedAt':at,
                               'reason':sample.get('reason','coverage-unavailable'),
                               'scope':'monitored-sources-only', 'allocationVersion':2}
        return document
    by_id = {row['deviceId']:row for row in sample['sources']}
    previous = state.get('sources', {}) if same else {}
    # Upgrade takes the last old sample as a new measurement baseline; it never
    # redistributes points allocated by a previous version.
    baseline = state.get('weightBaseline', previous) if same else {}
    candidates = set(state.get('candidates', []))
    recent = set()
    blocked = bool(state.get('blocked'))
    if same and state.get('capturedAt') and stamp(at)-stamp(state['capturedAt']) > MAX_GAP:
        blocked = True
    for did,row in by_id.items():
        old = previous.get(did, {})
        if any(row[k] < old.get(k,0) for k in ('events','tokens')):
            blocked = True
        if row['events'] > old.get('events',0) or row['unknown'] > old.get('unknown',0) or row.get('inFlight'):
            candidates.add(did)
        if row.get('recentActivity') or (row.get('lastActivityAt') and stamp(at)-stamp(row['lastActivityAt']) <= REPORTING_GUARD):
            recent.add(did)
    if set(previous)-set(by_id):
        blocked = True
    records = document.get('confirmations',[]) + document.get('automatic',[])
    allocated = sum((Decimal(str(row['usedPercent'])) for row in records if matches(row,window,plan)),Decimal(0))
    if not same and used == allocated and allocated > 0:
        # Owner-confirmed history is a closed baseline, not future estimation weight.
        baseline, candidates = by_id, set()
        state['boundaryAt'] = at
    correction = bool(state.get('correction')) or (same and used < Decimal(str(state['usedPercent'])))
    blocked = blocked or correction
    delta = max(Decimal(0),used-Decimal(str(state['usedPercent']))) if same else max(Decimal(0),used-allocated)
    pending = min(max(Decimal(0),used-allocated),Decimal(str(state.get('pendingPoints',0)))+delta)
    reason = 'no-new-quota'
    status = 'active'
    weights = {did:row['tokens']-baseline.get(did,{}).get('tokens',0) for did,row in by_id.items()
               if row['tokens'] > baseline.get(did,{}).get('tokens',0)}
    waiting = sorted(did for did in candidates if did not in weights)
    boundary_sources = candidates | recent
    sole = next(iter(boundary_sources)) if len(boundary_sources)==1 else None
    entries = []
    settled = False
    if blocked:
        reason = 'coverage-gap-or-counter-correction'
        # The gap's points stay unallocated; subsequent clean intervals start fresh.
        pending = Decimal(0)
        baseline, candidates = by_id, set()
    elif pending > 0:
        if sole and sole in by_id and by_id[sole]['userId'] in sample['userIds'] and (by_id[sole]['events'] or by_id[sole]['unknown'] or by_id[sole].get('inFlight')):
            shares = {sole:pending}
            method = 'observed-exclusive-interval' if same else 'observed-exclusive-period'
            reason = 'exclusive-source-inferred'
        elif weights and not waiting:
            shares = proportional_points(pending,weights)
            method = 'observed-token-weighted-interval'
            reason = 'concurrent-token-estimate'
        else:
            shares = {}
            method = None
            reason = 'awaiting-device-measurement' if waiting else 'no-measurable-activity'
        if shares:
            key = hashlib.sha256(json.dumps([identity,at,str(pending),sorted(weights.items()),method],separators=(',',':')).encode()).hexdigest()[:24]
            incomplete = any(row['unknown'] > baseline.get(did,{}).get('unknown',0) or row.get('inFlight')
                             for did,row in by_id.items() if did in candidates) or (method=='observed-token-weighted-interval' and bool(boundary_sources-set(weights)))
            for did,amount in shares.items():
                owner=by_id[did]
                if owner['userId'] not in sample['userIds'] or amount<=0:
                    continue  # Its weight stays in denominator; its share stays unassigned.
                record_key='auto-'+hashlib.sha256(json.dumps([identity,did,method],separators=(',',':')).encode()).hexdigest()[:24]
                existing=next((row for row in document.get('automatic',[]) if row['confirmationId']==record_key),None)
                if existing:
                    existing['usedPercent']=float(Decimal(str(existing['usedPercent']))+amount)
                    existing['confirmedAt']=at
                    existing['batches']=existing.get('batches',1)+1
                    existing['partialMeasurement']=existing.get('partialMeasurement',False) or incomplete
                else:
                    document.setdefault('automatic',[]).append({
                        'confirmationId':record_key,'userId':owner['userId'],'deviceId':did,
                        'usedPercent':float(amount),'planType':plan,'resetsAt':window['resetsAt'],
                        'windowDurationMins':window['windowDurationMins'],'confirmedAt':at,
                        'method':method,'scope':'monitored-sources-only','officialDeviceBilling':False,
                        'firstConfirmedAt':at,'batches':1,'partialMeasurement':incomplete})
                entries.append({'deviceId':did,'userId':owner['userId'],'usedPercent':float(amount)})
            document.setdefault('pendingAudit',[]).append({
                'schemaVersion':1,'decisionId':key,'window':identity,'quotaUsedPercent':float(used),
                'points':float(pending),'startedAt':state.get('boundaryAt',sample['startedAt']),
                'endedAt':at,'method':method,'basis':'observed-total-token-deltas',
                'weights':weights,'allocations':entries,'partialMeasurement':incomplete,
                'missingMeasurementSources':waiting})
            baseline, candidates, pending = by_id,set(),Decimal(0)
            settled = True
    if correction or allocated>used:
        status='reconciliation-required'
    new_boundary = at if settled or blocked else state.get('boundaryAt',sample['startedAt'])
    document['autoState']={'allocationVersion':2,'window':identity,'capturedAt':at,'usedPercent':float(used),
                           'sources':by_id,'weightBaseline':baseline,'candidates':sorted(candidates),
                           'pendingPoints':float(pending),'blocked':bool(correction),
                           'correction':correction,'boundaryAt':new_boundary}
    document['monitor']={'status':status,'capturedAt':at,'reason':reason,'scope':'monitored-sources-only',
                         'allocationVersion':2,'pendingSettlementPercent':float(pending),
                         'waitingDeviceIds':waiting if pending>0 else [],
                         'weightBasis':'observed-total-token-deltas', 'reportingGuardSeconds':REPORTING_GUARD}
    return document


def drain_audit(path, document):
    """Outbox is committed with allocations. Journal replay may repeat IDs, never quota."""
    for decision in document.get('pendingAudit',[]):
        reset=decision['window'][0]
        journal=path.with_name(path.stem+'.audit.'+str(reset)+'.jsonl')
        with os.fdopen(os.open(journal,os.O_WRONLY|os.O_APPEND|os.O_CREAT,0o600),'a') as stream:
            os.chmod(journal,0o600)
            stream.write(json.dumps(decision,separators=(',',':'))+'\n')
            stream.flush();os.fsync(stream.fileno())
    if document.get('pendingAudit'):
        document['pendingAudit']=[]
        atomic(path,document)


async def activity_sample():
    quota, host = snapshot(), host_usage()
    window = current_window(quota)
    if quota.get('status') != 'available' or not window:
        raise ValueError('fresh official quota required')
    start = datetime.fromtimestamp(window['resetsAt']-window['windowDurationMins']*60, timezone.utc)
    sample = {'window':window, 'planType':quota.get('planType'), 'capturedAt':quota['capturedAt'],
              'startedAt':start.isoformat(), 'healthy':True, 'sources':[], 'userIds':[]}
    if not host or host.get('totalTokens') is None or host.get('usageEvents') is None or not host['fresh'] or not matches(host, window, sample['planType']) or abs(stamp(host['capturedAt'])-stamp(quota['capturedAt'])) > 60:
        sample.update(healthy=False, reason='host-coverage-unavailable')
    else:
        sample['sources'].append({'deviceId':host['deviceId'], 'userId':host['userId'],
                                  'events':host['usageEvents'] or 0, 'tokens':host['totalTokens'] or 0,
                                  'unknown':host['unknownSegments'], 'lastActivityAt':host.get('lastActivityAt')})
    # Drain ordinary accounting first; remaining outbox entries block inference.
    await flush_events()
    if list(spool_dir().glob('*.json')):
        sample.update(healthy=False, reason='accounting-pending')
    conn = await _connect()
    try:
        async with conn.transaction(readonly=True, isolation='repeatable_read'):
            sample['userIds'] = [r['user_id'] for r in await conn.fetch("SELECT user_id FROM codex_ops.personnel_roster WHERE status='active'")]
            # Include revoked and non-roster devices too: their usage cannot disappear.
            rows = await conn.fetch('''SELECT d.device_id,d.user_id,count(r.request_id) events,
                coalesce(sum(r.total_tokens),0) tokens,count(r.request_id) FILTER (WHERE r.total_tokens IS NULL) unknown,
                max(r.finished_at) last_activity_at FROM codex_ops.devices d
                LEFT JOIN codex_ops.model_requests r ON r.device_id=d.device_id AND r.finished_at >= $1
                GROUP BY d.device_id''', start)
        for row in rows:
            sample['sources'].append({'deviceId':str(row['device_id']), 'userId':row['user_id'],
                                      'events':int(row['events']), 'tokens':int(row['tokens']), 'unknown':int(row['unknown']),
                                      'lastActivityAt':row['last_activity_at'].isoformat() if row['last_activity_at'] else None})
    finally:
        await conn.close()
    by_id = {row['deviceId']:row for row in sample['sources']}
    for path in (spool_dir()/'active').glob('*.json'):
        try:
            record = private_json(path)
            finished = record.get('finishedAt')
            if finished and stamp(finished) < stamp(sample['capturedAt'])-REPORTING_GUARD:
                path.unlink(missing_ok=True)
                continue
            source = by_id[record['deviceId']]
            source['inFlight'] = not bool(finished)
            source['recentActivity'] = True
        except (OSError,ValueError,KeyError,TypeError):
            sample.update(healthy=False, reason='unidentified-in-flight-request')
    return sample


async def reconcile():
    if not settings.codex_quota_attribution_file or not settings.codex_telemetry_enabled:
        raise ValueError('attribution and telemetry must be configured')
    path = Path(settings.codex_quota_attribution_file).expanduser()
    # All mutation callers use this lock, including administrative confirmations.
    with open(str(path)+'.lock','a') as lock:
        os.chmod(lock.name,0o600)
        fcntl.flock(lock,fcntl.LOCK_EX)
        document = private_json(path)
        drain_audit(path, document)
        try:
            sample = await asyncio.wait_for(activity_sample(), 20)
            document = advance(document, sample)
        except Exception:
            if document.get('autoState'):
                document['autoState']['blocked'] = True
            document['monitor'] = {'status':'paused', 'capturedAt':datetime.now(timezone.utc).isoformat(),
                                   'reason':'source-sampling-unavailable', 'scope':'monitored-sources-only'}
        atomic(path, document)
        drain_audit(path, document)
        return document['monitor']
