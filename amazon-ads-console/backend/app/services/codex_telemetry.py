"""Device-bound authentication and server-observed usage; never accept client token counts."""
import asyncio
import codecs
import hashlib
import json
import logging
import os
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from app.core.config import settings
from app.core import observability
from app.services.auth import _connect
from app.services import codex_activity, codex_control, codex_access, codex_models

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
        codex_control.require_device_enabled(row['device_id'])
        return dict(row)
    finally:
        await conn.close()


async def register_device(user_id, device_name, platform, key=None, device_id=None, *, auth_mode='api_key', approved=True, actor=None):
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
                await conn.execute('''INSERT INTO codex_ops.device_access(device_id,auth_mode,approved_at,approved_by)
                    VALUES($1,$2,CASE WHEN $3 THEN now() ELSE NULL END,$4)''', device_id, auth_mode, approved, actor if approved else None)
                await conn.execute('''INSERT INTO codex_ops.device_access_audit(device_id,action,auth_mode,actor)
                    VALUES($1,$2,$3,$4)''', device_id, 'create_approved' if approved else 'create_pending', auth_mode, actor)
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
    def __init__(self, capture_response=False, capture_output_items=False):
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.buffer = ''
        self.skipping = False
        self.response_id = None
        self.usage = None
        self.completed = False
        self.terminal_status = None
        self.first_output_at = None
        self.capture_response = capture_response
        self.response = None
        self.capture_output_items = capture_output_items
        self.output_items = {}
        # A terminal event repeats the generated output. Use the same bounded
        # limit for streamed and collected responses so a valid large terminal
        # event is not mistaken for a truncated stream. Parsed output is discarded
        # immediately unless this request explicitly collects a JSON response.
        self.max_event_size = 16*1024*1024

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
            if not isinstance(event,dict):
                continue
            kind = event.get('type')
            if self.capture_output_items and kind == 'response.output_item.done' and isinstance(event.get('item'),dict):
                index = event.get('output_index')
                if type(index) is int and index >= 0:
                    self.output_items[index] = event['item']
            # Record only a timestamp, never the generated text or tool arguments.
            if self.first_output_at is None and kind in (
                    'response.output_text.delta', 'response.reasoning_text.delta',
                    'response.reasoning_summary_text.delta', 'response.function_call_arguments.delta') and event.get('delta'):
                self.first_output_at = time.perf_counter()
            if kind not in ('response.completed','response.incomplete','response.failed'):
                continue
            self.observe_response(event.get('response'),kind == 'response.completed',kind.removeprefix('response.'))
        if len(self.buffer) > self.max_event_size:
            self.buffer = ''
            self.skipping = True

    def observe_response(self,response,completed,terminal_status=None):
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
        status = terminal_status or ('completed' if completed else response.get('status','incomplete'))
        self.terminal_status = status if status in ('completed','incomplete','failed') else None
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
                from app.services.codex_quota_batches import record_request
                await asyncio.to_thread(record_request, record)
                path.unlink(missing_ok=True)
                try:
                    # Private LISTEN/NOTIFY hint after committed accounting. No
                    # device identity, key or token payload crosses this channel.
                    # Failure must never fail or replay an already saved request.
                    await conn.execute("SELECT pg_notify('codex_usage_changed', '')")
                except Exception:
                    log.warning('codex_usage_notification_unavailable')
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


async def model_catalog(include_disabled=False):
    base,headers = upstream()
    try:
        async with httpx.AsyncClient(trust_env=False,follow_redirects=False,timeout=15) as client:
            response = await client.get(base+'/models',headers=headers)
            if response.status_code != 200:
                raise HTTPException(502,'Model catalog is unavailable')
            catalog = response.json()
            if not isinstance(catalog,dict) or not isinstance(catalog.get('data'),list):
                raise ValueError('Invalid upstream model catalog')
            return catalog if include_disabled else codex_models.filter_catalog(catalog)
    except (httpx.HTTPError,ValueError):
        raise HTTPException(502,'Model catalog is unavailable')


async def keepalive_chunks(source, interval=15):
    """Keep downstream SSE alive without cancelling a pending upstream read."""
    iterator = source.__aiter__()
    pending = asyncio.create_task(iterator.__anext__())
    try:
        while True:
            ready, _ = await asyncio.wait({pending}, timeout=interval)
            if not ready:
                yield None
                continue
            try:
                chunk = pending.result()
            except StopAsyncIteration:
                break
            yield chunk
            pending = asyncio.create_task(iterator.__anext__())
    finally:
        if not pending.done():
            pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)


async def proxy_response(device, body, route='/responses',forward_headers=None, observer=None, response_headers=None):
    codex_models.require_model(body)
    queued_at = time.perf_counter()
    lease = await codex_control.acquire(device['device_id'])
    queue_ms = round((time.perf_counter() - queued_at) * 1000, 3)
    try:
        await codex_access.recheck_queued(device)
        codex_models.require_model(body)
        status, content_type, request_id, stream = await _proxy_response(
            device, body, route, forward_headers, observer, response_headers, queue_ms)
        return status, content_type, request_id, codex_control.ControlledStream(stream, lease)
    except BaseException:
        lease.close()
        raise


async def _proxy_response(device, body, route='/responses',forward_headers=None, observer=None, response_headers=None, queue_ms=0):
    base,headers = upstream()
    request_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).isoformat()
    started_clock = time.perf_counter()
    trace_context = observability.request_context.get()
    trace_id = trace_context.get('request_id') if trace_context else request_id
    if trace_context is not None:
        trace_context['model_request_id'] = request_id
        trace_context['model_queue_ms'] = queue_ms
    try:
        requested_model = json.loads(body).get('model')
    except (ValueError, AttributeError):
        requested_model = None
    timing = {'started_at':started_at, 'trace_request_id':trace_id, 'queue_ms':queue_ms, 'user_id':device['user_id'],
              'model_slug':requested_model if isinstance(requested_model,str) and len(requested_model)<=256 else None}
    activity = start_activity(request_id, device['device_id'])
    # Preserve supported Codex session metadata without forwarding device auth,
    # cookies, arbitrary proxy headers or caller-selected upstream destinations.
    if forward_headers:
        for name in ('user-agent','session-id','thread-id','x-opencode-session',
                     'x-codex-beta-features','openai-beta','x-codex-client-version'):
            if forward_headers.get(name):
                headers[name] = forward_headers[name]
    headers['Content-Type'] = 'application/json'
    # Generated locally: never forward an untrusted caller correlation header.
    headers['X-Request-ID'] = request_id
    client = httpx.AsyncClient(trust_env=False,follow_redirects=False,
        timeout=httpx.Timeout(670,connect=10,pool=10))
    try:
        for attempt in range(2):
            try:
                response = await client.send(client.build_request('POST',base+route,headers=headers,content=body),stream=True)
                break
            except (httpx.ConnectError,httpx.ConnectTimeout):
                # A connection was never established: no model request was sent.
                # HTTP failures, read failures and partial output are never replayed.
                if attempt:
                    raise
                await asyncio.sleep(.2)
    except asyncio.CancelledError:
        if trace_context is not None:
            trace_context.update(model_outcome='client_cancelled',model_http_status=499,model_completed=False)
        try:
            stage_event({**timing,'request_id':request_id,'device_id':str(device['device_id']),
                'response_id':None,'finished_at':datetime.now(timezone.utc).isoformat(),
                'http_status':499,'completed':False,'usage':None})
        except Exception:
            log.error('codex_accounting_pending request_id=%s',request_id)
        finally:
            finish_activity(activity)
            await asyncio.shield(client.aclose())
        raise
    except httpx.HTTPError as exc:
        if trace_context is not None:
            trace_context.update(model_outcome='upstream_headers_error',model_http_status=502,
                model_completed=False,model_error_type=type(exc).__name__,
                model_headers_ms=round((time.perf_counter()-started_clock)*1000,3))
        await client.aclose()
        try:
            await save_event({**timing,'request_id':request_id,'device_id':str(device['device_id']),
                'response_id':None,'finished_at':datetime.now(timezone.utc).isoformat(),
                'http_status':502,'completed':False,'usage':None})
        except Exception:
            log.error('codex_accounting_pending request_id=%s',request_id)
        finally:
            finish_activity(activity)
        raise HTTPException(502,{'code':'upstream_connection_failed','message':'Model upstream is unavailable','source':'upstream'})
    if response.status_code in (401,403):
        upstream_status = response.status_code
        await response.aclose()
        await client.aclose()
        try:
            await save_event({**timing,'request_id':request_id,'device_id':str(device['device_id']),
                'response_id':None,'finished_at':datetime.now(timezone.utc).isoformat(),
                'http_status':502,'completed':False,'usage':None})
        except Exception:
            log.error('codex_accounting_pending request_id=%s',request_id)
        finally:
            finish_activity(activity)
        if trace_context is not None:
            trace_context.update(model_outcome='upstream_authentication_failed',model_http_status=502,
                                 model_completed=False,model_error_type='UpstreamHTTP'+str(upstream_status))
        raise HTTPException(502,{'code':'upstream_authentication_failed',
            'message':'The model source rejected its server credential; contact the administrator','source':'upstream'})
    headers_ms = round((time.perf_counter() - started_clock) * 1000, 3)
    upstream_request_id = response.headers.get('x-upstream-request-id') or response.headers.get('x-request-id')
    if not isinstance(upstream_request_id,str) or not observability._REQUEST_ID.fullmatch(upstream_request_id):
        upstream_request_id = None
    if response_headers is not None:
        response_headers['X-Model-Request-ID'] = request_id
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
        first_byte_ms = None
        error_type = None
        outcome = 'http_error' if status != 200 else 'incomplete'

        def failure_event():
            # Headers may already be HTTP 200. An explicit terminal error tells
            # streaming clients that partial output is not a completed response.
            # Never replay a request which could already have produced output.
            return ('\n\nevent: error\ndata: ' + json.dumps({
                'type':'error','code':'upstream_stream_interrupted',
                'message':'Model response was interrupted before completion. Partial output may be present.',
                'request_id':trace_id,'model_request_id':request_id}) + '\n\n').encode()

        try:
            chunks = keepalive_chunks(response.aiter_bytes()) if is_sse else response.aiter_bytes()
            async for chunk in chunks:
                if chunk is None:
                    yield b': keep-alive\n\n'
                    continue
                if chunk and first_byte_ms is None:
                    first_byte_ms = round((time.perf_counter() - started_clock) * 1000, 3)
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
            if status == 200:
                if is_sse:
                    observer.finish()
                elif not json_too_large:
                    try:
                        value = json.loads(json_body)
                        observer.observe_response(value,isinstance(value,dict) and value.get('status','completed')=='completed')
                    except (ValueError,UnicodeDecodeError):
                        pass
                outcome = observer.terminal_status or 'incomplete'
                if observer.terminal_status is None:
                    status = 502
                    error_type = 'MissingTerminalEvent'
                    if is_sse:
                        yield failure_event()
        except (asyncio.CancelledError,GeneratorExit):
            # A client closing after receiving our terminal error must not erase
            # the upstream failure which triggered that error.
            if error_type is None:
                status = 499
                outcome = 'client_cancelled'
            raise
        except httpx.HTTPError as exc:
            if is_sse:
                observer.finish()
            status = 502
            error_type = type(exc).__name__
            outcome = 'completed_transport_error' if observer.completed else 'transport_error'
            if is_sse and response.status_code == 200:
                if not observer.completed:
                    yield failure_event()
            else:
                raise
        finally:
            if is_sse and status in (200,499,502):
                observer.finish()
            ended_clock = time.perf_counter()
            stream_timing = {
                'model_request_id':request_id,'model_upstream_request_id':upstream_request_id,
                'model_outcome':outcome,'model_http_status':status,
                'model_completed':observer.completed,'model_error_type':error_type,
                'model_headers_ms':headers_ms,'model_first_byte_ms':first_byte_ms,
                'model_first_output_ms':round((observer.first_output_at - started_clock) * 1000, 3) if observer.first_output_at else None,
                'model_stream_ms':round((ended_clock - started_clock) * 1000 - headers_ms, 3),
            }
            if trace_context is not None:
                trace_context.update(stream_timing)
            record = {**timing,**stream_timing,'request_id':request_id,'device_id':str(device['device_id']),
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
