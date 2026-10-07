"""Request diagnostics shared by async dependencies and synchronous worker threads.

Only the explicitly defined fields below are emitted. Request bodies, arbitrary
query strings, SQL, exception messages and authentication headers are never read.
"""
from __future__ import annotations

import ipaddress
import json
import logging
import os
import re
import sys
import time
import traceback
import uuid
from collections import deque
from contextvars import ContextVar
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs

from starlette.responses import JSONResponse

request_context: ContextVar[Optional[dict[str, Any]]] = ContextVar("cpo_request_context", default=None)
COUNTERS = ("l1_hit", "l1_miss", "l1_stale", "l2_hit", "l2_miss", "l2_error", "lock_acquired", "lock_timeout", "psql_calls")
TIMINGS = ("lock_wait_ms", "db_wall_ms", "build_ms", "total_ms")
CONTEXT_FIELDS = ("user_id", "username", "role", "operator_group", "target_operator", "date", "period", "period_start", "period_end", "revision", "quality")
_REQUEST_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(record.diagnostic, ensure_ascii=False, separators=(",", ":"))


logger = logging.getLogger("cpo.diagnostics")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_JsonFormatter())
    logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


def update_context(**fields: Any) -> None:
    context = request_context.get()
    if context is not None:
        for key, value in fields.items():
            if key in CONTEXT_FIELDS:
                context[key] = value


def increment(field: str, amount: float = 1) -> None:
    context = request_context.get()
    if context is not None and field in COUNTERS + TIMINGS:
        context[field] += amount


def context_metadata() -> dict[str, Any]:
    context = request_context.get() or {}
    return {key: context.get(key) for key in ("revision", "date", "period_start", "period_end", "quality")}


def release_metadata() -> dict[str, str]:
    console = Path(__file__).resolve().parents[3]
    # release.json belongs to this immutable release, whereas the shared pointer
    # may still name the previous release during startup and health checks.
    for path in (console.parent / "release.json", console / "release.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            commit = record.get("commit", "unknown")
            release = record.get("ref") or record.get("release_id") or record.get("release") or path.parent.name
            return {"release": str(release)[:128], "commit": str(commit)[:64]}
        except (OSError, ValueError, AttributeError):
            continue
    return {"release": "development", "commit": "unknown"}


def capture_quality(value: Any) -> None:
    if not isinstance(value, dict) or "final_cpo" not in value:
        return
    summary = value.get("detailSummary") or value.get("summary") or {}
    update_context(quality={"final_cpo": bool(value["final_cpo"]),
                           "missingBusinessProducts": summary.get("missingBusinessProducts"),
                           "unpairedAdSpend": summary.get("unpairedAdSpend"),
                           "sourceCompleteness": value.get("sourceCompleteness")})


def capture_exception(exc: BaseException) -> None:
    context = request_context.get()
    if context is not None:
        context["exception_type"] = type(exc).__name__
        context["stack"] = _safe_stack(exc)


def _safe_stack(exc: BaseException) -> list[dict[str, Any]]:
    # Keep stack location and chained exception types, without source lines,
    # locals or messages (psql stderr can contain SQL or connection secrets).
    frames: list[dict[str, Any]] = []
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen:
        seen.add(id(exc))
        for frame in traceback.extract_tb(exc.__traceback__):
            frames.append({"file": frame.filename, "line": frame.lineno, "function": frame.name, "exception_type": type(exc).__name__})
        exc = exc.__cause__ or (None if exc.__suppress_context__ else exc.__context__)
    return frames[-80:]


def emit_diagnostic(record: dict[str, Any]) -> None:
    # Observability must never change a successful response or hide an exception.
    try:
        logger.info("request diagnostic", extra={"diagnostic": record})
    except Exception:
        pass
    path = os.environ.get("CPO_TRACE_LOG")
    if path:
        try:
            encoded = (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            # One append per record makes the multi-worker sink safe. Rotation is
            # external; reopen on each append so rename/create rotation works.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.write(fd, encoded)
            finally:
                os.close(fd)
        except (OSError, ValueError, TypeError):
            pass


def read_request_traces(limit: int = 100, request_id: Optional[str] = None,
                        username: Optional[str] = None, operator_group: Optional[str] = None,
                        endpoint: Optional[str] = None, status_code: Optional[int] = None) -> list[dict[str, Any]]:
    """Bounded tail of the local shared JSONL sink; newest first, no DB calls."""
    path = os.environ.get("CPO_TRACE_LOG")
    if not path:
        return []
    limit = max(1, min(int(limit), 500))
    filters = {"request_id": request_id, "username": username, "operator_group": operator_group,
               "endpoint": endpoint, "status_code": status_code}
    matches: deque[dict[str, Any]] = deque(maxlen=limit)
    try:
        # Do not scan an unbounded production log on the diagnostics endpoint.
        with open(path, "rb") as source:
            source.seek(0, os.SEEK_END)
            offset = max(0, source.tell() - 4 * 1024 * 1024)
            source.seek(offset)
            if offset:
                source.readline()
            for line in source:
                try:
                    record = json.loads(line)
                    if record.get("event") != "request_complete":
                        continue
                    if all(value is None or record.get(key) == value for key, value in filters.items()):
                        matches.append(record)
                except (ValueError, AttributeError):
                    continue
    except OSError:
        return []
    return list(reversed(matches))


def _request_id(scope: dict[str, Any]) -> str:
    try:
        peer = ipaddress.ip_address(scope.get("client", ("", 0))[0])
        networks = os.environ.get("CPO_TRUSTED_PROXY_CIDRS", "127.0.0.0/8,::1/128").split(",")
        trusted = any(peer in ipaddress.ip_network(value.strip(), strict=False) for value in networks if value.strip())
    except (ValueError, TypeError, IndexError):
        trusted = False
    supplied = [value.decode("ascii", errors="replace") for name, value in scope.get("headers", []) if name.lower() == b"x-request-id"]
    if trusted and len(supplied) == 1 and _REQUEST_ID.fullmatch(supplied[0]):
        return supplied[0]
    return uuid.uuid4().hex


class RequestDiagnosticsMiddleware:
    """Pure ASGI: retain one mutable context across AnyIO threadpool boundaries."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        start = time.perf_counter()
        context: dict[str, Any] = {
            "schema_version": 1, "event": "request_complete", "request_id": _request_id(scope),
            "timestamp": datetime.now(timezone.utc).isoformat(), "endpoint": "<unmatched>",
            "method": scope.get("method"), "status_code": 500, "pid": os.getpid(),
            "exception_type": None, "stack": [], **release_metadata(),
            **{field: None for field in CONTEXT_FIELDS}, **{field: 0 for field in COUNTERS + TIMINGS},
        }
        query = parse_qs(scope.get("query_string", b"").decode("utf-8", errors="replace"))
        anchor = query.get("date", [None])[0]
        try:
            context["date"] = date.fromisoformat(anchor).isoformat() if anchor else None
        except (ValueError, TypeError):
            pass
        period = query.get("period", ["daily"])[0]
        context["period"] = period if period in ("daily", "weekly", "monthly") else None
        token = request_context.set(context)
        response_started = False

        async def send_with_request_id(message):
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                context["status_code"] = message["status"]
                headers = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"x-request-id"]
                message = {**message, "headers": headers + [(b"x-request-id", context["request_id"].encode("ascii"))]}
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        except BaseException as exc:
            capture_exception(exc)
            if isinstance(exc, Exception) and not response_started:
                await JSONResponse({"detail": "Internal server error"}, status_code=500)(scope, receive, send_with_request_id)
            raise
        finally:
            route = scope.get("route")
            context["endpoint"] = getattr(route, "path", "<unmatched>")
            context["total_ms"] = round((time.perf_counter() - start) * 1000, 3)
            total = context["total_ms"]
            context["performance_class"] = "very_slow" if total >= 2000 else "slow" if total >= 200 else "normal"
            context["build"] = context["build_ms"] > 0
            context["performance_reason"] = ("contention" if context["lock_timeout"] or context["lock_wait_ms"] >= 1000
                else "cold_rebuild" if context["build_ms"] > 0 else "database" if context["db_wall_ms"] >= 1000 else "cached" if context["l1_hit"] or context["l2_hit"] else "normal")
            for field in TIMINGS:
                context[field] = round(context[field], 3)
            try:
                emit_diagnostic(context)
            finally:
                request_context.reset(token)
