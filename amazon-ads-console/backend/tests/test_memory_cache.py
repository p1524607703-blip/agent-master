from unittest.mock import Mock, patch

import pytest

from app.services.cache import MemoryTTLCache


def test_capacity_evicts_least_recently_used_report():
    cache = MemoryTTLCache(max_entries=2)
    cache.set('first', {'group': 'AJ'}, 60)
    cache.set('second', {'group': 'XM'}, 60)
    assert cache.get('first') == {'group': 'AJ'}
    cache.set('third', {'group': 'ZJ'}, 60)
    assert cache.get('second') is None
    assert cache.get('first') == {'group': 'AJ'}
    assert cache.get('third') == {'group': 'ZJ'}
    assert cache.stats()['entries'] == 2


def test_expiration_retains_only_bounded_stale_if_error_window():
    cache = MemoryTTLCache(max_entries=2)
    with patch('app.services.cache.time.monotonic', return_value=100):
        cache.set('report', {'spend': 20}, 1, stale_ttl=5)
    failing = Mock(side_effect=RuntimeError('database unavailable'))
    with patch('app.services.cache.time.monotonic', return_value=102):
        assert cache.get_or_set('report', failing, 1) == {'spend': 20}
    with patch('app.services.cache.time.monotonic', return_value=106):
        with pytest.raises(RuntimeError):
            cache.get_or_set('report', failing, 1)
        assert cache.stats()['entries'] == 0


def test_insert_reclaims_entries_past_stale_deadline():
    cache = MemoryTTLCache(max_entries=3)
    with patch('app.services.cache.time.monotonic', return_value=100):
        cache.set('old', 1, 1, stale_ttl=2)
    with patch('app.services.cache.time.monotonic', return_value=103):
        cache.set('new', 2, 60)
        assert cache.stats()['entries'] == 1
        assert cache.get('new') == 2
