"""Date validation must protect every report/read/download before cache or SQL work."""
from contextlib import ExitStack
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api import routes, operator_exports
from app.api.auth import require_session, require_own_operator_session


ENDPOINTS = [
    '/api/operator-cpo', '/api/operators/ZJ1', '/api/my-cpo',
    '/api/operator-reports/summary.xlsx',
    '/api/operator-reports/operators/ZJ1.xlsx', '/api/operator-reports/all.zip',
]


@pytest.fixture
def reports():
    app = FastAPI()
    app.include_router(routes.router, prefix='/api')
    app.include_router(operator_exports.router, prefix='/api')
    app.dependency_overrides[require_session] = lambda: ('fixture', {'roleCode': 'management'})
    app.dependency_overrides[require_own_operator_session] = lambda: (
        'fixture', {'roleCode': 'operator', 'operatorCode': 'ZJ1'})
    snapshot = {'data_date': '2026-10-19', 'operators': [], 'products': [], 'summary': {}}
    with ExitStack() as stack:
        cache = stack.enter_context(patch.object(routes.cache, 'get_or_set', return_value=snapshot))
        summary = stack.enter_context(patch.object(operator_exports, '_load_summary', return_value=snapshot))
        detail = stack.enter_context(patch.object(operator_exports, '_load_detail', return_value=snapshot))
        stack.enter_context(patch.object(operator_exports, 'summary_xlsx', return_value=b'xlsx'))
        stack.enter_context(patch.object(operator_exports, 'detail_xlsx', return_value=b'xlsx'))
        yield TestClient(app), (cache, summary, detail)


@pytest.mark.parametrize('path', ENDPOINTS)
@pytest.mark.parametrize('period', ['daily', 'weekly', 'monthly'])
@pytest.mark.parametrize('bad_date', [
    '', '2026-09', '2026-02-29', '2024-02-30', '2026-04-31', '2026-13-01',
    '2026-00-01', '0000-01-01', '20260901', '2026-W39-1',
    '2026-9-01', '2026-09-01T00:00:00', ' 2026-09-01',
])
def test_invalid_date_rejected_before_report_reads(reports, path, period, bad_date):
    client, readers = reports
    response = client.get(path, params={'date': bad_date, 'period': period})
    assert response.status_code == 422
    assert 'YYYY-MM-DD' in response.json()['detail']
    for reader in readers:
        reader.assert_not_called()


@pytest.mark.parametrize('path', ENDPOINTS)
@pytest.mark.parametrize('period', ['daily', 'weekly', 'monthly'])
@pytest.mark.parametrize('day', [None, '2026-09-01', '2026-09-30', '2024-02-29'])
def test_full_calendar_dates_and_omitted_latest_still_work(reports, path, period, day):
    client, readers = reports
    params = {'period': period}
    if day is not None:
        params['date'] = day
    response = client.get(path, params=params)
    assert response.status_code == 200
    assert sum(reader.call_count for reader in readers) == 1
    if 'operator-reports' in path:
        reader = readers[2] if '/operators/' in path else readers[1]
        assert reader.call_args.args[1 if '/operators/' in path else 0] == day
    else:
        key = readers[0].call_args.args[0]
        assert key.endswith(':' + (day or 'latest'))


@pytest.mark.parametrize('path', ENDPOINTS)
@pytest.mark.parametrize('period,day', [('monthly', '9999-12-01'), ('weekly', '9999-12-27')])
def test_calendar_window_overflow_rejected_before_report_reads(reports, path, period, day):
    client, readers = reports
    response = client.get(path, params={'date': day, 'period': period})
    assert response.status_code == 422
    for reader in readers:
        reader.assert_not_called()
