from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.routes import router
from app.api.auth import router as auth_router, require_session
from app.core.config import settings
from app.services.operator_cpo import operator_cpo_summary
from app.services.build_cache import BuildBusyError
from app.core.observability import RequestDiagnosticsMiddleware, capture_exception

app = FastAPI(title=settings.app_name, version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:15173",
        "http://127.0.0.1:15173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.add_middleware(RequestDiagnosticsMiddleware)
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(router, prefix=settings.api_prefix, dependencies=[Depends(require_session)])


@app.get(settings.api_prefix + '/ping')
def anonymous_ping():
    return {'ok': True}


@app.exception_handler(BuildBusyError)
async def build_busy_handler(request, exc):
    capture_exception(exc)
    return JSONResponse(status_code=503, content={'detail': 'CPO snapshot is being built. Retry shortly.', 'code': 'CPO_BUILD_BUSY'}, headers={'Retry-After': '2'})


@app.on_event("startup")
def warm_operator_snapshot():
    # Local auth acceptance explicitly disables this to avoid touching the RDS-backed CPO read model.
    if not settings.operator_warmup_enabled:
        return
    # Warm the latest operator daily read model so the first UI visit does not pay the RDS aggregation cost.
    try:
        operator_cpo_summary(None, 'daily')
    except Exception:
        # RDS health is exposed separately; a temporary warmup failure must not block API startup.
        pass
