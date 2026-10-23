"""Local acceptance slice of the allocation lifecycle; formal publication gated."""
import os
import uuid
from copy import deepcopy
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from .allocation_store import AllocationStore, StoreConflict, digest, now
from .allocation_cpo import business_metrics
from app.core.config import settings

TENANT = os.getenv("CPO_COMPANY_TENANT", "company")
MANAGERS = {"management", "super_admin"}


def error(status, code, message):
    raise HTTPException(status, detail={"code": code, "message": message})


def manager(user):
    return user.get("roleCode") in MANAGERS


def require_manager(user):
    if not manager(user):
        error(403, "CAPABILITY_DENIED", "此操作需要管理层权限")


def enabled():
    return os.getenv("CPO_ALLOCATION_ENABLED") == "1" if "CPO_ALLOCATION_ENABLED" in os.environ else settings.cpo_allocation_enabled


def can_create_run():
    value = os.getenv('CPO_ALLOCATION_CAN_CREATE_RUN')
    return value == '1' if value is not None else settings.cpo_allocation_can_create_run


def _no_float(value):
    if isinstance(value, float):
        raise ValueError("FLOAT_INPUT_FORBIDDEN")
    if isinstance(value, dict):
        for item in value.values():
            _no_float(item)
    elif isinstance(value, list):
        for item in value:
            _no_float(item)


class AllocationService:
    def __init__(self, store):
        self.store = store

    def create_run(self, payload, user, key):
        require_manager(user)
        if not can_create_run():
            error(409, 'TRIAL_CREATION_DISABLED', '当前发布提供已确认历史结果及冻结试算，在线新建试算尚未开放')
        if not key or len(key) > 200:
            error(422, "IDEMPOTENCY_KEY_REQUIRED", "请提供有效幂等键")
        if set(payload) - {"period", "report_timezone", "snapshot", "business_snapshot"}:
            error(422, "UNSUPPORTED_FIELD", "试算只接受明确的月份、时区及冻结输入")
        try:
            _no_float(payload)
            period = payload["period"]
            if datetime.strptime(period, "%Y-%m").strftime("%Y-%m") != period:
                raise ValueError("PERIOD_INVALID")
            ZoneInfo(payload["report_timezone"])
            snapshot = payload["snapshot"]
            if not isinstance(snapshot, dict) or not snapshot.get("campaigns") or not snapshot.get("products"):
                raise ValueError("SNAPSHOT_REQUIRED")
            if not isinstance(snapshot["campaigns"], list) or not isinstance(snapshot["products"], list) or any(not isinstance(c, dict) or not isinstance(c.get("rows", []), list) for c in snapshot["campaigns"]) or any(not isinstance(p, dict) for p in snapshot["products"]):
                raise ValueError("SNAPSHOT_SHAPE_INVALID")
            if snapshot.get("mode", "FULL") != "FULL":
                raise ValueError("MODE_NOT_EXPOSED_IN_ACCEPTANCE_API")
            if snapshot.get("currency") != "USD":
                raise ValueError("USD_EXPLICITLY_REQUIRED")
            if len(snapshot["campaigns"]) > 5000 or sum(len(c.get("rows", [])) for c in snapshot["campaigns"]) > 50000:
                error(413, "SNAPSHOT_TOO_LARGE", "试算输入超过本地验收限额")
            if "base_result" in snapshot:
                raise ValueError("BASE_RESULT_NOT_ALLOWED")
        except (KeyError, TypeError, ValueError, ZoneInfoNotFoundError) as exc:
            error(422, "INVALID_SNAPSHOT", str(exc))
        resource_id = str(uuid.uuid4())
        body = dict(id=resource_id, run_id=resource_id, created_at=now(), created_by=str(user["userId"]),
                    period=period, report_timezone=payload["report_timezone"], status="QUEUED",
                    calculation_status="QUEUED", review_status="DRAFT", purpose="DEVELOPMENT_TRIAL",
                    snapshot=deepcopy(snapshot), snapshot_hash=digest(snapshot), input_fingerprint=digest(payload),
                    business_snapshot=deepcopy(payload.get("business_snapshot")), result=None, summary=None,
                    capabilities={"formal_publication": False, "comparison": False, "source": "UPLOADED_FROZEN_TRIAL"},
                    events=[{"event": "CREATED", "actor": str(user["userId"]), "at": now()}])
        try:
            return self.store.create(TENANT, str(user["userId"]), "CREATE_RUN", key, payload, "run", body)
        except StoreConflict as exc:
            error(409, str(exc), "同一幂等键对应了不同内容")

    def execute(self, run_id):
        from .allocation_engine import calculate
        run = self.store.get(TENANT, "run", run_id)
        if not run or run["status"] != "QUEUED":
            return
        def start(body):
            body.update(status="RUNNING", calculation_status="RUNNING", lease_expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
            return body
        try:
            run = self.store.update(TENANT, "run", run_id, run["revision"], start)
        except StoreConflict:
            return
        try:
            result = calculate(run["snapshot"])
            status = result["calculation_status"]
            failure = None
        except Exception as exc:
            # No connection strings or arbitrary exception text in public state.
            result, status, failure = None, "FAILED", "INPUT_OR_CALCULATION_FAILED"
        if result is not None:
            try:
                result["cpo"] = business_metrics(result.get("products", []), run.get("business_snapshot"), run["period"], run["report_timezone"])
                result["business_issues"] = []
            except (ValueError, KeyError, TypeError, AttributeError, ArithmeticError):
                # Financial settlement can succeed independently of business CPO.
                result["cpo"] = business_metrics(result.get("products", []), invalid_reason="BUSINESS_SNAPSHOT_INVALID")
                result["business_issues"] = [{"code": "BUSINESS_SNAPSHOT_INVALID", "message": "业务快照存在缺口或冲突，费用保留，业务CPO待核验"}]
        def finish(body):
            body.update(result=result, summary=result.get("summary") if result else None,
                        result_hash=digest(result) if result else None, status=status,
                        calculation_status=status, review_status="DRAFT", error_code=failure, completed_at=now())
            body["events"].append({"event": status, "at": now()})
            return body
        try:
            self.store.update(TENANT, "run", run_id, run["revision"], finish)
        except StoreConflict:
            # A cancellation/retry won CAS; an expired worker cannot overwrite it.
            return

    def lifecycle_command(self, run_id, action, user, key, if_match):
        require_manager(user)
        self.get_run(run_id, user)
        if not key or len(key) > 200:
            error(422, "IDEMPOTENCY_KEY_REQUIRED", "请提供有效幂等键")
        if not if_match:
            error(428, "IF_MATCH_REQUIRED", "请先读取当前版本")
        try:
            if len(if_match) < 3 or not if_match.startswith('"') or not if_match.endswith('"'):
                raise ValueError()
            revision = int(if_match[1:-1])
        except ValueError:
            error(412, "ETAG_MISMATCH", "版本标记无效")
        def mutate(body):
            if action == "cancel":
                if body["status"] not in {"QUEUED", "RUNNING"}:
                    error(409, "RUN_NOT_CANCELLABLE", "该状态不能取消")
                body.update(status="CANCELLED", calculation_status="CANCELLED")
            else:
                if body["status"] in {"QUEUED", "RUNNING"}:
                    lease = body.get("lease_expires_at") or (datetime.fromisoformat(body["created_at"]) + timedelta(minutes=5)).isoformat()
                    if datetime.fromisoformat(lease) > datetime.now(timezone.utc):
                        error(409, "WORKER_LEASE_ACTIVE", "当前任务仍在处理，请稍后刷新")
                elif body["status"] != "FAILED":
                    error(409, "RUN_NOT_RETRYABLE", "只允许重试失败或已过期的任务")
                body.update(status="QUEUED", calculation_status="QUEUED", error_code=None, lease_expires_at=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
            body["events"].append({"event": action.upper(), "actor": str(user["userId"]), "at": now()})
            return body
        try:
            return self.store.command_update(TENANT, str(user["userId"]), action + ":" + run_id, key, {"revision": revision}, "run", run_id, revision, mutate)
        except StoreConflict as exc:
            error(412 if str(exc) == "ETAG_MISMATCH" else 409, str(exc), "版本或请求键冲突，请重新读取后处理")

    def get_run(self, run_id, user):
        run = self.store.get(TENANT, "run", run_id)
        if not run:
            error(404, "RESOURCE_NOT_FOUND", "未找到可访问的计算版本")
        if not manager(user):
            if user.get("roleCode") != "operator" or not user.get("operatorCode"):
                error(403, "CAPABILITY_DENIED", "当前账户没有读取权限")
            own = [p for p in (run.get("result") or {}).get("products", []) if p.get("group") == user["operatorCode"]]
            if not own:
                error(404, "RESOURCE_NOT_FOUND", "未找到可访问的计算版本")
        return run

    def project(self, run, user):
        visible = {k: v for k, v in run.items() if k not in {"snapshot", "business_snapshot", "result"}}
        if not manager(user):
            # Company-wide S/X/K, inputs, hashes and audit identities remain private.
            visible = {k: visible[k] for k in ("id", "run_id", "period", "status", "calculation_status", "review_status", "revision", "purpose", "capabilities", "provenance") if k in visible}
            visible["summary"] = None
        return visible

    def rows(self, run, report, user):
        if report not in {"products", "campaigns", "issues", "groups", "baselines", "cpo"}:
            error(422, "INVALID_REPORT", "未知的结果视图")
        if not manager(user) and report not in {"products", "cpo"}:
            error(403, "CAPABILITY_DENIED", "运营可读取本人款式及成本结果")
        rows = (run.get("result") or {}).get(report, [])
        if not manager(user):
            rows = [p for p in rows if p.get("group") == user.get("operatorCode")]
        return rows


def get_service():
    if not enabled():
        error(503, "MODULE_DISABLED", "广告分摊模块尚未启用，当前处于开发验收阶段")
    if os.getenv('CPO_ALLOCATION_STORAGE', settings.cpo_allocation_storage) == 'postgres':
        from .workflow_pg import PgAllocationStore
        return AllocationService(PgAllocationStore())
    path = os.getenv("CPO_ALLOCATION_DB", str(Path(__file__).resolve().parents[2] / ".local/allocation.sqlite3"))
    return AllocationService(AllocationStore(path))
