#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成「按 account_id LIST 分区」的 DDL，覆盖 5 事实表 + 5 快照表。
列定义直接从 loader 的 SPECS/TABLES/SNAPSHOT 导入，避免手写漂移。
每个表 = 4 个具名分区(川鹏/欧德思/洁博利/AMS) + 1 个 default 分区(兜底未登记账户)。
PK 含 account_id(=分区键)，故 loader 的 COPY+upsert / 快照 INSERT...ON CONFLICT 照常工作。
"""
import importlib.util, os

LOADER = "/Users/panjinlong/Documents/agent-master/ad-reports-export/subscribed_reports_to_rds.py"
spec = importlib.util.spec_from_file_location("loader", LOADER)
L = importlib.util.module_from_spec(spec)
spec.loader.exec_module(L)

TYPEMAP = {'id': 'text', 'date': 'date', 'num': 'numeric', 'text': 'text'}

ACCOUNTS = {
    'chuanpeng': 'amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh',
    'oudesi':    'amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919',
    'jieboli':   'amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh',
    'ams':       'amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz',
}

def col_sql(cols):
    return ', '.join('%s %s' % (en, TYPEMAP[typ]) for (cn, en, typ) in cols)

out = []
out.append("-- 按 account_id LIST 分区的 5 事实表 + 5 快照表")
out.append("-- 生成器: gen_partitioned_ddl.py (列定义导入 loader, 防漂移)")
out.append("")

# ---- 事实表 ----
for ptype, (table, pk) in L.TABLES.items():
    cols = L.SPECS[ptype]
    full = [(cn, en, typ) for (cn, en, typ) in cols] + \
           [('source_file_name', 'source_file_name', 'text'),
            ('source_file_hash', 'source_file_hash', 'text')]
    out.append("DROP TABLE IF EXISTS %s CASCADE;" % table)
    out.append("CREATE TABLE %s (\n  %s,\n  PRIMARY KEY (%s)\n) PARTITION BY LIST (account_id);"
               % (table, col_sql(full), ', '.join(pk)))
    for short, aid in ACCOUNTS.items():
        out.append("CREATE TABLE %s_p_%s PARTITION OF %s FOR VALUES IN ('%s');"
                   % (table, short, table, aid))
    out.append("CREATE TABLE %s_p_default PARTITION OF %s DEFAULT;" % (table, table))
    out.append("")

# ---- 快照表 ----
for ptype, (stable, fact_cols, snap_pk) in L.SNAPSHOT.items():
    cols = L.SPECS[ptype]
    snap_cols = [('snapshot_date', 'snapshot_date', 'date'), ('run_id', 'run_id', 'text')] + \
                [(cn, en, typ) for (cn, en, typ) in cols]
    pk_sql = ', '.join(['snapshot_date'] + snap_pk)
    out.append("DROP TABLE IF EXISTS %s CASCADE;" % stable)
    out.append("CREATE TABLE %s (\n  %s,\n  PRIMARY KEY (%s)\n) PARTITION BY LIST (account_id);"
               % (stable, col_sql(snap_cols), pk_sql))
    for short, aid in ACCOUNTS.items():
        out.append("CREATE TABLE %s_p_%s PARTITION OF %s FOR VALUES IN ('%s');"
                   % (stable, short, stable, aid))
    out.append("CREATE TABLE %s_p_default PARTITION OF %s DEFAULT;" % (stable, stable))
    out.append("")

sql = '\n'.join(out)
dst = "/Users/panjinlong/Documents/agent-master/ad-reports-export/sql/partitioned_tables.sql"
open(dst, 'w').write(sql)
print("wrote", dst, "bytes=", len(sql), "lines=", sql.count(chr(10)))
