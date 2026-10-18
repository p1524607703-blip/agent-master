import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, model_validator

from app.api.auth import require_management_session
from app.core.config import settings
from app.services import codex_devices as service

router = APIRouter(prefix='/codex', tags=['codex'])
bearer = HTTPBearer(auto_error=False)


class DeviceRequest(BaseModel):
    user_id: int = Field(gt=0)
    device_name: str = Field(min_length=1, max_length=128)
    platform: str = Field(default='', max_length=64)


class HeartbeatRequest(BaseModel):
    agent_version: str = Field(default='1', max_length=64)


class UsageRequest(BaseModel):
    device_id: UUID
    response_id: str = Field(min_length=1, max_length=256)
    model: str = Field(min_length=1, max_length=128)
    outcome: Literal['completed', 'failed', 'interrupted']
    occurred_at: datetime
    input_tokens: Optional[int] = Field(default=None, ge=0, le=10**12)
    cached_input_tokens: Optional[int] = Field(default=None, ge=0, le=10**12)
    output_tokens: Optional[int] = Field(default=None, ge=0, le=10**12)
    reasoning_tokens: Optional[int] = Field(default=None, ge=0, le=10**12)

    @model_validator(mode='after')
    def validate_usage(self):
        if self.occurred_at.tzinfo is None or self.occurred_at > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError('A timezone-aware event time no more than 5 minutes in the future is required')
        if (self.input_tokens is None) != (self.output_tokens is None):
            raise ValueError('Input and output usage must both be present or both unknown')
        for child, parent in ((self.cached_input_tokens,self.input_tokens), (self.reasoning_tokens,self.output_tokens)):
            if child is not None and (parent is None or child > parent):
                raise ValueError('Usage subset exceeds parent token count')
        return self


@router.get('/overview', dependencies=[Depends(require_management_session)])
async def overview():
    return await service.overview()


@router.post('/devices', dependencies=[Depends(require_management_session)])
async def create_device(payload: DeviceRequest):
    name = payload.device_name.strip()
    if not name:
        raise HTTPException(422, 'Device name is required')
    result = await service.create_device(payload.user_id, name, payload.platform.strip())
    if result is None:
        raise HTTPException(404, 'Active distribution member not found')
    return result


@router.delete('/devices/{device_id}', dependencies=[Depends(require_management_session)])
async def revoke_device(device_id: UUID):
    if not await service.revoke_device(device_id):
        raise HTTPException(404, 'Device not found')
    return {'ok': True}


@router.post('/heartbeat')
async def heartbeat(payload: HeartbeatRequest, auth: HTTPAuthorizationCredentials = Depends(bearer)):
    if auth is None or not await service.heartbeat(auth.credentials, payload.agent_version):
        raise HTTPException(401, 'Invalid device heartbeat credential')
    return {'ok': True, 'intervalSeconds': 30}


@router.post('/usage')
async def usage(payload: UsageRequest, auth: HTTPAuthorizationCredentials = Depends(bearer)):
    # Device heartbeat keys can never submit usage. Only the master proxy reporter may do so.
    expected = settings.codex_usage_reporter_key
    if not expected:
        raise HTTPException(503, 'Proxy usage reporter is not configured')
    if auth is None or not secrets.compare_digest(auth.credentials, expected):
        raise HTTPException(401, 'Invalid usage reporter credential')
    return {'recorded': await service.record_usage(payload)}
