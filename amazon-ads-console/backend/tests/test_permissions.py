import unittest
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient
from app.core.config import settings
from app.main import app
from app.api import auth, routes
from app.services import operator_cpo
from app.services.build_cache import BuildBusyError
from app.services.cache import cache


USERS = {
    'manager': {'userId': '1', 'username': 'manager', 'roleCode': 'management', 'operatorCode': None},
    'admin': {'userId': '2', 'username': 'admin', 'roleCode': 'super_admin', 'operatorCode': None},
    'xm': {'userId': '3', 'username': 'xm', 'roleCode': 'operator', 'operatorCode': 'XM1', 'displayName': '雪敏'},
    'aj': {'userId': '4', 'username': 'aj', 'roleCode': 'operator', 'operatorCode': 'AJ1', 'displayName': '爱菊'},
    'unbound': {'userId': '5', 'username': 'unbound', 'roleCode': 'operator', 'operatorCode': None},
    'unknown': {'userId': '6', 'username': 'unknown', 'roleCode': 'viewer', 'operatorCode': 'XM1'},
}


class PermissionTests(unittest.TestCase):
    def setUp(self):
        self.warmup = patch.object(settings, 'operator_warmup_enabled', False)
        self.warmup.start()
        self.resolver = patch.object(auth, 'resolve_session', AsyncMock(side_effect=lambda token: USERS.get(token)))
        self.resolver.start()
        self.query_block = patch('app.services.rds_query.subprocess.run', side_effect=AssertionError('No live DB calls in permission tests'))
        self.query_block.start()
        self.logger = patch('app.core.observability.logger.info')
        self.logger.start()
        self.client = TestClient(app)
        self.client.__enter__()
        cache.clear()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.query_block.stop()
        self.logger.stop()
        self.resolver.stop()
        self.warmup.stop()
        cache.clear()

    def get(self, path, user=None):
        return self.client.get(path, headers={'Authorization': 'Bearer ' + user} if user else {})

    def test_anonymous_ping_exposes_only_boolean(self):
        response = self.get('/api/ping')
        self.assertEqual(response.json(), {'ok': True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.headers.get('X-Request-ID'))

    def test_anonymous_data_and_diagnostics_need_session(self):
        for path in ('/api/operator-cpo', '/api/my-cpo', '/api/operators/XM', '/api/operator-periods', '/api/cache/stats', '/api/diagnostics/status', '/api/diagnostics/requests'):
            with self.subTest(path=path):
                self.assertEqual(self.get(path).status_code, 401)

    def test_operator_cannot_access_management_even_after_cache_is_warm(self):
        with patch.object(routes, 'operator_cpo_summary', return_value={'operators': [{'group': 'XM1'}, {'group': 'AJ1'}]}):
            self.assertEqual(self.get('/api/operator-cpo?date=2026-10-04', 'manager').status_code, 200)
        for user in ('xm', 'aj', 'unknown'):
            for path in ('/api/operator-cpo?date=2026-10-04', '/api/dashboard/overview', '/api/product-mappings', '/api/cache/stats', '/api/health', '/api/reports', '/api/diagnostics/status', '/api/diagnostics/requests'):
                with self.subTest(user=user, path=path):
                    self.assertEqual(self.get(path, user).status_code, 403)

    def test_management_and_admin_access_all_groups(self):
        with patch.object(routes, 'operator_cpo_detail', return_value={'products': []}) as detail:
            for user in ('manager', 'admin'):
                for target in ('XM', 'AJ1', '雪敏', '爱菊'):
                    self.assertEqual(self.get('/api/operators/' + target + '?date=2026-10-04', user).status_code, 200)
            self.assertTrue(detail.called)

    def test_changed_url_cannot_cross_operator_boundary(self):
        with patch.object(routes, 'operator_cpo_detail', return_value={'products': [{'group': 'XM1'}], 'businessMappingConflictOrders': 12, 'businessOutOfScopeOrders': 16}) as detail:
            for target in ('XM', 'XM1', '雪敏'):
                response = self.get('/api/operators/' + target, 'xm')
                self.assertEqual(response.status_code, 200)
                self.assertNotIn('businessMappingConflictOrders', response.json())
            for user, target in (('xm', 'AJ'), ('xm', '爱菊'), ('aj', 'XM'), ('aj', '雪敏'), ('xm', 'XM-private'), ('unbound', 'XM')):
                with self.subTest(user=user, target=target):
                    self.assertEqual(self.get('/api/operators/' + target, user).status_code, 403)
            self.assertEqual(detail.call_count, 3)

    def test_my_cpo_ignores_frontend_group_and_omits_global_audit(self):
        data = {'operators': [{'groups': ['XM1'], 'name': '雪敏'}, {'groups': ['AJ1'], 'name': '爱菊'}], 'data_date': '2026-10-04', 'period': 'daily', 'businessUnmappedOrders': 999, 'businessOutOfScopeParents': ['private'], 'note': 'company-wide $999'}
        def detail(name, *args):
            group = 'XM1' if name == '雪敏' else 'AJ1'
            return {'products': [{'group': group}], 'summary': {}, 'final_cpo': True}
        with patch.object(operator_cpo, 'operator_cpo_summary', return_value=data), patch.object(operator_cpo, 'operator_cpo_detail', side_effect=detail):
            for user, expected in (('xm', 'XM1'), ('aj', 'AJ1')):
                response = self.get('/api/my-cpo?date=2026-10-04&operator=AJ1&operatorCode=AJ1', user)
                self.assertEqual(response.status_code, 200)
                self.assertEqual([row['group'] for row in response.json()['products']], [expected])
                self.assertEqual(len(response.json()['operators']), 1)
                self.assertNotIn('businessUnmappedOrders', response.json())
                self.assertNotIn('company-wide', response.text)

    def test_unbound_group_fails_before_any_loader(self):
        with patch.object(operator_cpo, 'operator_cpo_summary') as loader:
            self.assertEqual(self.get('/api/my-cpo', 'unbound').status_code, 403)
            loader.assert_not_called()

    def test_unknown_role_cannot_access_my_cpo_even_with_group(self):
        self.assertEqual(self.get('/api/my-cpo', 'unknown').status_code, 403)

    def test_revoked_group_cannot_use_warm_my_cpo_cache(self):
        with patch.object(routes, 'my_cpo_summary', return_value={'products': [{'group': 'XM1'}]}):
            self.assertEqual(self.get('/api/my-cpo', 'xm').status_code, 200)
            USERS['xm']['operatorCode'] = None
            try:
                self.assertEqual(self.get('/api/my-cpo', 'xm').status_code, 403)
            finally:
                USERS['xm']['operatorCode'] = 'XM1'

    def test_busy_build_is_controlled_503(self):
        with patch.object(routes, 'operator_cpo_summary', side_effect=BuildBusyError('busy')):
            response = self.get('/api/operator-cpo?date=2026-10-04', 'manager')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Retry-After'], '2')
        self.assertEqual(response.json()['code'], 'CPO_BUILD_BUSY')


if __name__ == '__main__':
    unittest.main()
