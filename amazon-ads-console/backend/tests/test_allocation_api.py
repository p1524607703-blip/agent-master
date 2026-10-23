import copy
import csv
import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.allocation import router
from app.api.auth import require_session
from app.services.allocation import AllocationService, get_service
from app.services.allocation_store import AllocationStore, StoreConflict


def snapshot():
    return {"currency": "USD", "products": [
        {"id": "a", "group": "AJ1", "style": "=A1", "unit": "双"},
        {"id": "b", "group": "ZJ1", "style": "W8SO", "manual_baseline": "3.00", "unit": "双"}],
        "campaigns": [{"source": "AMS", "account_id": "000012345678901234567890", "campaign_id": "0001",
                       "creator_group": "AJ1", "ad_product": "SP", "spend": "100.00", "units": 10,
                       "rows": [{"id": "row1", "product_id": "b", "units": 10, "purchases": 5,
                                 "promoted_product_id": "a", "promotion_confirmed": True, "source_isolation_required": False}],
                       "remainder": {"manual_payer_id": "a", "manual_evidence_id": "approved1"}}]}


@pytest.fixture
def client(tmp_path):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    service = AllocationService(AllocationStore(tmp_path / "allocation.sqlite3"))
    user = {"userId": "manager", "roleCode": "management", "operatorCode": ""}
    app.dependency_overrides[require_session] = lambda: ("session", user)
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        client.actor = user
        client.service = service
        yield client


def create(client, key="create1", **override):
    body = {"period": "2026-09", "report_timezone": "America/Los_Angeles", "snapshot": snapshot()}
    body.update(override)
    return client.post("/api/ad-allocation/v1/runs", json=body, headers={"Idempotency-Key": key})


def test_trial_lifecycle_is_frozen_and_not_formal(client):
    response = create(client)
    assert response.status_code == 202
    rid = response.json()["run_id"]
    result = client.get("/api/ad-allocation/v1/runs/" + rid)
    assert result.status_code == 200
    assert result.json()["status"] == "SUCCEEDED"
    assert result.json()["summary"]["final_cost"] == "100.00"
    assert result.json()["review_status"] == "DRAFT"
    assert result.json()["capabilities"]["formal_publication"] is False
    assert "snapshot" not in result.json() and "result" not in result.json()
    assert result.headers["etag"] == '"3"'
    assert client.post("/api/ad-allocation/v1/runs/" + rid + "/confirm", json={}).status_code == 405
    stored = client.service.store.get("company", "run", rid)
    assert stored["snapshot"]["campaigns"][0]["spend"] == "100.00"


def test_idempotency_reuses_completed_run_and_conflicts(client):
    first = create(client).json()
    second = create(client)
    assert second.json()["run_id"] == first["run_id"]
    assert second.json()["status"] == "SUCCEEDED"
    assert create(client, period="2026-10").status_code == 409
    assert len(client.service.store.list("company", "run")) == 1


def test_explicit_scope_and_precision_validation(client):
    assert client.post("/api/ad-allocation/v1/runs", json={}).status_code == 422
    assert create(client, period="2026-9").status_code == 422
    assert create(client, report_timezone="bad/timezone").status_code == 422
    assert create(client, tenant_id="other").status_code == 422
    value = snapshot()
    value["campaigns"][0]["spend"] = 100.0
    assert create(client, snapshot=value).status_code == 422
    value = snapshot()
    value["mode"] = "REMAINDER_ONLY"
    assert create(client, snapshot=value).status_code == 422


def test_operator_rows_and_export_never_leak_company_totals(client):
    rid = create(client).json()["run_id"]
    client.actor.update(userId="operator", roleCode="operator", operatorCode="ZJ1")
    detail = client.get("/api/ad-allocation/v1/runs/" + rid).json()
    assert detail["summary"] is None and "created_by" not in detail and "snapshot_hash" not in detail
    products = client.get("/api/ad-allocation/v1/runs/" + rid + "/products").json()["items"]
    assert [p["id"] for p in products] == ["b"]
    assert client.get("/api/ad-allocation/v1/runs/" + rid + "/campaigns").status_code == 403
    assert client.get("/api/ad-allocation/v1/runs/" + rid + "/issues").status_code == 403
    assert create(client, key="op").status_code == 403
    client.actor["operatorCode"] = "OTHER"
    assert client.get("/api/ad-allocation/v1/runs/" + rid).status_code == 404
    assert client.get("/api/ad-allocation/v1/runs").json()["items"] == []


def test_export_is_frozen_authorized_and_formula_safe(client):
    rid = create(client).json()["run_id"]
    response = client.post("/api/ad-allocation/v1/runs/" + rid + "/exports", json={"format": "csv", "report": "products"}, headers={"Idempotency-Key": "export1"})
    assert response.status_code == 202
    eid = response.json()["export_id"]
    content = client.get("/api/ad-allocation/v1/exports/" + eid + "/download")
    assert content.status_code == 200 and "X-Content-SHA256" in content.headers
    rows = list(csv.DictReader(io.StringIO(content.content.decode("utf-8-sig"))))
    assert rows[0]["style"] == "'=A1"
    assert sum(int(r["final_minor"]) for r in rows) == 10000
    assert all(r["purpose"] == "DEVELOPMENT_TRIAL" for r in rows)
    client.actor.update(userId="other", roleCode="operator", operatorCode="AJ1")
    assert client.get("/api/ad-allocation/v1/exports/" + eid + "/download").status_code == 404


def test_shared_group_visibility_and_old_exports_reauthorize_current_scope(client):
    rid = create(client).json()['run_id']
    path = '/api/ad-allocation/v1/runs/' + rid
    client.actor.update(userId='operator', roleCode='operator', operatorCode='AJ1')
    expected = client.get(path + '/products').json()['items']
    export = client.post(path + '/exports', json={'format': 'csv', 'report': 'products'},
                         headers={'Idempotency-Key': 'own-export'}).json()
    download = '/api/ad-allocation/v1/exports/' + export['id'] + '/download'
    for code in ('AJ2', 'AJ0'):
        client.actor['operatorCode'] = code
        assert client.get(path + '/products').json()['items'] == expected
        assert client.get(download).status_code == 200
        assert client.get(path + '/groups').status_code == 403
    client.actor['operatorCode'] = 'ZJ1'
    assert client.get(download).status_code == 403
    assert [row['group'] for row in client.get(path + '/products').json()['items']] == ['ZJ1']
    assert client.get(path + '/workbook.xlsx').status_code == 200
    client.actor['operatorCode'] = 'XM1'
    assert client.get(download).status_code == 404


def test_cursor_is_bound_to_result_and_actor(client):
    rid = create(client).json()["run_id"]
    first = client.get("/api/ad-allocation/v1/runs/" + rid + "/products?limit=1").json()
    second = client.get("/api/ad-allocation/v1/runs/" + rid + "/products", params={"cursor": first["next_cursor"], "limit": 1}).json()
    assert first["items"][0]["id"] != second["items"][0]["id"]
    assert second["next_cursor"] is None
    assert client.get("/api/ad-allocation/v1/runs/" + rid + "/campaigns", params={"cursor": first["next_cursor"]}).status_code == 400
    assert client.get("/api/ad-allocation/v1/runs/" + rid + "/products?limit=201").status_code == 422


def test_cpo_missing_binding_preserves_cost(client):
    rid = create(client).json()["run_id"]
    rows = client.get("/api/ad-allocation/v1/runs/" + rid + "/cpo").json()["items"]
    assert rows[1]["final_cost"] == "30.00"
    assert rows[1]["ordered_product_units"] is None
    assert rows[1]["allocation_business_cpo"] is None
    assert rows[1]["allocation_attributed_unit_cost"] == "3.000000"


def test_unauthenticated_and_disabled_default(tmp_path, monkeypatch):
    monkeypatch.delenv("CPO_ALLOCATION_ENABLED", raising=False)
    monkeypatch.setenv("CPO_ALLOCATION_DB", str(tmp_path / "not-created.sqlite3"))
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as session:
        assert session.get("/ad-allocation/v1/capabilities").status_code == 401
        app.dependency_overrides[require_session] = lambda: ("session", {"userId": "u", "roleCode": "management"})
        assert session.get("/ad-allocation/v1/capabilities").json()["enabled"] is False
        assert session.get("/ad-allocation/v1/runs").status_code == 503
    assert not (tmp_path / "not-created.sqlite3").exists()


def test_store_cas_and_tenant_partition(tmp_path):
    store = AllocationStore(tmp_path / "s.sqlite3")
    store.create("t", "a", "create", "k", {}, "run", {"id": "r"})
    assert store.get("other", "run", "r") is None
    def write(_):
        try:
            store.update("t", "run", "r", 1, lambda body: body)
            return True
        except StoreConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, [1, 2])) == [False, True]


def test_old_claim_write_paths_blocked_when_pilot_enabled(monkeypatch):
    from app.api.routes import router as legacy
    monkeypatch.setenv("CPO_ALLOCATION_ENABLED", "1")
    app = FastAPI()
    app.include_router(legacy)
    app.dependency_overrides[require_session] = lambda: ("session", {"userId": "u", "roleCode": "operator"})
    with TestClient(app) as client:
        # Production already removed these legacy write endpoints entirely.
        assert client.post("/cpo-claims", json={}).status_code in {404, 409}
        assert client.post("/cpo-claims/fake/decision", json={}).status_code in {404, 409}


def test_xlsx_filters_operator_and_preserves_missing_amounts(client):
    from zipfile import ZipFile
    rid = create(client).json()['run_id']
    client.actor.update(userId='operator', roleCode='operator', operatorCode='ZJ1')
    response = client.get('/api/ad-allocation/v1/runs/' + rid + '/workbook.xlsx')
    assert response.status_code == 200
    with ZipFile(io.BytesIO(response.content)) as archive:
        xml = archive.read('xl/worksheets/sheet1.xml').decode()
        assert 'W8SO' in xml and 'ZJ1' in xml
        assert 'AJ1' not in xml and '=A1' not in xml
        assert '<f>' not in xml
    client.actor.update(operatorCode='MISSING')
    assert client.get('/api/ad-allocation/v1/runs/' + rid + '/workbook.xlsx').status_code == 404


def test_business_conflict_does_not_discard_financial_result(client):
    business = {"id": "b", "period": "2026-09", "report_timezone": "America/Los_Angeles", "binding_version": "v1",
                "facts": [{"account_id": "s", "marketplace": "US", "date": "2026-09-01", "child_asin": "B", "fact_version": "1", "ordered_product_units": 1}] * 2}
    rid = create(client, business_snapshot=business).json()["run_id"]
    detail = client.get("/api/ad-allocation/v1/runs/" + rid).json()
    assert detail["status"] == "SUCCEEDED" and detail["summary"]["final_cost"] == "100.00"
    rows = client.get("/api/ad-allocation/v1/runs/" + rid + "/cpo").json()["items"]
    assert all(row["denominator_status"] == "BUSINESS_SNAPSHOT_INVALID" and row["ordered_product_units"] is None for row in rows)


def test_expired_worker_retry_reuses_frozen_input_with_cas(client):
    from datetime import datetime, timezone, timedelta
    rid = create(client).json()["run_id"]
    store = client.service.store
    def crash(body):
        body.update(status="RUNNING", calculation_status="RUNNING", lease_expires_at=(datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(), result=None)
        return body
    store.update("company", "run", rid, 3, crash)
    path = "/api/ad-allocation/v1/runs/" + rid + "/retry"
    assert client.post(path, headers={"Idempotency-Key": "retry1"}).status_code == 428
    assert client.post(path, headers={"Idempotency-Key": "retry1", "If-Match": '"3"'}).status_code == 412
    response = client.post(path, headers={"Idempotency-Key": "retry1", "If-Match": '"4"'})
    assert response.status_code == 202
    assert client.get("/api/ad-allocation/v1/runs/" + rid).json()["status"] == "SUCCEEDED"
    repeated = client.post(path, headers={"Idempotency-Key": "retry1", "If-Match": '"4"'})
    assert repeated.status_code == 202 and repeated.json()["status"] == "SUCCEEDED"
    assert len(store.list("company", "run")) == 1
