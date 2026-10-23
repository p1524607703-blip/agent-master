"""PostgreSQL workflow persistence, isolated from warehouse facts and mappings.

The small console workload uses revisioned JSON documents. CAS commits make an
approval or idempotent command atomic even across application processes.
"""
import base64
import json
import os
import subprocess
from contextlib import contextmanager
from copy import deepcopy

from .allocation_store import StoreConflict, canonical, digest


def _rows(sql):
    # stdin avoids OS argument-size limits for persisted report documents.
    try:
        process = subprocess.run(
            ['psql', '-X', '-q', '-t', '-A', '-v', 'ON_ERROR_STOP=1', '-f', '-'],
            input=sql, text=True, capture_output=True, timeout=30, env=os.environ.copy())
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError('WORKFLOW_DATABASE_UNAVAILABLE') from None
    if process.returncode:
        raise RuntimeError('WORKFLOW_DATABASE_QUERY_FAILED')
    return json.loads(process.stdout.strip() or '[]')


class PgDocumentRepository:
    NAMES = {'allocation-console', 'mapping-proposals'}

    def __init__(self, name, conflict_factory=StoreConflict):
        if name not in self.NAMES:
            raise ValueError('INVALID_WORKFLOW_NAMESPACE')
        self.name, self.conflict_factory = name, conflict_factory

    def read(self):
        # Names are fixed enum values, never request-provided SQL identifiers.
        rows = _rows("SELECT coalesce(json_agg(q),'[]'::json) FROM (SELECT revision,payload "
                     "FROM app.cpo_workflow_documents WHERE name='%s') q;" % self.name)
        if not rows:
            raise RuntimeError('WORKFLOW_SCHEMA_NOT_INITIALIZED')
        return rows[0]

    @contextmanager
    def transaction(self):
        row = self.read()
        before = canonical(row['payload'])
        state = deepcopy(row['payload'])
        yield state
        after = canonical(state)
        if after == before:
            return
        encoded = base64.b64encode(after.encode()).decode('ascii')
        revision = int(row['revision'])
        updated = _rows(
            "WITH changed AS (UPDATE app.cpo_workflow_documents SET payload=convert_from(decode('%s','base64'),'UTF8')::jsonb,"
            "revision=revision+1,updated_at=clock_timestamp() WHERE name='%s' AND revision=%d RETURNING revision) "
            "SELECT coalesce(json_agg(changed),'[]'::json) FROM changed;"
            % (encoded, self.name, revision))
        if not updated:
            raise self.conflict_factory('WORKFLOW_VERSION_CONFLICT')


class PgAllocationStore:
    def __init__(self):
        self.repository = PgDocumentRepository('allocation-console')

    @staticmethod
    def _object_key(tenant, kind, resource_id):
        return canonical([tenant, kind, resource_id])

    @staticmethod
    def _command_key(tenant, actor, command, key):
        return canonical([tenant, actor, command, key])

    def get(self, tenant, kind, resource_id):
        return deepcopy(self.repository.read()['payload']['objects'].get(self._object_key(tenant, kind, resource_id)))

    def list(self, tenant, kind):
        objects = self.repository.read()['payload']['objects']
        return [deepcopy(value) for key, value in sorted(objects.items()) if json.loads(key)[:2] == [tenant, kind]]

    def create(self, tenant, actor, command, key, request, kind, body):
        fingerprint = digest(request)
        command_key = self._command_key(tenant, actor, command, key)
        with self.repository.transaction() as state:
            previous = state['commands'].get(command_key)
            if previous:
                if previous['fingerprint'] != fingerprint:
                    raise StoreConflict('IDEMPOTENCY_CONFLICT')
                return deepcopy(state['objects'][previous['object_key']]), False
            object_key = self._object_key(tenant, kind, body['id'])
            if object_key in state['objects']:
                raise StoreConflict('OBJECT_ALREADY_EXISTS')
            saved = dict(body, revision=1)
            state['objects'][object_key] = saved
            state['commands'][command_key] = {'fingerprint': fingerprint, 'object_key': object_key}
            return deepcopy(saved), True

    def update(self, tenant, kind, resource_id, expected_revision, mutate):
        object_key = self._object_key(tenant, kind, resource_id)
        with self.repository.transaction() as state:
            current = state['objects'].get(object_key)
            if current is None:
                raise KeyError(resource_id)
            if current['revision'] != expected_revision:
                raise StoreConflict('ETAG_MISMATCH')
            updated = mutate(deepcopy(current))
            updated['revision'] = expected_revision + 1
            state['objects'][object_key] = updated
            return deepcopy(updated)

    def command_update(self, tenant, actor, command, key, request, kind, resource_id, expected_revision, mutate):
        object_key = self._object_key(tenant, kind, resource_id)
        command_key = self._command_key(tenant, actor, command, key)
        fingerprint = digest(request)
        with self.repository.transaction() as state:
            current = state['objects'].get(object_key)
            if current is None:
                raise KeyError(resource_id)
            previous = state['commands'].get(command_key)
            if previous:
                if previous['fingerprint'] != fingerprint or previous['object_key'] != object_key:
                    raise StoreConflict('IDEMPOTENCY_CONFLICT')
                return deepcopy(current), False
            if current['revision'] != expected_revision:
                raise StoreConflict('ETAG_MISMATCH')
            updated = mutate(deepcopy(current))
            updated['revision'] = expected_revision + 1
            state['objects'][object_key] = updated
            state['commands'][command_key] = {'fingerprint': fingerprint, 'object_key': object_key}
            return deepcopy(updated), True
