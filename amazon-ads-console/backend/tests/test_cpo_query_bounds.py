import asyncio
from datetime import date, timedelta
import os
import random
import subprocess
import time
import unittest
from unittest.mock import patch

import asyncpg

from app.services import app_db, operator_cpo, rds_query


class QueryDeadlineTests(unittest.TestCase):
    def test_server_deadline_precedes_client_deadline_and_retains_other_options(self):
        original = {'PGOPTIONS': '-c search_path=core', 'PGPASSWORD': 'fixture'}
        bounded = rds_query.bounded_query_env(original)
        self.assertEqual(original['PGOPTIONS'], '-c search_path=core')
        self.assertEqual(bounded['PGOPTIONS'], '-c search_path=core -c statement_timeout=28000')
        self.assertEqual(bounded['PGPASSWORD'], 'fixture')


@unittest.skipUnless(os.environ.get('CPO_QUERY_TEST_SOCKET'), 'requires disposable PostgreSQL fixture')
class CompleteDaysIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.socket = os.environ['CPO_QUERY_TEST_SOCKET']
        if not cls.socket.startswith('/tmp/cpo-query-'):
            raise RuntimeError('Refusing to test against a non-isolated database')
        cls.user = os.environ['USER']
        cls.psql = os.environ['CPO_QUERY_TEST_PSQL']
        cls.execute('''CREATE SCHEMA core;
          CREATE TABLE core.import_batches(batch_id bigint PRIMARY KEY,target_table text);
          CREATE TABLE core.report_business_child_asin_daily(account_name text,stat_date date);
          CREATE TABLE core.report_business_parent_asin_period(account_name text,report_start_date date,report_end_date date);
          CREATE TABLE core.report_advertised_product_daily(account_name text,stat_date date,batch_id bigint);
          CREATE TABLE core.report_purchased_product_daily(account_name text,stat_date date,batch_id bigint);
          INSERT INTO core.import_batches VALUES (1,'core.report_advertised_product_daily'),
            (2,'core.report_purchased_product_daily'),(3,'wrong-table');''')

    @classmethod
    def execute(cls, sql, args=(), fetch=False):
        async def run():
            c = await asyncpg.connect(host=cls.socket, user=cls.user, database='postgres')
            try:
                return [dict(r) for r in await c.fetch(sql, *args)] if fetch else await c.execute(sql, *args)
            finally:
                await c.close()
        return asyncio.run(run())

    def setUp(self):
        self.execute('TRUNCATE core.report_business_child_asin_daily,core.report_business_parent_asin_period,core.report_advertised_product_daily,core.report_purchased_product_daily')

    def result(self, start=None, end=None):
        with patch.object(operator_cpo, 'query_rows', side_effect=lambda sql: self.execute(sql, fetch=True)):
            return operator_cpo._complete_days_uncached(start, end)

    def test_randomized_missing_accounts_duplicates_invalid_batches_and_parent_fallback(self):
        rng = random.Random(82471)
        expected = []
        sql = []
        for i in range(75):
            d = (date(2026, 1, 1) + timedelta(days=i)).isoformat()
            child, parent, advertised, purchased = [
                [rng.random() < .85 for _ in accounts] for accounts in
                [operator_cpo.BUSINESS_ACCOUNTS, operator_cpo.BUSINESS_ACCOUNTS,
                 operator_cpo.AD_ACCOUNTS, operator_cpo.AD_ACCOUNTS]]
            if (all(child) or all(parent)) and all(advertised) and all(purchased):
                expected.append(d)
            for name, valid in zip(operator_cpo.BUSINESS_ACCOUNTS, child):
                if valid:
                    sql.append(f"INSERT INTO core.report_business_child_asin_daily VALUES ('{name}','{d}'),('{name}','{d}');")
            for name, valid in zip(operator_cpo.BUSINESS_ACCOUNTS, parent):
                end = d if valid else (date.fromisoformat(d)+timedelta(days=1)).isoformat()
                sql.append(f"INSERT INTO core.report_business_parent_asin_period VALUES ('{name}','{d}','{end}');")
            for table, flags, batch in [('advertised', advertised, 1), ('purchased', purchased, 2)]:
                for name, valid in zip(operator_cpo.AD_ACCOUNTS, flags):
                    # Foreign and wrong-table batches cannot make an account complete.
                    sql.append(f"INSERT INTO core.report_{table}_product_daily VALUES ('{name}','{d}',3),('{name}','{d}',999),('{name}','{d}',NULL);")
                    if valid:
                        sql.append(f"INSERT INTO core.report_{table}_product_daily VALUES ('{name}','{d}',{batch}),('{name}','{d}',{batch});")
        self.execute(''.join(sql))
        self.assertGreater(len(expected), 0)
        self.assertEqual(self.result(), expected)
        self.assertEqual(self.result('2026-01-13','2026-02-18'), [d for d in expected if '2026-01-13' <= d <= '2026-02-18'])
        self.assertEqual(self.result('2026-02-18','2026-01-13'), [])

    def test_empty_or_unrelated_accounts_never_create_complete_dates(self):
        self.assertEqual(self.result(), [])
        self.execute("INSERT INTO core.report_business_child_asin_daily VALUES ('unrelated','2026-01-01');")
        self.assertEqual(self.result(), [])

    def test_server_cancels_both_channels_before_their_client_exits(self):
        env = {'PGHOST': self.socket, 'PGPORT': '5432', 'PGUSER': self.user, 'PGDATABASE': 'postgres',
               'RDS_PGHOST': self.socket, 'RDS_PGPORT': '5432', 'RDS_PGUSER': self.user, 'RDS_PGDATABASE': 'postgres'}
        original = subprocess.run
        def local_psql(args, **kwargs):
            return original([self.psql, *args[1:]], **kwargs)
        with patch.dict(os.environ, env), patch.object(rds_query, 'STATEMENT_TIMEOUT_MS', 100), patch.object(subprocess, 'run', side_effect=local_psql):
            for module in [rds_query, app_db]:
                started = time.monotonic()
                with self.assertRaises(rds_query.DatabaseQueryError):
                    module._run('SELECT pg_sleep(3) /* cpo_timeout_fixture */')
                self.assertLess(time.monotonic()-started, 2)
        active = self.execute("SELECT pid FROM pg_stat_activity WHERE state='active' AND pid<>pg_backend_pid() AND query LIKE '%cpo_timeout_fixture%'", fetch=True)
        self.assertEqual(active, [])


if __name__ == '__main__':
    unittest.main()
