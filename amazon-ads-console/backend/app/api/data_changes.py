"""Feature-gated, authenticated proposal API. SQL storage is opened lazily."""
import csv
import io
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from fastapi.routing import APIRoute
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import require_session
from app.services.data_changes import COLUMNS, ChangeError, DataChangeService, SQLiteDataChangeRepository
from app.services.allocation import enabled as allocation_enabled
from app.core.config import settings


class UploadRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    file_name: str = Field(min_length=1, max_length=255)
    csv_text: str = Field(min_length=1)
    context: dict[str, str] = Field(default_factory=dict)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: str
    reason: str = Field(min_length=1, max_length=4000)
    content_hash: str


def default_service():
    if os.getenv('CPO_ALLOCATION_STORAGE', settings.cpo_allocation_storage) == 'postgres':
        from app.services.workflow_pg import PgDocumentRepository
        repository = PgDocumentRepository('mapping-proposals', lambda code: ChangeError(409, code, '审批记录已更新，请刷新后重试'))
        return DataChangeService(repository)
    path = os.getenv('CPO_DATA_CHANGES_DB', str(Path(__file__).resolve().parents[2] / 'var' / 'data_changes.sqlite3'))
    return DataChangeService(SQLiteDataChangeRepository(path))


class BoundedRequestRoute(APIRoute):
    def get_route_handler(self):
        original = super().get_route_handler()

        async def bounded(request):
            if request.method == 'POST':
                maximum = 10 * 1024 * 1024
                total, chunks = 0, []
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > maximum:
                        return JSONResponse(status_code=413, content={'detail': {'code': 'REQUEST_TOO_LARGE', 'message': 'Maximum request size is 10 MiB.'}})
                    chunks.append(chunk)
                request._body = b''.join(chunks)
            return await original(request)
        return bounded


def build_router(service_provider=default_service, server_tenant=None, enabled=None):
    router = APIRouter(prefix='/data-changes', tags=['data-changes'], route_class=BoundedRequestRoute)
    # Tenant is deployment-owned. No request field may override it.
    tenant = server_tenant or os.getenv('CPO_COMPANY_TENANT', 'company')

    def service():
        active = enabled if enabled is not None else allocation_enabled()
        if not active:
            raise HTTPException(503, detail={'code': 'MODULE_DISABLED', 'message': 'The allocation pilot has not been enabled.'})
        return service_provider() if callable(service_provider) else service_provider

    def invoke(operation):
        try:
            return operation()
        except ChangeError as exc:
            raise HTTPException(exc.status, detail={'code': exc.code, 'message': exc.message}) from exc

    def etag_response(response, result):
        response.headers['ETag'] = result['etag']
        return result

    @router.get('/templates')
    def template(template: str = Query('mapping'), session=Depends(require_session), svc=Depends(service)):
        if template != 'mapping':
            raise HTTPException(422, detail={'code': 'TEMPLATE_NOT_SUPPORTED', 'message': 'Only mapping-v1 CSV is implemented.'})
        output = io.StringIO(newline='')
        csv.writer(output).writerow(COLUMNS)
        return Response('\ufeff' + output.getvalue(), media_type='text/csv; charset=utf-8',
                        headers={'Content-Disposition': 'attachment; filename="mapping-v1.csv"', 'X-Template-Version': 'mapping-v1'})

    @router.post('/uploads', status_code=202)
    def upload(payload: UploadRequest, response: Response, session=Depends(require_session), svc=Depends(service),
               idempotency_key: Optional[str] = Header(None)):
        result = invoke(lambda: svc.upload(tenant, session[1], payload.file_name, payload.csv_text, payload.context, idempotency_key))
        return etag_response(response, result)

    @router.get('')
    def batches(session=Depends(require_session), svc=Depends(service), cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
        return invoke(lambda: svc.list(tenant, session[1], cursor, limit))

    @router.get('/{batch_id}')
    def detail(batch_id: str, response: Response, session=Depends(require_session), svc=Depends(service)):
        return etag_response(response, invoke(lambda: svc.get(tenant, session[1], batch_id)))

    @router.get('/{batch_id}/rows')
    def rows(batch_id: str, session=Depends(require_session), svc=Depends(service), cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
        return invoke(lambda: svc.rows(tenant, session[1], batch_id, cursor, limit))

    @router.get('/{batch_id}/impact')
    def impact(batch_id: str, session=Depends(require_session), svc=Depends(service)):
        return invoke(lambda: svc.impact(tenant, session[1], batch_id))

    @router.post('/{batch_id}/revisions', status_code=202)
    def revision(batch_id: str, payload: UploadRequest, response: Response, session=Depends(require_session), svc=Depends(service),
                 idempotency_key: Optional[str] = Header(None), if_match: Optional[str] = Header(None)):
        return etag_response(response, invoke(lambda: svc.upload(tenant, session[1], payload.file_name, payload.csv_text,
                                                               payload.context, idempotency_key, parent_id=batch_id, parent_if_match=if_match)))

    @router.post('/{batch_id}/submit')
    def submit(batch_id: str, response: Response, session=Depends(require_session), svc=Depends(service),
               if_match: Optional[str] = Header(None), idempotency_key: Optional[str] = Header(None)):
        return etag_response(response, invoke(lambda: svc.command(tenant, session[1], batch_id, 'submit', {}, if_match, idempotency_key)))

    @router.post('/{batch_id}/withdraw')
    def withdraw(batch_id: str, response: Response, session=Depends(require_session), svc=Depends(service),
                 if_match: Optional[str] = Header(None), idempotency_key: Optional[str] = Header(None)):
        return etag_response(response, invoke(lambda: svc.command(tenant, session[1], batch_id, 'withdraw', {}, if_match, idempotency_key)))

    @router.post('/{batch_id}/decision')
    def decision(batch_id: str, payload: DecisionRequest, response: Response, session=Depends(require_session), svc=Depends(service),
                 if_match: Optional[str] = Header(None), idempotency_key: Optional[str] = Header(None)):
        return etag_response(response, invoke(lambda: svc.command(tenant, session[1], batch_id, 'decision', payload.model_dump(), if_match, idempotency_key)))

    @router.post('/{batch_id}/apply')
    def apply(batch_id: str, response: Response, session=Depends(require_session), svc=Depends(service),
              if_match: Optional[str] = Header(None), idempotency_key: Optional[str] = Header(None)):
        return etag_response(response, invoke(lambda: svc.command(tenant, session[1], batch_id, 'apply', {}, if_match, idempotency_key)))

    return router
