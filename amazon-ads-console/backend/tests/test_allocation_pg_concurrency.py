"""Real disposable PostgreSQL 16 concurrency/lock/CAS acceptance.

Only usable with run_ephemeral_concurrency_pg.sh. Never connects to existing DB.
"""
import asyncio
import os
from uuid import uuid4
import pytest

from app.services.allocation_pg_async_store import AsyncAllocationPgStore
from app.services.allocation_pg_driver_support import isolated_connection
from app.services.allocation_pg_store import AllocationPgError
from app.services.allocation_sources import capture,validate_scope,TABLES
import json


def _connector():
    if not os.environ.get("CPO_TEST_PG_SOCKET"):
        pytest.skip("Temporary socket not configured")
    return isolated_connection()


def _capture():
    scope={"period":"2026-09","report_timezone":"America/Los_Angeles",
           "currency":"USD","account_ids":["acct1"],"ad_products":["SP"]}
    row={"account_id":"acct1","ad_product":"Sponsored Products","campaign_id":"c1",
         "stat_date":"2026-09-17","budget_currency":"USD","row_hash":"rh1",
         "source_file_hash":"fh1","batch_id":1,"purchases":1,"units":1,"spend":"0.01"}
    data={"database":"amazon_ads_v2","role":"ads_readonly","default_read_only":"on",
          "scope":validate_scope(scope),
          "facts":{table:[dict(row,row_hash=table)] for table in TABLES},
          "mappings":{"child":[],"parent":[]}}
    return capture(scope,lambda _:json.dumps(data))


def test_parallel_freeze_same_hash_one_insert_and_one_replay():
    connect=_connector()
    async def scenario():
        store=AsyncAllocationPgStore(connect,allow_isolated_development_writes=True)
        tenant="parallel-"+str(uuid4())
        source=_capture()
        ids=[str(uuid4()),str(uuid4())]
        results=await asyncio.wait_for(
            asyncio.gather(*(store.freeze_snapshot(tenant,x,"subagent-test",source) for x in ids)),
            timeout=8)
        assert sorted(x["created"] for x in results)==[False,True]
        assert results[0]["snapshot_id"]==results[1]["snapshot_id"]
        saved=await store.read_snapshot(tenant,results[0]["snapshot_id"])
        assert saved["capture"]["content_hash"]==source["content_hash"]
        con=await connect()
        try:
            count=await con.fetchval("SELECT count(*) FROM allocation_finance.source_snapshots WHERE tenant_id=$1",tenant)
            assert count==1
        finally:
            await con.close()
    asyncio.run(scenario())


def test_immutable_frozen_payload_even_with_owner_access():
    connect=_connector()
    async def scenario():
        import asyncpg
        store=AsyncAllocationPgStore(connect,allow_isolated_development_writes=True)
        tenant="immutable-"+str(uuid4())
        created=await store.freeze_snapshot(tenant,str(uuid4()),"test",_capture())
        con=await connect()
        try:
            with pytest.raises(asyncpg.PostgresError,match="SOURCE_SNAPSHOT_IMMUTABLE"):
                await con.execute("UPDATE allocation_finance.source_snapshots SET frozen_payload='{}'::jsonb WHERE tenant_id=$1",tenant)
            count=await con.fetchval("SELECT count(*) FROM allocation_finance.source_snapshots WHERE tenant_id=$1",tenant)
            assert count==1
        finally:
            await con.close()
    asyncio.run(scenario())


def test_race_publish_cas_only_one_wins():
    connect=_connector()
    async def publish():
        con=await connect()
        try:
            return await con.fetchval(
                "SELECT allocation_finance.publish_locked_run($1,$2::uuid,$3,$4)",
                "tenant-test","00000000-0000-0000-0000-000000000004",2,"test-auditor")
        finally:
            await con.close()
    async def scenario():
        import asyncpg
        result=await asyncio.gather(publish(),publish(),return_exceptions=True)
        success=[x for x in result if isinstance(x,int)]
        errors=[x for x in result if isinstance(x,asyncpg.PostgresError)]
        assert success==[3] and len(errors)==1
        assert "PUBLICATION_CAS_CONFLICT" in str(errors[0])
        con=await connect()
        try:
            final=await con.fetchval(
                "SELECT revision FROM allocation_finance.publication_pointers WHERE tenant_id='tenant-test'")
            assert final==3
        finally:
            await con.close()
    asyncio.run(scenario())


def test_rls_does_not_expose_rows_to_limited_operator_role():
    connect=_connector()
    async def scenario():
        con=await connect()
        try:
            async with con.transaction():
                await con.execute("SET LOCAL ROLE allocation_operator")
                count=await con.fetchval("SELECT count(*) FROM allocation_finance.runs")
                assert count==0
        finally:
            await con.close()
    asyncio.run(scenario())
