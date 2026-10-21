"""Read a private, sanitized snapshot; upstream login credentials stay on the source host."""
import json
import math
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings


def window(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError('invalid quota window')
    used, minutes, reset = (value.get(k) for k in ('usedPercent', 'windowDurationMins', 'resetsAt'))
    if isinstance(used, bool) or not isinstance(used, (int, float)) or not math.isfinite(used) or not 0 <= used <= 100:
        raise ValueError('invalid quota percentage')
    if type(minutes) is not int or minutes <= 0 or type(reset) is not int or reset <= 0:
        raise ValueError('invalid quota period')
    return {'usedPercent': used, 'remainingPercent': 100-used,
            'windowDurationMins': minutes, 'resetsAt': reset}


def snapshot():
    if not settings.codex_quota_snapshot_file:
        return {'status': 'unconfigured', 'primary': None, 'secondary': None, 'accountTotalTokens': None, 'tokenTotalScope':'unverified'}
    try:
        path = Path(settings.codex_quota_snapshot_file).expanduser()
        stat = path.stat()
        if stat.st_size > 32768 or stat.st_mode & 0o077:
            raise ValueError('quota snapshot must be private and bounded')
        value = json.loads(path.read_text())
        captured = datetime.fromisoformat(value['capturedAt'].replace('Z', '+00:00'))
        if captured.tzinfo is None or value.get('schemaVersion') != 1:
            raise ValueError('invalid quota snapshot')
        age = (datetime.now(timezone.utc)-captured).total_seconds()
        status = 'available' if value.get('status') == 'available' and -30 <= age <= 300 else 'stale' if age > 300 else 'unavailable'
        result = {'status': status, 'capturedAt': captured.isoformat(),
                  'primary': None, 'secondary': None, 'source': 'official-account-rate-limits',
                  'accountTotalTokens':None, 'tokenTotalScope':'unverified'}
        if status == 'available':
            result['primary'] = window(value.get('primary'))
            result['secondary'] = window(value.get('secondary'))
            if not result['primary'] and not result['secondary']:
                result['status'] = 'unavailable'
            plan = value.get('planType')
            result['planType'] = plan if isinstance(plan, str) and len(plan) <= 32 else None
        return result
    except (OSError, ValueError, KeyError, TypeError):
        return {'status': 'unavailable', 'primary': None, 'secondary': None, 'accountTotalTokens': None, 'tokenTotalScope':'unverified'}
