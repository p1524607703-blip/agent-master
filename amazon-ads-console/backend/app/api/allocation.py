import base64
import csv
import hashlib
import io
import json
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query, Request, Response

from .auth import require_session
from app.services.allocation import TENANT, enabled, error, get_service, manager, can_create_run
from app.services.allocation_store import digest, now, StoreConflict
from app.core.config import settings

router = APIRouter(prefix="/ad-allocation/v1", tags=["allocation"], dependencies=[Depends(require_session)])


async def bounded_json(request):
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > 10 * 1024 * 1024:
            error(413, "UPLOAD_TOO_LARGE", "请求最大10MB")
    try:
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, UnicodeDecodeError):
        error(422, "INVALID_JSON", "请求须为JSON对象")


def etag(response, resource):
    response.headers["ETag"] = '"%s"' % resource["revision"]
    response.headers["X-Request-ID"] = str(uuid.uuid4())


def paginate(rows, scope, cursor, limit):
    offset = 0
    marker = digest(scope)
    if cursor:
        try:
            decoded = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
            if decoded["scope"] != marker or type(decoded["offset"]) is not int or decoded["offset"] < 0:
                raise ValueError()
            offset = decoded["offset"]
        except Exception:
            error(400, "INVALID_CURSOR", "分页标记无效或不属于当前版本与筛选")
    sliced = rows[offset:offset + limit]
    next_cursor = None
    if offset + limit < len(rows):
        next_cursor = base64.urlsafe_b64encode(json.dumps({"scope": marker, "offset": offset + limit}).encode()).decode()
    return {"items": sliced, "next_cursor": next_cursor, "total": len(rows)}


@router.get("/capabilities")
def capabilities(session=Depends(require_session)):
    if settings.cpo_allocation_environment == 'PRODUCTION':
        return {"enabled": enabled(), "environment": "PRODUCTION", "formal_publication": False,
                "comparison": False, "can_create_run": manager(session[1]) and enabled() and can_create_run(),
                "export_formats": ["csv", "xlsx"], "authoritative_source_connected": False,
                "confirmed_reference_available": settings.cpo_allocation_reference_available,
                "source_mode": "CONFIRMED_REFERENCE_AND_FROZEN_TRIAL", "storage": "postgres",
                "message": "9月运营确认版与新SOP冻结试算分别展示；待核试算不替代确认版。数据审批通过后进入待生效状态。"}
    return {"enabled": enabled(), "environment": "DEVELOPMENT_ACCEPTANCE", "formal_publication": False,
            "comparison": False, "can_create_run": manager(session[1]) and enabled() and can_create_run(),
            "export_formats": ["csv"], "authoritative_source_connected": False,
            "message": "开发验收，尚未接入正式数据"}


@router.post("/runs", status_code=202)
async def create_run(request: Request, response: Response, tasks: BackgroundTasks,
                     idempotency_key: Optional[str] = Header(None), session=Depends(require_session), service=Depends(get_service)):
    run, created = service.create_run(await bounded_json(request), session[1], idempotency_key)
    if created:
        tasks.add_task(service.execute, run["id"])
    etag(response, run)
    return service.project(run, session[1])


@router.get("/runs")
def list_runs(period: Optional[str] = None, cursor: Optional[str] = None, limit: int = Query(50, ge=1, le=200),
              session=Depends(require_session), service=Depends(get_service)):
    user = session[1]
    rows = []
    for run in service.store.list(TENANT, "run"):
        if period and run["period"] != period:
            continue
        try:
            service.get_run(run["id"], user)
        except Exception as exc:
            if getattr(exc, "status_code", None) == 404:
                continue
            raise
        rows.append(service.project(run, user))
    return paginate(rows, ["runs", period, user["userId"]], cursor, limit)


@router.get("/runs/{run_id}")
def get_run(run_id: str, response: Response, session=Depends(require_session), service=Depends(get_service)):
    run = service.get_run(run_id, session[1])
    etag(response, run)
    return service.project(run, session[1])


@router.post("/runs/{run_id}/retry", status_code=202)
def retry(run_id: str, tasks: BackgroundTasks, response: Response, if_match: Optional[str] = Header(None),
          idempotency_key: Optional[str] = Header(None), session=Depends(require_session), service=Depends(get_service)):
    run, changed = service.lifecycle_command(run_id, "retry", session[1], idempotency_key, if_match)
    if changed:
        tasks.add_task(service.execute, run_id)
    etag(response, run)
    return service.project(run, session[1])


@router.post("/runs/{run_id}/cancel", status_code=202)
def cancel(run_id: str, response: Response, if_match: Optional[str] = Header(None),
           idempotency_key: Optional[str] = Header(None), session=Depends(require_session), service=Depends(get_service)):
    run, _ = service.lifecycle_command(run_id, "cancel", session[1], idempotency_key, if_match)
    etag(response, run)
    return service.project(run, session[1])


@router.get("/runs/{run_id}/workbook.xlsx")
def product_workbook(run_id: str, session=Depends(require_session), service=Depends(get_service)):
    from app.services.operator_export_workbooks import workbook
    from decimal import Decimal
    run = service.get_run(run_id, session[1])
    products = service.rows(run, 'products', session[1])
    if not run.get('result'):
        error(409, 'RESULT_NOT_READY', '计算结果尚未生成')
    provenance = run.get('provenance') or {}
    reference = run.get('purpose') == 'OPERATIONS_CONFIRMED_REFERENCE'
    rows = [
        [run['period'] + (' 运营确认历史参考' if reference else ' 冻结试算（待核实）')],
        ['来源：' + str(provenance.get('source_label', '冻结输入')) + '；规则：' + str(provenance.get('rule_version', '未指定'))],
        ['导出范围按当前登录角色过滤；币种USD；空白表示未确定。历史参考不代表新SOP重算。'],
        ['运营组', '款号', '自推归因件数', '光环归因件数', '自推费用', '光环费用', '保护留存', '剩余归款',
         '最终承担费用', '暂计承担费用', '广告归因件数', '广告归因每件成本'],
    ]
    def number(value):
        return None if value is None else float(Decimal(str(value)))
    for item in products:
        rows.append([item.get('group'), item.get('style'), item.get('direct_units'), item.get('halo_units'),
                     *[number(item.get(key)) for key in ['self_cost', 'halo_cost', 'protection_cost', 'remainder_cost', 'final_cost', 'provisional_cost']],
                     item.get('attributed_units'), number(item.get('allocation_attributed_unit_cost'))])
    content = workbook(rows, money_columns=(5, 6, 7, 8, 9, 10, 12), numeric_columns=(3, 4, 11))
    return Response(content, media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': 'attachment; filename="allocation_%s_products.xlsx"' % run_id,
                             'Cache-Control': 'private, no-store', 'X-Content-SHA256': hashlib.sha256(content).hexdigest()})


@router.get("/runs/{run_id}/{report}")
def get_rows(run_id: str, report: str, cursor: Optional[str] = None, limit: int = Query(50, ge=1, le=200),
             session=Depends(require_session), service=Depends(get_service)):
    run = service.get_run(run_id, session[1])
    rows = service.rows(run, report, session[1])
    return paginate(rows, [run_id, report, session[1]["userId"], run.get("result_hash")], cursor, limit)


@router.post("/runs/{run_id}/exports", status_code=202)
async def export_run(run_id: str, request: Request, idempotency_key: Optional[str] = Header(None),
                     session=Depends(require_session), service=Depends(get_service)):
    user = session[1]
    run = service.get_run(run_id, user)
    payload = await bounded_json(request)
    if payload.get("format") != "csv":
        error(422, "FORMAT_NOT_AVAILABLE", "当前验收版本支持CSV；正式11表XLSX待模板验收")
    if not idempotency_key or len(idempotency_key) > 200:
        error(422, "IDEMPOTENCY_KEY_REQUIRED", "请提供幂等键")
    if not run.get("result"):
        error(409, "RESULT_NOT_READY", "计算结果尚未生成")
    report = payload.get("report", "products")
    rows = service.rows(run, report, user)
    export_id = str(uuid.uuid4())
    purpose = run.get('purpose', 'DEVELOPMENT_TRIAL')
    prefix = 'confirmed_reference' if purpose == 'OPERATIONS_CONFIRMED_REFERENCE' else 'trial'
    export = dict(id=export_id, export_id=export_id, run_id=run_id, report=report, status="SUCCEEDED",
                  created_at=now(), created_by=str(user["userId"]), result_hash=run["result_hash"],
                  rows=rows, purpose=purpose, filename="%s_%s_%s.csv" % (prefix, run_id, report))
    try:
        export, _ = service.store.create(TENANT, str(user["userId"]), "EXPORT:" + run_id, idempotency_key, payload, "export", export)
    except StoreConflict as exc:
        error(409, str(exc), "导出幂等键对应了不同内容")
    return {k: v for k, v in export.items() if k != "rows"}


@router.get("/exports/{export_id}/download")
def download(export_id: str, session=Depends(require_session), service=Depends(get_service)):
    user = session[1]
    export = service.store.get(TENANT, "export", export_id)
    if not export or (not manager(user) and export["created_by"] != str(user["userId"])):
        error(404, "RESOURCE_NOT_FOUND", "未找到可下载的文件")
    run = service.get_run(export["run_id"], user)
    # Reauthorize every row at download, even when ownership changes after export.
    allowed_rows = service.rows(run, export["report"], user)
    allowed_hashes = {digest(row) for row in allowed_rows}
    if any(digest(row) not in allowed_hashes for row in export["rows"]):
        error(403, "EXPORT_SCOPE_CHANGED", "下载权限范围已经变化，请重新导出")
    rows = export["rows"]
    columns = sorted({key for row in rows for key in row})
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(["purpose", "run_id", "result_hash", "rule_version", "report_exported_date"] + columns)
    def cell(value):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else "" if value is None else str(value)
        # Excel CSV import must never interpret untrusted labels as formulas.
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text
    for row in rows:
        provenance = run.get('provenance') or {}
        writer.writerow([cell(export.get('purpose', run.get('purpose', 'DEVELOPMENT_TRIAL'))), run["id"], run["result_hash"],
                         cell(provenance.get('rule_version')), cell(provenance.get('report_exported_date'))] + [cell(row.get(k)) for k in columns])
    content = stream.getvalue().encode("utf-8-sig")
    return Response(content, media_type="text/csv; charset=utf-8", headers={
        "Content-Disposition": 'attachment; filename="%s"' % export["filename"],
        "X-Content-SHA256": hashlib.sha256(content).hexdigest(), "Cache-Control": "no-store"})
