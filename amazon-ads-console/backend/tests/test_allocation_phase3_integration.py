"""Phase-3 handoff integration: deliberately no production financial approval."""
import json
import pytest

from app.services.allocation_sources import TABLES, capture, validate_scope
from app.services.allocation_input_adapter import (
    prepare_source_handoff, require_financial_ready, AllocationHandoffBlocked)
from app.services.allocation_mapping_freeze import freeze_review_request, verify_review_request
from app.services.allocation_pg_store import AllocationPgStore, AllocationPgError


SCOPE={"period":"2026-09","report_timezone":"America/Los_Angeles","currency":"USD",
       "account_ids":["account-X"],"ad_products":["SP"]}
SID="00000000-0000-0000-0000-000000000055"


def _capture():
    base={"account_id":"account-X","ad_product":"Sponsored Products","campaign_id":"000123",
          "campaign_name":"ZJ1-W81","stat_date":"2026-09-15",
          "budget_currency":"USD","source_file_hash":"file-hash","batch_id":1,
          "units":2,"purchases":2,"spend":"8.34"}
    data={"database":"amazon_ads_v2","role":"ads_readonly","default_read_only":"on",
          "scope":validate_scope(SCOPE),
          "facts":{t:[dict(base,row_hash="hash-"+t)] for t in TABLES},
          "mappings":{"child":[],"parent":[]}}
    return capture(SCOPE,lambda _sql:json.dumps(data))


def _mapping():
    def item(label,child=None):
        row={"account_scope":label,"parent_asin":"B012345678","product_code":"W81",
             "operator_group":"ZJ1","mapping_status":"confirmed",
             "effective_date":"2026-09-01"}
        if child is not None:row["child_asin"]=child
        return row
    app={"child":[item("Shop", "B0ABC12345")],"parent":[item("Shop")]}
    warehouse={"child":[item("Warehouse", "B0ABC12345")],"parent":[item("Warehouse")]}
    return freeze_review_request(app,warehouse,{"Shop":"account-X","Warehouse":"account-X"},
                                 {"confirmed"},"2026-09-30",["account-X"],"finance-team")


class FakeCursor:
    def __init__(self, connection):self.connection=connection
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def execute(self,sql,params):self.connection.calls.append((sql,params))
    def fetchone(self):return (SID,)


class FakeConnection:
    def __init__(self):self.calls=[];self.saved=False
    def cursor(self):return FakeCursor(self)
    def commit(self):self.saved=True
    def rollback(self):raise AssertionError("unexpected rollback")
    def close(self):pass


def test_technical_mapping_and_canonical_source_still_not_approved():
    frozen=_capture(); ledger=prepare_source_handoff(frozen);mapping=_mapping()
    assert ledger["campaigns"][0]["campaign_spend"]=="8.34"
    assert ledger["financial_ready"] is False and ledger["may_run_engine"] is False
    assert mapping["candidate_products"] and mapping["technical_issues"]==[]
    assert verify_review_request(mapping)["financial_approved"] is False
    with pytest.raises(AllocationHandoffBlocked,match="NOT_APPROVED"):
        require_financial_ready(ledger)


def test_canonical_snapshot_may_be_archived_only_pending_review():
    frozen=_capture();connection=FakeConnection()
    repository=AllocationPgStore(lambda:connection,allow_isolated_development_writes=True)
    result=repository.freeze_snapshot("dev-tenant",SID,"tester",frozen)
    assert connection.saved and result["evidence_status"]=="PENDING_REVIEW"
    assert result["content_hash"]==frozen["content_hash"]
    with pytest.raises(AllocationPgError,match="WORKFLOW_NOT_CONNECTED"):
        repository.publish_locked("dev-tenant",SID,0,"tester")


def test_cross_product_spend_is_never_accidentally_added():
    frozen=_capture()
    frozen["facts"][TABLES[1]][0]["spend"]="1000.00"
    from app.services.allocation_store import digest
    frozen["content_hash"]=digest({k:v for k,v in frozen.items() if k!="content_hash"})
    ledger=prepare_source_handoff(frozen)
    assert ledger["campaigns"][0]["campaign_spend"]=="8.34"
    assert ledger["evidence_tables"]==[
        "core.report_advertised_product_daily","core.report_purchased_product_daily"]
