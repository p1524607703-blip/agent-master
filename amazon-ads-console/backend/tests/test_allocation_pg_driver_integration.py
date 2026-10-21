"""Runs only on a new temporary socket-only PostgreSQL started by the wrapper."""
import asyncio
import json
import os
from uuid import uuid4

import pytest
from app.services.allocation_pg_async_store import AsyncAllocationPgStore, AllocationPgError
from app.services.allocation_store import digest
from app.services.allocation_sources import capture,validate_scope,TABLES


def sample():
    scope={"period":"2026-09","report_timezone":"America/Los_Angeles","currency":"USD",
           "account_ids":["test-account"],"ad_products":["SP"]}
    row={"account_id":"test-account","ad_product":"Sponsored Products",
         "campaign_id":"cmp-1","stat_date":"2026-09-15","budget_currency":"USD",
         "row_hash":"r1","source_file_hash":"file1","batch_id":1,
         "spend":"3.21","purchases":2,"units":2}
    data={"database":"amazon_ads_v2","role":"ads_readonly","default_read_only":"on",
          "scope":validate_scope(scope),
          "facts":{table:[dict(row, row_hash="r1-"+table)] for table in TABLES},
          "mappings":{"child":[],"parent":[]}}
    return capture(scope,lambda _:json.dumps(data))


def isolated_connector():
    sock=os.getenv("CPO_TEST_PG_SOCKET")
    if not sock:
        pytest.skip("No temporary PG socket, use run_ephemeral_driver_pg.sh")
    if not sock.startswith("/tmp/cpo-") or "socket" not in sock:
        raise RuntimeError("TEST_PG_SOCKET_MUST_BE_EPHEMERAL")
    import asyncpg
    async def connect():
        return await asyncpg.connect(host=sock,port=int(os.environ["CPO_TEST_PG_PORT"]),
                                     user=os.environ["CPO_TEST_PG_USER"],database="postgres")
    return connect


def test_live_pg_freeze_replay_rollback_and_tenant_scope():
    connect=isolated_connector()
    async def scenario():
        s=AsyncAllocationPgStore(connect,allow_isolated_development_writes=True)
        cap=sample(); sid=str(uuid4())
        first=await s.freeze_snapshot("test-tenant",sid,"test-actor",cap)
        assert first["created"] is True and first["evidence_status"]=="PENDING_REVIEW"
        replay=await s.freeze_snapshot("test-tenant",str(uuid4()),"test-actor",cap)
        assert replay["created"] is False and replay["snapshot_id"]==sid
        assert (await s.read_snapshot("test-tenant",sid))["capture"]==cap
        try:
            await s.read_snapshot("other-tenant",sid)
            assert False,"cross tenant read should fail"
        except KeyError:
            pass
        tampered=dict(cap)
        tampered["scope"]=dict(cap["scope"],period="2026-10")
        try:
            await s.freeze_snapshot("test-tenant",str(uuid4()),"test-actor",tampered)
            assert False,"tamper write should fail"
        except AllocationPgError as ex:
            assert "HASH_MISMATCH" in str(ex)
        try:
            await s.publish_locked("test-tenant",sid,0,"test-actor")
            assert False,"unverified finance publication must be refused"
        except AllocationPgError as ex:
            assert "NOT_CONNECTED" in str(ex)
    asyncio.run(scenario())


def test_live_pg_default_write_flag_is_closed():
    connect=isolated_connector()
    async def scenario():
        s=AsyncAllocationPgStore(connect)
        with pytest.raises(AllocationPgError,match="DISABLED"):
            await s.freeze_snapshot("test-tenant",str(uuid4()),"test-actor",sample())
    asyncio.run(scenario())
