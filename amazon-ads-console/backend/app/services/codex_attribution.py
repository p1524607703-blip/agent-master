"""Official account percentages with distinct confirmations and explicit usage estimates."""
import json
import math
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.core.config import settings


def private_json(path):
    p = Path(path).expanduser()
    stat = p.stat()
    if stat.st_mode & 0o077 or stat.st_size > 65536:
        raise ValueError('private bounded telemetry file required')
    value = json.loads(p.read_text())
    if not isinstance(value, dict) or value.get('schemaVersion') != 1:
        raise ValueError('unsupported telemetry')
    return value


def current_window(quota):
    windows = [w for w in (quota.get('primary'), quota.get('secondary')) if w]
    return next((w for w in windows if w['windowDurationMins'] == 10080), windows[0] if windows else None)


WINDOW_DRIFT_SECONDS = 5


def same_period(entry, window, plan):
    return (entry.get('windowDurationMins') == window['windowDurationMins'] and
            entry.get('planType') == plan and type(entry.get('resetsAt')) is int and
            abs(entry['resetsAt']-window['resetsAt']) <= WINDOW_DRIFT_SECONDS)


def account_attribution(quota, user_ids):
    result = {'status': 'unavailable', 'usedPercent': None, 'remainingPercent': None,
              'confirmedPercent': None, 'unattributedPercent': None, 'members': [],
              'denominator': 'official-window-capacity', 'capturedAt': quota.get('capturedAt')}
    w = current_window(quota)
    if quota.get('status') != 'available' or not w:
        return result
    start = w['resetsAt'] - w['windowDurationMins']*60
    if w['resetsAt'] <= datetime.now(timezone.utc).timestamp():
        return result
    result.update(windowDurationMins=w['windowDurationMins'], resetsAt=w['resetsAt'],
                  startedAt=datetime.fromtimestamp(start, timezone.utc).isoformat(),
                  usedPercent=w['usedPercent'], remainingPercent=w['remainingPercent'])
    try:
        document = private_json(settings.codex_quota_attribution_file) if settings.codex_quota_attribution_file else {}
        confirmations = document.get('confirmations', [])
        automatic = document.get('automatic', [])
        if not isinstance(confirmations, list) or not isinstance(automatic, list):
            raise ValueError('invalid confirmations')
        amounts = {int(uid): Decimal(0) for uid in user_ids}
        evidence = {int(uid): [] for uid in user_ids}
        ids = set()
        manual_total = Decimal(0)
        weighted_total = Decimal(0)
        partial_estimate = False
        device_amounts = {}
        for entry, is_auto in [(entry,False) for entry in confirmations] + [(entry,True) for entry in automatic]:
            if entry.get('superseded') or not same_period(entry,w,quota.get('planType')):
                continue
            uid, percent, key = entry['userId'], entry['usedPercent'], entry['confirmationId']
            at = datetime.fromisoformat(entry['confirmedAt'].replace('Z','+00:00'))
            if type(uid) is not int or uid not in amounts or type(percent) not in (int,float) or not math.isfinite(percent) or not 0 <= percent <= 100 or not isinstance(key,str) or not key or key in ids or at.tzinfo is None:
                raise ValueError('invalid confirmed attribution')
            if not start <= at.timestamp() <= min(w['resetsAt'], datetime.now(timezone.utc).timestamp()+30):
                raise ValueError('confirmation outside its official period')
            ids.add(key)
            amounts[uid] += Decimal(str(percent))
            method = entry.get('method') if is_auto else 'owner-confirmed'
            if is_auto and method not in ('observed-exclusive-period', 'observed-exclusive-interval', 'observed-token-weighted-interval'):
                raise ValueError('invalid automatic evidence')
            if method == 'observed-token-weighted-interval':
                weighted_total += Decimal(str(percent))
                partial_estimate = partial_estimate or entry.get('partialMeasurement', False)
            if not is_auto:
                manual_total += Decimal(str(percent))
            device_id = entry.get('deviceId')
            if device_id:
                if not isinstance(device_id, str) or len(device_id) > 128:
                    raise ValueError('invalid device identity')
                device_amounts[(uid, device_id)] = device_amounts.get((uid, device_id), Decimal(0)) + Decimal(str(percent))
            evidence[uid].append({'confirmationId': key, 'confirmedAt': at.isoformat(), 'method': method,
                                  'deviceId': device_id, 'usedPercent': percent,
                                  'partialMeasurement': entry.get('partialMeasurement', False)})
        confirmed = sum(amounts.values())
        used = Decimal(str(w['usedPercent']))
        if confirmed > used:
            return {**result, 'status': 'reconciliation-required', 'recordedConfirmedPercent': float(confirmed)}
        return {**result, 'status': 'available', 'confirmedPercent': float(confirmed),
                'unattributedPercent': float(used-confirmed),
                'ownerConfirmedPercent': float(manual_total), 'automaticPercent': float(confirmed-manual_total),
                'concurrentEstimatedPercent': float(weighted_total), 'partialConcurrentEstimate': partial_estimate,
                'automaticMonitor': document.get('monitor'),
                'deviceShares': [{'userId': uid, 'deviceId': did, 'usedPercent': float(amount)} for (uid,did),amount in device_amounts.items()],
                'members': [{'userId': uid, 'usedPercent': float(amount), 'evidence': evidence[uid]}
                            for uid, amount in amounts.items()]}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {**result, 'status': 'invalid-configuration'}


def host_usage():
    if not settings.codex_host_usage_snapshot_file:
        return None
    try:
        value = private_json(settings.codex_host_usage_snapshot_file)
        if type(value.get('userId')) is not int or not isinstance(value.get('deviceId'), str):
            raise ValueError('invalid host identity')
        captured = datetime.fromisoformat(value['capturedAt'].replace('Z','+00:00'))
        age = (datetime.now(timezone.utc)-captured).total_seconds()
        if captured.tzinfo is None:
            raise ValueError('invalid host time')
        result = {'userId': value['userId'], 'deviceId': value['deviceId'],
                  'capturedAt': captured.isoformat(), 'fresh': value.get('status') == 'available' and -30 <= age <= 300,
                  'codexRunning': value.get('codexRunning') is True,
                  'periodStartedAt': value.get('periodStartedAt'), 'resetsAt': value.get('resetsAt'),
                  'windowDurationMins': value.get('windowDurationMins'), 'planType': value.get('planType'),
                  'lastActivityAt': value.get('lastActivityAt'),
                  'scope': 'local-log-events', 'unknownSegments': value.get('unknownSegments', 0)}
        for field in ('totalTokens','todayTokens','inputTokens','outputTokens','cachedTokens','reasoningTokens','usageEvents'):
            count = value.get(field)
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError('invalid local count')
            result[field] = count
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return None
