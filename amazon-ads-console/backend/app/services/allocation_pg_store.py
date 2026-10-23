"""Experimental, driver-injected PostgreSQL allocation store.

Production writes are disabled unless the caller explicitly enables isolated
development writes. This module never imports an RDS config or creates a socket.
"""
from contextlib import contextmanager
import json
from uuid import UUID

from .allocation_store import canonical, digest


class AllocationPgError(ValueError):
    pass


def _required(label, value):
    if not isinstance(value, str) or not value.strip() or len(value) > 256 or "\x00" in value:
        raise AllocationPgError(label + "_REQUIRED")
    return value


def _uuid(value):
    try:
        return str(UUID(_required("UUID", value)))
    except (ValueError, TypeError, AttributeError) as error:
        raise AllocationPgError("INVALID_UUID") from error


def _verify_snapshot(snapshot):
    if not isinstance(snapshot, dict) or snapshot.get("capabilities", {}).get("formal_publication") is not False:
        raise AllocationPgError("UNAPPROVED_CAPTURE_ONLY")
    source = {k: v for k, v in snapshot.items() if k != "content_hash"}
    if snapshot.get("content_hash") != digest(source):
        raise AllocationPgError("SNAPSHOT_HASH_MISMATCH")
    scope = snapshot.get("scope")
    if not isinstance(scope, dict) or not isinstance(snapshot.get("manifest"), list):
        raise AllocationPgError("SNAPSHOT_METADATA_REQUIRED")
    if not isinstance(scope.get("period"), str) or not scope.get("report_timezone") or scope.get("currency") != "USD":
        raise AllocationPgError("SNAPSHOT_SCOPE_INVALID")
    if snapshot.get("quality_audit", {}).get("issue_count", 0):
        raise AllocationPgError("SNAPSHOT_HAS_QUALITY_ISSUES")
    # Source coverage and external approval are deliberately not inferred.
    return scope


class AllocationPgStore:
    def __init__(self, connection_factory, *, allow_isolated_development_writes=False):
        if not callable(connection_factory):
            raise TypeError("DBAPI_CONNECTION_FACTORY_REQUIRED")
        self.connect = connection_factory
        self.allow_writes = allow_isolated_development_writes

    @contextmanager
    def _transaction(self):
        if not self.allow_writes:
            raise AllocationPgError("DEVELOPMENT_STORE_DISABLED")
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def freeze_snapshot(self, tenant, snapshot_id, actor, captured):
        """Insert one exact frozen capture idempotently, always PENDING_REVIEW."""
        _required("TENANT", tenant)
        _required("ACTOR", actor)
        sid = _uuid(snapshot_id)
        scope = _verify_snapshot(captured)
        shash = digest(scope)
        chash = captured["content_hash"]
        with self._transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO allocation_finance.source_snapshots
                    (tenant_id,snapshot_id,report_period,report_timezone,currency,
                     scope_sha256,content_sha256,frozen_payload,manifest,created_by)
                    VALUES (%s,%s::uuid,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)
                    ON CONFLICT (tenant_id,content_sha256) DO NOTHING
                    RETURNING snapshot_id::text""",
                    (tenant, sid, scope["period"], scope["report_timezone"], "USD",
                     shash, chash, canonical(captured), canonical(captured["manifest"]), actor))
                inserted = cursor.fetchone()
                if inserted is not None:
                    return {"tenant_id": tenant, "snapshot_id": inserted[0],
                            "content_hash": chash, "evidence_status": "PENDING_REVIEW",
                            "created": True}
                cursor.execute(
                    """SELECT snapshot_id::text,evidence_status,scope_sha256
                    FROM allocation_finance.source_snapshots
                    WHERE tenant_id=%s AND content_sha256=%s""",
                    (tenant, chash))
                existing = cursor.fetchone()
                if existing is None or existing[2] != shash:
                    raise AllocationPgError("SNAPSHOT_IDEMPOTENCY_CONFLICT")
                return {"tenant_id": tenant, "snapshot_id": existing[0],
                        "content_hash": chash, "evidence_status": existing[1],
                        "created": False}

    def read_snapshot(self, tenant, snapshot_id):
        """Read and re-hash frozen payload; never translate it into approval."""
        _required("TENANT", tenant)
        sid = _uuid(snapshot_id)
        with self._transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """SELECT frozen_payload,content_sha256,evidence_status
                    FROM allocation_finance.source_snapshots
                    WHERE tenant_id=%s AND snapshot_id=%s::uuid""", (tenant, sid))
                row = cursor.fetchone()
                if row is None:
                    raise KeyError(sid)
                payload = json.loads(row[0]) if isinstance(row[0], str) else row[0]
                _verify_snapshot(payload)
                if row[1] != payload["content_hash"]:
                    raise AllocationPgError("SNAPSHOT_REHASH_FAILED")
                return {"capture": payload, "evidence_status": row[2],
                        "financial_approved": False}

    def publish_locked(self, tenant, run_id, expected_revision, actor, *,
                       allow_approval_workflow=False):
        """Never expose real publication until the reviewed actor workflow exists."""
        _required("TENANT", tenant)
        _required("ACTOR", actor)
        rid = _uuid(run_id)
        if not allow_approval_workflow:
            raise AllocationPgError("APPROVAL_WORKFLOW_NOT_CONNECTED")
        if type(expected_revision) is not int or expected_revision < 0:
            raise AllocationPgError("INVALID_EXPECTED_REVISION")
        with self._transaction() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT allocation_finance.publish_locked_run(%s,%s::uuid,%s,%s)",
                    (tenant, rid, expected_revision, actor))
                row = cursor.fetchone()
                if row is None:
                    raise AllocationPgError("PUBLICATION_CAS_NO_RESPONSE")
                return int(row[0])
