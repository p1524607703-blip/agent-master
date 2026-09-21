from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'backend'))
import run_rds  # noqa: E402,F401  - loads PG* application DB settings
from app.services.app_db import query_rows  # noqa: E402

SOURCE = ROOT / 'reference' / 'product_mapping' / '全部账户_运营产品标准映射表.csv'
EVIDENCE = 'reference/product_mapping/全部账户_运营产品标准映射表.csv'


def q(value: str | None) -> str:
    if value is None:
        return 'NULL'
    return "'" + str(value).replace("'", "''") + "'"


def app_exec(sql: str) -> str:
    proc = subprocess.run(
        ['psql', '-h', os.environ['PGHOST'], '-p', os.environ['PGPORT'], '-U', os.environ['PGUSER'], '-d', os.environ['PGDATABASE'],
         '-X', '-q', '-t', '-A', '-v', 'ON_ERROR_STOP=1', '-c', sql],
        env=os.environ.copy(), capture_output=True, text=True, timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or 'app db write failed')
    return proc.stdout.strip()


def load_candidates() -> tuple[list[dict], dict]:
    rows = list(csv.DictReader(SOURCE.open(encoding='utf-8-sig', newline='')))
    parent_rows: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get('当前状态') != '当前业务报告已命中':
            continue
        for parent in [x.strip() for x in (row.get('父ASIN') or '').split('|') if x.strip()]:
            parent_rows[parent].append(row)

    conflicts = {}
    candidates = []
    for parent, rs in parent_rows.items():
        identities = {(r.get('产品代号') or '', r.get('运营组') or '') for r in rs}
        if len(identities) != 1:
            conflicts[parent] = sorted(identities)
            continue
        row = rs[0]
        candidates.append({
            'parent_asin': parent,
            'product_code': (row.get('产品代号') or '').strip(),
            'owner_group': (row.get('运营组') or '').strip(),
            'operator_name': (row.get('运营姓名') or '').strip(),
            'business_account': (row.get('业务账户') or '').strip(),
            'ad_account': (row.get('广告账户') or '').strip(),
        })
    return candidates, {'source_rows': len(rows), 'candidate_parents': len(candidates), 'source_conflicts': conflicts}


def main() -> int:
    parser = argparse.ArgumentParser(description='Idempotently restore explicit parent-ASIN CPO mappings into amazon_ads.app.asin_parent_map.')
    parser.add_argument('--apply', action='store_true', help='Write non-conflicting mappings. Default is dry-run.')
    args = parser.parse_args()

    candidates, audit = load_candidates()
    existing = {r['parent_asin']: r for r in query_rows(
        "SELECT parent_asin,product_code,owner_group,status,evidence FROM app.asin_parent_map ORDER BY parent_asin"
    )}
    before = len(existing)
    inserts = []
    same = []
    db_conflicts = []
    for row in candidates:
        old = existing.get(row['parent_asin'])
        if old:
            if (old.get('product_code') or '') == row['product_code'] and (old.get('owner_group') or '') == row['owner_group']:
                same.append(row['parent_asin'])
            else:
                db_conflicts.append({
                    'parent_asin': row['parent_asin'],
                    'existing_product': old.get('product_code'), 'incoming_product': row['product_code'],
                    'existing_group': old.get('owner_group'), 'incoming_group': row['owner_group'],
                })
            continue
        inserts.append(row)

    result = {
        **audit, 'before_count': before, 'already_same': len(same),
        'pending_insert': len(inserts), 'db_conflicts': db_conflicts, 'applied': bool(args.apply),
    }
    if args.apply and inserts:
        values = []
        for r in inserts:
            evidence = f"{EVIDENCE}; business={r['business_account']}; ad={r['ad_account']}; operator={r['operator_name']}"
            values.append('(' + ','.join([
                q(r['parent_asin']), q(r['product_code']), 'NULL', q(r['owner_group']), 'NULL',
                q('standard_mapping'), q('high'), q('confirmed'), q(evidence), 'NULL', 'NULL',
                'now()', q('cpo_mapping_sync'), 'now()'
            ]) + ')')
        sql = "INSERT INTO app.asin_parent_map (parent_asin,product_code,brand,owner_group,child_asin,match_signal,confidence,status,evidence,conflict,source_title,built_at,verified_by,verified_at) VALUES " + ','.join(values) + " ON CONFLICT (parent_asin) DO NOTHING;"
        app_exec(sql)
    after = query_rows("SELECT count(*)::int n FROM app.asin_parent_map")[0]['n']
    result['after_count'] = after
    result['inserted_now'] = after - before
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not db_conflicts and not audit['source_conflicts'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
