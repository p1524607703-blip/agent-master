import json
import uuid
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.api.auth import require_management_session
from app.services.codex_devices import overview as read_overview
from app.services import codex_telemetry as telemetry
from app.services import codex_responses
from app.core.config import settings
from app.services.auth import _connect
from app.services.codex_quota import snapshot as quota_snapshot

router = APIRouter(prefix='/codex', tags=['codex'])
device_bearer = HTTPBearer(auto_error=False)


async def require_device(credentials: HTTPAuthorizationCredentials = Depends(device_bearer)):
    key = credentials.credentials if credentials and credentials.scheme.lower() == 'bearer' else None
    return await telemetry.authenticate(key)


class AccessName(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    deviceName: str = Field(min_length=1,max_length=80)

    @field_validator('deviceName')
    @classmethod
    def readable_name(cls, value):
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
            raise ValueError('Use a single-line access name')
        return value


class Registration(AccessName):
    userId: int = Field(gt=0)
    platform: str = Field(pattern='^(windows|macos|linux)$')


class Heartbeat(BaseModel):
    model_config = ConfigDict(extra='forbid')
    codexRunning: StrictBool
    clientVersion: str = Field(default='',max_length=64)


@router.post('/devices',dependencies=[Depends(require_management_session)])
async def register(payload: Registration):
    value = await telemetry.register_device(payload.userId,payload.deviceName,payload.platform)
    return JSONResponse(value,headers={'Cache-Control':'no-store'})


@router.patch('/devices/{device_id}',dependencies=[Depends(require_management_session)])
async def rename(device_id: uuid.UUID, payload: AccessName):
    telemetry.require_enabled()
    conn = await _connect()
    try:
        row = await conn.fetchrow('''UPDATE codex_ops.devices SET device_name=$2
            WHERE device_id=$1 AND revoked_at IS NULL RETURNING device_id,device_name''',device_id,payload.deviceName)
        if row is None:
            raise HTTPException(404,'Active API key not found')
        return {'deviceId':str(row['device_id']),'deviceName':row['device_name']}
    finally:
        await conn.close()


@router.get('/access-config',dependencies=[Depends(require_management_session)])
async def access_config():
    telemetry.require_enabled()
    base = settings.codex_public_base_url.strip().rstrip('/')
    try:
        parsed = urlsplit(base)
        valid = bool(parsed.scheme=='https' and parsed.hostname and not parsed.username and not parsed.password
                     and not parsed.query and not parsed.fragment and parsed.path.endswith('/v1')
                     and not any(ord(ch)<=32 for ch in base))
        parsed.port  # Validate a configured port without trusting request Host headers.
    except ValueError:
        valid = False
    models, available = [], True
    try:
        catalog = await telemetry.model_catalog()
        models = [item['id'] for item in catalog.get('data',[]) if isinstance(item,dict)
                  and isinstance(item.get('id'),str) and 0 < len(item['id']) <= 256]
    except HTTPException:
        available = False
    return JSONResponse({'baseUrl':base if valid else None,'models':models,'modelsAvailable':available,
                         'protocol':'Responses API','keyShownOnce':True},headers={'Cache-Control':'no-store'})


@router.delete('/devices/{device_id}',dependencies=[Depends(require_management_session)])
async def revoke(device_id: uuid.UUID):
    telemetry.require_enabled()
    conn = await _connect()
    try:
        at = await conn.fetchval('''UPDATE codex_ops.devices SET revoked_at=coalesce(revoked_at,now()),
            codex_running=false WHERE device_id=$1 RETURNING revoked_at''',device_id)
        if at is None:
            raise HTTPException(404,'Device not found')
        return {'revoked':True,'revokedAt':at}
    finally:
        await conn.close()


@router.post('/heartbeat')
async def heartbeat(payload: Heartbeat,device=Depends(require_device)):
    return await telemetry.heartbeat(device,payload.codexRunning,payload.clientVersion)


@router.get('/v1/models')
async def models(device=Depends(require_device)):
    return JSONResponse(await telemetry.model_catalog(),headers={'Cache-Control':'no-store'})


@router.post('/v1/responses')
@router.post('/v1/responses/compact')
async def responses(request: Request,device=Depends(require_device)):
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>16*1024*1024:
            raise HTTPException(413,'Model request too large')
    try:
        value = json.loads(body)
    except (ValueError,UnicodeDecodeError):
        raise HTTPException(400,'Expected JSON model request')
    if not isinstance(value,dict):
        raise HTTPException(400,'Expected JSON model object')
    route = '/responses/compact' if request.url.path.endswith('/compact') else '/responses'
    wire_body, stream_requested = (bytes(body), True) if route.endswith('/compact') else codex_responses.prepare(value)
    if len(wire_body)>16*1024*1024:
        raise HTTPException(413,'Model request too large')
    observer = telemetry.UsageObserver(capture_response=True) if not stream_requested else None
    status,content_type,rid,stream = await telemetry.proxy_response(device,wire_body,route,request.headers,observer=observer)
    headers={'Cache-Control':'no-store','X-Request-ID':rid}
    if not stream_requested:
        return await codex_responses.collect(status,content_type,stream,observer,headers)
    return StreamingResponse(stream,status_code=status,headers={
        **headers,'Content-Type':content_type,'X-Accel-Buffering':'no'})


@router.get('/account-quota', dependencies=[Depends(require_management_session)])
async def account_quota():
    return quota_snapshot()


@router.get('/overview', dependencies=[Depends(require_management_session)])
async def overview():
    return await read_overview()
