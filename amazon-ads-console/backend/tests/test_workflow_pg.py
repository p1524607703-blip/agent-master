"""Real PostgreSQL tests use a disposable socket-only cluster, never app settings."""
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from app.services.workflow_pg import PgAllocationStore, PgDocumentRepository
from app.services.allocation_store import StoreConflict
from app.services.data_changes import ChangeError, DataChangeService


@pytest.fixture(scope='module')
def pg_environment():
    if not all(shutil.which(n) for n in ['initdb', 'pg_ctl', 'psql']) or (hasattr(os, 'geteuid') and os.geteuid() == 0):
        pytest.skip('Requires non-root local PostgreSQL tools for isolated workflow tests')
    root = Path(tempfile.mkdtemp(prefix='cpo-docpg-', dir='/tmp'))
    socket = root / 'socket'
    socket.mkdir()
    env = os.environ.copy()
    env.update(LC_ALL='C', LANG='C')
    def run(args):
        return subprocess.run(args, check=True, capture_output=True, text=True, env=env)
    try:
        run(['initdb', '-D', str(root / 'db'), '--auth-local=trust', '--auth-host=reject', '--no-instructions'])
        run(['pg_ctl', '-D', str(root / 'db'), '-l', str(root / 'server.log'), '-o', "-k %s -p 55927 -h ''" % socket, '-w', 'start'])
        yield {'PGHOST': str(socket), 'PGPORT': '55927', 'PGUSER': getpass.getuser(), 'PGDATABASE': 'postgres', 'PGSSLMODE': 'disable'}
    finally:
        if (root / 'db/postmaster.pid').exists():
            run(['pg_ctl', '-D', str(root / 'db'), '-m', 'immediate', '-w', 'stop'])
        shutil.rmtree(root)


@pytest.fixture
def workflow(monkeypatch, pg_environment):
    for key, value in pg_environment.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv('PGOPTIONS', raising=False)
    migration = Path(__file__).resolve().parents[1] / 'migrations/20261020_workflow_documents.sql'
    sql = 'DROP SCHEMA IF EXISTS app CASCADE; CREATE SCHEMA app;\n' + migration.read_text()
    subprocess.run(['psql', '-X', '-q', '-v', 'ON_ERROR_STOP=1', '-f', '-'], input=sql, env=os.environ.copy(), text=True, check=True, capture_output=True)
    return PgAllocationStore()


def test_persistent_idempotency_and_tenant_scope(workflow):
    request = {'value': "O'Reilly; $$ -- \n中文"}
    first, created = workflow.create('t', 'u', 'CREATE', 'key', request, 'run', {'id': 'r', **request})
    assert created and first['revision'] == 1
    second, created = PgAllocationStore().create('t', 'u', 'CREATE', 'key', request, 'run', {'id': 'different'})
    assert not created and second == first
    assert workflow.get('other', 'run', 'r') is None and workflow.list('other', 'run') == []
    with pytest.raises(StoreConflict, match='IDEMPOTENCY_CONFLICT'):
        workflow.create('t', 'u', 'CREATE', 'key', {}, 'run', {'id': 'r'})


def test_atomic_rollback_and_large_document_stdin(workflow):
    workflow.create('t', 'u', 'CREATE', 'k', {}, 'run', {'id': 'r', 'text': 'x' * 200000})
    def fail(body):
        body['text'] = 'should roll back'
        raise ValueError('abort')
    with pytest.raises(ValueError):
        workflow.update('t', 'run', 'r', 1, fail)
    assert len(workflow.get('t', 'run', 'r')['text']) == 200000
    assert workflow.get('t', 'run', 'r')['revision'] == 1


def test_concurrent_cas_has_one_winner(workflow):
    barrier = Barrier(2)
    def write(value):
        try:
            with PgDocumentRepository('allocation-console').transaction() as state:
                barrier.wait(timeout=5)
                state['objects']['concurrency'] = value
            return True
        except StoreConflict:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, [1, 2])) == [False, True]


def test_versioned_command_replay(workflow):
    workflow.create('t', 'u', 'CREATE', 'k', {}, 'run', {'id': 'r'})
    first, created = workflow.command_update('t', 'u', 'CANCEL', 'c', {'v': 1}, 'run', 'r', 1, lambda body: dict(body, status='CANCELLED'))
    assert created and first['revision'] == 2
    replay, created = workflow.command_update('t', 'u', 'CANCEL', 'c', {'v': 1}, 'run', 'r', 1, lambda body: pytest.fail('Must not execute again'))
    assert not created and replay == first
    with pytest.raises(StoreConflict):
        workflow.update('t', 'run', 'r', 1, lambda body: body)


def test_approval_and_allocation_namespaces_are_separate(workflow):
    from test_data_changes import csv_text, OP, MANAGER
    repository = PgDocumentRepository('mapping-proposals', lambda code: ChangeError(409, code, 'Reload'))
    service = DataChangeService(repository)
    batch = service.upload('company', OP, 'mapping.csv', csv_text({}), {}, 'upload')
    batch = service.command('company', OP, batch['id'], 'submit', {}, batch['etag'], 'submit')
    approved = service.command('company', MANAGER, batch['id'], 'decision', {'decision': 'APPROVE', 'reason': 'reviewed', 'content_hash': batch['content_hash']}, batch['etag'], 'decision')
    assert approved['status'] == 'APPROVED_PENDING_APPLY'
    assert workflow.list('company', 'run') == []
