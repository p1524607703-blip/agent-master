"""AsyncPG allocation archive adapter for isolated integration acceptance.

This is NOT linked to production sessions. Only explicit development mode
permits write connections, and all records start PENDING_REVIEW.
"""
from contextlib import asynccontextmanager
import json
from uuid import UUID
from .allocation_store import canonical, digest
from .allocation_pg_store import _verify_snapshot, AllocationPgError


class AsyncAllocationPgStore:
    def __init__(self, connect, *, allow_isolated_development_writes=False):
        if not callable(connect):
            raise TypeError("ASYNC_CONNECTION_FACTORY_REQUIRED")
        self.connect = connect
        self.allow_writes = allow_isolated_development_writes

    @asynccontextmanager
    async def transaction(self):
        if not self.allow_writes:
            raise AllocationPgError("DEVELOPMENT_STORE_DISABLED")
        con = await self.connect()
        try:
            async with con.transaction():
                yield con
        finally:
            await con.close()

    async def freeze_snapshot(self, tenant, snapshot_id, actor, captured):
        if not isinstance(tenant,str) or not tenant or not isinstance(actor,str) or not actor:
            raise AllocationPgError("TENANT_ACTOR_REQUIRED")
        try:
            uid=str(UUID(snapshot_id))
        except (TypeError,ValueError,AttributeError) as ex:
            raise AllocationPgError("SNAPSHOT_ID_INVALID") from ex
        scope=_verify_snapshot(captured)
        shash=digest(scope); chash=captured["content_hash"]
        async with self.transaction() as con:
            record=await con.fetchrow(
                """INSERT INTO allocation_finance.source_snapshots
                (tenant_id,snapshot_id,report_period,report_timezone,currency,
                 scope_sha256,content_sha256,frozen_payload,manifest,created_by)
                VALUES ($1,$2::uuid,$3,$4,'USD',$5,$6,$7::jsonb,$8::jsonb,$9)
                ON CONFLICT (tenant_id,content_sha256) DO NOTHING
                RETURNING snapshot_id::text""",
                tenant,uid,scope["period"],scope["report_timezone"],
                shash,chash,canonical(captured),canonical(captured["manifest"]),actor)
            if record is not None:
                return {"tenant_id":tenant,"snapshot_id":record["snapshot_id"],
                        "content_hash":chash,"created":True,"evidence_status":"PENDING_REVIEW"}
            row=await con.fetchrow(
                """SELECT snapshot_id::text,scope_sha256,evidence_status
                FROM allocation_finance.source_snapshots
                WHERE tenant_id=$1 AND content_sha256=$2""",tenant,chash)
            if row is None or row["scope_sha256"]!=shash:
                raise AllocationPgError("SNAPSHOT_IDEMPOTENCY_CONFLICT")
            return {"tenant_id":tenant,"snapshot_id":row["snapshot_id"],
                    "content_hash":chash,"created":False,"evidence_status":row["evidence_status"]}

    async def read_snapshot(self, tenant, snapshot_id):
        if not isinstance(tenant,str) or not tenant:
            raise AllocationPgError("TENANT_REQUIRED")
        try:
            uid=str(UUID(snapshot_id))
        except (TypeError,ValueError,AttributeError) as ex:
            raise AllocationPgError("SNAPSHOT_ID_INVALID") from ex
        async with self.transaction() as con:
            row=await con.fetchrow(
                """SELECT frozen_payload,content_sha256,evidence_status
                FROM allocation_finance.source_snapshots
                WHERE tenant_id=$1 AND snapshot_id=$2::uuid""",tenant,uid)
            if row is None:
                raise KeyError(uid)
            capture=json.loads(row["frozen_payload"])
            _verify_snapshot(capture)
            if capture["content_hash"]!=row["content_sha256"]:
                raise AllocationPgError("SNAPSHOT_REHASH_FAILED")
            return {"capture":capture,"evidence_status":row["evidence_status"],
                    "financial_approved":False}

    async def publish_locked(self,*args,**kwargs):
        raise AllocationPgError("TRUSTED_FINANCIAL_APPROVAL_SERVICE_NOT_CONNECTED")
