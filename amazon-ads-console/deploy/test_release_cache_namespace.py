import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

# Tests run with backend on sys.path, as with the other deploy tests.
from app.services.build_cache import RedisBuildCache

class NamespaceTests(unittest.TestCase):
 def test_two_live_releases_never_share_build_or_coverage_keys(self):
  client = type('Redis', (), {'get': lambda s,k: None})()
  cache = RedisBuildCache(client=client)
  keys=[]
  for commit in ('a'*40,'b'*40):
   with patch.dict(os.environ, {'CPO_CACHE_NAMESPACE':commit}):
    keys.append(cache.key('2026-01-01','2026-01-31','same-revision'))
    with patch.object(cache,'_get_or_set_key',side_effect=lambda key,*args:key):
     keys.extend([cache.get_or_set_complete_days(None,None,'same',lambda:[]), cache.get_or_set_report_catalog('same',lambda:{})])
  self.assertEqual(len(set(keys)),6)
 def test_invalid_namespace_rejected(self):
  with patch.dict(os.environ, {'CPO_CACHE_NAMESPACE':'bad:*'}):
   with self.assertRaises(ValueError):RedisBuildCache.key('a','b','c')
