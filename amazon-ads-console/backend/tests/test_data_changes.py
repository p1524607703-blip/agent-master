import csv
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.auth import require_session
from app.api.data_changes import build_router
from app.services.data_changes import COLUMNS, ChangeError, DataChangeService, SQLiteDataChangeRepository

OP = {'userId': 'operator-1', 'roleCode': 'operator', 'operatorCode': 'AJ1'}
MANAGER = {'userId': 'manager-1', 'roleCode': 'management', 'operatorCode': 'AJ1'}
OTHER = {'userId': 'operator-2', 'roleCode': 'operator', 'operatorCode': 'AJ2'}


def csv_text(*rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({'change_type': 'ADD', 'account_id': '00001234567890123456789', 'marketplace_id': 'ATVPDKIKX0DER',
                         'operator_code': 'AJ1', 'product_code': 'W81V5女', 'no_parent': 'true', 'child_asin': 'B012345678',
                         'effective_from': '2026-09-01', 'reason': 'new confirmed listing', **row})
    return output.getvalue()


@pytest.fixture
def service(tmp_path):
    return DataChangeService(SQLiteDataChangeRepository(str(tmp_path / 'staging.sqlite3')))


def upload(service, user=OP, key='upload-1', **row):
    return service.upload('company', user, 'mapping.csv', csv_text(row), {}, key)


def submit(service, batch, user=OP, key='submit-1'):
    return service.command('company', user, batch['id'], 'submit', {}, batch['etag'], key)


def decision(service, batch, user=MANAGER, key='review-1', decision='APPROVE'):
    return service.command('company', user, batch['id'], 'decision',
                           {'decision': decision, 'reason': 'independent review', 'content_hash': batch['content_hash']}, batch['etag'], key)


def assert_code(code, function):
    with pytest.raises(ChangeError) as caught:
        function()
    assert caught.value.code == code


def test_new_standalone_product_independent_review_and_never_effective(service):
    batch = upload(service)
    assert batch['status'] == 'READY'
    assert batch['capabilities']['can_submit']
    batch = submit(service, batch)
    assert batch['status'] == 'SUBMITTED'
    approved = decision(service, batch)
    assert approved['status'] == 'APPROVED_PENDING_APPLY'
    assert not approved['capabilities']['can_apply']
    assert_code('AUTHORITATIVE_APPLY_NOT_CONFIGURED', lambda: service.command('company', MANAGER, batch['id'], 'apply', {}, approved['etag'], 'apply'))
    assert service.get('company', OP, batch['id'])['status'] == 'APPROVED_PENDING_APPLY'


def test_management_self_approval_forbidden(service):
    batch = submit(service, upload(service, user=MANAGER), user=MANAGER)
    assert_code('INDEPENDENT_REVIEWER_REQUIRED', lambda: decision(service, batch, user=MANAGER))


def test_scope_isolation_and_spoofed_operator_never_ready(service):
    batch = upload(service)
    assert_code('BATCH_NOT_FOUND', lambda: service.get('company', OTHER, batch['id']))
    assert_code('BATCH_NOT_FOUND', lambda: service.get('other-company', MANAGER, batch['id']))
    assert service.list('company', OTHER)['items'] == []
    invalid = upload(service, key='spoof', operator_code='AJ2')
    assert invalid['status'] == 'VALIDATION_FAILED'
    assert_code('BATCH_NOT_READY', lambda: submit(service, invalid))


def test_missing_parent_rejected_without_explicit_standalone(service):
    invalid = upload(service, no_parent='')
    assert invalid['status'] == 'VALIDATION_FAILED'


def test_exact_sku_multiple_listing_links_without_duplicate_financial_subject(service):
    text = csv_text({'sku': ' MiXeD-sku '}, {'sku': 'another-sku'})
    batch = service.upload('company', OP, 'a.csv', text, {}, 'many-sku')
    rows = service.rows('company', OP, batch['id'])['items']
    assert batch['status'] == 'READY'
    assert rows[0]['new_values']['sku'] == ' MiXeD-sku '
    assert rows[0]['record_key'] == rows[1]['record_key']
    assert rows[0]['new_values']['account_id'] == '00001234567890123456789'


def test_formula_and_unresolved_sku_never_ready(service):
    assert upload(service, sku='=HYPERLINK("bad")')['status'] == 'VALIDATION_FAILED'
    assert upload(service, key='unresolved', sku='only-sku', child_asin='')['status'] == 'VALIDATION_FAILED'


def test_duplicate_child_conflicting_target_fails_atomically(service):
    batch = service.upload('company', OP, 'a.csv', csv_text({}, {'product_code': 'different'}), {}, 'conflict')
    assert batch['status'] == 'VALIDATION_FAILED'
    assert_code('BATCH_NOT_READY', lambda: submit(service, batch))


def test_missing_authoritative_adapter_prevents_modify(service):
    batch = upload(service, change_type='MODIFY', record_id='row1', expected_version='4', modified_fields='product_code')
    assert batch['status'] == 'VALIDATION_FAILED'
    assert 'AUTHORITATIVE_SOURCE_UNAVAILABLE' in service.rows('company', OP, batch['id'])['items'][0]['errors']


def test_idempotency_and_duplicate_file(service):
    batch = upload(service)
    assert upload(service)['id'] == batch['id']
    assert upload(service, key='another-key')['id'] == batch['id']
    assert_code('IDEMPOTENCY_CONFLICT', lambda: upload(service, product_code='other'))
    result = submit(service, batch)
    assert submit(service, batch) == result
    assert_code('VERSION_CONFLICT', lambda: submit(service, batch, key='second-submit'))


def test_concurrent_review_exactly_one_succeeds(service):
    batch = submit(service, upload(service))
    def approve(number):
        user = {**MANAGER, 'userId': 'manager-' + str(number)}
        try:
            return decision(service, batch, user=user, key='review-' + str(number))['status']
        except ChangeError as exc:
            return exc.code
    with ThreadPoolExecutor(2) as executor:
        results = list(executor.map(approve, [2, 3]))
    assert sorted(results) == ['APPROVED_PENDING_APPLY', 'VERSION_CONFLICT']


def test_rejection_revision_preserves_original(service):
    batch = decision(service, submit(service, upload(service)), decision='REJECT')
    revision = service.upload('company', OP, 'revision.csv', csv_text({'sku': 'new'}), {}, 'revision', parent_id=batch['id'], parent_if_match=batch['etag'])
    assert revision['parent_id'] == batch['id']
    assert service.get('company', OP, batch['id'])['status'] == 'REJECTED'


def test_api_auth_disabled_limits_and_cas(service):
    app = FastAPI()
    app.include_router(build_router(lambda: service, enabled=True), prefix='/api')
    with TestClient(app) as client:
        assert client.get('/api/data-changes').status_code == 401
        app.dependency_overrides[require_session] = lambda: ('token', OP)
        assert client.get('/api/data-changes/templates').status_code == 200
        result = client.post('/api/data-changes/uploads', json={'file_name': 'a.csv', 'csv_text': csv_text({})}, headers={'Idempotency-Key': 'upload'})
        assert result.status_code == 202
        batch = result.json()
        assert result.headers['etag'] == batch['etag']
        missing_cas = client.post('/api/data-changes/' + batch['id'] + '/submit', headers={'Idempotency-Key': 'submit'})
        assert missing_cas.status_code == 428
        assert client.get('/api/data-changes?limit=201').status_code == 422
        assert client.post('/api/data-changes/uploads', json={'file_name': 'a.csv', 'csv_text': csv_text({}), 'tenant_id': 'spoof'}).status_code == 422
    disabled = FastAPI()
    disabled.include_router(build_router(lambda: service, enabled=False), prefix='/api')
    disabled.dependency_overrides[require_session] = lambda: ('token', OP)
    assert TestClient(disabled).get('/api/data-changes').status_code == 503


def test_effective_overlap_and_same_sku_across_store(service):
    conflict = service.upload('company', OP, 'overlap.csv', csv_text({}, {'product_code': 'OTHER', 'effective_from': '2026-09-15'}), {}, 'overlap')
    assert conflict['status'] == 'VALIDATION_FAILED'
    assert 'CHILD_EFFECTIVE_INTERVAL_OVERLAP' in service.rows('company', OP, conflict['id'])['items'][1]['errors']
    legitimate = service.upload('company', OP, 'stores.csv', csv_text({'sku': 'SameSKU'}, {'sku': 'SameSKU', 'account_id': 'second-store', 'child_asin': 'B098765432'}), {}, 'stores')
    assert legitimate['status'] == 'READY'


def test_unique_sku_resolves_and_modify_blank_does_not_clear(service):
    class Source:
        def get_record(self, tenant, record_id):
            return {'record_id': 'row1', 'version': '4', 'account_id': '00001234567890123456789', 'marketplace_id': 'ATVPDKIKX0DER',
                    'operator_code': 'AJ1', 'product_code': 'W81V5女', 'no_parent': True, 'child_asin': 'B012345678',
                    'sku': 'PreserveMe', 'effective_from': '2026-08-01', 'product_category': 'verified-category'}
        def resolve_sku(self, tenant, account, market, sku, effective_from):
            return ['B012345678']
    service.source_adapter = Source()
    resolved = upload(service, sku='source-SKU', child_asin='')
    assert resolved['status'] == 'READY'
    assert service.rows('company', OP, resolved['id'])['items'][0]['new_values']['child_asin'] == 'B012345678'
    changed = upload(service, key='modify', change_type='MODIFY', record_id='row1', expected_version='4',
                     modified_fields='sku|product_category', clear_fields='product_category', sku='')
    row = service.rows('company', OP, changed['id'])['items'][0]
    assert changed['status'] == 'READY'
    assert row['new_values']['sku'] == 'PreserveMe'
    assert 'product_category' not in row['new_values']
    assert row['old_values']['product_category'] == 'verified-category'
    # Staging has not called any authoritative mutation method.
    assert row['old_values']['version'] == '4'


def test_upload_size_transport_size_and_content_hash(service):
    assert_code('UPLOAD_TOO_LARGE', lambda: service.upload('company', OP, 'a.csv', 'a' * (1024 * 1024 + 1), {}, 'large'))
    batch = submit(service, upload(service))
    assert_code('CONTENT_HASH_MISMATCH', lambda: service.command('company', MANAGER, batch['id'], 'decision',
                {'decision': 'APPROVE', 'reason': 'review', 'content_hash': 'forged'}, batch['etag'], 'hash'))
    app = FastAPI()
    app.include_router(build_router(lambda: service, enabled=True), prefix='/api')
    app.dependency_overrides[require_session] = lambda: ('token', OP)
    response = TestClient(app).post('/api/data-changes/uploads', content=b'x' * (10 * 1024 * 1024 + 1), headers={'Content-Type': 'application/json'})
    assert response.status_code == 413
    assert response.json()['detail']['code'] == 'REQUEST_TOO_LARGE'


@pytest.mark.parametrize('template_name', ['mapping', 'mapping-add'])
def test_downloaded_template_round_trip_context_and_row_errors(service, template_name):
    """Download real headers; fill demonstration rows and validate via the API."""
    app = FastAPI()
    app.include_router(build_router(lambda: service, enabled=True), prefix='/api')
    app.dependency_overrides[require_session] = lambda: ('token', OP)
    with TestClient(app) as client:
        response = client.get('/api/data-changes/templates', params={'template': template_name})
        assert response.status_code == 200
        assert response.content.startswith(b'\xef\xbb\xbf')
        header = next(csv.reader(io.StringIO(response.content.decode('utf-8-sig'))))
        assert header == (COLUMNS if template_name == 'mapping' else
                          ['change_type', 'product_code', 'parent_asin', 'no_parent', 'child_asin', 'sku'])
        assert len(list(csv.reader(io.StringIO(response.text)))) == 1  # no accidental example record
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=header)
        writer.writeheader()
        writer.writerows([
            {'change_type': 'ADD', 'product_code': 'DEMO-01', 'parent_asin': 'B000000001', 'child_asin': 'B000000002'},
            {'change_type': 'ADD', 'product_code': 'DEMO-02', 'no_parent': 'true', 'child_asin': 'B000000003'},
        ])
        context = {'account_id': 'DEMO-ACCOUNT', 'marketplace_id': 'DEMO-MARKET',
                   'operator_code': OP['operatorCode'], 'effective_from': '2026-10-23', 'reason': 'demonstration only'}
        payload = {'file_name': 'demo.csv', 'csv_text': '\ufeff' + output.getvalue(), 'context': context}
        result = client.post('/api/data-changes/uploads', json=payload, headers={'Idempotency-Key': template_name})
        assert result.status_code == 202
        assert result.json()['status'] == 'READY'
        rows = client.get('/api/data-changes/' + result.json()['id'] + '/rows').json()['items']
        assert [row['line'] for row in rows] == [2, 3]
        assert all(row['new_values']['account_id'] == 'DEMO-ACCOUNT' and not row['errors'] for row in rows)
        # The minimal template cannot bypass operator scope or parent requirements.
        payload['context']['operator_code'] = 'OTHER'
        payload['csv_text'] = payload['csv_text'].replace('B000000001', '')
        invalid = client.post('/api/data-changes/uploads', json=payload, headers={'Idempotency-Key': template_name + '-bad'}).json()
        assert invalid['status'] == 'VALIDATION_FAILED'
        errors = client.get('/api/data-changes/' + invalid['id'] + '/rows').json()['items'][0]
        assert errors['line'] == 2
        assert 'PARENT_OR_EXPLICIT_NO_PARENT_REQUIRED' in errors['errors']
        assert 'TARGET_OUTSIDE_OWN_SCOPE' in errors['errors']


@pytest.mark.parametrize('operation', ['MODIFY', 'DISABLE'])
def test_full_template_existing_record_requirements(service, operation):
    batch = upload(service, change_type=operation)
    issues = service.rows('company', OP, batch['id'])['items'][0]['errors']
    assert 'RECORD_VERSION_REQUIRED' in issues
    if operation == 'MODIFY':
        assert 'MODIFIED_FIELDS_REQUIRED' in issues
    unresolved = upload(service, key='unresolved', change_type=operation,
                        record_id='DEMO-RECORD', expected_version='1', modified_fields='product_code')
    assert 'AUTHORITATIVE_SOURCE_UNAVAILABLE' in service.rows('company', OP, unresolved['id'])['items'][0]['errors']
