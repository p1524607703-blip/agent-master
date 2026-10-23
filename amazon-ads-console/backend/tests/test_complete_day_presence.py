"""Exercise real PostgreSQL presence semantics using VALUES, never fact tables."""
import json
import os
import re
import subprocess
from unittest.mock import patch

import pytest

from app.services import operator_cpo as service


def fixture_sql():
    child, parent, ads, purchases = [], [], [], []
    for day in range(1, 10):
        date = f"DATE '2026-09-{day:02}'"
        for index, account in enumerate(service.BUSINESS_ACCOUNTS):
            value = service._sql_names((account,))
            if day in (1,4,5,7) or (day in (2,3) and index < len(service.BUSINESS_ACCOUNTS)-1) or (day in (8,9) and index > 0):
                child.append(f'({date},{value})')
            if day in (3,9) or (day == 2 and index == len(service.BUSINESS_ACCOUNTS)-1):
                parent.append(f'({date},{date},{value})')
            if day == 6:
                parent.append(f"({date},DATE '2026-09-07',{value})")
        for index, account in enumerate(service.AD_ACCOUNTS):
            value = service._sql_names((account,))
            batch = 3 if day == 4 and index == len(service.AD_ACCOUNTS)-1 else 1
            ads.append(f'({date},{value},{batch})')
            if day == 7:
                ads.append(f'({date},{value},{batch})')
            if not (day == 5 and index == len(service.AD_ACCOUNTS)-1):
                purchases.append(f'({date},{value},2)')
    return ','.join([
        'fixture_child(stat_date,account_name) AS (VALUES '+','.join(child)+')',
        'fixture_parent(report_start_date,report_end_date,account_name) AS (VALUES '+','.join(parent)+')',
        'fixture_ads(stat_date,account_name,batch_id) AS (VALUES '+','.join(ads)+')',
        'fixture_purchases(stat_date,account_name,batch_id) AS (VALUES '+','.join(purchases)+')',
        "fixture_batches(batch_id,target_table) AS (VALUES (1,'core.report_advertised_product_daily'),(2,'core.report_purchased_product_daily'),(3,'wrong_source'))",
    ])


@pytest.mark.skipif(not os.getenv('CPO_SQL_TEST_SSH'), reason='Optional readonly PostgreSQL fixture execution')
def test_complete_days_preserve_child_parent_fallback_and_canonical_sources():
    statements = []
    replacements = {
        'core.report_business_child_asin_daily':'fixture_child',
        'core.report_business_parent_asin_period':'fixture_parent',
        'core.report_advertised_product_daily':'fixture_ads',
        'core.report_purchased_product_daily':'fixture_purchases',
        'core.import_batches':'fixture_batches',
    }
    for start,end in ((None,None),('2026-09-04','2026-09-07')):
        captured = []
        with patch.object(service,'query_rows',side_effect=lambda sql: captured.append(sql) or []):
            service._complete_days_uncached(start,end)
        query = captured[0].strip().removeprefix('WITH')
        for source,target in replacements.items():
            query = re.sub(r'\b(FROM|JOIN)\s+'+re.escape(source)+r'\b',lambda m:m[1]+' '+target,query)
        # Only CTE fixtures can be table references; source names in string
        # literals intentionally remain unchanged to test canonical lineage.
        assert not re.search(r'\b(?:FROM|JOIN)\s+core\.',query)
        statements.append("SELECT coalesce(json_agg(q.d ORDER BY q.d),'[]'::json)::text FROM (WITH "+fixture_sql()+','+query+') q;')
    sql="BEGIN READ ONLY; SET LOCAL statement_timeout='5s';\n"+'\n'.join(statements)+'\nROLLBACK;'
    result=subprocess.run(['ssh','-o','BatchMode=yes',os.environ['CPO_SQL_TEST_SSH'],
        'sudo -u postgres psql -X -q -t -A -v ON_ERROR_STOP=1 -d amazon_ads_v2'],
        input=sql,text=True,capture_output=True,check=True,timeout=20)
    actual=[json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    assert actual == [['2026-09-01','2026-09-03','2026-09-07','2026-09-09'],['2026-09-07']]
