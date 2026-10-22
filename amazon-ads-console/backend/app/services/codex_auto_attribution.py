"""Conservative device attribution inferred from monitored activity, never official billing.

A quota counter is rounded and account-wide. Carry all candidate sources until it
moves and retain a 30-minute overlap guard for delayed reporting. Mixed sources,
gaps and corrections are left unallocated. This cannot cover unmonitored clients.
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


def advance(document, sample):
    """Pure transition. Replay safe: automatic entries and cursor share one atomic file."""
    document = json.loads(json.dumps(document))
    window, plan = sample['window'], sample['planType']
    at, used = sample['capturedAt'], Decimal(str(window['usedPercent']))
    sources = sample['sources']
    identity = [window['resetsAt'], window['windowDurationMins'], plan]
    state = document.get('autoState')
    same = bool(state and state.get('window') == identity)
    if same and state.get('capturedAt') and stamp(at) <= stamp(state['capturedAt']):
        return document
    if not same:
        # Preserve old automatic history in the same bounded audit document.
        state = {'window':identity, 'candidates':[], 'blocked':False, 'usedPercent':float(used), 'boundaryAt':sample['startedAt']}
    if not sample['healthy']:
        # Do not consume a quota boundary while any required source is unavailable.
        state['blocked'] = True
        state['healthFailureAt'] = at
        document['autoState'] = state
        document['monitor'] = {'status':'paused', 'capturedAt':at, 'reason':sample.get('reason', 'coverage-unavailable'),
                               'scope':'monitored-sources-only', 'reportingGuardSeconds':REPORTING_GUARD}
        return document
    previous_sources = state.get('sources', {}) if same else {}
    by_id = {row['deviceId']:row for row in sources}
    candidates = set(state.get('candidates', []))
    blocked = state.get('blocked', False)
    recent = set()
    if same and 'capturedAt' in state and stamp(at)-stamp(state['capturedAt']) > MAX_GAP:
        blocked = True
    for did, row in by_id.items():
        old = previous_sources.get(did)
        active = row['events'] > 0 if not same else row['events'] > (old or {}).get('events', 0)
        if old and any(row[k] < old[k] for k in ('events','tokens','unknown')):
            blocked = True
        # Unknown Token quantities still have a known device identity. They
        # count as source activity, not as an unidentified account client.
        active = active or row['unknown'] > (old or {}).get('unknown', 0)
        if active or row.get('inFlight'):
            candidates.add(did)
        if row.get('recentActivity') or (row.get('lastActivityAt') and stamp(at)-stamp(row['lastActivityAt']) <= REPORTING_GUARD):
            recent.add(did)
    if set(previous_sources)-set(by_id):
        blocked = True
    records = document.get('confirmations', []) + document.get('automatic', [])
    allocated = sum((Decimal(str(e['usedPercent'])) for e in records if matches(e, window, plan)), Decimal(0))
    before = Decimal(str(state['usedPercent']))
    correction = same and used < before
    blocked = blocked or state.get('correction', False) or correction
    delta = max(Decimal(0), used-before) if same else max(Decimal(0), used-allocated)
    assignable = min(delta, max(Decimal(0), used-allocated))
    # An initial complete period has a stricter sole-source test than later intervals.
    if not same:
        candidates = {did for did,row in by_id.items() if row['events'] or row['unknown'] or row.get('inFlight') or row.get('recentActivity')}
    boundary_sources = candidates | recent
    eligible = next(iter(boundary_sources)) if len(boundary_sources) == 1 else None
    owner = by_id.get(eligible, {})
    reason = 'no-new-quota'
    if delta > 0:
        reason = 'coverage-gap-or-counter-correction' if blocked else 'multiple-or-unknown-sources'
        if eligible and (owner.get('events') or owner.get('unknown') or owner.get('inFlight') or owner.get('recentActivity')) and not blocked and type(owner.get('userId')) is int and owner['userId'] in sample['userIds'] and assignable > 0:
            digest = hashlib.sha256(json.dumps([identity,at,float(used),eligible],separators=(',',':')).encode()).hexdigest()[:24]
            entry = {'confirmationId':'auto-'+digest, 'userId':owner['userId'], 'deviceId':eligible,
                     'usedPercent':float(assignable), 'planType':plan, 'resetsAt':window['resetsAt'],
                     'windowDurationMins':window['windowDurationMins'], 'confirmedAt':at,
                     'method':'observed-exclusive-interval' if same else 'observed-exclusive-period',
                     'intervalStartedAt':state.get('boundaryAt', sample['startedAt']),
                     'scope':'monitored-sources-only', 'officialDeviceBilling':False}
            document.setdefault('automatic', []).append(entry)
            reason = 'exclusive-source-inferred'
        # A mixed/failed boundary stays unallocated; never silently backfill it later.
        candidates = set()
        blocked = bool(correction or state.get('correction', False))
    document['autoState'] = {'window':identity, 'capturedAt':at, 'usedPercent':float(used),
                             'sources':by_id, 'candidates':sorted(candidates), 'blocked':blocked,
                             'boundaryAt':at if delta > 0 else state.get('boundaryAt', sample['startedAt']),
                             'correction':bool(correction or state.get('correction', False))}
    document['monitor'] = {'status':'reconciliation-required' if allocated > used or correction else 'active',
                           'capturedAt':at, 'reason':reason, 'scope':'monitored-sources-only',
                           'reportingGuardSeconds':REPORTING_GUARD}
    return document


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
        try:
            sample = await asyncio.wait_for(activity_sample(), 20)
            document = advance(document, sample)
        except Exception:
            if document.get('autoState'):
                document['autoState']['blocked'] = True
            document['monitor'] = {'status':'paused', 'capturedAt':datetime.now(timezone.utc).isoformat(),
                                   'reason':'source-sampling-unavailable', 'scope':'monitored-sources-only'}
        atomic(path, document)
        return document['monitor']
