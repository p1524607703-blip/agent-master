#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 business-report/out 下的「按父商品」业务报告 CSV 载入 RDS（amazon_ads_v2）。

目标表：
    core.report_business_parent_asin_period
    唯一键 (account_id, report_start_date, report_end_date, parent_asin)
    → 按期间存储：单日存 (D, D)，周快照存 (周一, 周日)，靠 start/end 区分，互不覆盖。
    另有兼容视图 core.business_report_parent_asin_period 指向它（旧名仍可解析）。

设计要点
- 幂等两重：① import_batches.file_hash 唯一，同一文件不重复导；② 目标表 ON CONFLICT DO UPDATE，
  Amazon 回溯修正数据时会被更新（而不是静默丢弃）。
- 默认不做 DDL（表不存在会直接报错，不擅自改生产库）；首次建表用 `--init-ddl`。
- 数值清洗：千分符 / "US$" 前缀 / 百分号全部剥掉，非法值落 NULL 并计数告警。
- 连接从 amazon-ads-console/backend/.env 的 RDS_DATABASE_URL 读（指向 amazon_ads_v2），
  脚本里不出现任何凭据。

用法
    python3 br_to_rds.py --init-ddl         # 首次：建表（幂等）
    python3 br_to_rds.py                    # 导入 out/ 下全部 CSV
    python3 br_to_rds.py --file out/xx.csv  # 单个文件
    python3 br_to_rds.py --dry-run          # 只解析校验, 不写库
    python3 br_to_rds.py --force            # 忽略 file_hash 去重, 强制重导
"""
import os, re, sys, csv, io, json, hashlib, subprocess, argparse, datetime
from urllib.parse import parse_qs, unquote, urlsplit

HERE  = os.path.dirname(os.path.abspath(__file__))
REPO  = os.path.dirname(HERE)
ENV_PATH = os.path.join(REPO, 'amazon-ads-console', 'backend', '.env')
OUT   = os.path.join(HERE, 'out')
DDL_SQL = os.path.join(HERE, 'sql', '004_business_report_table.sql')
TARGET_TABLE = 'core.report_business_parent_asin_period'


def _init_env():
    """从 backend/.env 读 RDS_DATABASE_URL（数据仓库），导出 PG* 供 psql 子进程继承。"""
    if not os.path.isfile(ENV_PATH):
        raise SystemExit(f'找不到 {ENV_PATH}')
    dsn = ''
    for line in open(ENV_PATH, encoding='utf-8'):
        if line.startswith('RDS_DATABASE_URL='):
            dsn = line.split('=', 1)[1].strip()
            break
    if not dsn:
        raise SystemExit('backend/.env 里没有 RDS_DATABASE_URL')
    p = urlsplit(dsn)
    q = parse_qs(p.query)
    os.environ['PGHOST'] = p.hostname or ''
    os.environ['PGPORT'] = str(p.port or 5432)
    os.environ['PGUSER'] = unquote(p.username or '')
    os.environ['PGPASSWORD'] = unquote(p.password or '')
    os.environ['PGDATABASE'] = p.path.lstrip('/')
    if q.get('sslmode'):
        os.environ['PGSSLMODE'] = q['sslmode'][-1]
    if q.get('sslrootcert'):
        os.environ['PGSSLROOTCERT'] = q['sslrootcert'][-1]
    os.environ['PGCONNECT_TIMEOUT'] = '20'


_init_env()
PGHOST = os.environ['PGHOST']
PGPORT = os.environ['PGPORT']
PGUSER = os.environ['PGUSER']
PGDB   = os.environ['PGDATABASE']

# 紫鸟店铺名 -> (Amazon 广告账户 ID, 账户名)。取自 core.report_business_parent_asin_period 存量。
STORE_MAP = {
    '川鹏2号':   ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh', 'WHITIN'),
    '欧德思美站': ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919', 'BLOOMNEXT'),
    '洁博利美站': (None, None),   # 无业务报告权限, 命中则跳过
}

# CSV 中文表头 -> 目标列
COL_MAP = {
    '（父）ASIN':            'parent_asin',
    '标题':                  'title',
    '会话数 - 总计':          'sessions_total',
    '会话 - 总计 - B2B':      'sessions_b2b',
    '转化率 - 移动应用 - B2B': 'mobile_app_conversion_rate_b2b_pct',
    '会话百分比 - 移动应用':   'mobile_app_session_pct',
    '会话百分比 - 浏览器':     'browser_session_pct',
    '会话百分比 - 浏览器 - B2B': 'browser_session_b2b_pct',
    '已订购商品数量':          'ordered_product_units',
    '已订购商品数量 - B2B':    'ordered_product_units_b2b',
    '商品会话百分比':          'unit_session_pct',
    '商品会话百分比 - B2B':    'unit_session_b2b_pct',
    '已订购商品销售额':        'ordered_product_sales',
    '已订购商品销售额 - B2B':  'ordered_product_sales_b2b',
    '订单商品总数':            'total_order_items',
    '订单商品总数 - B2B':      'total_order_items_b2b',
}
ORDER = ['parent_asin', 'title', 'sessions_total', 'sessions_b2b',
         'mobile_app_conversion_rate_b2b_pct', 'mobile_app_session_pct',
         'browser_session_pct', 'browser_session_b2b_pct',
         'ordered_product_units', 'ordered_product_units_b2b',
         'unit_session_pct', 'unit_session_b2b_pct',
         'ordered_product_sales', 'ordered_product_sales_b2b',
         'total_order_items', 'total_order_items_b2b']
INT_COLS = {'sessions_total', 'sessions_b2b', 'ordered_product_units',
            'ordered_product_units_b2b', 'total_order_items', 'total_order_items_b2b'}
NUM_COLS = {'mobile_app_conversion_rate_b2b_pct', 'mobile_app_session_pct',
            'browser_session_pct', 'browser_session_b2b_pct',
            'unit_session_pct', 'unit_session_b2b_pct',
            'ordered_product_sales', 'ordered_product_sales_b2b'}
REPORT_TYPE = 'report_business_parent_asin_period'
TABLE = TARGET_TABLE

def q(v):
    """SQL 字面量转义。psql -c 模式下 :variable 插值不生效, 只能在 Python 侧拼字面量。"""
    if v is None:
        return 'NULL'
    return "'" + str(v).replace("'", "''") + "'"

def psql(sql, tuples_only=True):
    args = ['psql', '-h', PGHOST, '-p', str(PGPORT), '-U', PGUSER, '-d', PGDB,
            '-v', 'ON_ERROR_STOP=1']
    # 注意: 不能写成 '-tAc' —— 其中 c 会被当成 -c 选项并把后续参数当 SQL 吞掉, 必须分开写
    if tuples_only:
        args += ['-t', '-A']
    # 注意: psql 的位置参数是 dbname, SQL 必须用 -c / -f 传, 否则会被当成库名
    if sql.startswith('@'):
        args += ['-f', sql[1:]]
    else:
        args += ['-c', sql]
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'psql 失败: {r.stderr.strip()[:400]}')
    return r.stdout.strip()

def clean_number(v, col):
    """剥掉千分符 / US$ / 百分号; 非法值返回 '' (NULL)"""
    s = (v or '').strip().replace('﻿', '')
    if s == '' or s in ('--', '-', 'N/A', 'n/a'):
        return ''
    s = s.replace(',', '').replace('%', '')
    s = re.sub(r'^(US\$|US|\$|USD\s*)', '', s, flags=re.I).strip()
    if s == '' or s.lower() in ('nan', 'inf'):
        return ''
    try:
        if col in INT_COLS:
            int(round(float(s)))
        else:
            float(s)
    except ValueError:
        return ''
    return s

def parse_name(fn):
    """BR_<店铺>_daily_<YYYY-MM-DD>.csv / BR_<店铺>_weekly_<YYYYMMDD>-<YYYYMMDD>.csv"""
    m = re.match(r'^BR_(.+)_daily_(\d{4}-\d{2}-\d{2})\.csv$', fn)
    if m:
        return m.group(1), m.group(2), m.group(2), 'daily'
    m = re.match(r'^BR_(.+)_weekly_(\d{8})-(\d{8})\.csv$', fn)
    if m:
        s, e = m.group(2), m.group(3)
        f = f'{s[:4]}-{s[4:6]}-{s[6:]}'
        t = f'{e[:4]}-{e[4:6]}-{e[6:]}'
        return m.group(1), f, t, 'weekly'
    return None

def load_one(path, dry=False, force=False):
    fn = os.path.basename(path)
    meta = parse_name(fn)
    if not meta:
        return {'file': fn, 'status': 'skipped', 'reason': '文件名不符合命名规范'}
    store, start, end, kind = meta
    if store not in STORE_MAP:
        return {'file': fn, 'status': 'skipped', 'reason': f'未知店铺 {store}'}
    acc_id, acc_name = STORE_MAP[store]
    if not acc_id:
        return {'file': fn, 'status': 'skipped', 'reason': f'{store} 未配置 account_id(无权限?)'}

    raw = open(path, 'rb').read()
    fhash = hashlib.sha256(raw).hexdigest()
    text = raw.decode('utf-8-sig')

    rdr = csv.reader(io.StringIO(text))
    header = next(rdr)
    header = [h.strip().replace('﻿', '') for h in header]
    missing = [h for h in COL_MAP if h not in header]
    if missing:
        return {'file': fn, 'status': 'failed', 'reason': f'CSV 缺少列: {missing}'}
    idx = {COL_MAP[h]: header.index(h) for h in COL_MAP}

    rows, bad_cells, padded_titles = [], 0, 0
    for r in rdr:
        if not any(c.strip() for c in r):
            continue
        if len(r) < len(header):
            r = r + [''] * (len(header) - len(r))
        out = [acc_id, acc_name, start, end]
        pasin = r[idx['parent_asin']].strip()
        for col in ORDER:
            v = r[idx[col]].strip()
            if col == 'title' and not v:
                # 目标表 title NOT NULL; 少数父 ASIN 无标题(下架/未维护), 用 ASIN 回填而不是丢行
                v = pasin
                padded_titles += 1
            if col in ('parent_asin', 'title'):
                out.append(v)
            else:
                c = clean_number(v, col)
                if v and not c:
                    bad_cells += 1
                out.append(c)
        rows.append(out)

    if not rows:
        return {'file': fn, 'status': 'failed', 'reason': 'CSV 无数据行'}

    res = {'file': fn, 'store': store, 'account': acc_name, 'start': start, 'end': end,
           'kind': kind, 'rows': len(rows), 'bad_cells': bad_cells, 'hash': fhash[:12]}

    if dry:
        res['status'] = 'dry-run'
        return res

    # 幂等: 同一文件内容已导过就跳过
    if not force:
        exist = psql("SELECT batch_id || '|' || import_status FROM core.import_batches "
                     f"WHERE file_hash={q(fhash)}")
        if exist:
            bid_old, st_old = (exist.split('|') + [''])[:2]
            if st_old == 'processing':
                # 上次导入中途失败留下的孤儿批次(无数据行), 清掉重导, 否则会被永久跳过
                psql(f"DELETE FROM core.import_batches WHERE batch_id={bid_old}")
                res['note'] = f'清理孤儿批次 {bid_old}(processing)'
            else:
                res['status'] = 'skipped'
                res['reason'] = f'已导入过 (batch {bid_old}, {st_old})'
                return res

    # 1) 建批次
    bid = psql(f"""
        INSERT INTO core.import_batches
          (file_name, file_hash, source_path, report_type, report_start_date, report_end_date,
           exported_at, export_time_source, source_row_count, valid_row_count, failed_row_count,
           import_status, metadata)
        VALUES ({q(fn)}, {q(fhash)}, {q(path)}, {q(REPORT_TYPE)}, {q(start)}::date, {q(end)}::date,
                now(), 'filename', {len(rows)}, 0, 0, 'processing', {q(json.dumps({
                    'store': store, 'account_name': acc_name, 'kind': kind,
                    'bad_cells': bad_cells}))}::jsonb)
        RETURNING batch_id
    """)
    # psql 即使 -t -A 也会在结果后附带命令标签(如 "INSERT 0 1"), 只取第一行
    bid = (bid or '').strip().splitlines()[0].strip()
    if not bid.isdigit():
        raise RuntimeError(f'batch_id 解析异常: {bid!r}')

    # 2) 一个会话内: 建临时表 -> \copy -> upsert -> 回写批次
    # 落临时 CSV 再 \copy FROM '文件': 比 \copy FROM STDIN 稳, 不受 -f 脚本模式下终止符解析的坑影响
    tmp_csv = f"/tmp/_br_import_{bid}.csv"
    with open(tmp_csv, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL, lineterminator='\n')
        w.writerow(['account_id', 'account_name', 'report_start_date', 'report_end_date'] + ORDER)
        w.writerows(rows)

    cols = ['account_id', 'account_name', 'report_start_date', 'report_end_date'] + ORDER
    def cast_expr(c):
        # 注意: 别在单引号 f-string 里写 '' , 会被吞掉变成空参数; 这里用双引号包裹, 内层单引号安全
        if c in INT_COLS:
            return f"nullif(btrim({c}), '')::bigint"
        if c in NUM_COLS:
            return f"nullif(btrim({c}), '')::numeric"
        return f'btrim({c})'

    set_clause = ',\n              '.join(
        f'{c} = EXCLUDED.{c}' for c in ORDER if c != 'parent_asin')
    sql = f"""
CREATE TEMP TABLE br_import ({', '.join(c + ' text' for c in cols)});
\\copy br_import FROM '{tmp_csv}' CSV HEADER

DO $$
DECLARE n int;
BEGIN
  INSERT INTO {TABLE}
    (account_id, account_name, report_start_date, report_end_date, {', '.join(ORDER)},
     currency_code, source_batch_id)
  SELECT btrim(account_id), account_name, report_start_date::date, report_end_date::date,
         {', '.join(cast_expr(c) for c in ORDER)},
         'USD', {bid}::bigint
  FROM br_import
  WHERE btrim(parent_asin) <> ''
  ON CONFLICT (account_id, report_start_date, report_end_date, parent_asin)
  DO UPDATE SET {set_clause},
                source_batch_id = EXCLUDED.source_batch_id,
                updated_at = now();
  GET DIAGNOSTICS n = ROW_COUNT;
  UPDATE core.import_batches
     SET valid_row_count = n, failed_row_count = {len(rows)} - n,
         import_status = CASE WHEN n = 0 THEN 'failed' WHEN n < {len(rows)} THEN 'partial' ELSE 'success' END
   WHERE batch_id = {bid}::bigint;
END $$;
SELECT import_status || '|' || valid_row_count FROM core.import_batches WHERE batch_id = {bid}::bigint;
"""
    tf = '/tmp/_br_import_%s.sql' % bid
    with open(tf, 'w', encoding='utf-8') as f:
        f.write(sql)
    try:
        out = psql('@' + tf)
    finally:
        for p in (tf, tmp_csv):
            try:
                os.unlink(p)
            except OSError:
                pass

    # -f 模式下 stdout 会混入 CREATE TABLE / COPY / DO 等命令标签, 只取最后一行结果
    lines = [l for l in (out or '').strip().splitlines() if l.strip()]
    parts = (lines[-1] if lines else '').split('|')
    res['status'] = parts[0] if parts and parts[0] else 'unknown'
    res['batch_id'] = bid
    if len(parts) > 1:
        res['upserted'] = parts[1]
    return res

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', help='单个 CSV 路径')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--force', action='store_true')
    ap.add_argument('--init-ddl', action='store_true', help='先执行 sql/004 建表（幂等）')
    a = ap.parse_args()

    if a.init_ddl:
        print(f'执行 DDL: {DDL_SQL}')
        psql('@' + DDL_SQL, tuples_only=False)
        print('建表完成（或已存在）。')

    files = [a.file] if a.file else sorted(
        os.path.join(OUT, f) for f in os.listdir(OUT) if f.endswith('.csv'))
    if not files:
        print('没有可导入的 CSV')
        return 0

    print(f'目标库 {PGHOST}/{PGDB}  用户 {PGUSER}  文件数 {len(files)}'
          f'{"  [DRY-RUN]" if a.dry_run else ""}')
    print('-' * 96)
    summary = []
    for p in files:
        try:
            r = load_one(p, dry=a.dry_run, force=a.force)
        except Exception as e:
            r = {'file': os.path.basename(p), 'status': 'error', 'reason': str(e)[:200]}
        summary.append(r)
        tail = r.get('reason') or f"{r.get('rows', '')} 行 -> {r.get('upserted', '')} 写入"
        print(f"{r['status']:<9} {r['file']:<44} {tail}")

    print('-' * 96)
    ok = [r for r in summary if r['status'] in ('success', 'partial')]
    sk = [r for r in summary if r['status'] == 'skipped']
    bad = [r for r in summary if r['status'] in ('failed', 'error', 'unknown')]
    print(f"成功 {len(ok)} / 跳过 {len(sk)} / 失败 {len(bad)}")
    return 1 if bad else 0

if __name__ == '__main__':
    sys.exit(main())
