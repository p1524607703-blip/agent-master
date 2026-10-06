from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class _Entry:
    value: Any
    expires_at: float
    stale_until: float


class MemoryTTLCache:
    """In-process read-model cache.

    PostgreSQL remains the source of truth. Expired values may be served briefly
    when RDS is temporarily unavailable (stale-if-error), avoiding blank pages.
    """

    def __init__(self) -> None:
        self._data: dict[str, _Entry] = {}
        self._lock = threading.RLock()
        self._hits = 0
        self._misses = 0
        self._stale_hits = 0

    def _entry(self, key: str) -> _Entry | None:
        with self._lock:
            return self._data.get(key)

    def get(self, key: str) -> Any | None:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.expires_at <= now:
                self._misses += 1
                return None
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int, stale_ttl: int = 3600) -> Any:
        now = time.monotonic()
        with self._lock:
            self._data[key] = _Entry(
                value=value,
                expires_at=now + max(1, ttl),
                stale_until=now + max(ttl, stale_ttl),
            )
        return value

    def get_or_set(self, key: str, loader: Callable[[], Any], ttl: int, stale_ttl: int = 3600) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        stale = self._entry(key)
        try:
            value = loader()
            return self.set(key, value, ttl, stale_ttl)
        except Exception:
            now = time.monotonic()
            if stale is not None and stale.stale_until > now:
                with self._lock:
                    self._stale_hits += 1
                return stale.value
            raise

    def invalidate_prefix(self, *prefixes: str) -> int:
        with self._lock:
            keys = [k for k in self._data if any(k.startswith(p) for p in prefixes)]
            for key in keys:
                self._data.pop(key, None)
            return len(keys)

    def clear(self) -> int:
        with self._lock:
            n = len(self._data)
            self._data.clear()
            return n

    def stats(self) -> dict[str, int | str]:
        with self._lock:
            return {
                'backend': 'memory',
                'entries': len(self._data),
                'hits': self._hits,
                'misses': self._misses,
                'stale_hits': self._stale_hits,
            }


cache = MemoryTTLCache()


def invalidate_data_read_models() -> int:
    cleared = cache.invalidate_prefix(
        'dashboard:',
        'trend:',
        'operator:',
        'my-cpo:',
        'products:',
        'reports:',
    )
    try:
        from .build_cache import build_cache
        cleared += build_cache.clear()
    except Exception:
        pass
    return cleared
