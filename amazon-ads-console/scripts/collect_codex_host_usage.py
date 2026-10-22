"""Read only local token-count events; export counters, never chat text or auth."""
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

FIELDS = {'inputTokens':'input_tokens', 'outputTokens':'output_tokens', 'totalTokens':'total_tokens',
          'cachedTokens':'cached_input_tokens', 'reasoningTokens':'reasoning_output_tokens'}


def usage(value):
    if not isinstance(value, dict):
        return None
    counts = {k: value.get(v) for k,v in FIELDS.items()}
    if any(type(v) is not int or v < 0 for v in counts.values()):
        return None
    if counts['inputTokens']+counts['outputTokens'] != counts['totalTokens'] or counts['cachedTokens'] > counts['inputTokens'] or counts['reasoningTokens'] > counts['outputTokens']:
        return None
    return counts


def main_running(home, executable):
    # Environment output is consumed privately and never logged/exported.
    rows = subprocess.check_output(['ps','-axo','pid=,command='], text=True)
    for row in rows.splitlines():
        parts = row.strip().split(None,1)
        if len(parts) != 2 or parts[1] != executable:
            continue
        env = subprocess.check_output(['ps','eww','-p',parts[0],'-o','command='], text=True)
        match = re.search(r'(?:^|\s)CODEX_HOME=([^\s]+)', env)
        process_home = Path(match[1]).expanduser().resolve() if match else Path.home()/'.codex'
        if process_home == home:
            return True
    return False


def measured(events, meta, cutoff):
    totals = {k: 0 for k in FIELDS}
    previous = None
    unknown = count = 0
    for at, current, last in sorted(set(events), key=lambda v: (v[0],v[1])):
        current, last = dict(zip(FIELDS,current)), dict(zip(FIELDS,last)) if last else None
        if at < cutoff:
            previous = current
            continue
        if previous is None:
            # New, non-forked logs can establish a complete zero baseline.
            delta = current if meta and meta['created'] >= cutoff and not meta['forked'] and current == last else None
        else:
            delta = {k: current[k]-previous[k] for k in FIELDS}
            if any(v < 0 for v in delta.values()):
                delta = None
        previous = current
        if delta is None:
            unknown += 1
        elif delta['totalTokens'] > 0:
            count += 1
            for k in FIELDS:
                totals[k] += delta[k]
    return totals, unknown, count


def collect_host(config, quota):
    windows = [w for w in (quota.get('primary'),quota.get('secondary')) if w]
    w = next((w for w in windows if w['windowDurationMins'] == 10080), windows[0] if windows else None)
    if quota.get('status') != 'available' or not w:
        raise ValueError('official period unavailable')
    # Preserve the prior period boundary when the official epoch jitters by seconds.
    prior_path = config.get('localSnapshot')
    if prior_path:
        try:
            p=Path(prior_path)
            if p.stat().st_mode & 0o077 or p.stat().st_size>65536:
                raise ValueError('private prior snapshot required')
            prior=json.loads(p.read_text())
            if (prior.get('planType')==quota.get('planType') and prior.get('windowDurationMins')==w['windowDurationMins']
                    and type(prior.get('resetsAt')) is int and abs(prior['resetsAt']-w['resetsAt'])<=5):
                w={**w,'resetsAt':prior['resetsAt']}
        except (OSError,ValueError,TypeError,KeyError):
            pass
    now = datetime.now(timezone.utc)
    start = datetime.fromtimestamp(w['resetsAt']-w['windowDurationMins']*60, timezone.utc)
    today = now.astimezone(ZoneInfo('Asia/Shanghai')).replace(hour=0,minute=0,second=0,microsecond=0).astimezone(timezone.utc)
    home = Path(config['codexHome']).expanduser().resolve()
    if not (home/'sessions').is_dir():
        raise ValueError('local session store unavailable')
    sessions = {}
    scanned = invalid = 0
    for path in (home/'sessions').rglob('*.jsonl'):
        if path.is_symlink() or path.stat().st_mtime < min(start,today).timestamp():
            continue
        scanned += 1
        meta = None
        events = []
        with path.open() as stream:
            for line in stream:
                if '"token_count"' not in line and '"session_meta"' not in line:
                    continue
                if not line.endswith('\n'):
                    continue  # The running writer can finish this event next poll.
                try:
                    value = json.loads(line)
                    payload = value.get('payload') or {}
                    if value.get('type') == 'session_meta' and meta is None:
                        meta = {'id': payload['id'], 'created': datetime.fromisoformat(payload['timestamp'].replace('Z','+00:00')),
                                'forked': bool(payload.get('forked_from_id'))}
                    elif value.get('type') == 'event_msg' and payload.get('type') == 'token_count':
                        info = payload.get('info') or {}
                        total = usage(info.get('total_token_usage'))
                        if total is None:
                            continue
                        at = datetime.fromisoformat(value['timestamp'].replace('Z','+00:00'))
                        if at > now:
                            continue
                        last = usage(info.get('last_token_usage'))
                        events.append((at, tuple(total.values()), tuple(last.values()) if last else None))
                except (ValueError,KeyError,TypeError):
                    invalid += 1
        if meta:
            key = meta['id']
            bucket = sessions.setdefault(key, {'meta':meta,'events':[]})
            bucket['events'].extend(events)
    last_activity = max((at for session in sessions.values() for at,_,_ in session['events'] if at >= start), default=None)
    window_totals = {k: 0 for k in FIELDS}
    daily_total = count = unknown = 0
    for session in sessions.values():
        totals, gaps, n = measured(session['events'],session['meta'],start)
        daily, _, _ = measured(session['events'],session['meta'],today)
        for k in FIELDS:
            window_totals[k] += totals[k]
        daily_total += daily['totalTokens']
        count += n
        unknown += gaps
    return {'schemaVersion':1, 'status':'available', 'capturedAt':now.isoformat(),
            'userId':config['userId'], 'deviceId':config['deviceId'],
            'codexRunning':main_running(home,config['mainExecutable']),
            'periodStartedAt':start.isoformat(), 'resetsAt':w['resetsAt'],
            'windowDurationMins':w['windowDurationMins'], 'planType':quota.get('planType'),
            **window_totals, 'todayTokens':daily_total, 'usageEvents':count,
            'unknownSegments':unknown+invalid, 'scannedSessions':len(sessions),
            'lastActivityAt':last_activity.isoformat() if last_activity else None,
            'scope':'local-log-events', 'coverage':'local-files-only'}
