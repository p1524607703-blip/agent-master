import json
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.api.auth import require_session, require_super_admin_session
from app.services.frontend_errors import record_frontend_error
from app.services.diagnostics import request_traces

router=APIRouter(prefix='/diagnostics')
@router.post('/frontend-errors',status_code=202)
async def ingest_frontend_error(request: Request, session=Depends(require_session)):
 body=bytearray()
 async for chunk in request.stream():
  body.extend(chunk)
  if len(body)>16_384:raise HTTPException(413,'Frontend diagnostic too large')
 try:data=json.loads(body)
 except (ValueError,UnicodeDecodeError):raise HTTPException(400,'Invalid frontend diagnostic') from None
 return record_frontend_error(data,session[1])

@router.get('/frontend-errors',dependencies=[Depends(require_super_admin_session)])
def frontend_error_history(username: str|None=Query(None,max_length=100), user_id: str|None=Query(None,max_length=100),
 page_path: str|None=Query(None,max_length=300), client_commit: str|None=Query(None,max_length=64),
 kind: str|None=Query(None,max_length=40), since: str|None=Query(None,max_length=50),
 until: str|None=Query(None,max_length=50), limit: int=Query(100,ge=1,le=200)):
 try:return request_traces(event='frontend_error',username=username,user_id=user_id,page_path=page_path,
                          client_commit=client_commit,kind=kind,since=since,until=until,limit=limit)
 except ValueError as exc:raise HTTPException(422,str(exc)) from None
