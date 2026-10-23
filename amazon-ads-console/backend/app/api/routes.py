from urllib.parse import unquote
from typing import Any, Dict, Optional, Tuple, Literal
from fastapi import APIRouter, Depends, Query, Header, Request, HTTPException
from fastapi.responses import JSONResponse
# 业务读全部走「一份报告一张表」的新事实层（core.report_*_daily）
from app.services.report_data import reports
from app.services.operator_cpo import operator_cpo_summary, operator_cpo_detail, operator_period_options, my_cpo_summary, _data_revision, operator_group_of
# 运营页权限在读取缓存之前验证角色与运营组绑定
from app.api.auth import require_session, require_management_session, require_super_admin_session, require_operator_access, require_own_operator_session
# 产品主数据：读取V2正式映射视图，只读直显，无控制台确认写入路径
from app.services.full_funnel_visibility import full_funnel_for_viewer
from app.services.roster import product_mappings
from app.services.rds_query import ping
from app.services.cpo_imports import validate_upload, commit_upload, source_status
from app.services.cache import cache
from app.services.diagnostics import diagnostic_status, request_traces

router = APIRouter()

# Authenticated legacy clients receive a cheap, explicit retirement response.
# No loader, cache or database work runs for removed modules.
@router.api_route('/dashboard/overview', methods=['GET'])
@router.api_route('/dashboard/trend', methods=['GET'])
@router.api_route('/products', methods=['GET'])
@router.api_route('/cpo-jobs', methods=['GET'])
@router.api_route('/issues', methods=['GET'])
@router.api_route('/rules/product-allocation', methods=['GET'])
@router.api_route('/rules/ad-type', methods=['GET'])
@router.api_route('/product-mappings/discover', methods=['POST'])
@router.api_route('/product-mappings', methods=['POST'])
def retired_module():
    return JSONResponse(status_code=410, content={
        'code': 'MODULE_RETIRED', 'message': '此功能已移除，请使用 CPO 或费用分摊页面。',
    })

@router.get('/health', dependencies=[Depends(require_super_admin_session)])
def health():
    try:
        return {'status':'ok','database_mode':'rds-live','database_ok':ping()}
    except Exception as e:
        return {'status':'degraded','database_mode':'rds-live','database_ok':False,'error':str(e)}

@router.get('/operator-periods')
def operator_periods():
    return operator_period_options()

def _full_funnel_response(data, user):
    if 'fullFunnel' not in data:
        return data
    try:
        ledger = full_funnel_for_viewer(data['fullFunnel'], user.get('roleCode'),
                                      user.get('operatorCode') or user.get('operator_code'))
    except Exception:
        raise HTTPException(status_code=503, detail='全流域权限规则暂时不可用，请稍后重试。') from None
    return {**data, 'fullFunnel': ledger}


@router.get('/operator-cpo')
def operator_cpo(date: Optional[str] = None, period: str = Query('daily'),
                 sb_attribution_mode: Literal['name','asin'] = 'name',
                 session: Tuple[str, Dict[str, Any]] = Depends(require_session)):
    user = session[1]
    if user.get('roleCode') not in ('management', 'super_admin') and (
            user.get('roleCode') != 'operator' or not operator_group_of(user.get('operatorCode'))):
        raise HTTPException(403, 'An active operator group is required')
    period = period if period in ('daily','weekly','monthly') else 'daily'
    data = cache.get_or_set(f'operator:summary:{sb_attribution_mode}:{period}:{date or "latest"}', lambda: operator_cpo_summary(date, period, sb_attribution_mode), 60)
    if session[1].get('roleCode') == 'operator':
        # Shared totals do not include company-wide full-funnel disclosure.
        data = {k: v for k, v in data.items() if k in {
            'operators', 'data_date', 'period', 'period_start', 'period_end', 'final_cpo', 'period_label', 'sbAttributionMode'}}
        own = operator_group_of(user.get('operatorCode') or user.get('operator_code'))
        data['operators'] = [
            dict(row) if any(str(g or '').upper()[:2] == own for g in (row.get('groups') or [row.get('group')]))
            else {k: v for k, v in row.items() if k != 'pendingProductSpend'}
            for row in data.get('operators', [])
        ]
    return _full_funnel_response(data, session[1])

@router.get('/operators/{operator}', dependencies=[Depends(require_operator_access)])
def operator_view(operator: str, date: Optional[str] = None, period: str = Query('daily'),
                  sb_attribution_mode: Literal['name','asin'] = 'name',
                  session: Tuple[str, Dict[str, Any]] = Depends(require_operator_access)):
    period = period if period in ('daily','weekly','monthly') else 'daily'
    data = cache.get_or_set(f'operator:detail:{operator}:{sb_attribution_mode}:{period}:{date or "latest"}', lambda: operator_cpo_detail(operator,date,period,sb_attribution_mode=sb_attribution_mode), 60)
    if session[1].get('roleCode') != 'operator':
        # Management uses the aggregate disclosure panel, never an operator detail panel.
        return {key: value for key, value in data.items() if key != 'fullFunnel'}
    data = _full_funnel_response(data, session[1])
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
           sb_attribution_mode: Literal['name','asin'] = 'name',
           session: Tuple[str, Dict[str, Any]] = Depends(require_own_operator_session)):
    period = period if period in ('daily','weekly','monthly') else 'daily'
    user = session[1] or {}
    code = user.get('operatorCode') or user.get('operator_code') or ''
    display_name = user.get('displayName') or user.get('display_name') or ''
    data = cache.get_or_set(f'my-cpo:{code or "none"}:{display_name}:{sb_attribution_mode}:{period}:{date or "latest"}',
                            lambda: my_cpo_summary(code, date, period, display_name, sb_attribution_mode), 60)
    return _full_funnel_response(data, user)

@router.get('/product-mappings', dependencies=[Depends(require_management_session)])
def product_mapping_list():
    return cache.get_or_set('roster:v2:'+_data_revision(), product_mappings, 300)

@router.get('/cpo/source-status', dependencies=[Depends(require_super_admin_session)])
def cpo_source_status(date: str):
    return source_status(date)

@router.post('/cpo/imports/validate', dependencies=[Depends(require_super_admin_session)])
async def cpo_import_validate(request: Request, account: str, report_type: str, date: str, x_file_name: str = Header(...)):
    data = await request.body()
    return validate_upload(account, report_type, date, unquote(x_file_name), data)

@router.post('/cpo/imports/{token}/commit', dependencies=[Depends(require_super_admin_session)])
def cpo_import_commit(token: str, confirm_historical: bool = False):
    return commit_upload(token, confirm_historical)

@router.get('/reports', dependencies=[Depends(require_super_admin_session)])
def report_list(): return reports()

@router.get('/cache/stats', dependencies=[Depends(require_super_admin_session)])
def cache_stats(): return cache.stats()


@router.get('/diagnostics/status', dependencies=[Depends(require_super_admin_session)])
def system_diagnostics():
    return diagnostic_status()


@router.get('/diagnostics/requests', dependencies=[Depends(require_super_admin_session)])
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
