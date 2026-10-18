from fastapi import APIRouter, Depends

from app.api.auth import require_management_session
from app.services.codex_devices import overview as read_overview

router = APIRouter(prefix='/codex', tags=['codex'])


@router.get('/overview', dependencies=[Depends(require_management_session)])
async def overview():
    return await read_overview()
