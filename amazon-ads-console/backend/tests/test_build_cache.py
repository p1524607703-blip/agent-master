import unittest
import threading
import time
import pickle
from unittest.mock import Mock

from app.services.build_cache import RedisBuildCache, BuildBusyError


class _FakeLock:
    def acquire(self, blocking=True):
        return True

    def release(self):
        return None

    def extend(self, timeout, replace_ttl=False):
        return True


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

    def lock(self, key, timeout=None, blocking_timeout=None, thread_local=True):
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

    def test_lock_timeout_never_starts_loader(self):
        fake = _FakeRedis()
        fake.lock = Mock(return_value=Mock(acquire=Mock(return_value=False)))
        loader = Mock()
        with self.assertRaises(BuildBusyError):
            RedisBuildCache(client=fake).get_or_set('2026-10-04', '2026-10-04', '581', loader)
        loader.assert_not_called()

    def test_timeout_reads_snapshot_completed_by_other_worker(self):
        fake = _FakeRedis()
        key = RedisBuildCache.key('2026-10-04', '2026-10-04', '581')
        def acquire(**kwargs):
            fake.data[key] = pickle.dumps({'done': True})
            return False
        fake.lock = Mock(return_value=Mock(acquire=acquire))
        loader = Mock()
        self.assertEqual(RedisBuildCache(client=fake).get_or_set('2026-10-04', '2026-10-04', '581', loader), {'done': True})
        loader.assert_not_called()

    def test_loader_error_is_not_retried_and_lock_is_released(self):
        fake = _FakeRedis()
        lock = Mock(acquire=Mock(return_value=True))
        fake.lock = Mock(return_value=lock)
        loader = Mock(side_effect=RuntimeError('loader failure'))
        with self.assertRaisesRegex(RuntimeError, 'loader failure'):
            RedisBuildCache(client=fake).get_or_set('2026-10-04', '2026-10-04', '581', loader)
        self.assertEqual(loader.call_count, 1)
        lock.release.assert_called_once()

    def test_write_failure_does_not_repeat_loader(self):
        fake = _FakeRedis()
        fake.setex = Mock(side_effect=ConnectionError('redis down'))
        loader = Mock(return_value={'ok': True})
        self.assertEqual(RedisBuildCache(client=fake).get_or_set('2026-10-04', '2026-10-04', '581', loader), {'ok': True})
        loader.assert_called_once()

    def test_clear_preserves_active_build_lock(self):
        fake = _FakeRedis()
        fake.data['cpo:build:v1:581:2026-10-04:2026-10-04:lock'] = b'owner'
        fake.data['cpo:build:v1:581:2026-10-04:2026-10-04'] = b'value'
        self.assertEqual(RedisBuildCache(client=fake).clear(), 1)
        self.assertEqual(list(fake.data.values()), [b'owner'])

    def test_long_build_renews_lease(self):
        fake = _FakeRedis()
        lock = Mock(acquire=Mock(return_value=True), extend=Mock(return_value=True))
        fake.lock = Mock(return_value=lock)
        cache = RedisBuildCache(client=fake)
        cache.lock_lease_seconds = 0.3
        def loader():
            time.sleep(0.36)
            return 'done'
        self.assertEqual(cache.get_or_set('2026-10-04', '2026-10-04', '581', loader), 'done')
        self.assertGreaterEqual(lock.extend.call_count, 2)
        self.assertFalse(fake.lock.call_args.kwargs['thread_local'])

    def test_lost_lease_returns_busy_without_retry(self):
        fake = _FakeRedis()
        fake.lock = Mock(return_value=Mock(acquire=Mock(return_value=True), extend=Mock(return_value=False)))
        cache = RedisBuildCache(client=fake)
        cache.lock_lease_seconds = 0.3
        loader = Mock(side_effect=lambda: time.sleep(0.15))
        with self.assertRaises(BuildBusyError):
            cache.get_or_set('2026-10-04', '2026-10-04', '581', loader)
        loader.assert_called_once()
        self.assertFalse(fake.data)

    def test_concurrent_redis_outage_has_one_loader(self):
        fake = _FakeRedis()
        fake.get = Mock(side_effect=ConnectionError())
        cache = RedisBuildCache(client=fake)
        loader = Mock(side_effect=lambda: (time.sleep(0.06), {'ok': True})[1])
        results = []
        workers = [threading.Thread(target=lambda: results.append(cache.get_or_set('2026-10-04', '2026-10-04', '581', loader))) for _ in range(4)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(results, [{'ok': True}] * 4)
        loader.assert_called_once()

    def test_concurrent_workers_share_one_redis_build(self):
        fake = _FakeRedis()
        shared_lock = threading.Lock()
        class LockHandle:
            def acquire(self, blocking=True):
                return shared_lock.acquire(timeout=1)
            def release(self):
                shared_lock.release()
            def extend(self, timeout, replace_ttl=False):
                return True
        fake.lock = Mock(side_effect=lambda *args, **kwargs: LockHandle())
        workers_cache = [RedisBuildCache(client=fake) for _ in range(4)]
        loader = Mock(side_effect=lambda: (time.sleep(0.06), {'ok': True})[1])
        results = []
        workers = [threading.Thread(target=lambda cache=cache: results.append(cache.get_or_set('2026-10-04', '2026-10-04', '581', loader))) for cache in workers_cache]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(results, [{'ok': True}] * 4)
        loader.assert_called_once()


if __name__ == "__main__":
    unittest.main()
