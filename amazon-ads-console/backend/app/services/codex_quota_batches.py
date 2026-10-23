"""Revisable quota estimates backed by a private, idempotent measurement journal.

Official percentages have no per-request attribution. Adjacent quota changes in
the observation horizon share evidence once; later evidence revises estimates,
never manual confirmations or the legacy v3 settlements.
"""
import contextlib
import hashlib
import json
import math
import os
import re
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal

from app.core.config import settings

OBSERVATION_SECONDS = 1800
MICROS = 1000000


def timestamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('timezone required')
    return result.timestamp()


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def database_path():
    configured = settings.codex_quota_attribution_file
    return Path(str(Path(configured).expanduser())+'.batches.sqlite3') if configured else None


@contextlib.contextmanager
def database(path=None):
    path = Path(path) if path else database_path()
    if not path:
        raise ValueError('batch ledger not configured')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.is_symlink():
        raise ValueError('private ledger cannot be a symlink')
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    os.close(fd); os.chmod(path, 0o600)
    connection = sqlite3.connect(str(path), timeout=2)
    connection.row_factory = sqlite3.Row
    # DELETE journal avoids a long-lived shared-memory sidecar with sensitive
    # metadata. SQLite inherits the 0600 database permissions for its journal.
    connection.execute('PRAGMA journal_mode=DELETE')
    connection.executescript('''
        CREATE TABLE IF NOT EXISTS evidence (
          event_key TEXT PRIMARY KEY, response_id TEXT UNIQUE, source TEXT NOT NULL,
          user_id INTEGER NOT NULL, started REAL NOT NULL, ended REAL NOT NULL,
          tokens INTEGER, input_tokens INTEGER, output_tokens INTEGER,
          cached_tokens INTEGER, reasoning_tokens INTEGER, model TEXT,
          eligible INTEGER NOT NULL, timing_complete INTEGER NOT NULL,
          first_seen REAL NOT NULL, changed_at REAL NOT NULL, group_id TEXT);
        CREATE INDEX IF NOT EXISTS evidence_time ON evidence(ended, started);
        CREATE INDEX IF NOT EXISTS evidence_group ON evidence(group_id, source);
        CREATE INDEX IF NOT EXISTS evidence_unassigned ON evidence(ended,started) WHERE group_id IS NULL AND eligible=1;
        CREATE TABLE IF NOT EXISTS owners(source TEXT PRIMARY KEY,user_id INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS group_sources(
          group_id TEXT NOT NULL,source TEXT NOT NULL,user_id INTEGER NOT NULL,tokens INTEGER NOT NULL,
          unknown_count INTEGER NOT NULL,event_count INTEGER NOT NULL,min_started REAL NOT NULL,
          max_ended REAL NOT NULL,incomplete_count INTEGER NOT NULL,PRIMARY KEY(group_id,source));
        CREATE TRIGGER IF NOT EXISTS evidence_aggregate AFTER UPDATE OF group_id,tokens,started,timing_complete ON evidence
        BEGIN
          UPDATE group_sources SET tokens=tokens-coalesce(old.tokens,0),unknown_count=unknown_count-(old.tokens IS NULL),
            event_count=event_count-1,incomplete_count=incomplete_count-(NOT old.timing_complete)
            WHERE old.group_id IS NOT NULL AND group_id=old.group_id AND source=old.source;
          INSERT INTO group_sources SELECT new.group_id,new.source,new.user_id,coalesce(new.tokens,0),
            new.tokens IS NULL,1,new.started,new.ended,NOT new.timing_complete WHERE new.group_id IS NOT NULL
          ON CONFLICT(group_id,source) DO UPDATE SET tokens=tokens+excluded.tokens,
            unknown_count=unknown_count+excluded.unknown_count,event_count=event_count+1,
            min_started=min(min_started,excluded.min_started),max_ended=max(max_ended,excluded.max_ended),
            incomplete_count=incomplete_count+excluded.incomplete_count;
        END;
        CREATE TABLE IF NOT EXISTS cursors (window_id TEXT PRIMARY KEY, body TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS groups (
          group_id TEXT PRIMARY KEY, window_id TEXT NOT NULL, started REAL NOT NULL,
          ended REAL NOT NULL, blocked INTEGER NOT NULL, reason TEXT,
          revision INTEGER NOT NULL DEFAULT 0,fingerprint TEXT,context TEXT NOT NULL DEFAULT '{}');
        CREATE INDEX IF NOT EXISTS groups_window ON groups(window_id, started);
        CREATE TABLE IF NOT EXISTS batches (
          batch_id TEXT PRIMARY KEY, group_id TEXT NOT NULL, window_id TEXT NOT NULL,
          quota_at REAL NOT NULL, points INTEGER NOT NULL, state TEXT NOT NULL,
          revision INTEGER NOT NULL DEFAULT 0, initial_revision INTEGER NOT NULL DEFAULT 0,
          fingerprint TEXT, allocations TEXT NOT NULL DEFAULT '{}',
          updated REAL NOT NULL, confidence TEXT NOT NULL DEFAULT 'low', unknown_sources TEXT NOT NULL DEFAULT '[]');
        CREATE TABLE IF NOT EXISTS revisions (
          group_id TEXT NOT NULL, revision INTEGER NOT NULL, recorded REAL NOT NULL,
          reason TEXT NOT NULL, before_context TEXT NOT NULL, after_context TEXT NOT NULL,
          PRIMARY KEY(group_id, revision));
    ''')
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def bounded_text(value, maximum):
    return isinstance(value, str) and 0 < len(value) <= maximum and all(ord(c) >= 32 for c in value)


def upsert_evidence(conn, value, observed):
    source, key, uid = value['source'], value['eventKey'], value['userId']
    if not bounded_text(source,128) or not bounded_text(key,320) or type(uid) is not int or uid <= 0:
        raise ValueError('invalid measurement identity')
    start, end = timestamp(value['startedAt']), timestamp(value['endedAt'])
    if not math.isfinite(start+end) or start > end or end > observed+30:
        raise ValueError('invalid measurement time')
    counts = [value.get(k) for k in ('totalTokens','inputTokens','outputTokens','cachedTokens','reasoningTokens')]
    if any(v is not None and (type(v) is not int or not 0 <= v <= 10**12) for v in counts):
        raise ValueError('invalid measurement count')
    if counts[0] is not None and (counts[1] is None or counts[2] is None or counts[0] != counts[1]+counts[2]):
        raise ValueError('inconsistent measurement count')
    if counts[3] is not None and (counts[1] is None or counts[3]>counts[1]):
        raise ValueError('invalid cached measurement')
    if counts[4] is not None and (counts[2] is None or counts[4]>counts[2]):
        raise ValueError('invalid reasoning measurement')
    rid = value.get('responseId')
    if rid is not None and not bounded_text(rid,256):
        raise ValueError('invalid response identity')
    model = value.get('model')
    if model is not None and not bounded_text(model,256):
        model = None
    owner = conn.execute('SELECT user_id FROM owners WHERE source=?',(source,)).fetchone()
    if owner and owner['user_id']!=uid:
        raise ValueError('source identity cannot be rebound')
    conn.execute('INSERT OR IGNORE INTO owners VALUES (?,?)',(source,uid))
    prior = conn.execute('SELECT * FROM evidence WHERE event_key=? OR (response_id IS NOT NULL AND response_id=?)', (key,rid)).fetchone()
    if prior:
        if prior['source'] != source or prior['user_id'] != uid:
            raise ValueError('measurement identity cannot be rebound')
        # A known, already-counted measurement is immutable. Unknown -> measured
        # enrichment updates one row and retains its original event-time boundary.
        if prior['tokens'] is None and counts[0] is not None:
            conn.execute('''UPDATE evidence SET tokens=?,input_tokens=?,output_tokens=?,cached_tokens=?,reasoning_tokens=?,
                response_id=coalesce(response_id,?),model=coalesce(model,?),changed_at=? WHERE event_key=?''',
                (*counts,rid,model,observed,prior['event_key']))
        if not prior['timing_complete'] and value.get('timingComplete') is True:
            # The SQL recovery scan can win the race against the richer gateway
            # journal callback. Upgrade timing without adding the Tokens again;
            # event-time ownership is then reconsidered in the next reconciliation.
            conn.execute('''UPDATE evidence SET started=?,timing_complete=1,model=coalesce(model,?),
                changed_at=?,group_id=NULL WHERE event_key=?''',(min(start,prior['started']),model,observed,prior['event_key']))
        return
    conn.execute('''INSERT INTO evidence(event_key,response_id,source,user_id,started,ended,tokens,input_tokens,
        output_tokens,cached_tokens,reasoning_tokens,model,eligible,timing_complete,first_seen,changed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (key,rid,source,uid,start,end,*counts,model,int(value.get('eligible',True)),
         int(value.get('timingComplete',False)),observed,observed))


def record_request(record):
    if not database_path():
        return
    uid = record.get('user_id')
    if type(uid) is not int:
        # Legacy spooled events do not carry trusted user identity. They remain
        # in the authoritative PostgreSQL Token ledger, outside new batch weights.
        return
    usage = record.get('usage') or {}
    value = {'eventKey':'gateway:'+record['request_id'], 'responseId':record.get('response_id'),
        'source':record['device_id'],'userId':uid,
        'startedAt':record.get('started_at') or record['finished_at'], 'endedAt':record['finished_at'],
        'model':record.get('model_slug'),'timingComplete':bool(record.get('started_at')),
        'eligible':not(record['http_status'] in (400,401,403,404,405,413,422,429) and not record.get('response_id')),
        **{dest:usage.get(key) for dest,key in [('totalTokens','total_tokens'),('inputTokens','input_tokens'),
            ('outputTokens','output_tokens'),('cachedTokens','cached_tokens'),('reasoningTokens','reasoning_tokens')]}}
    with database() as conn:
        upsert_evidence(conn,value,datetime.now(timezone.utc).timestamp())


def proportional(points, weights):
    total = sum(weights.values())
    if total <= 0:
        return {}
    shares = {key:points*weight//total for key,weight in weights.items()}
    order = sorted(weights,key=lambda key:(-(points*weights[key] % total),key))
    for key in order[:points-sum(shares.values())]:
        shares[key] += 1
    return shares


def native_evidence(sample, host):
    try:
        path = Path(settings.codex_host_usage_snapshot_file).expanduser().with_suffix('.evidence.json')
        stat = path.stat()
        if path.is_symlink() or stat.st_mode & 0o077 or stat.st_size>8*1024*1024:
            raise ValueError('private bounded evidence required')
        value = json.loads(path.read_text())
        captured = timestamp(value['capturedAt'])
        if (value.get('schemaVersion')!=1 or value.get('status')!='available' or value.get('complete') is not True
                or not host or value.get('userId')!=host['userId'] or value.get('deviceId')!=host['deviceId']
                or value.get('planType')!=sample['planType']
                or abs(timestamp(value['periodStartedAt'])-timestamp(sample['startedAt']))>5
                or not -30<=timestamp(sample['observedAt'])-captured<=300):
            raise ValueError('native evidence unavailable')
        rows = value['events']
        if not isinstance(rows,list) or len(rows)>50000:
            raise ValueError('native evidence too large')
        if any(row.get('source')!=host['deviceId'] or row.get('userId')!=host['userId']
               or not row.get('eventKey','').startswith('host:') for row in rows):
            raise ValueError('native identity mismatch')
        measured = [row for row in rows if row.get('totalTokens') is not None]
        if (sum(row['totalTokens'] for row in measured)!=host.get('totalTokens')
                or len(measured)!=host.get('usageEvents')
                or len(rows)-len(measured)!=host.get('unknownSegments')):
            raise ValueError('native evidence does not reconcile to the host counters')
        return {'complete':True,'events':rows}
    except (OSError,ValueError,TypeError,KeyError,AttributeError):
        return {'complete':False,'events':[]}


def canonical_identity(sample, document, conn):
    window, plan = sample['window'], sample['planType']
    prior = (document.get('autoState') or {}).get('window') or []
    if len(prior)==3 and prior[1:]==[window['windowDurationMins'],plan] and abs(prior[0]-window['resetsAt'])<=5:
        return prior
    # SQLite commits before the compact JSON projection. Recover the canonical
    # period even if a crash occurred between those two writes at a reset boundary.
    for row in conn.execute('SELECT body FROM cursors'):
        identity = json.loads(row['body'])['window']
        if identity[1:]==[window['windowDurationMins'],plan] and abs(identity[0]-window['resetsAt'])<=5:
            return identity
    return [window['resetsAt'],window['windowDurationMins'],plan]


def advance(conn, document, sample, native):
    now = timestamp(sample.get('observedAt',sample['capturedAt']))
    quota_at = timestamp(sample['capturedAt'])
    identity = canonical_identity(sample,document,conn)
    wid = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
    used = int(Decimal(str(sample['window']['usedPercent']))*MICROS)
    row = conn.execute('SELECT body FROM cursors WHERE window_id=?',(wid,)).fetchone()
    cursor = json.loads(row['body']) if row else None
    healthy = sample['healthy'] and native.get('complete') is True
    if not cursor:
        if not healthy:
            raise ValueError('measurement coverage required before cutover')
        cursor = {'window':identity,'used':used,'quotaAt':quota_at,'observedAt':now,'cutoverAt':quota_at,
                  'blocked':False,'sources':sample['sources']}
    else:
        if now < cursor['observedAt'] or quota_at < cursor['quotaAt']:
            return projection(conn,wid,cursor,now,sample)
        previous = {r['deviceId']:r for r in cursor.get('sources',[])}
        regress = any(r['tokens'] < previous.get(r['deviceId'],{}).get('tokens',0) or
                      r['events'] < previous.get(r['deviceId'],{}).get('events',0) for r in sample['sources'])
        gap = now-cursor['observedAt']>300 or regress or bool(set(previous)-{r['deviceId'] for r in sample['sources']})
        corrected = used < cursor['used']
        if corrected:
            cursor['correction'] = True
        delta = max(0,used-cursor['used'])
        if delta:
            blocked = not healthy or gap or cursor.get('blocked') or cursor.get('correction')
            latest = conn.execute('SELECT * FROM groups WHERE window_id=? ORDER BY ended DESC LIMIT 1',(wid,)).fetchone()
            join = latest and not latest['blocked'] and not blocked and quota_at-latest['ended']<=OBSERVATION_SECONDS
            if join:
                gid = latest['group_id']
                conn.execute('UPDATE groups SET ended=? WHERE group_id=?',(quota_at,gid))
            else:
                gid = hashlib.sha256(json.dumps([wid,quota_at,used]).encode()).hexdigest()[:24]
                start = latest['ended'] if latest else cursor['cutoverAt']
                conn.execute('INSERT OR IGNORE INTO groups(group_id,window_id,started,ended,blocked,reason) VALUES (?,?,?,?,?,?)',
                    (gid,wid,start,quota_at,int(bool(blocked)), 'coverage-gap-or-counter-correction' if blocked else None))
            bid = hashlib.sha256(json.dumps([wid,quota_at,used,'batch']).encode()).hexdigest()[:24]
            conn.execute('''INSERT OR IGNORE INTO batches(batch_id,group_id,window_id,quota_at,points,state,updated)
                VALUES (?,?,?,?,?,?,?)''',(bid,gid,wid,quota_at,delta,'unattributed' if blocked else 'provisional',now))
        cursor.update(used=max(used,cursor['used']),quotaAt=max(quota_at,cursor['quotaAt']),observedAt=now,
                      blocked=not healthy or bool(cursor.get('correction')),sources=sample['sources'])
    for value in native.get('events',[])+sample.get('gatewayEvidence',[]) if healthy else []:
        upsert_evidence(conn,value,now)
    conn.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)',(wid,json.dumps(cursor)))
    groups = conn.execute('SELECT * FROM groups WHERE window_id=? ORDER BY started,ended',(wid,)).fetchall()
    # Earliest matching event-time group owns each measurement once. An enriched
    # result never migrates to the device/group active at arrival time.
    for group in groups:
        conn.execute('''UPDATE evidence SET group_id=? WHERE group_id IS NULL AND eligible=1
            AND ended>? AND started<=?''',(group['group_id'],group['started'],group['ended']))
        if healthy:
            revise_group(conn,group,sample,now)
    return projection(conn,wid,cursor,now,sample)


def revise_group(conn, group, sample, now):
    gid = group['group_id']
    rows = conn.execute('SELECT * FROM group_sources WHERE group_id=? AND event_count>0',(gid,)).fetchall()
    weights, owners, unknown, partial = {}, {}, set(), False
    for row in rows:
        source = row['source']; owners[source] = row['user_id']
        if row['unknown_count']:
            unknown.add(source)
        if row['tokens']>0:
            weights[source] = weights.get(source,0)+row['tokens']
        partial |= bool(row['incomplete_count']) or row['min_started']<group['started'] or row['max_ended']>group['ended']
    active = set()
    for request in sample.get('activeRequests',[]):
        owner = conn.execute('SELECT group_id FROM groups WHERE window_id=? AND ended>=? ORDER BY started,ended LIMIT 1',
            (group['window_id'],timestamp(request['startedAt']))).fetchone()
        if owner and owner['group_id']==gid:
            active.add(request['deviceId'])
    waiting = sorted((unknown | active)-set(weights))
    partial |= bool(unknown or active)
    if group['blocked']:
        state, confidence = 'unattributed', 'unavailable'
    elif waiting or not weights:
        state, confidence = 'waiting', 'unavailable'
    else:
        state = 'observed-estimate' if now-group['ended']>=OBSERVATION_SECONDS and not partial else 'provisional'
        confidence = 'low' if partial or len(weights)>1 else 'medium'
    evidence = {'weights':weights,'unknownSources':sorted(unknown),'activeSources':sorted(active),
                'partialMeasurement':partial,'basis':'observed-event-time-token-counts',
                'groupStartedAt':iso(group['started']),'groupEndedAt':iso(group['ended'])}
    context = {'evidence':evidence,'owners':owners,'userIds':sorted(sample['userIds']),'state':state,'confidence':confidence}
    fingerprint = hashlib.sha256(json.dumps(context,sort_keys=True).encode()).hexdigest()
    if fingerprint==group['fingerprint']:
        return
    revision = group['revision']+1
    reason = 'coverage-gap-retained-unattributed' if group['blocked'] else 'initial-estimate' if revision==1 else 'late-measurement-or-observation-recalculation'
    # One group revision stores the evidence vectors once, even when 100 quota
    # batches share them. Per-batch before/after amounts are reconstructed exactly.
    conn.execute('INSERT INTO revisions VALUES (?,?,?,?,?,?)',
        (gid,revision,now,reason,group['context'],json.dumps(context)))
    conn.execute('UPDATE groups SET revision=?,fingerprint=?,context=? WHERE group_id=?',
        (revision,fingerprint,json.dumps(context),gid))
    for batch in conn.execute('SELECT * FROM batches WHERE group_id=? ORDER BY quota_at',(gid,)).fetchall():
        allocations = context_allocations(batch['points'],context)
        conn.execute('''UPDATE batches SET state=?,revision=?,initial_revision=CASE WHEN initial_revision=0 THEN ? ELSE initial_revision END,
            fingerprint=?,allocations=?,updated=?,confidence=?,unknown_sources=?
            WHERE batch_id=?''',(state,revision,revision,fingerprint,json.dumps(allocations),now,confidence,json.dumps(waiting),batch['batch_id']))


def projection(conn,wid,cursor,now,sample):
    allocations = {}
    provisional = stable = pending = revisions = 0
    for batch in conn.execute('SELECT * FROM batches WHERE window_id=?',(wid,)):
        shares = json.loads(batch['allocations'])
        assigned = sum(row['micros'] for row in shares.values())
        pending += batch['points']-assigned
        provisional += assigned if batch['state']=='provisional' else 0
        stable += assigned if batch['state']=='observed-estimate' else 0
        for source,row in shares.items():
            key = (row['userId'],source,batch['state'])
            allocations[key] = allocations.get(key,0)+row['micros']
    revisions = conn.execute('SELECT coalesce(sum(max(revision-1,0)),0) FROM groups WHERE window_id=?',(wid,)).fetchone()[0]
    latest = conn.execute('SELECT b.*,g.started,g.ended FROM batches b JOIN groups g USING(group_id) WHERE b.window_id=? ORDER BY b.quota_at DESC LIMIT 12',(wid,)).fetchall()
    detail = [{'batchId':row['batch_id'],'groupId':row['group_id'],'quotaCapturedAt':iso(row['quota_at']),
        'points':row['points']/MICROS,'status':row['state'],'revision':row['revision'],
        'updatedAt':iso(row['updated']),'confidence':row['confidence'],
        'unattributedPercent':(row['points']-sum(v['micros'] for v in json.loads(row['allocations']).values()))/MICROS,
        'startedAt':iso(row['started']),'throughAt':iso(row['ended']),
        'observeUntil':iso(row['ended']+OBSERVATION_SECONDS),'waitingDeviceIds':json.loads(row['unknown_sources'])} for row in latest]
    return {'window':cursor['window'],'cutoverAt':iso(cursor['cutoverAt']), 'capturedAt':iso(now),
        'status':'reconciliation-required' if cursor.get('correction') else 'active' if not cursor.get('blocked') else 'paused',
        'provisionalPercent':provisional/MICROS,'observedEstimatePercent':stable/MICROS,
        'pendingBatchPercent':pending/MICROS,'recalculationCount':revisions,
        'observationSeconds':OBSERVATION_SECONDS, 'latestBatches':detail,
        'allocations':[{'userId':uid,'deviceId':did,'status':state,'usedPercent':amount/MICROS}
            for (uid,did,state),amount in sorted(allocations.items())]}


def context_allocations(points, context):
    if context.get('state') not in ('provisional','observed-estimate'):
        return {}
    shares = proportional(points,context['evidence']['weights'])
    return {key:{'userId':context['owners'][key],'micros':amount} for key,amount in shares.items()
            if context['owners'][key] in context['userIds']}


def revisions(batch_id):
    if not re.fullmatch('[0-9a-f]{24}',batch_id):
        raise ValueError('batch unavailable')
    path = database_path()
    if not path or path.is_symlink() or not path.is_file() or path.stat().st_mode & 0o077:
        raise ValueError('batch unavailable')
    conn = sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True,timeout=2)
    conn.row_factory = sqlite3.Row
    try:
        found = conn.execute('SELECT * FROM batches WHERE batch_id=?',(batch_id,)).fetchone()
        if not found:
            raise ValueError('batch unavailable')
        rows = conn.execute('SELECT * FROM revisions WHERE group_id=? AND revision>=? ORDER BY revision DESC LIMIT 50',
            (found['group_id'],found['initial_revision'])).fetchall() if found['initial_revision'] else []
        return {'batchId':batch_id,'limit':50,'revisions':[{
            'revision':row['revision'],'recordedAt':iso(row['recorded']),'reason':row['reason'],
            'before':context_allocations(found['points'],json.loads(row['before_context'])) if row['revision']>found['initial_revision'] else {},
            'after':context_allocations(found['points'],json.loads(row['after_context'])),
            'evidence':json.loads(row['after_context'])['evidence']} for row in rows]}
    finally:
        conn.close()
