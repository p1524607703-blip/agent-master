from typing import Any, Dict, Tuple
import re

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.services.auth import create_session, resolve_session, revoke_session
from app.core.observability import update_context
from app.services.operator_cpo import OPERATOR_NAMES, operator_group_of

router = APIRouter(prefix='/auth', tags=['auth'])
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Invalid credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )


async def require_session(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
) -> Tuple[str, Dict[str, Any]]:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise unauthorized()
    user = await resolve_session(credentials.credentials)
    if user is None:
        raise unauthorized()
    update_context(user_id=str(user.get('userId') or ''), username=user.get('username'),
                   role=user.get('roleCode'), operator_group=str(user.get('operatorCode') or '').upper()[:2] or None)
    return credentials.credentials, user


async def require_management_session(session: Tuple[str, Dict[str, Any]] = Depends(require_session)):
    if session[1].get('roleCode') not in ('management', 'super_admin'):
        raise HTTPException(status_code=403, detail='Management access required')
    return session


async def require_own_operator_session(session: Tuple[str, Dict[str, Any]] = Depends(require_session)):
    if session[1].get('roleCode') != 'operator' or not operator_group_of(session[1].get('operatorCode')):
        raise HTTPException(status_code=403, detail='An active operator group is required')
    return session


async def require_operator_access(operator: str, session: Tuple[str, Dict[str, Any]] = Depends(require_session)):
    raw = operator.strip()
    upper = raw.upper()
    group = upper[:2] if re.fullmatch(r'[A-Z]{2}[0-9]*', upper) and upper[:2] in OPERATOR_NAMES else next((code for code, name in OPERATOR_NAMES.items() if name == raw), None)
    update_context(target_operator=group or 'unknown')
    user = session[1]
    if user.get('roleCode') in ('management', 'super_admin'):
        if group is None:
            raise HTTPException(status_code=404, detail='Operator not found')
        return session
    code = str(user.get('operatorCode') or '').upper()
    if user.get('roleCode') != 'operator' or not re.fullmatch(r'[A-Z]{2}[0-9]+', code) or group != code[:2]:
        raise HTTPException(status_code=403, detail='Operator group access denied')
    return session


@router.post('/login')
async def login(payload: LoginRequest):
    created = await create_session(payload.username, payload.password)
    if created is None:
        raise unauthorized()
    token, expires_at, user = created
    return {
        'accessToken': token,
        'tokenType': 'bearer',
        'expiresAt': expires_at,
        'user': user,
    }


@router.get('/me')
async def me(session: Tuple[str, Dict[str, Any]] = Depends(require_session)):
    return {'user': session[1]}


@router.post('/logout')
async def logout(session: Tuple[str, Dict[str, Any]] = Depends(require_session)):
    await revoke_session(session[0])
    return {'ok': True}
