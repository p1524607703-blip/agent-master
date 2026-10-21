"""Explicit private artifact import; never reclassifies a trial as confirmed."""
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import run_rds
from app.services.workflow_pg import PgAllocationStore
from app.services.allocation_store import digest


def main():
    source = Path(sys.argv[1])
    expected = sys.argv[2]
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('ARTIFACT_HASH_MISMATCH')
    document = json.loads(raw)
    assert document['schema_version'] == 1
    store = PgAllocationStore()
    imported = []
    for run in document['runs']:
        assert run['period'] == '2026-09'
        if run['purpose'] == 'OPERATIONS_CONFIRMED_REFERENCE':
            assert (run['status'], run['calculation_status'], run['review_status']) == ('REFERENCE', 'NOT_RECALCULATED', 'OPERATIONS_CONFIRMED')
            assert run['provenance']['workbook_sha256'] == document['source_workbook_sha256']
        else:
            assert run['purpose'] == 'REAL_DATA_TRIAL'
            assert run['status'] == run['calculation_status'] == 'PARTIAL'
            assert run['provenance']['input_fingerprint'] == document['trial_input_fingerprint']
        assert run['capabilities']['formal_publication'] is False
        run['result_hash'] = digest(run['result'])
        saved, created = store.create('company', 'release-import', 'IMPORT_RELEASE', run['id'] + ':' + expected,
                                     {'artifact_hash': expected, 'id': run['id']}, 'run', run)
        assert saved['result_hash'] == run['result_hash']
        imported.append({'run_id': run['id'], 'created': created, 'status': run['status']})
    print(json.dumps({'artifact_sha256': expected, 'imported': imported}))


if __name__ == '__main__':
    main()
