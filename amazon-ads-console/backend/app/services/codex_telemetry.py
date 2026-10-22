"""Device-bound authentication and server-observed usage; never accept client token counts."""
import asyncio
import codecs
import hashlib
import json
import logging
import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.services.auth import _connect
from app.services import codex_activity

log = logging.getLogger(__name__)


def require_enabled():
    if not settings.codex_telemetry_enabled:
        raise HTTPException(503, 'Device integration has not been activated')


def key_hash(key):
    return hashlib.sha256(key.encode()).hexdigest()


async def authenticate(key):
    require_enabled()
    if not key or not 32 <= len(key) <= 256:
        raise HTTPException(401, 'Invalid device credential')
    conn = await _connect()
    try:
        row = await conn.fetchrow('''SELECT d.device_id,d.user_id FROM codex_ops.devices d
            JOIN codex_ops.personnel_roster r ON r.user_id=d.user_id
            WHERE d.key_hash=$1 AND d.revoked_at IS NULL AND r.status='active' ''', key_hash(key))
        if row is None:
            raise HTTPException(401, 'Invalid device credential')
        return dict(row)
    finally:
        await conn.close()


async def register_device(user_id, device_name, platform, key=None, device_id=None):
    require_enabled()
    key = key or ('sk-cpo-' + secrets.token_urlsafe(32))
    if not 40 <= len(key) <= 256:
        raise ValueError('Invalid generated credential length')
    device_id = uuid.UUID(str(device_id)) if device_id else uuid.uuid4()
    conn = await _connect()
    try:
        async with conn.transaction():
            active = await conn.fetchval("SELECT user_id FROM codex_ops.personnel_roster WHERE user_id=$1 AND status='active'", user_id)
            if active is None:
                raise HTTPException(404, 'Active distribution member not found')
            # An imported private manifest can safely be retried, but cannot rebind a device.
            existing = await conn.fetchrow('SELECT user_id,key_hash,revoked_at FROM codex_ops.devices WHERE device_id=$1 FOR UPDATE', device_id)
            if existing:
                if existing['user_id'] != user_id or existing['key_hash'] != key_hash(key) or existing['revoked_at'] is not None:
                    raise HTTPException(409, 'Device registration conflicts with an existing device')
            else:
                await conn.execute('''INSERT INTO codex_ops.devices
                    (device_id,user_id,device_name,platform,key_hash) VALUES ($1,$2,$3,$4,$5)''',
                    device_id,user_id,device_name,platform,key_hash(key))
        return {'deviceId':str(device_id),'apiKey':key}
    finally:
        await conn.close()


async def heartbeat(device, codex_running, client_version):
    conn = await _connect()
    try:
        at = await conn.fetchval('''UPDATE codex_ops.devices SET last_heartbeat_at=now(),
            codex_running=$2,client_version=$3 WHERE device_id=$1 AND revoked_at IS NULL
            RETURNING last_heartbeat_at''', device['device_id'],codex_running,client_version)
        if at is None:
            raise HTTPException(401, 'Device has been revoked')
        return {'accepted':True,'serverTime':at,'onlineTimeoutSeconds':120}
    finally:
        await conn.close()


class UsageObserver:
    """Bounded accounting parser; optionally retain terminal JSON in memory, never on disk."""
    def __init__(self, capture_response=False):
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.buffer = ''
        self.skipping = False
        self.response_id = None
        self.usage = None
        self.completed = False
        self.capture_response = capture_response
        self.response = None
        self.max_event_size = 16*1024*1024 if capture_response else 1024*1024

    def feed(self, chunk):
        self.buffer += self.decoder.decode(chunk)
        while '\n' in self.buffer:
            line,self.buffer = self.buffer.split('\n',1)
            if self.skipping:
                self.skipping = False
                continue
            if len(line) > self.max_event_size or not line.startswith('data:'):
                continue
            try:
                event = json.loads(line[5:].strip())
            except ValueError:
                continue
            if not isinstance(event,dict) or event.get('type') not in ('response.completed','response.incomplete','response.failed'):
                continue
            self.observe_response(event.get('response'),event['type'] == 'response.completed')
        if len(self.buffer) > self.max_event_size:
            self.buffer = ''
            self.skipping = True

    def observe_response(self,response,completed):
        if not isinstance(response,dict):
            return
        rid = response.get('id')
        if not isinstance(rid,str) or not 1 <= len(rid) <= 256:
            return
        if self.response_id != rid:
            self.usage = None
            self.response = None
        self.response_id = rid
        self.completed = completed
        if self.capture_response:
            self.response = response
        usage = valid_usage(response.get('usage'))
        if usage is not None:
            self.usage = usage

    def finish(self):
        # Some upstreams end the final data line at EOF without a trailing LF.
        self.feed(b'\n')


def valid_usage(value):
    if not isinstance(value,dict):
        return None
    def count(v):
        return isinstance(v,int) and not isinstance(v,bool) and 0 <= v <= 10**12
    names = ['input_tokens','output_tokens','total_tokens']
    if not all(count(value.get(name)) for name in names):
        return None
    if value['total_tokens'] != value['input_tokens'] + value['output_tokens']:
        return None
    result = {name:value[name] for name in names}
    for parent,detail,child,dest in [('input_tokens','input_tokens_details','cached_tokens','cached_tokens'),
                                   ('output_tokens','output_tokens_details','reasoning_tokens','reasoning_tokens')]:
        detail_value = value.get(detail)
        number = detail_value.get(child) if isinstance(detail_value,dict) else None
        result[dest] = number if count(number) and number <= value[parent] else None
    return result


def spool_dir():
    p = Path(settings.codex_event_spool_dir).expanduser()
    p.mkdir(parents=True,exist_ok=True,mode=0o700)
    return p


def stage_event(record):
    # Persist only accounting fields before attempting the DB. Survives DB outages and restarts.
    path = spool_dir() / (record['request_id']+'.json')
    temporary = path.with_suffix('.tmp')
    fd = os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(record,stream,separators=(',',':'))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary,path)
    return path


def start_activity(request_id, device_id):
    # Separate from the terminal outbox: a running request is evidence of activity
    # even before its first token or terminal accounting event reaches the DB.
    directory = spool_dir()/'active'
    directory.mkdir(mode=0o700, exist_ok=True)
    path = directory/(request_id+'.json')
    codex_activity.begin(path, device_id)
    return path


def finish_activity(path):
    # Keep a short overlap journal so a DB-snapshot/completion race cannot hide
    # another device while a quota sample is being reconciled.
    try:
        value = json.loads(path.read_text())
        value['finishedAt'] = datetime.now(timezone.utc).isoformat()
        temporary = path.with_suffix('.tmp')
        with os.fdopen(os.open(temporary, os.O_WRONLY|os.O_CREAT|os.O_TRUNC, 0o600), 'w') as stream:
            json.dump(value, stream)
        os.replace(temporary, path)
    except (OSError, ValueError):
        log.error('codex_activity_finish_failed')
    finally:
        codex_activity.release(path)


async def save_event(record):
    path = stage_event(record)
    await flush_events([path])


async def flush_events(paths=None):
    paths = paths if paths is not None else sorted(spool_dir().glob('*.json'))[:100]
    if not paths:
        return
    conn = await _connect()
    try:
        for path in paths:
            try:
                record = json.loads(path.read_text())
                usage = record.get('usage') or {}
                await conn.execute('''INSERT INTO codex_ops.model_requests
                    (request_id,device_id,response_id,finished_at,http_status,completed,
                     input_tokens,output_tokens,total_tokens,cached_tokens,reasoning_tokens)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) ON CONFLICT DO NOTHING''',
                    uuid.UUID(record['request_id']),uuid.UUID(record['device_id']),record.get('response_id'),
                    datetime.fromisoformat(record['finished_at']),record['http_status'],record['completed'],
                    *[usage.get(k) for k in ['input_tokens','output_tokens','total_tokens','cached_tokens','reasoning_tokens']])
                if usage:
                    # An unknown terminal event may be followed by a replay carrying
                    # valid usage. Enrich that same response once, never double count
                    # or transfer attribution to another device. First timestamps stay.
                    await conn.execute('''UPDATE codex_ops.model_requests SET
                        input_tokens=$4,output_tokens=$5,total_tokens=$6,
                        cached_tokens=$7,reasoning_tokens=$8,completed=completed OR $9
                        WHERE device_id=$1 AND total_tokens IS NULL
                        AND (request_id=$2 OR (response_id IS NOT NULL AND response_id=$3))''',
                        uuid.UUID(record['device_id']),uuid.UUID(record['request_id']),record.get('response_id'),
                        *[usage.get(k) for k in ['input_tokens','output_tokens','total_tokens','cached_tokens','reasoning_tokens']],
                        record['completed'])
                path.unlink(missing_ok=True)
            except (OSError,ValueError):
                log.error('codex_accounting_spool_invalid file=%s',path.name)
    finally:
        await conn.close()


def upstream():
    base = settings.codex_upstream_base_url.rstrip('/')
    parsed = urlsplit(base)
    if not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password or parsed.scheme not in ('http','https'):
        raise HTTPException(503,'Model upstream has not been configured')
    if parsed.scheme == 'http' and parsed.hostname not in ('127.0.0.1','::1','localhost'):
        raise HTTPException(503,'Model upstream must use HTTPS or loopback')
    try:
        path = Path(settings.codex_upstream_key_file or '').expanduser()
        if os.name == 'posix' and path.stat().st_mode & 0o077:
            raise OSError('credential file must be private')
        key = path.read_text().strip()
    except OSError:
        raise HTTPException(503,'Model upstream credential is unavailable')
    if not key or '\n' in key:
        raise HTTPException(503,'Model upstream credential is invalid')
    return base,{'Authorization':'Bearer '+key,'Accept-Encoding':'identity'}


async def model_catalog():
    base,headers = upstream()
    try:
        async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=15) as client:
            response = await client.get(base+'/models',headers=headers)
            if response.status_code != 200:
                raise HTTPException(502,'Model catalog is unavailable')
            return response.json()
    except (httpx.HTTPError,ValueError):
        raise HTTPException(502,'Model catalog is unavailable')


async def proxy_response(device, body, route='/responses',forward_headers=None, observer=None, response_headers=None):
    base,headers = upstream()
    request_id = str(uuid.uuid4())
    activity = start_activity(request_id, device['device_id'])
    # Preserve supported Codex session metadata without forwarding device auth,
    # cookies, arbitrary proxy headers or caller-selected upstream destinations.
    if forward_headers:
        for name in ('user-agent','session-id','thread-id','x-opencode-session',
                     'x-codex-beta-features','openai-beta','x-codex-client-version'):
            if forward_headers.get(name):
                headers[name] = forward_headers[name]
    headers['Content-Type'] = 'application/json'
    client = httpx.AsyncClient(trust_env=False,follow_redirects=False,
        timeout=httpx.Timeout(300,connect=10,pool=10))
    try:
        response = await client.send(client.build_request('POST',base+route,headers=headers,content=body),stream=True)
    except asyncio.CancelledError:
        try:
            stage_event({'request_id':request_id,'device_id':str(device['device_id']),
                'response_id':None,'finished_at':datetime.now(timezone.utc).isoformat(),
                'http_status':499,'completed':False,'usage':None})
        except Exception:
            log.error('codex_accounting_pending request_id=%s',request_id)
        finally:
            finish_activity(activity)
            await asyncio.shield(client.aclose())
        raise
    except httpx.HTTPError:
        await client.aclose()
        try:
            await save_event({'request_id':request_id,'device_id':str(device['device_id']),
                'response_id':None,'finished_at':datetime.now(timezone.utc).isoformat(),
                'http_status':502,'completed':False,'usage':None})
        except Exception:
            log.error('codex_accounting_pending request_id=%s',request_id)
        finally:
            finish_activity(activity)
        raise HTTPException(502,'Model upstream is unavailable')
    if response_headers is not None:
        # Preserve bounded retry guidance without exposing arbitrary source headers.
        for name in ('Retry-After', 'X-Relay-Limit-Origin'):
            value = response.headers.get(name)
            if value and len(value) <= 256 and all(32 <= ord(ch) < 127 for ch in value):
                response_headers[name] = value
    observer = observer or UsageObserver()
    async def generate():
        status = response.status_code
        is_sse = 'text/event-stream' in response.headers.get('content-type','')
        json_body = bytearray()
        json_too_large = False
        try:
            async for chunk in response.aiter_bytes():
                if status == 200:
                    if is_sse:
                        observer.feed(chunk)
                    elif not json_too_large:
                        if len(json_body)+len(chunk) <= 16*1024*1024:
                            json_body.extend(chunk)
                        else:
                            json_body.clear()
                            json_too_large = True
                yield chunk
            if status == 200 and not is_sse and not json_too_large:
                try:
                    value = json.loads(json_body)
                    observer.observe_response(value,isinstance(value,dict) and value.get('status','completed')=='completed')
                except (ValueError,UnicodeDecodeError):
                    pass
        except (asyncio.CancelledError,GeneratorExit):
            status = 499
            raise
        except httpx.HTTPError:
            status = 502
            raise
        finally:
            if is_sse and status in (200,499,502):
                observer.finish()
            record = {'request_id':request_id,'device_id':str(device['device_id']),
                'response_id':observer.response_id,'finished_at':datetime.now(timezone.utc).isoformat(),
                'http_status':status,'completed':observer.completed,'usage':observer.usage}
            # Stage synchronously before any cancellation point, even on client disconnect.
            try:
                path = stage_event(record)
            except Exception:
                path = None
                log.error('codex_accounting_pending request_id=%s',request_id)
            finally:
                finish_activity(activity)
            async def cleanup():
                try:
                    await response.aclose()
                finally:
                    await client.aclose()
                if path:
                    try:
                        await asyncio.wait_for(flush_events([path]),timeout=5)
                    except Exception:
                        log.error('codex_accounting_pending request_id=%s',request_id)
            await asyncio.shield(cleanup())
    return response.status_code,response.headers.get('content-type','text/event-stream'),request_id,generate()
