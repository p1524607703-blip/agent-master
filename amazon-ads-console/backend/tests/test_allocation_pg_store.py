import copy
from uuid import uuid4
import pytest

from app.services.allocation_pg_store import AllocationPgStore, AllocationPgError
from app.services.allocation_store import digest


class Cursor:
    def __init__(self, conn):
        self.conn = conn
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def execute(self, sql, params):
        self.conn.queries.append((sql,params))
    def fetchone(self):
        return self.conn.responses.pop(0) if self.conn.responses else None


class Conn:
    def __init__(self, responses=()):
        self.responses=list(responses)
        self.queries=[]
        self.commits=0
        self.rollbacks=0
        self.closed=0
    def cursor(self):
        return Cursor(self)
    def commit(self):
        self.commits+=1
    def rollback(self):
        self.rollbacks+=1
    def close(self):
        self.closed+=1


SNAP_ID="00000000-0000-0000-0000-000000000001"
RUN_ID="00000000-0000-0000-0000-000000000002"

def capture():
    payload={"scope":{"period":"2026-09","report_timezone":"America/Los_Angeles","currency":"USD",
                      "account_ids":["account-1"],"ad_products":["SP"]},
             "facts": {"report_campaign_daily":[],"report_advertised_product_daily":[],
                       "report_purchased_product_daily":[]},
             "manifest":[],"quality_audit":{"issue_count":0},
             "capabilities":{"formal_publication":False}}
    payload["content_hash"]=digest(payload)
    return payload


def test_default_write_gate_does_not_connect():
    with pytest.raises(AllocationPgError,match="DISABLED"):
        AllocationPgStore(lambda: 1).freeze_snapshot("t",SNAP_ID,"actor",capture())


def test_insert_frozen_snapshot_is_parameterized_and_pending():
    c=Conn([(SNAP_ID,)])
    result=AllocationPgStore(lambda:c,allow_isolated_development_writes=True).freeze_snapshot("t",SNAP_ID,"actor",capture())
    assert result["created"] and result["evidence_status"]=="PENDING_REVIEW"
    assert c.commits==1 and c.closed==1 and c.rollbacks==0
    sql,params=c.queries[0]
    assert "ON CONFLICT" in sql and "%s::jsonb" in sql and params[0]=="t"
    assert params[7].startswith('{"capabilities"')


def test_replayed_hash_returns_same_existing_row_without_duplicate():
    snap=capture()
    c=Conn([None,(SNAP_ID,"PENDING_REVIEW",digest(snap["scope"]))])
    result=AllocationPgStore(lambda:c,allow_isolated_development_writes=True).freeze_snapshot("t",SNAP_ID,"actor",snap)
    assert result["created"] is False and result["snapshot_id"]==SNAP_ID
    assert len(c.queries)==2


def test_tampered_snapshot_prevents_connection():
    p=capture()
    p["facts"]["report_campaign_daily"].append({"fake":"tamper"})
    with pytest.raises(AllocationPgError,match="HASH_MISMATCH"):
        AllocationPgStore(lambda:None,allow_isolated_development_writes=True).freeze_snapshot("t",SNAP_ID,"actor",p)


def test_quality_issues_block_freeze():
    p=capture();p["quality_audit"]["issue_count"]=1;p["content_hash"]=digest({k:v for k,v in p.items() if k!="content_hash"})
    with pytest.raises(AllocationPgError,match="QUALITY_ISSUES"):
        AllocationPgStore(lambda:None,allow_isolated_development_writes=True).freeze_snapshot("t",SNAP_ID,"actor",p)


def test_read_rehash_and_no_inferred_financial_approval():
    p=capture()
    c=Conn([(p,p["content_hash"],"VERIFIED")])
    result=AllocationPgStore(lambda:c,allow_isolated_development_writes=True).read_snapshot("t",SNAP_ID)
    assert result["capture"]==p and result["financial_approved"] is False
    assert "snapshot_id=%s::uuid" in c.queries[0][0]


def test_cross_tenant_read_never_uses_unscoped_query():
    p=capture()
    c=Conn([(p,p["content_hash"],"PENDING_REVIEW")])
    AllocationPgStore(lambda:c,allow_isolated_development_writes=True).read_snapshot("tenant-A",SNAP_ID)
    assert c.queries[0][1]==("tenant-A",SNAP_ID)


def test_publish_requires_external_actor_workflow_by_default():
    conn=Conn([(1,)])
    with pytest.raises(AllocationPgError,match="WORKFLOW_NOT_CONNECTED"):
        AllocationPgStore(lambda:conn,allow_isolated_development_writes=True).publish_locked("t",RUN_ID,0,"actor")
    assert not conn.queries


def test_publish_only_calls_db_cas_function_with_revision_and_actor():
    conn=Conn([(2,)])
    rev=AllocationPgStore(lambda:conn,allow_isolated_development_writes=True).publish_locked(
        "tenant-A",RUN_ID,1,"manager",allow_approval_workflow=True)
    assert rev==2
    assert conn.queries[0][1]==("tenant-A",RUN_ID,1,"manager")
    assert "publish_locked_run" in conn.queries[0][0]


def test_bad_revision_type_rejected():
    c=Conn([(1,)])
    with pytest.raises(AllocationPgError,match="REVISION"):
        AllocationPgStore(lambda:c,allow_isolated_development_writes=True).publish_locked(
            "t",RUN_ID,True,"actor",allow_approval_workflow=True)
    assert not c.queries


def test_failed_query_rolls_back_and_closes():
    class Fail(Cursor):
        def execute(self, sql, params):
            raise RuntimeError("db failure")
    class Broken(Conn):
        def cursor(self):
            return Fail(self)
    c=Broken()
    with pytest.raises(RuntimeError,match="db failure"):
        AllocationPgStore(lambda:c,allow_isolated_development_writes=True).freeze_snapshot("t",SNAP_ID,"actor",capture())
    assert c.rollbacks==1 and c.closed==1 and c.commits==0
