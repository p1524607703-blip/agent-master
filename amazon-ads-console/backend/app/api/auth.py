from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.services.auth import create_session, resolve_session, revoke_session

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
    return credentials.credentials, user


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
