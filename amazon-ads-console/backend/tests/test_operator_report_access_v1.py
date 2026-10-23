"""Permissions: team summary for management only, detail only own group or management."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import patch

from app.api.routes import router
from app.api.auth import require_session


def app_as(role, code=None):
    app=FastAPI()
    app.include_router(router,prefix='/api')
    app.dependency_overrides[require_session]=lambda: ('fixture', {'roleCode':role,'operatorCode':code})
    return TestClient(app)


def test_operator_cannot_read_team_summary():
    with patch('app.api.routes.cache.get_or_set',return_value={'operators':[{'name':'子娟'},{'name':'雪敏'}]}) as cached:
        r=app_as('operator','ZJ1').get('/api/operator-cpo?date=2026-10-17')
    assert r.status_code==403
    cached.assert_not_called()


def test_operator_can_read_own_detail_and_alias():
    with patch('app.api.routes.cache.get_or_set',return_value={'operator':'子娟','products':[]}):
        for path in ('子娟','ZJ1'):
            r=app_as('operator','ZJ1').get('/api/operators/'+path+'?date=2026-10-17')
            assert r.status_code==200


def test_operator_cannot_read_other_detail_before_cache_or_service():
    with patch('app.api.routes.cache.get_or_set') as cache,patch('app.api.routes.operator_cpo_detail') as live:
        r=app_as('operator','ZJ1').get('/api/operators/雪敏?date=2026-10-17')
        assert r.status_code==403
        cache.assert_not_called()
        live.assert_not_called()


def test_operator_without_mapping_denied_details():
    r=app_as('operator','??1').get('/api/operators/雪敏?date=2026-10-17')
    assert r.status_code==403


def test_manager_can_read_every_detail():
    with patch('app.api.routes.cache.get_or_set',return_value={'operator':'雪敏','products':[]}):
        for role in ('management','super_admin'):
            r=app_as(role).get('/api/operators/雪敏?date=2026-10-17')
            assert r.status_code==200


def test_arbitrary_role_cannot_read_details():
    r=app_as('viewer').get('/api/operators/雪敏?date=2026-10-17')
    assert r.status_code==403
