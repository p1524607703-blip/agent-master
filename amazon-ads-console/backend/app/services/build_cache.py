from __future__ import annotations

import os
import pickle
import threading
from datetime import date
from typing import Any, Callable, Optional

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

    def _record(self, field: str) -> None:
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

    def _get_or_set_key(self, key: str, ttl: int, loader: Callable[[], Any]) -> Any:
        client = self._get_client()
        if client is None:
            return loader()
        try:
            raw = client.get(key)
            if raw is not None:
                self._record("hit")
                return pickle.loads(raw)
            self._record("miss")

            lock = client.lock(f"{key}:lock", timeout=30, blocking_timeout=8)
            acquired = lock.acquire(blocking=True)
            if not acquired:
                return loader()
            try:
                raw = client.get(key)
                if raw is not None:
                    self._record("hit")
                    return pickle.loads(raw)
                value = loader()
                client.setex(key, ttl, pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL))
                self._record("write")
                return value
            finally:
                try:
                    lock.release()
                except Exception:
                    pass
        except Exception:
            self._record("error")
            return loader()

    def get_or_set(self, start: str, end: str, revision: str, loader: Callable[[], Any]) -> Any:
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
        key = f"cpo:complete-days:v1:{revision}:{start_key}:{end_key}"
        return self._get_or_set_key(key, self.historical_ttl, loader)

    def clear(self) -> int:
        client = self._get_client()
        if client is None:
            return 0
        try:
            keys = list(client.scan_iter(match="cpo:build:v1:*"))
            keys.extend(client.scan_iter(match="cpo:complete-days:v1:*"))
            unique_keys = list(dict.fromkeys(keys))
            return int(client.delete(*unique_keys)) if unique_keys else 0
        except Exception:
            self._record("error")
            return 0

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
