from __future__ import annotations

import os
import pickle
import threading
import time
from weakref import WeakValueDictionary
from datetime import date
from typing import Any, Callable, Optional

from app.core.observability import increment, update_context


class BuildBusyError(RuntimeError):
    """Another worker owns the build or its renewable lease was lost."""

try:
    import redis
except ImportError:  # pragma: no cover - release dependency normally provides this.
    redis = None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


class RedisBuildCache:
    """Shared cache for expensive CPO period builds.

    PostgreSQL remains the source of truth. Redis only stores derived _build()
    snapshots and every Redis failure falls back to the loader.
    """

    def __init__(
        self,
        *,
        client: Any = None,
        enabled: Optional[bool] = None,
        redis_url: Optional[str] = None,
        recent_ttl: Optional[int] = None,
        historical_ttl: Optional[int] = None,
        recent_days: Optional[int] = None,
    ) -> None:
        self.enabled = _env_bool("CPO_REDIS_ENABLED", True) if enabled is None else enabled
        self.redis_url = redis_url or os.getenv("CPO_REDIS_URL", "redis://127.0.0.1:6379/0")
        self.recent_ttl = recent_ttl or int(os.getenv("CPO_REDIS_RECENT_TTL", "300"))
        self.historical_ttl = historical_ttl or int(os.getenv("CPO_REDIS_HISTORICAL_TTL", "21600"))
        self.recent_days = recent_days or int(os.getenv("CPO_REDIS_RECENT_DAYS", "14"))
        self._client = client
        self._client_lock = threading.Lock()
        self._stats_lock = threading.Lock()
        self._hits = 0
        self._misses = 0
        self._errors = 0
        self._writes = 0
        self.lock_wait_seconds = max(0.01, float(os.getenv("CPO_REDIS_LOCK_WAIT_SECONDS", "8")))
        self.lock_lease_seconds = max(0.3, float(os.getenv("CPO_REDIS_LOCK_LEASE_SECONDS", "30")))
        self._fallback_locks: Any = WeakValueDictionary()
        self._fallback_values: dict[str, tuple[float, Any]] = {}

    def _record(self, field: str) -> None:
        increment({"hit": "l2_hit", "miss": "l2_miss", "error": "l2_error"}.get(field, ""))
        with self._stats_lock:
            if field == "hit":
                self._hits += 1
            elif field == "miss":
                self._misses += 1
            elif field == "error":
                self._errors += 1
            elif field == "write":
                self._writes += 1

    def _get_client(self):
        if not self.enabled:
            return None
        if self._client is not None:
            return self._client
        if redis is None:
            return None
        with self._client_lock:
            if self._client is None:
                self._client = redis.Redis.from_url(
                    self.redis_url,
                    decode_responses=False,
                    socket_connect_timeout=0.2,
                    socket_timeout=0.5,
                    health_check_interval=30,
                )
        return self._client

    @staticmethod
    def key(start: str, end: str, revision: str) -> str:
        return f"cpo:build:v1:{revision}:{start}:{end}"

    def _ttl(self, end: str) -> int:
        try:
            age = (date.today() - date.fromisoformat(end)).days
        except ValueError:
            age = 0
        return self.recent_ttl if age <= self.recent_days else self.historical_ttl

    def _fallback(self, key: str, ttl: int, loader: Callable[[], Any]) -> Any:
        # A Redis outage must not produce a stampede within each worker either.
        with self._client_lock:
            lock = self._fallback_locks.setdefault(key, threading.Lock())
        started = time.perf_counter()
        acquired = lock.acquire(timeout=self.lock_wait_seconds)
        increment("lock_wait_ms", (time.perf_counter() - started) * 1000)
        if not acquired:
            increment("lock_timeout")
            raise BuildBusyError("Local CPO build is busy")
        increment("lock_acquired")
        try:
            entry = self._fallback_values.get(key)
            if entry and entry[0] > time.monotonic():
                return entry[1]
            value = loader()
            self._fallback_values[key] = (time.monotonic() + ttl, value)
            # Bound the emergency cache across historical-date requests.
            if len(self._fallback_values) > 256:
                self._fallback_values.pop(next(iter(self._fallback_values)))
            return value
        finally:
            lock.release()

    def _get_or_set_key(self, key: str, ttl: int, loader: Callable[[], Any]) -> Any:
        client = self._get_client()
        if client is None:
            return loader() if not self.enabled else self._fallback(key, ttl, loader)
        try:
            raw = client.get(key)
            if raw is not None:
                self._record("hit")
                return pickle.loads(raw)
        except Exception:
            self._record("error")
            return self._fallback(key, ttl, loader)
        self._record("miss")
        started = time.perf_counter()
        try:
            lock = client.lock(f"{key}:lock", timeout=self.lock_lease_seconds,
                               blocking_timeout=self.lock_wait_seconds, thread_local=False)
            acquired = lock.acquire(blocking=True)
        except Exception:
            self._record("error")
            return self._fallback(key, ttl, loader)
        finally:
            increment("lock_wait_ms", (time.perf_counter() - started) * 1000)
        if not acquired:
            try:
                raw = client.get(key)
                if raw is not None:
                    self._record("hit")
                    return pickle.loads(raw)
            except Exception:
                self._record("error")
            increment("lock_timeout")
            raise BuildBusyError("CPO build lock wait timed out")
        increment("lock_acquired")
        stop = threading.Event()
        lease_lost = threading.Event()

        def renew():
            while not stop.wait(self.lock_lease_seconds / 3):
                try:
                    if not lock.extend(self.lock_lease_seconds, replace_ttl=True):
                        lease_lost.set()
                        return
                except Exception:
                    lease_lost.set()
                    return

        renewer = threading.Thread(target=renew, daemon=True, name="cpo-build-lease")
        renewer.start()
        try:
            try:
                raw = client.get(key)
                if raw is not None:
                    self._record("hit")
                    return pickle.loads(raw)
            except Exception:
                self._record("error")
            # Loader exceptions deliberately bypass Redis I/O error handlers:
            # never retry an expensive or mutating loader after it has started.
            value = loader()
            if lease_lost.is_set():
                self._record("error")
                increment("lock_timeout")
                raise BuildBusyError("CPO build lease was lost")
            try:
                client.setex(key, ttl, pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
                self._record("write")
            except Exception:
                self._record("error")
            return value
        finally:
            stop.set()
            renewer.join(timeout=1)
            try:
                lock.release()
            except Exception:
                self._record("error")

    def get_or_set(self, start: str, end: str, revision: str, loader: Callable[[], Any]) -> Any:
        update_context(revision=revision, period_start=start, period_end=end)
        return self._get_or_set_key(self.key(start, end, revision), self._ttl(end), loader)

    def get_or_set_complete_days(
        self,
        start: Optional[str],
        end: Optional[str],
        revision: str,
        loader: Callable[[], Any],
    ) -> Any:
        start_key = start or "all"
        end_key = end or "all"
        update_context(revision=revision)
        key = f"cpo:complete-days:v1:{revision}:{start_key}:{end_key}"
        return self._get_or_set_key(key, self.historical_ttl, loader)

    def clear(self) -> int:
        with self._client_lock:
            self._fallback_values.clear()
        client = self._get_client()
        if client is None:
            return 0
        try:
            keys = list(client.scan_iter(match="cpo:build:v1:*"))
            keys.extend(client.scan_iter(match="cpo:complete-days:v1:*"))
            unique_keys = [key for key in dict.fromkeys(keys) if not (key.decode() if isinstance(key, bytes) else key).endswith(":lock")]
            return int(client.delete(*unique_keys)) if unique_keys else 0
        except Exception:
            self._record("error")
            return 0

    def health(self) -> dict[str, Any]:
        """Probe Redis without mutating business cache counters or exposing its URL."""
        started = time.perf_counter()
        with self._stats_lock:
            errors = self._errors
        if not self.enabled:
            return {
                "enabled": False,
                "available": False,
                "status": "disabled",
                "errors": errors,
                "check_ms": round((time.perf_counter() - started) * 1000, 3),
            }
        client = self._get_client()
        available = False
        if client is not None:
            try:
                available = bool(client.ping())
            except Exception:
                available = False
        status = "unavailable" if not available else "degraded" if errors > 0 else "healthy"
        return {
            "enabled": True,
            "available": available,
            "status": status,
            "errors": errors,
            "check_ms": round((time.perf_counter() - started) * 1000, 3),
        }

    def stats(self) -> dict[str, Any]:
        with self._stats_lock:
            return {
                "backend": "redis",
                "enabled": self.enabled,
                "url": self.redis_url.rsplit("@", 1)[-1],
                "hits": self._hits,
                "misses": self._misses,
                "writes": self._writes,
                "errors": self._errors,
                "recent_ttl": self.recent_ttl,
                "historical_ttl": self.historical_ttl,
            }


build_cache = RedisBuildCache()
