from urllib.parse import unquote
from typing import Any, Dict, Optional, Tuple
from fastapi import APIRouter, Depends, Query, Header, Request, HTTPException
from fastapi.responses import JSONResponse
from app.services.mock_data import JOBS,ISSUES,PRODUCT_RULES,AD_TYPE_RULES
# 业务读全部走「一份报告一张表」的新事实层（core.report_*_daily）
from app.services.report_data import dashboard_overview, dashboard_trend, products, reports
from app.services.operator_cpo import operator_cpo_summary, operator_cpo_detail, operator_period_options, my_cpo_summary
# 运营页权限在读取缓存之前验证角色与运营组绑定
from app.api.auth import require_session, require_management_session, require_operator_access, require_own_operator_session
# 产品主数据：直接读应用库 app.product_roster，只读直显，无「管理/确认」写入路径
from app.services.roster import product_mappings, not_supported
from app.services.rds_query import ping
from app.services.cpo_imports import validate_upload, commit_upload, source_status
from app.services.cache import cache
from app.services.diagnostics import diagnostic_status, request_traces

router = APIRouter()

# ── 已下架模块（2026-09-15 用户要求暂时隐藏）──────────────────────────────
# 前端路由与侧边栏入口已摘除；这里把对应接口一并封住，
# 避免有人直接 curl 到半成品数据。视图文件与 service 代码保留，恢复时删掉这几行即可。
RETIRED_MODULES = {
    'products': '产品明细',
    'ad_type_rule': '广告类型规则',
}

def _retired(key: str) -> JSONResponse:
    """已下架模块统一以 HTTP 410 Gone 响应 —— 在协议层就表明「曾经存在、现在不提供了」。"""
    return JSONResponse(status_code=410, content={
        'status': 'GONE',
        'code': 'MODULE_RETIRED',
        'module': RETIRED_MODULES[key],
        'message': f"{RETIRED_MODULES[key]} 模块已暂时下架，接口不再提供数据。",
        'hint': '前端入口已隐藏。如需恢复，请在后端 routes.py 与前端 router/AppSidebar 中一并还原。',
    })

@router.get('/health', dependencies=[Depends(require_management_session)])
def health():
    try:
        return {'status':'ok','database_mode':'rds-live','database_ok':ping()}
    except Exception as e:
        return {'status':'degraded','database_mode':'rds-live','database_ok':False,'error':str(e)}

@router.get('/dashboard/overview', dependencies=[Depends(require_management_session)])
def overview(account_id: Optional[str] = None, date: Optional[str] = None):
    return cache.get_or_set(f'dashboard:{account_id or "default"}:{date or "latest"}', lambda: dashboard_overview(account_id,date), 60)

@router.get('/dashboard/trend', dependencies=[Depends(require_management_session)])
def trend(account_id: Optional[str] = None, end_date: Optional[str] = None, days: int = Query(14,ge=1,le=90)):
    return cache.get_or_set(f'trend:{account_id or "default"}:{end_date or "latest"}:{days}', lambda: dashboard_trend(account_id,end_date,days), 60)

@router.get('/operator-periods')
def operator_periods():
    return operator_period_options()

@router.get('/operator-cpo', dependencies=[Depends(require_management_session)])
def operator_cpo(date: Optional[str] = None, period: str = Query('daily')):
    period = period if period in ('daily','weekly','monthly') else 'daily'
    return cache.get_or_set(f'operator:summary:{period}:{date or "latest"}', lambda: operator_cpo_summary(date, period), 60)

@router.get('/operators/{operator}', dependencies=[Depends(require_operator_access)])
def operator_view(operator: str, date: Optional[str] = None, period: str = Query('daily'),
                  session: Tuple[str, Dict[str, Any]] = Depends(require_operator_access)):
    period = period if period in ('daily','weekly','monthly') else 'daily'
    data = cache.get_or_set(f'operator:detail:{operator}:{period}:{date or "latest"}', lambda: operator_cpo_detail(operator,date,period), 60)
    if session[1].get('roleCode') == 'operator':
        # Group detail is shared, but global audit volumes are management-only.
        return {key: value for key, value in data.items()
                if key not in {'businessMappingConflictOrders', 'businessOutOfScopeOrders'}}
    return data

# ── 运营页：我的 CPO 单双数据（只看自己）─────────────────────────────────
# 与 /operator-cpo 共用同一套口径与表格字段，区别有两个：
#   1) 需要登录态，运营组从会话里的 operatorCode 推导（ZJ1 → ZJ），不接收前端传参，杜绝越权查看他人；
#   2) 跨全部广告账户汇总（管理页只取单账户），否则运营自己的量分散在多个账户里看不到。
@router.get('/my-cpo')
def my_cpo(date: Optional[str] = None, period: str = Query('daily'),
           session: Tuple[str, Dict[str, Any]] = Depends(require_own_operator_session)):
    period = period if period in ('daily','weekly','monthly') else 'daily'
    user = session[1] or {}
    code = user.get('operatorCode') or user.get('operator_code') or ''
    display_name = user.get('displayName') or user.get('display_name') or ''
    return cache.get_or_set(f'my-cpo:{code or "none"}:{display_name}:{period}:{date or "latest"}',
                            lambda: my_cpo_summary(code, date, period, display_name), 60)

@router.get('/products', dependencies=[Depends(require_management_session)])
def product_list(account_id: Optional[str] = None, date: Optional[str] = None, limit: int = Query(50,ge=1,le=200)):
    # 已下架：产品明细模块。原实现见 app.services.report_data.products
    return _retired('products')

@router.get('/product-mappings', dependencies=[Depends(require_management_session)])
def product_mapping_list():
    return cache.get_or_set('roster:v1', product_mappings, 300)

@router.post('/product-mappings/discover', dependencies=[Depends(require_management_session)])
def product_mapping_discover(date: Optional[str] = None, account: Optional[str] = None):
    # 停用：改为「开发端核验 → 只读直显」，不再做候选发现
    return not_supported('自动发现新品')

@router.post('/product-mappings', dependencies=[Depends(require_management_session)])
async def product_mapping_create(request: Request):
    # 停用：不再支持控制台端人工新增/确认
    return not_supported('手动新增产品映射')


@router.get('/cpo/source-status', dependencies=[Depends(require_management_session)])
def cpo_source_status(date: str):
    return source_status(date)

@router.post('/cpo/imports/validate', dependencies=[Depends(require_management_session)])
async def cpo_import_validate(request: Request, account: str, report_type: str, date: str, x_file_name: str = Header(...)):
    data = await request.body()
    return validate_upload(account, report_type, date, unquote(x_file_name), data)

@router.post('/cpo/imports/{token}/commit', dependencies=[Depends(require_management_session)])
def cpo_import_commit(token: str, confirm_historical: bool = False):
    return commit_upload(token, confirm_historical)

@router.get('/cpo-jobs', dependencies=[Depends(require_management_session)])
def cpo_jobs(): return JOBS
@router.get('/issues', dependencies=[Depends(require_management_session)])
def issues(): return ISSUES
@router.get('/rules/product-allocation', dependencies=[Depends(require_management_session)])
def product_rules(): return PRODUCT_RULES
@router.get('/rules/ad-type', dependencies=[Depends(require_management_session)])
def ad_type_rules(): 
    # 已下架：广告类型模块。原实现返回 app.services.mock_data.AD_TYPE_RULES
    return _retired('ad_type_rule')
@router.get('/reports', dependencies=[Depends(require_management_session)])
def report_list(): return cache.get_or_set('reports:all', reports, 60)

@router.get('/cache/stats', dependencies=[Depends(require_management_session)])
def cache_stats(): return cache.stats()


@router.get('/diagnostics/status', dependencies=[Depends(require_management_session)])
def system_diagnostics():
    return diagnostic_status()


@router.get('/diagnostics/requests', dependencies=[Depends(require_management_session)])
def diagnostic_requests(
    request_id: Optional[str] = Query(None, max_length=128),
    user_id: Optional[str] = Query(None, max_length=100),
    username: Optional[str] = Query(None, max_length=100),
    endpoint: Optional[str] = Query(None, max_length=200),
    since: Optional[str] = Query(None, max_length=50),
    until: Optional[str] = Query(None, max_length=50),
    limit: int = Query(100, ge=1, le=200),
):
    try:
        return request_traces(request_id=request_id, user_id=user_id, username=username,
                              endpoint=endpoint, since=since, until=until, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
