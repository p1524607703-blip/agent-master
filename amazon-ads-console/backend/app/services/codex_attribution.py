"""Confirmed percentage points of an official account window, never token weighting."""
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
        confirmations = private_json(settings.codex_quota_attribution_file).get('confirmations', []) if settings.codex_quota_attribution_file else []
        if not isinstance(confirmations, list):
            raise ValueError('invalid confirmations')
        amounts = {int(uid): Decimal(0) for uid in user_ids}
        evidence = {int(uid): [] for uid in user_ids}
        ids = set()
        for entry in confirmations:
            if (entry.get('resetsAt'), entry.get('windowDurationMins'), entry.get('planType')) != (w['resetsAt'], w['windowDurationMins'], quota.get('planType')):
                continue
            uid, percent, key = entry['userId'], entry['usedPercent'], entry['confirmationId']
            at = datetime.fromisoformat(entry['confirmedAt'].replace('Z','+00:00'))
            if type(uid) is not int or uid not in amounts or type(percent) not in (int,float) or not math.isfinite(percent) or not 0 <= percent <= 100 or not isinstance(key,str) or not key or key in ids or at.tzinfo is None:
                raise ValueError('invalid confirmed attribution')
            if not start <= at.timestamp() <= min(w['resetsAt'], datetime.now(timezone.utc).timestamp()+30):
                raise ValueError('confirmation outside its official period')
            ids.add(key)
            amounts[uid] += Decimal(str(percent))
            evidence[uid].append({'confirmationId': key, 'confirmedAt': at.isoformat(), 'method': 'owner-confirmed'})
        confirmed = sum(amounts.values())
        used = Decimal(str(w['usedPercent']))
        if confirmed > used:
            return {**result, 'status': 'reconciliation-required', 'recordedConfirmedPercent': float(confirmed)}
        return {**result, 'status': 'available', 'confirmedPercent': float(confirmed),
                'unattributedPercent': float(used-confirmed),
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
                  'scope': 'local-log-events', 'unknownSegments': value.get('unknownSegments', 0)}
        for field in ('totalTokens','todayTokens','inputTokens','outputTokens','cachedTokens','reasoningTokens','usageEvents'):
            count = value.get(field)
            if count is not None and (type(count) is not int or count < 0):
                raise ValueError('invalid local count')
            result[field] = count
        return result
    except (OSError, ValueError, TypeError, KeyError):
        return None
