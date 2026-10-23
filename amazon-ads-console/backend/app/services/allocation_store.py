"""Durable development repository. Never reads or mutates canonical business facts.

Production publication deliberately requires a future PostgreSQL repository and
authoritative snapshot adapter. SQLite transactions protect local CAS/idempotency.
"""
import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


class StoreConflict(Exception):
    pass


class AllocationStore:
    def __init__(self, path):
        self.path = str(path)

    @contextmanager
    def transaction(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("CREATE TABLE IF NOT EXISTS allocation_objects (tenant TEXT NOT NULL, kind TEXT NOT NULL, id TEXT NOT NULL, revision INTEGER NOT NULL, body TEXT NOT NULL, PRIMARY KEY(tenant,kind,id))")
            conn.execute("CREATE TABLE IF NOT EXISTS allocation_commands (tenant TEXT NOT NULL, actor TEXT NOT NULL, command TEXT NOT NULL, key TEXT NOT NULL, fingerprint TEXT NOT NULL, object_id TEXT NOT NULL, PRIMARY KEY(tenant,actor,command,key))")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get(self, tenant, kind, resource_id):
        with self.transaction() as conn:
            row = conn.execute("SELECT body FROM allocation_objects WHERE tenant=? AND kind=? AND id=?", (tenant, kind, resource_id)).fetchone()
        return json.loads(row[0]) if row else None

    def list(self, tenant, kind):
        with self.transaction() as conn:
            rows = conn.execute("SELECT body FROM allocation_objects WHERE tenant=? AND kind=? ORDER BY id", (tenant, kind)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def create(self, tenant, actor, command, key, request, kind, body):
        fingerprint = digest(request)
        with self.transaction() as conn:
            previous = conn.execute("SELECT fingerprint,object_id FROM allocation_commands WHERE tenant=? AND actor=? AND command=? AND key=?", (tenant, actor, command, key)).fetchone()
            if previous:
                if previous[0] != fingerprint:
                    raise StoreConflict("IDEMPOTENCY_CONFLICT")
                row = conn.execute("SELECT body FROM allocation_objects WHERE tenant=? AND kind=? AND id=?", (tenant, kind, previous[1])).fetchone()
                return json.loads(row[0]), False
            body = dict(body, revision=1)
            conn.execute("INSERT INTO allocation_objects VALUES (?,?,?,?,?)", (tenant, kind, body["id"], 1, canonical(body)))
            conn.execute("INSERT INTO allocation_commands VALUES (?,?,?,?,?,?)", (tenant, actor, command, key, fingerprint, body["id"]))
            return body, True

    def update(self, tenant, kind, resource_id, expected_revision, mutate):
        with self.transaction() as conn:
            row = conn.execute("SELECT body FROM allocation_objects WHERE tenant=? AND kind=? AND id=?", (tenant, kind, resource_id)).fetchone()
            if not row:
                raise KeyError(resource_id)
            body = json.loads(row[0])
            if body["revision"] != expected_revision:
                raise StoreConflict("ETAG_MISMATCH")
            updated = mutate(body)
            updated["revision"] = expected_revision + 1
            conn.execute("UPDATE allocation_objects SET revision=?,body=? WHERE tenant=? AND kind=? AND id=? AND revision=?", (updated["revision"], canonical(updated), tenant, kind, resource_id, expected_revision))
            return updated

    def command_update(self, tenant, actor, command, key, request, kind, resource_id, expected_revision, mutate):
        fingerprint = digest(request)
        with self.transaction() as conn:
            previous = conn.execute("SELECT fingerprint,object_id FROM allocation_commands WHERE tenant=? AND actor=? AND command=? AND key=?", (tenant, actor, command, key)).fetchone()
            row = conn.execute("SELECT body FROM allocation_objects WHERE tenant=? AND kind=? AND id=?", (tenant, kind, resource_id)).fetchone()
            if not row:
                raise KeyError(resource_id)
            body = json.loads(row[0])
            if previous:
                if previous[0] != fingerprint or previous[1] != resource_id:
                    raise StoreConflict("IDEMPOTENCY_CONFLICT")
                return body, False
            if body["revision"] != expected_revision:
                raise StoreConflict("ETAG_MISMATCH")
            updated = mutate(body)
            updated["revision"] = expected_revision + 1
            conn.execute("UPDATE allocation_objects SET revision=?,body=? WHERE tenant=? AND kind=? AND id=?", (updated["revision"], canonical(updated), tenant, kind, resource_id))
            conn.execute("INSERT INTO allocation_commands VALUES (?,?,?,?,?,?)", (tenant, actor, command, key, fingerprint, resource_id))
            return updated, True
