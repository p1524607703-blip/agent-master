import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from app.api.auth import require_management_session
from app.services.codex_devices import overview as read_overview
from app.services import codex_telemetry as telemetry
from app.services.auth import _connect

router = APIRouter(prefix='/codex', tags=['codex'])
device_bearer = HTTPBearer(auto_error=False)


async def require_device(credentials: HTTPAuthorizationCredentials = Depends(device_bearer)):
    key = credentials.credentials if credentials and credentials.scheme.lower() == 'bearer' else None
    return await telemetry.authenticate(key)


class Registration(BaseModel):
    model_config = ConfigDict(extra='forbid')
    userId: int = Field(gt=0)
    deviceName: str = Field(min_length=1,max_length=80)
    platform: str = Field(pattern='^(windows|macos|linux)$')


class Heartbeat(BaseModel):
    model_config = ConfigDict(extra='forbid')
    codexRunning: StrictBool
    clientVersion: str = Field(default='',max_length=64)


@router.post('/devices',dependencies=[Depends(require_management_session)])
async def register(payload: Registration):
    value = await telemetry.register_device(payload.userId,payload.deviceName,payload.platform)
    return JSONResponse(value,headers={'Cache-Control':'no-store'})


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
    status,content_type,rid,stream = await telemetry.proxy_response(device,bytes(body),route,request.headers)
    return StreamingResponse(stream,status_code=status,headers={
        'Content-Type':content_type,'Cache-Control':'no-store','X-Accel-Buffering':'no','X-Request-ID':rid})


@router.get('/overview', dependencies=[Depends(require_management_session)])
async def overview():
    return await read_overview()
