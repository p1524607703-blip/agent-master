#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把一份 Amazon 品牌分析周报 CSV (中文表头) 载入 RDS core 周表。
- SCP (搜索目录绩效) -> core.search_catalog_performance_weekly
- SQP (搜索查询绩效) -> core.search_query_performance_weekly
通过 psql COPY FROM STDIN 写入, 不保留任何本地文件。
CSV 前 2 行为元数据(报告范围/选择周), 第 3 行起才是真实表头+数据。
"""
import sys, os, re, csv, io, hashlib, subprocess, datetime

from pathlib import Path as _ConfigPath
sys.path.insert(0, str(_ConfigPath(__file__).resolve().parents[1]))
from database_config import configure_warehouse_env
configure_warehouse_env()

PGHOST   = os.environ['PGHOST']
PGPORT   = os.environ.get('PGPORT', '5432')
PGUSER   = os.environ.get('PGUSER', 'amazon_ads_admin')
PGDB     = os.environ.get('PGDB',   'amazon_ads_v2')
PGPASSWORD = os.environ.get('PGPASSWORD', '')
BRAND    = os.environ.get('BA_BRAND', 'WHITIN')
BATCH_ID = os.environ.get('BA_BATCH_ID', '')  # 由调用方传入, 便于追溯

# ---- 中文表头 -> 英文列 映射 ----
SCP_MAP = {
 'ASIN 商品名称':'asin_title',
 'ASIN':'asin',
 '分类':'category',
 '曝光: 曝光总量':'impressions',
 '曝光量：评级（中位数）':'impressions_rating_median',
 '曝光：售价(中位数)':'impressions_median_price',
 '曝光：当日达配送速度':'impressions_same_day_delivery',
 '曝光量：1 天配送速度':'impressions_one_day_delivery',
 '曝光量：2 天配送速度':'impressions_two_day_delivery',
 '点击: 点击量':'clicks',
 '点击：点击率 （CTR）':'click_through_rate_pct',
 '点击量：价格(中位数)':'click_median_price',
 '点击量：当日达配送速度':'clicks_same_day_delivery',
 '点击量：1 天配送速度':'clicks_one_day_delivery',
 '点击：2天配送速度':'clicks_two_day_delivery',
 '加入购物车 : 加购数':'cart_adds',
 '加入购物车：售价（中位数）':'cart_add_median_price',
 '购物车添加：当日达配送速度':'cart_adds_same_day_delivery',
 '加入购物车：1 天配送速度':'cart_adds_one_day_delivery',
 '购物车添加：2 天配送速度':'cart_adds_two_day_delivery',
 '下单成交：成交总量':'purchases',
 '下单成交：搜索来源销售额':'search_attributed_sales',
 '购买次数：转化率 %':'conversion_rate_pct',
 '购买次数：评分（中位数）':'purchase_rating_median',
 '购买次数：价格（中位数）':'purchase_median_price',
 '下单成交：当日达配送速度':'purchases_same_day_delivery',
 '下单成交：1 天配送速度':'purchases_one_day_delivery',
 '下单：2天配送速度':'purchases_two_day_delivery',
 '报告日期':'report_date',
}
SQP_MAP = {
 '搜索查询':'search_query',
 '搜索查询得分':'search_query_score',
 '搜索查询量':'search_query_volume',
 '曝光：曝光总量':'impressions_total',
 '曝光: 曝光品牌数量':'brand_impressions',
 '曝光: 品牌曝光占比 %':'brand_impression_share_pct',
 '点击量：总次数':'clicks_total',
 '点击量：点击率 %':'click_rate_pct',
 '点击量：点击的品牌数':'brand_clicks',
 '点击量：品牌点击占比 %':'brand_click_share_pct',
 '点击量：价格(中位数)':'click_median_price',
 '点击量：品牌售价（中位数）':'brand_click_median_price',
 '点击量：当日达配送速度':'clicks_same_day_delivery',
 '点击量：1 天配送速度':'clicks_one_day_delivery',
 '点击：2天配送速度':'clicks_two_day_delivery',
 '购物车添加：总数':'cart_adds_total',
 '加入购物车：加购率%':'cart_add_rate_pct',
 '加入购物车：涉及品牌数':'brand_cart_adds',
 '购物车添加：品牌份额 %':'brand_cart_add_share_pct',
 '加入购物车：售价（中位数）':'cart_add_median_price',
 '购物车添加：品牌价格（中位数）':'brand_cart_add_median_price',
 '购物车添加：当日达配送速度':'cart_adds_same_day_delivery',
 '加入购物车：1 天配送速度':'cart_adds_one_day_delivery',
 '购物车添加：2 天配送速度':'cart_adds_two_day_delivery',
 '购买：下单总数':'purchases_total',
 '下单成交：成交转化率%':'purchase_rate_pct',
 '购买次数：品牌数量':'brand_purchases',
 '购买次数：品牌份额 %':'brand_purchase_share_pct',
 '购买次数：价格（中位数）':'purchase_median_price',
 '购买次数：品牌价格（中位数）':'brand_purchase_median_price',
 '下单成交：当日达配送速度':'purchases_same_day_delivery',
 '下单成交：1 天配送速度':'purchases_one_day_delivery',
 '下单：2天配送速度':'purchases_two_day_delivery',
 '报告日期':'report_date',
}
# 有序英文列(不含元数据列)
SCP_COLS = list(SCP_MAP.values())
SQP_COLS = list(SQP_MAP.values())

def norm(s):
    s = s.replace('：', ':').replace('（', '(').replace('）', ')')
    s = re.sub(r'\s+', ' ', s).strip()
    return s

def detect_type(fname):
    if '搜索目录绩效' in fname: return 'scp'
    if '搜索查询绩效' in fname: return 'sqp'
    raise SystemExit(f'无法识别报表类型: {fname}')

def parse_week(fname):
    m = re.search(r'Week_(\d{4})_(\d{2})_(\d{2})', fname)
    if not m: raise SystemExit(f'文件名中找不到 Week_YYYY_MM_DD: {fname}')
    y,mo,d = map(int, m.groups())
    end = datetime.date(y, mo, d)
    start = end - datetime.timedelta(days=6)
    return start, end

def parse_report_date(v):
    v = (v or '').strip()
    for fmt in ('%Y/%m/%d','%Y-%m-%d','%m/%d/%Y'):
        try: return datetime.datetime.strptime(v, fmt).date().isoformat()
        except: pass
    return ''

def main():
    if len(sys.argv) < 2:
        raise SystemExit('用法: ba_to_rds.py <csv_path>')
    path = sys.argv[1]
    fname = os.path.basename(path)
    rtype = detect_type(fname)
    start, end = parse_week(fname)
    mkt = 'US' if fname.startswith('US') else 'UNKNOWN'
    fhash = hashlib.sha256(open(path,'rb').read()).hexdigest()

    # 读 CSV
    with open(path, newline='', encoding='utf-8-sig') as f:
        rows = list(csv.reader(f))
    # 找真实表头行
    hdr_i = None
    key0 = 'ASIN 商品名称' if rtype=='scp' else '搜索查询'
    for i,r in enumerate(rows):
        if r and r[0].strip() == key0:
            hdr_i = i; break
    if hdr_i is None:
        raise SystemExit(f'找不到表头行 ({key0}) in {fname}')
    header = [norm(c) for c in rows[hdr_i]]
    data = rows[hdr_i+1:]

    mp = SCP_MAP if rtype=='scp' else SQP_MAP
    cols = SCP_COLS if rtype=='scp' else SQP_COLS
    table = 'core.search_catalog_performance_weekly' if rtype=='scp' else 'core.search_query_performance_weekly'
    rev = {v:k for k,v in mp.items()}         # english -> chinese
    norm_header_idx = {norm(c):i for i,c in enumerate(header)}

    # 构造 COPY 列顺序: 元数据 + 指标 + 追溯
    copy_cols = ['marketplace','brand_name','week_start_date','week_end_date'] + cols + \
                ['source_batch_id','source_file_name','source_file_hash']
    # 每行数据
    out_rows = []
    for r in data:
        if not any(c.strip() for c in r): continue
        meta = [mkt, BRAND, start.isoformat(), end.isoformat()]
        vals = []
        for col in cols:
            ch = rev.get(col)
            idx = norm_header_idx.get(norm(ch)) if ch else None
            v = r[idx].strip() if (idx is not None and idx < len(r)) else ''
            vals.append(v)
        # report_date 特殊处理(已在 cols 中, 来自 CSV 报告日期列)
        tail = [BATCH_ID, fname, fhash]
        out_rows.append(meta + vals + tail)

    # 用 psql: 先 COPY 进临时表, 再 INSERT...ON CONFLICT DO NOTHING 进正式表 (幂等, 重跑不重复)
    conflict_cols = ['marketplace','asin','week_start_date','week_end_date'] if rtype=='scp' else ['marketplace','search_query','week_start_date','week_end_date']
    def esc(v):
        s = '' if v is None else str(v)
        return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '')
    lines = ['\t'.join(esc(x) for x in r) for r in out_rows]
    data = '\n'.join(lines) + '\n'
    cols_sql = ', '.join(copy_cols)
    conflict_sql = ', '.join(conflict_cols)
    # 注意: COPY 会一直读到 \. 为止, 所以数据必须紧跟 COPY 语句, 截断后再放后续 INSERT/SELECT
    head = (
        f"CREATE TEMP TABLE ba_tmp (LIKE {table} INCLUDING DEFAULTS) ON COMMIT PRESERVE ROWS;\n"
        f"COPY ba_tmp ({cols_sql}) FROM STDIN WITH (DELIMITER E'\\t', NULL '');\n"
    )
    tail = (
        f"INSERT INTO {table} ({cols_sql}) SELECT {cols_sql} FROM ba_tmp ON CONFLICT ({conflict_sql}) DO NOTHING;\n"
        f"SELECT count(*) FROM ba_tmp;\n"
    )
    env = os.environ.copy(); env['PGPASSWORD'] = PGPASSWORD
    proc = subprocess.Popen(
        ['psql','-h',PGHOST,'-p',PGPORT,'-U',PGUSER,'-d',PGDB,'-v','ON_ERROR_STOP=1','-X','-t','-A'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, text=True)
    out,err = proc.communicate(input=head + data + '\\.\n' + tail)
    if proc.returncode != 0:
        raise SystemExit(f'载入失败 ({table} {fname}):\n{err}')
    print(f'OK {rtype} {fname} | week {start}..{end} | rows={len(out_rows)} | table={table}')

if __name__ == '__main__':
    main()
