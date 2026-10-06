import unittest

from app.services.build_cache import RedisBuildCache


class _FakeLock:
    def acquire(self, blocking=True):
        return True

    def release(self):
        return None


class _FakeRedis:
    def __init__(self):
        self.data = {}
        self.ttls = {}

    def get(self, key):
        return self.data.get(key)

    def setex(self, key, ttl, value):
        self.data[key] = value
        self.ttls[key] = ttl
        return True

    def lock(self, key, timeout=None, blocking_timeout=None):
        return _FakeLock()

    def scan_iter(self, match=None):
        prefix = (match or "").rstrip("*")
        return [k for k in self.data if k.startswith(prefix)]

    def delete(self, *keys):
        removed = 0
        for key in keys:
            if key in self.data:
                removed += 1
                del self.data[key]
        return removed


class RedisBuildCacheTests(unittest.TestCase):
    def test_same_period_reuses_one_build(self):
        fake = _FakeRedis()
        cache = RedisBuildCache(client=fake, enabled=True, recent_ttl=300, historical_ttl=3600)
        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            return {"products": [{"code": "W81"}], "portfolio": {"雪敏": {"W81"}}}

        first = cache.get_or_set("2026-10-04", "2026-10-04", "581", loader)
        second = cache.get_or_set("2026-10-04", "2026-10-04", "581", loader)

        self.assertEqual(first, second)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(cache.stats()["hits"], 1)

    def test_complete_days_reuses_one_query(self):
        fake = _FakeRedis()
        cache = RedisBuildCache(client=fake, enabled=True, recent_ttl=300, historical_ttl=3600)
        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            return ["2026-10-03", "2026-10-04"]

        first = cache.get_or_set_complete_days(None, None, "581", loader)
        second = cache.get_or_set_complete_days(None, None, "581", loader)

        self.assertEqual(first, second)
        self.assertEqual(calls["n"], 1)
        self.assertIn("cpo:complete-days:v1:581:all:all", fake.data)

    def test_disabled_cache_falls_back_to_loader(self):
        cache = RedisBuildCache(enabled=False)
        calls = {"n": 0}

        def loader():
            calls["n"] += 1
            return {"n": calls["n"]}

        self.assertEqual(cache.get_or_set("2026-10-04", "2026-10-04", "581", loader), {"n": 1})
        self.assertEqual(cache.get_or_set("2026-10-04", "2026-10-04", "581", loader), {"n": 2})

    def test_clear_removes_build_keys(self):
        fake = _FakeRedis()
        cache = RedisBuildCache(client=fake, enabled=True)
        cache.get_or_set("2026-10-04", "2026-10-04", "581", lambda: {"ok": True})
        cache.get_or_set_complete_days(None, None, "581", lambda: ["2026-10-04"])
        self.assertEqual(cache.clear(), 2)
        self.assertEqual(fake.data, {})


if __name__ == "__main__":
    unittest.main()
