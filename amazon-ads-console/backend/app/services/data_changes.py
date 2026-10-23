"""Isolated, transactional approval staging. Never a source of effective CPO mappings."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

MANAGEMENT = {'management', 'super_admin'}
COLUMNS = ['change_type', 'account_id', 'marketplace_id', 'operator_code', 'product_code',
           'parent_asin', 'no_parent', 'child_asin', 'sku', 'effective_from', 'effective_to',
           'reason', 'record_id', 'expected_version', 'modified_fields', 'clear_fields',
           'product_category', 'age_segment', 'business_group']
# Batch context supplies account, marketplace, operator, date and reason.
ADD_TEMPLATE_COLUMNS = ['change_type', 'product_code', 'parent_asin', 'no_parent', 'child_asin', 'sku']
EDITABLE = {'operator_code', 'product_code', 'parent_asin', 'no_parent', 'child_asin',
            'sku', 'effective_from', 'effective_to', 'product_category', 'age_segment', 'business_group'}
NULLABLE = {'parent_asin', 'sku', 'effective_to', 'product_category', 'age_segment', 'business_group'}
ASIN = re.compile(r'^[A-Z0-9]{10}$')


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ChangeError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


class SQLiteDataChangeRepository:
    """One JSON document guarded by an SQLite write transaction; local staging only."""
    def __init__(self, path: str):
        self.path = str(path)

    @contextmanager
    def transaction(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=20)
        try:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('CREATE TABLE IF NOT EXISTS approval_staging (id INTEGER PRIMARY KEY CHECK (id=1), payload TEXT NOT NULL)')
            found = connection.execute('SELECT payload FROM approval_staging WHERE id=1').fetchone()
            state = json.loads(found[0]) if found else {'batches': {}, 'idempotency': {}}
            yield state
            connection.execute('INSERT INTO approval_staging(id,payload) VALUES (1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload',
                               (json.dumps(state, ensure_ascii=False, separators=(',', ':')),))
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()


class DataChangeService:
    def __init__(self, repository, source_adapter=None):
        self.repository, self.source_adapter = repository, source_adapter

    @staticmethod
    def _identity(user):
        if not user.get('userId'):
            raise ChangeError(403, 'SUBMITTER_ID_REQUIRED', 'A server-authenticated user ID is required.')
        if user.get('roleCode') not in MANAGEMENT | {'operator'}:
            raise ChangeError(403, 'ROLE_FORBIDDEN', 'This role cannot access mapping proposals.')
        return str(user['userId'])

    def _batch(self, state, tenant, user, batch_id):
        uid = self._identity(user)
        batch = state['batches'].get(batch_id)
        if not batch or batch['tenant_id'] != tenant or (batch['created_by'] != uid and user.get('roleCode') not in MANAGEMENT):
            raise ChangeError(404, 'BATCH_NOT_FOUND', 'Proposal not found.')
        return batch

    @staticmethod
    def _view(batch, user):
        result = copy.deepcopy({key: value for key, value in batch.items() if key not in {'rows', 'file_content'}})
        owner = batch['created_by'] == str(user.get('userId'))
        result['etag'] = '"%s"' % batch['version']
        result['capabilities'] = {
            'can_submit': owner and batch['status'] == 'READY',
            'can_review': not owner and user.get('roleCode') in MANAGEMENT and batch['status'] in {'SUBMITTED', 'UNDER_REVIEW'},
            'can_withdraw': owner and batch['status'] in {'READY', 'VALIDATION_FAILED', 'SUBMITTED'},
            'can_apply': False,
        }
        return result

    @staticmethod
    def _cas(batch, if_match):
        if if_match is None:
            raise ChangeError(428, 'IF_MATCH_REQUIRED', 'If-Match is required.')
        if if_match != '"%s"' % batch['version']:
            raise ChangeError(412, 'VERSION_CONFLICT', 'The proposal version changed; reload before retrying.')

    def _idempotent(self, state, tenant, user, action, key, request):
        if not key or len(key) > 200:
            raise ChangeError(400, 'IDEMPOTENCY_KEY_REQUIRED', 'A nonempty Idempotency-Key of at most 200 characters is required.')
        token = digest([tenant, self._identity(user), action, key])
        request_hash = digest(request)
        existing = state['idempotency'].get(token)
        if existing:
            if existing['request_hash'] != request_hash:
                raise ChangeError(409, 'IDEMPOTENCY_CONFLICT', 'The same key was used with different content.')
            return token, request_hash, copy.deepcopy(existing['response'])
        return token, request_hash, None

    @staticmethod
    def _remember(state, token, request_hash, response):
        state['idempotency'][token] = {'request_hash': request_hash, 'response': copy.deepcopy(response)}
        return response

    def _validate(self, tenant, user, raw_rows, context):
        output, identities, sku_links, intervals = [], {}, {}, {}
        for line, raw in enumerate(raw_rows, start=2):
            values = {key: (value if key == 'sku' else value.strip()) for key, value in raw.items()}
            for key, value in context.items():
                if key in COLUMNS and not values.get(key) and value is not None:
                    values[key] = str(value) if key == 'sku' else str(value).strip()
            errors, old = [], None
            def issue(code):
                if code not in errors:
                    errors.append(code)
            if any(value.lstrip().startswith(('=', '+', '@')) or '\x00' in value for value in values.values()):
                issue('UNSAFE_CELL')
            operation = values.get('change_type', '').upper()
            values['change_type'] = operation
            if operation not in {'ADD', 'MODIFY', 'DISABLE'}:
                issue('CHANGE_TYPE_INVALID')
            for field in ('account_id', 'marketplace_id', 'operator_code', 'product_code', 'effective_from', 'reason'):
                if not values.get(field):
                    issue(field.upper() + '_REQUIRED')
            for field in ('account_id', 'marketplace_id', 'product_code'):
                if re.fullmatch(r'[+-]?\d+(?:\.\d+)?[Ee][+-]?\d+', values.get(field, '')):
                    issue(field.upper() + '_SCIENTIFIC_NOTATION')
            if user.get('roleCode') == 'operator' and values.get('operator_code') != user.get('operatorCode'):
                issue('TARGET_OUTSIDE_OWN_SCOPE')
            modified = {item.strip() for item in values.get('modified_fields', '').split('|') if item.strip()}
            clear = {item.strip() for item in values.get('clear_fields', '').split('|') if item.strip()}
            if not modified <= EDITABLE or not clear <= NULLABLE or clear - modified:
                issue('FIELD_SET_INVALID')
            if operation in {'MODIFY', 'DISABLE'}:
                if not values.get('record_id') or not values.get('expected_version'):
                    issue('RECORD_VERSION_REQUIRED')
                elif self.source_adapter is None:
                    issue('AUTHORITATIVE_SOURCE_UNAVAILABLE')
                else:
                    old = self.source_adapter.get_record(tenant, values['record_id'])
                    if old is None or (user.get('roleCode') == 'operator' and old.get('operator_code') != user.get('operatorCode')):
                        old = None
                        issue('RECORD_NOT_ACCESSIBLE')
                    elif str(old.get('version')) != values['expected_version']:
                        issue('RECORD_VERSION_CONFLICT')
                    elif old.get('account_id') != values.get('account_id') or old.get('marketplace_id') != values.get('marketplace_id'):
                        issue('RECORD_SCOPE_MISMATCH')
                if operation == 'MODIFY' and not modified:
                    issue('MODIFIED_FIELDS_REQUIRED')
            new = {key: value for key, value in values.items() if key not in {'modified_fields', 'clear_fields', 'expected_version', 'record_id', 'reason', 'change_type'} and value != ''}
            if old:
                new = {key: value for key, value in old.items() if key != 'version'}
                for key in modified:
                    if key in clear:
                        new.pop(key, None)
                    elif values.get(key) != '':
                        new[key] = values[key]
                new['effective_from'] = values.get('effective_from')
            new['active'] = operation != 'DISABLE'
            no_parent = str(new.get('no_parent', '')).lower() in {'true', '1', 'yes'}
            new['no_parent'] = no_parent
            child = new.get('child_asin')
            if not child and new.get('sku') and self.source_adapter and all(new.get(field) for field in ('account_id', 'marketplace_id', 'effective_from')):
                candidates = self.source_adapter.resolve_sku(tenant, new['account_id'], new['marketplace_id'], new['sku'], new['effective_from'])
                if len(candidates) == 1:
                    child = new['child_asin'] = candidates[0]
                else:
                    issue('SKU_MAPPING_AMBIGUOUS' if candidates else 'SKU_MAPPING_UNRESOLVED')
            if not child:
                issue('CHILD_ASIN_REQUIRED_OR_SKU_UNRESOLVED')
            elif not ASIN.fullmatch(child):
                issue('CHILD_ASIN_INVALID')
            parent = new.get('parent_asin')
            if parent and not ASIN.fullmatch(parent):
                issue('PARENT_ASIN_INVALID')
            if (not parent and not no_parent) or (parent and no_parent):
                issue('PARENT_OR_EXPLICIT_NO_PARENT_REQUIRED')
            interval_valid = False
            try:
                start = date.fromisoformat(new.get('effective_from', ''))
                end = date.fromisoformat(new['effective_to']) if new.get('effective_to') else None
                if end and end < start:
                    issue('EFFECTIVE_INTERVAL_INVALID')
                else:
                    interval_valid = True
            except (ValueError, TypeError):
                issue('EFFECTIVE_DATE_INVALID')
            record_key = [new.get('account_id'), new.get('marketplace_id'), child, new.get('effective_from')]
            key = tuple(record_key)
            # Repeated child rows are listing links, not repeated financial-product subjects.
            main = {field: value for field, value in new.items() if field != 'sku'}
            if key in identities and identities[key] != main:
                issue('DUPLICATE_CHILD_CONFLICT')
            identities[key] = main
            if new.get('sku'):
                sku_key = (new.get('account_id'), new.get('marketplace_id'), new['sku'], new.get('effective_from'))
                if sku_key in sku_links and sku_links[sku_key] != child:
                    issue('SKU_MAPPING_CONFLICT')
                sku_links[sku_key] = child
            if interval_valid:
                scope = (new.get('account_id'), new.get('marketplace_id'))
                interval_keys = [('child',) + scope + (child,)]
                if new.get('sku'):
                    interval_keys.append(('sku',) + scope + (new['sku'],))
                for interval_key in interval_keys:
                    for previous, previous_start, previous_end in intervals.get(interval_key, []):
                        if start > (previous_end or date.max) or previous_start > (end or date.max):
                            continue
                        previous_main = {field: value for field, value in previous.items() if field not in {'sku', 'effective_from', 'effective_to'}}
                        current_main = {field: value for field, value in new.items() if field not in {'sku', 'effective_from', 'effective_to'}}
                        if interval_key[0] == 'child' and previous_main != current_main:
                            issue('CHILD_EFFECTIVE_INTERVAL_OVERLAP')
                        if interval_key[0] == 'sku' and child != previous.get('child_asin'):
                            issue('SKU_EFFECTIVE_INTERVAL_OVERLAP')
                    intervals.setdefault(interval_key, []).append((new, start, end))
            output.append({'line': line, 'record_key': record_key, 'old_values': old, 'new_values': new,
                           'changed_fields': sorted(modified if old else set(new)), 'expected_version': values.get('expected_version'),
                           'reason': values.get('reason'), 'errors': errors})
        return output

    def upload(self, tenant, user, file_name, csv_text, context, idempotency_key, parent_id=None, parent_if_match=None):
        self._identity(user)
        if not file_name.lower().endswith('.csv'):
            raise ChangeError(415, 'CSV_REQUIRED', 'Upload UTF-8 CSV; spreadsheet macros and formulas are not executed.')
        if len(csv_text.encode('utf-8')) > 1024 * 1024:
            raise ChangeError(413, 'UPLOAD_TOO_LARGE', 'Maximum CSV size is 1 MiB.')
        try:
            reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')), strict=True)
            if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or set(reader.fieldnames) - set(COLUMNS):
                raise ChangeError(422, 'CSV_HEADERS_INVALID', 'Unknown or repeated CSV columns.')
            raw_rows = []
            for row in reader:
                if len(raw_rows) >= 5000:
                    raise ChangeError(413, 'ROW_LIMIT_EXCEEDED', 'Maximum 5000 rows per upload.')
                if None in row or any(value is None for value in row.values()):
                    raise ChangeError(422, 'CSV_ROW_INVALID', f'CSV row {reader.line_num}: column count differs from the header.')
                raw_rows.append(row)
        except csv.Error as exc:
            raise ChangeError(422, 'CSV_INVALID', 'Malformed CSV.') from exc
        if not raw_rows:
            raise ChangeError(422, 'CSV_EMPTY', 'At least one business row is required.')
        if set(context) - set(COLUMNS):
            raise ChangeError(422, 'CONTEXT_INVALID', 'Only documented business fields may be prefilled.')
        request = {'file_name': file_name, 'csv_text': csv_text, 'context': context, 'parent_id': parent_id}
        with self.repository.transaction() as state:
            token, request_hash, cached = self._idempotent(state, tenant, user, 'upload', idempotency_key, request)
            if cached:
                return cached
            if parent_id:
                parent = self._batch(state, tenant, user, parent_id)
                self._cas(parent, parent_if_match)
                if parent['created_by'] != str(user['userId']) or parent['status'] not in {'REJECTED', 'VALIDATION_FAILED', 'CONFLICT', 'WITHDRAWN'}:
                    raise ChangeError(409, 'REVISION_NOT_ALLOWED', 'Create a revision only after rejection, conflict, validation failure or withdrawal.')
            content_hash = digest({'file_hash': hashlib.sha256(csv_text.encode()).hexdigest(), 'context': context, 'parent_id': parent_id})
            for batch in state['batches'].values():
                if batch['tenant_id'] == tenant and batch['created_by'] == str(user['userId']) and batch['content_hash'] == content_hash:
                    return self._remember(state, token, request_hash, self._view(batch, user))
            rows = self._validate(tenant, user, raw_rows, context)
            errors = sum(bool(row['errors']) for row in rows)
            batch = {'id': str(uuid4()), 'tenant_id': tenant, 'created_by': str(user['userId']),
                     'operator_code': user.get('operatorCode'), 'file_name': file_name, 'file_content': csv_text,
                     'file_hash': hashlib.sha256(csv_text.encode()).hexdigest(), 'content_hash': content_hash,
                     'rows_hash': digest(rows), 'row_count': len(rows), 'error_count': errors, 'rows': rows,
                     'status': 'VALIDATION_FAILED' if errors else 'READY', 'version': 1, 'created_at': now(),
                     'parent_id': parent_id, 'reviewer_id': None, 'review_reason': None,
                     'authoritative_apply_configured': False, 'audit': []}
            batch['audit'].append({'action': 'UPLOADED_AND_VALIDATED', 'actor': str(user['userId']), 'at': now(), 'rows_hash': batch['rows_hash']})
            state['batches'][batch['id']] = batch
            return self._remember(state, token, request_hash, self._view(batch, user))

    def list(self, tenant, user, cursor=0, limit=50):
        self._identity(user)
        with self.repository.transaction() as state:
            batches = [batch for batch in state['batches'].values() if batch['tenant_id'] == tenant and
                       (batch['created_by'] == str(user['userId']) or user.get('roleCode') in MANAGEMENT)]
            batches.sort(key=lambda batch: (batch['created_at'], batch['id']), reverse=True)
            return {'items': [self._view(batch, user) for batch in batches[cursor:cursor + limit]],
                    'next_cursor': str(cursor + limit) if len(batches) > cursor + limit else None}

    def get(self, tenant, user, batch_id):
        with self.repository.transaction() as state:
            return self._view(self._batch(state, tenant, user, batch_id), user)

    def rows(self, tenant, user, batch_id, cursor=0, limit=50):
        with self.repository.transaction() as state:
            batch = self._batch(state, tenant, user, batch_id)
            return {'items': copy.deepcopy(batch['rows'][cursor:cursor + limit]),
                    'next_cursor': str(cursor + limit) if len(batch['rows']) > cursor + limit else None}

    def command(self, tenant, user, batch_id, action, payload, if_match, idempotency_key):
        with self.repository.transaction() as state:
            batch = self._batch(state, tenant, user, batch_id)
            token, request_hash, cached = self._idempotent(state, tenant, user, [batch_id, action], idempotency_key, payload)
            if cached:
                return cached
            self._cas(batch, if_match)
            owner = batch['created_by'] == str(user['userId'])
            if action == 'submit':
                if not owner:
                    raise ChangeError(403, 'OWNER_REQUIRED', 'Only the submitter may submit this proposal.')
                if batch['status'] != 'READY':
                    raise ChangeError(409, 'BATCH_NOT_READY', 'All rows must pass validation before submission.')
                batch['status'] = 'SUBMITTED'
            elif action == 'withdraw':
                if not owner:
                    raise ChangeError(403, 'OWNER_REQUIRED', 'Only the submitter may withdraw this proposal.')
                if batch['status'] not in {'READY', 'VALIDATION_FAILED', 'SUBMITTED'}:
                    raise ChangeError(409, 'WITHDRAW_NOT_ALLOWED', 'This proposal can no longer be withdrawn.')
                batch['status'] = 'WITHDRAWN'
            elif action == 'decision':
                if user.get('roleCode') not in MANAGEMENT or owner:
                    raise ChangeError(403, 'INDEPENDENT_REVIEWER_REQUIRED', 'A different authorized manager must review the proposal.')
                if batch['status'] not in {'SUBMITTED', 'UNDER_REVIEW'}:
                    raise ChangeError(409, 'REVIEW_NOT_ALLOWED', 'This proposal is not awaiting review.')
                if payload.get('content_hash') != batch['content_hash']:
                    raise ChangeError(409, 'CONTENT_HASH_MISMATCH', 'Reviewed content does not match this proposal.')
                if not str(payload.get('reason', '')).strip() or payload.get('decision') not in {'APPROVE', 'REJECT'}:
                    raise ChangeError(422, 'DECISION_INVALID', 'An APPROVE or REJECT decision and a reason are required.')
                batch['status'] = 'APPROVED_PENDING_APPLY' if payload['decision'] == 'APPROVE' else 'REJECTED'
                batch['reviewer_id'], batch['review_reason'] = str(user['userId']), payload['reason'].strip()
            elif action == 'apply':
                # No staging record can become effective without an integrated, atomic authority adapter.
                if user.get('roleCode') not in MANAGEMENT:
                    raise ChangeError(403, 'APPLY_SERVICE_REQUIRED', 'Only the controlled application service can apply changes.')
                raise ChangeError(409, 'AUTHORITATIVE_APPLY_NOT_CONFIGURED', 'Approved proposals remain pending; no effective mapping or historical result has been changed.')
            else:
                raise ChangeError(400, 'ACTION_INVALID', 'Unknown action.')
            batch['version'] += 1
            batch['audit'].append({'action': action.upper(), 'actor': str(user['userId']), 'at': now(),
                                   'content_hash': batch['content_hash'], 'reason': payload.get('reason'), 'version': batch['version']})
            return self._remember(state, token, request_hash, self._view(batch, user))

    def impact(self, tenant, user, batch_id):
        with self.repository.transaction() as state:
            batch = self._batch(state, tenant, user, batch_id)
            return {'batch_id': batch_id, 'accounts': sorted({row['new_values'].get('account_id', '') for row in batch['rows']}),
                    'product_codes': sorted({row['new_values'].get('product_code', '') for row in batch['rows']}),
                    'effective_from': sorted({row['new_values'].get('effective_from', '') for row in batch['rows']}),
                    'historical_results_changed': False, 'run_impact': None,
                    'reason': 'AUTHORITATIVE_IMPACT_ADAPTER_NOT_CONFIGURED', 'requires_new_snapshot': True}
