#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把 Amazon 广告「已订阅的报告」(advertising.amazon.com/reporting) 的 5 份 CSV 落地到 RDS。

与 ba_to_rds.py (Brand Analytics 周报) 同模式：
  - 中文表头 -> 英文列 (snake_case)
  - COPY 进临时表 -> INSERT...ON CONFLICT DO UPDATE (upsert, 幂等可重跑)
  - 加 source_file_name / source_file_hash / imported_at 追溯列

但订阅报告有 3 个 BA 周报没有的坑，必须清洗：
  1. 长数字 ID 被 Excel 转义成 ="amzn1..." 形式 -> 提取值
  2. 日期是 2026年9月3日 中文 -> 转 2026-09-03
  3. 百分比列带 % 后缀 (0.7368%) -> 去 % 转 numeric

订阅报告第 1 行就是表头 (不像 BA 周报有前 2 行元数据)。

用法:
  python3 subscribed_reports_to_rds.py <csv_or_dir> [<csv_or_dir> ...]
  目录下会自动识别 5 个已知文件名。
"""
import sys, os, re, csv, hashlib, subprocess, datetime, uuid

# ⚠️ 2026-09-21 状态：**本脚本已废弃，不可用于现行数据仓库**。
# ⚠️ 2026-09-30 追加：数据库已从阿里云 RDS 迁至腾讯云服务器自建 PostgreSQL
#   （经 SSH 隧道 127.0.0.1:15432 访问）。本脚本的连接已随 database_config 一起切换，
#   但「已废弃」的结论不变 —— 原因 2 是表结构问题，换主机解决不了。
#   两处硬伤，改一行 host 修不好：
#   1) 原 PGHOST 指向旧服务器 121.41.134.56（已整机退役，ping 100% 丢包）；
#   2) 更根本的是——它写的是 `core.subscribed_*_daily` 系列表，
#      而这些表在现行主库 amazon_ads_v2 里**全部不存在**（旧 analytics/ops schema 已下线）。
#   现行广告订阅报告入库路径（写 core.report_*_daily）：
#       /Users/panjinlong/Documents/amazon-ads-data/scripts/import_account_30d_reports.py --base-dir <目录>
#   若要复活本脚本，必须先把其 TABLES 映射重定向到现行 core.report_* 表并核对列集。
#   保留文件仅为追溯历史清洗逻辑（="amzn1..." 反转义 / 中文日期 / 百分号）。
from pathlib import Path as _ConfigPath
sys.path.insert(0, str(_ConfigPath(__file__).resolve().parents[1]))
from database_config import configure_warehouse_env
configure_warehouse_env()

PGHOST = os.environ['PGHOST']
PGPORT = os.environ.get('PGPORT', '5432')
PGUSER = os.environ.get('PGUSER', 'amazon_ads_admin')
PGDB   = os.environ.get('PGDB', 'amazon_ads_v2')
PGPASSWORD = os.environ.get('PGPASSWORD', '')

# 类型: id | date | num | text
CAMPAIGN_COLS = [
    ('广告主账户 ID', 'account_id', 'id'),
    ('广告主账户名称', 'account_name', 'text'),
    ('管理员账户', 'manager_account', 'text'),
    ('广告产品', 'ad_product', 'text'),
    ('广告活动编号', 'campaign_id', 'id'),
    ('广告活动名称', 'campaign_name', 'text'),
    ('全球广告活动 ID', 'global_campaign_id', 'id'),
    ('预算货币', 'budget_currency', 'text'),
    ('日期', 'stat_date', 'date'),
    ('展示量', 'impressions', 'num'),
    ('可见展示量', 'viewable_impressions', 'num'),
    ('点击量', 'clicks', 'num'),
    ('点击率', 'ctr_pct', 'num'),
    ('浏览点击率 (vCTR)', 'vctr_pct', 'num'),
    ('总成本', 'cost', 'num'),
    ('购买量', 'purchases', 'num'),
    ('购买量（品牌新客）', 'new_to_brand_purchases', 'num'),
    ('单次购买成本', 'cost_per_purchase', 'num'),
    ('每次购买成本（品牌新客）', 'new_to_brand_cost_per_purchase', 'num'),
    ('销售额', 'sales', 'num'),
    ('长期销售', 'long_term_sales', 'num'),
    ('ROAS', 'roas', 'num'),
    ('长期 ROAS', 'long_term_roas', 'num'),
]

# 广告位/搜索词/推广的商品/CPO 四份共享的 28 个指标列
METRICS = [
    ('展示量', 'impressions', 'num'),
    ('点击量', 'clicks', 'num'),
    ('点击率', 'ctr_pct', 'num'),
    ('总成本', 'cost', 'num'),
    ('购买量', 'purchases', 'num'),
    ('销售额', 'sales', 'num'),
    ('已售商品数量', 'units', 'num'),
    ('单次购买成本', 'cost_per_purchase', 'num'),
    ('购买率', 'purchase_rate_pct', 'num'),
    ('ROAS', 'roas', 'num'),
    ('推广商品的购买量', 'promoted_purchases', 'num'),
    ('推广商品的销量', 'promoted_sales', 'num'),
    ('已售商品数量（推广）', 'promoted_units', 'num'),
    ('推广商品的每次购买费用', 'promoted_cost_per_purchase', 'num'),
    ('购买率（推广的商品）', 'promoted_purchase_rate_pct', 'num'),
    ('推广商品的 ROAS', 'promoted_roas', 'num'),
    ('购买量（光环）', 'halo_purchases', 'num'),
    ('销售额（光环）', 'halo_sales', 'num'),
    ('已售商品数量（光环）', 'halo_units', 'num'),
    ('购买量（品牌新客）', 'new_to_brand_purchases', 'num'),
    ('销售额（品牌新客）', 'new_to_brand_sales', 'num'),
    ('已售商品数量（品牌新客）', 'new_to_brand_units', 'num'),
    ('每次购买成本（品牌新客）', 'new_to_brand_cost_per_purchase', 'num'),
    ('购买率（品牌新客）', 'new_to_brand_purchase_rate_pct', 'num'),
    ('ROAS（品牌新客）', 'new_to_brand_roas', 'num'),
    ('商品详情页浏览量', 'detail_page_views', 'num'),
    ('单次商品详情页浏览成本', 'cost_per_detail_page_view', 'num'),
    ('商品详情页浏览率', 'detail_page_view_rate_pct', 'num'),
]

PLACEMENT_COLS = [
    ('预算货币', 'budget_currency', 'text'),
    ('广告主账户 ID', 'account_id', 'id'),
    ('广告主账户名称', 'account_name', 'text'),
    ('广告组合编号', 'portfolio_id', 'id'),
    ('广告组合名称', 'portfolio_name', 'text'),
    ('广告活动编号', 'campaign_id', 'id'),
    ('广告活动名称', 'campaign_name', 'text'),
    ('广告组编号', 'ad_group_id', 'id'),
    ('广告组名称', 'ad_group_name', 'text'),
    ('广告位分类', 'placement', 'text'),
    ('日期', 'stat_date', 'date'),
] + METRICS

SEARCH_TERM_COLS = [
    ('预算货币', 'budget_currency', 'text'),
    ('广告主账户 ID', 'account_id', 'id'),
    ('广告主账户名称', 'account_name', 'text'),
    ('广告组合编号', 'portfolio_id', 'id'),
    ('广告组合名称', 'portfolio_name', 'text'),
    ('广告活动编号', 'campaign_id', 'id'),
    ('广告活动名称', 'campaign_name', 'text'),
    ('广告组编号', 'ad_group_id', 'id'),
    ('广告组名称', 'ad_group_name', 'text'),
    ('搜索词', 'search_term', 'text'),
    ('日期', 'stat_date', 'date'),
] + METRICS

PRODUCT_COLS = [
    ('预算货币', 'budget_currency', 'text'),
    ('广告主账户 ID', 'account_id', 'id'),
    ('广告主账户名称', 'account_name', 'text'),
    ('广告组合编号', 'portfolio_id', 'id'),
    ('广告组合名称', 'portfolio_name', 'text'),
    ('广告活动编号', 'campaign_id', 'id'),
    ('广告活动名称', 'campaign_name', 'text'),
    ('广告组编号', 'ad_group_id', 'id'),
    ('广告组名称', 'ad_group_name', 'text'),
    ('推广的商品编号', 'advertised_product_id', 'id'),
    ('推广的商品名称', 'advertised_product_name', 'text'),
    ('推广的商品父级编号', 'advertised_product_parent_id', 'id'),
    ('推广的商品品牌', 'advertised_product_brand', 'text'),
    ('推广的商品品类', 'advertised_product_category', 'text'),
    ('推广的商品子品类', 'advertised_product_subcategory', 'text'),
    ('推广的商品组', 'advertised_product_group', 'text'),
    ('推广的商品 SKU-Advertised product SKU', 'advertised_product_sku', 'text'),
    ('推广的商品站点-Advertised product marketplace', 'advertised_product_marketplace', 'text'),
    ('日期', 'stat_date', 'date'),
] + METRICS

SPECS = {
    'campaign': CAMPAIGN_COLS,
    'placement': PLACEMENT_COLS,
    'search_term': SEARCH_TERM_COLS,
    'product': PRODUCT_COLS,
    'cpo': PRODUCT_COLS,  # CPO 与推广的商品列结构一致
}
TABLES = {
    'campaign': ('core.subscribed_campaign_daily', ['account_id', 'campaign_id', 'stat_date']),
    'placement': ('core.subscribed_placement_daily', ['account_id', 'campaign_id', 'ad_group_id', 'placement', 'stat_date']),
    'search_term': ('core.subscribed_search_term_daily', ['account_id', 'campaign_id', 'ad_group_id', 'search_term', 'stat_date']),
    'product': ('core.subscribed_product_daily', ['account_id', 'campaign_id', 'ad_group_id', 'advertised_product_id', 'stat_date']),
    'cpo': ('core.subscribed_product_cpo_daily', ['account_id', 'campaign_id', 'ad_group_id', 'advertised_product_id', 'stat_date']),
}

# 历史快照: 每次导入把事实表整表状态存档(归因漂移研究用)。
# 每项 = (快照表, 业务列[与事实表同名], 快照表PK除 snapshot_date/run_id 外的列)
SNAPSHOT = {
    'campaign': ('core.subscribed_campaign_daily_snapshot',
                 [c[1] for c in CAMPAIGN_COLS],
                 ['account_id', 'campaign_id', 'stat_date']),
    'product':  ('core.subscribed_product_daily_snapshot',
                 [c[1] for c in PRODUCT_COLS],
                 ['account_id', 'campaign_id', 'ad_group_id', 'advertised_product_id', 'stat_date']),
    'search_term': ('core.subscribed_search_term_daily_snapshot',
                 [c[1] for c in SEARCH_TERM_COLS],
                 ['account_id', 'campaign_id', 'ad_group_id', 'search_term', 'stat_date']),
    'placement': ('core.subscribed_placement_daily_snapshot',
                 [c[1] for c in PLACEMENT_COLS],
                 ['account_id', 'campaign_id', 'ad_group_id', 'placement', 'stat_date']),
    'cpo':      ('core.subscribed_product_cpo_daily_snapshot',
                 [c[1] for c in PRODUCT_COLS],
                 ['account_id', 'campaign_id', 'ad_group_id', 'advertised_product_id', 'stat_date']),
}


def norm(s):
    s = (s or '').replace('：', ':').replace('（', '(').replace('）', ')')
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def clean_id(v):
    v = (v or '').strip()
    # Amazon 导出把长数字 ID 写成 ="amzn1..." 防 Excel 科学计数法
    m = re.match(r'^="?(.*?)"?$', v)
    return m.group(1) if m else v


def clean_date(v):
    m = re.match(r'(\d{4})年(\d{1,2})月(\d{1,2})日', (v or '').strip())
    if m:
        return '%s-%02d-%02d' % (m.group(1), int(m.group(2)), int(m.group(3)))
    return ''


def clean_num(v):
    v = (v or '').strip().replace('%', '').replace(',', '')
    return v


def esc(v):
    s = '' if v is None else str(v)
    return s.replace('\\', '\\\\').replace('\t', '\\t').replace('\n', '\\n').replace('\r', '')


def sq(v):
    """SQL 字符串字面量转义: 单引号翻倍。用于拼入 INSERT 语句的值。"""
    s = '' if v is None else str(v)
    return s.replace("'", "''")


# 报告文件名 -> 类型 的识别映射。多店铺扩展时, 把各店订阅报告的实际文件名片段
# 追加进本列表即可(顺序即优先级, 先匹配先生效); 不修改代码逻辑。
# 例: ('欧德思推广的商品 30D', 'product') 等, 待逐店核对订阅列表后补。
DEFAULT_REPORT_TYPE_MAP = [
    ('广告活动 30D 日期', 'campaign'),
    ('广告位 30D 日期', 'placement'),
    ('搜索词 30D 日期', 'search_term'),
    ('推广的商品 30D 日期', 'product'),
    # CPO 报告名各店专属, 全部登记; detect_type 按子串匹配, 互不冲突
    ('川鹏推广的商品 每日CPO单双计算', 'cpo'),
    ('欧德思 推广的商品 每日CPO单双计算', 'cpo'),
    ('洁博利 推广的商品 每日CPO单双计算', 'cpo'),
    ('AMS 推广的商品 每日CPO单双计算', 'cpo'),
]
# 允许环境变量 SUBSCRIBED_REPORT_MAP 覆盖(格式: "文件名片段:类型,..." ), 便于不改代码扩店
def _load_report_map():
    import os as _os
    env = _os.environ.get('SUBSCRIBED_REPORT_MAP')
    if env:
        return [tuple(p.split(':', 1)) for p in env.split(',') if ':' in p]
    return DEFAULT_REPORT_TYPE_MAP

REPORT_TYPE_MAP = _load_report_map()


def detect_type(fname):
    for frag, ptype in REPORT_TYPE_MAP:
        if frag in fname:
            return ptype
    raise SystemExit('无法识别报表类型: ' + fname)


def load_file(path, run_id, snapshot_date, ptype_override=None, source_file_name_override=None):
    # Web手动补传与本地自动化共用同一入库核心；本地调用不传override，行为保持不变。
    ptype = ptype_override or detect_type(os.path.basename(path))
    table, pk = TABLES[ptype]
    cols = SPECS[ptype]
    col_names = [c[1] for c in cols] + ['source_file_name', 'source_file_hash']
    hmap = {norm(c[0]): (c[1], c[2]) for c in cols}
    fhash = hashlib.sha256(open(path, 'rb').read()).hexdigest()
    source_file_name = source_file_name_override or os.path.basename(path)

    with open(path, encoding='utf-8-sig', errors='replace', newline='') as fh:
        r = csv.reader(fh)
        header = [norm(c) for c in next(r)]  # 订阅报告第 1 行即表头
        hidx = {norm(c): i for i, c in enumerate(header)}
        # 校验所有列都在表头中
        missing = [cn for cn in hmap if cn not in hidx]
        if missing:
            raise SystemExit('表头缺列: %s in %s' % (missing, os.path.basename(path)))
        # 父级编号列位置, 供空 product_id 兜底构造哨兵
        parent_idx = hidx.get(norm('推广的商品父级编号'))
        out_rows = []
        for row in r:
            if not any(x.strip() for x in row):
                continue
            vals = []
            for cn, en, typ in cols:
                idx = hidx.get(norm(cn))
                v = row[idx].strip() if (idx is not None and idx < len(row)) else ''
                if typ == 'id':
                    v = clean_id(v)
                elif typ == 'date':
                    v = clean_date(v)
                elif typ == 'num':
                    v = clean_num(v)
                # 搜索词报告的「其他搜索词(已汇总)」行 search_term 为空,
                # 用稳定哨兵值替代, 既保 NOT NULL 又保 upsert 幂等。
                if en == 'search_term' and v == '':
                    v = '其他搜索词（已汇总）'
                # 推广的商品 / CPO 报告的「其他推广商品(已汇总)」行 product_id 为空,
                # 用父级编号兜底构造稳定哨兵, 保 NOT NULL + upsert 幂等 + 不丢行。
                if en == 'advertised_product_id' and v == '':
                    pv = row[parent_idx].strip() if (parent_idx is not None and parent_idx < len(row)) else ''
                    pv = clean_id(pv)
                    v = 'OTHER|' + (pv if pv else 'AGG')
                # 广告位报告的「未指定/汇总」行 placement 为空, 用稳定哨兵替代
                # (每条空 placement 行的 account+campaign+ad_group+date 唯一, 不丢行)。
                if en == 'placement' and v == '':
                    v = '未指定广告位（汇总）'
                vals.append(v)
            vals += [source_file_name, fhash]
            out_rows.append(vals)

    raw_count = len(out_rows)
    # 去重: 源 CSV 内同一 PK 可能重复出现 (Amazon 偶发/聚合行碰撞),
    # 保留末行, 避免 COPY 进临时表后 INSERT...ON CONFLICT 报
    # "cannot affect row a second time"。幂等、不丢真实数据。
    pk_pos = [col_names.index(pc) for pc in pk]
    dedup = {}
    for row in out_rows:
        dedup[tuple(row[p] for p in pk_pos)] = row
    dropped = raw_count - len(dedup)
    out_rows = list(dedup.values())

    if not out_rows:
        print('SKIP (无数据行): %s' % os.path.basename(path))
        return None
    if dropped:
        print('  (去重丢弃 %d 行重复 PK)' % dropped)

    # 数据窗口末位 + 账户(用于 import_batch 血缘)
    sd_i = col_names.index('stat_date')
    ac_i = col_names.index('account_id')
    max_sd = max((row[sd_i] for row in out_rows), default=None) or None
    account_id = out_rows[0][ac_i]

    set_cols = [c for c in col_names if c not in pk]
    update_sql = ', '.join('%s=EXCLUDED.%s' % (c, c) for c in set_cols)
    head = (
        "CREATE TEMP TABLE sub_tmp (LIKE %s INCLUDING DEFAULTS) ON COMMIT PRESERVE ROWS;\n"
        "COPY sub_tmp (%s) FROM STDIN WITH (DELIMITER E'\\t', NULL '');\n"
    ) % (table, ', '.join(col_names))
    tail = (
        "INSERT INTO %s (%s) SELECT %s FROM sub_tmp ON CONFLICT (%s) DO UPDATE SET %s;\n"
        "SELECT count(*) FROM sub_tmp;\n"
    ) % (table, ', '.join(col_names), ', '.join(col_names), ', '.join(pk), update_sql)
    # import_batch 血缘行: 与本次 upsert 同事务写入, 加载失败则整批回滚
    ib_sql = (
        "INSERT INTO core.import_batch (run_id, account_id, report_type, source_file_name, "
        "source_file_hash, file_row_count, loaded_row_count, dropped_dup_rows, exported_at, status) "
        "VALUES ('%s', '%s', '%s', '%s', '%s', %d, %d, %d, %s, 'ok');\n"
    ) % (run_id, sq(account_id), ptype, sq(source_file_name), fhash,
         raw_count, len(out_rows), dropped,
         ("'%s'" % max_sd) if max_sd else 'NULL')

    data = '\n'.join('\t'.join(esc(x) for x in row) for row in out_rows) + '\n'
    env = os.environ.copy()
    env['PGPASSWORD'] = PGPASSWORD
    proc = subprocess.Popen(
        ['psql', '-h', PGHOST, '-p', PGPORT, '-U', PGUSER, '-d', PGDB,
         '-v', 'ON_ERROR_STOP=1', '-X', '-t', '-A'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=True)
    out, err = proc.communicate(input=head + data + '\\.\n' + tail + ib_sql)
    if proc.returncode != 0:
        raise SystemExit('载入失败 (%s %s):\n%s' % (ptype, os.path.basename(path), err))
    print('OK %-10s %-40s rows=%s -> %s (去重丢弃 %d)' % (ptype, os.path.basename(path), len(out_rows), table, dropped))
    return {'ptype': ptype, 'table': table, 'loaded': len(out_rows),
            'dropped': dropped, 'max_sd': max_sd, 'account_id': account_id}


def take_snapshots(run_id, snapshot_date):
    """把 campaign / product 事实表当前整表状态存档到 *_snapshot(归因漂移研究)。"""
    env = os.environ.copy()
    env['PGPASSWORD'] = PGPASSWORD
    for ptype, (stable, fact_cols, snap_pk) in SNAPSHOT.items():
        ftable = TABLES[ptype][0]
        ins_cols = ['snapshot_date', 'run_id'] + fact_cols
        sel = ["'%s'::date" % snapshot_date, "'%s'" % run_id] + list(fact_cols)
        sql = (
            "INSERT INTO %s (%s) SELECT %s FROM %s "
            "ON CONFLICT (snapshot_date, %s) DO NOTHING;\n"
            "SELECT count(*) FROM %s WHERE snapshot_date='%s'::date;\n"
        ) % (stable, ', '.join(ins_cols), ', '.join(sel), ftable,
             ', '.join(snap_pk), stable, snapshot_date)
        proc = subprocess.Popen(
            ['psql', '-h', PGHOST, '-p', PGPORT, '-U', PGUSER, '-d', PGDB,
             '-v', 'ON_ERROR_STOP=1', '-X', '-t', '-A'],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True)
        out, err = proc.communicate(input=sql)
        if proc.returncode != 0:
            raise SystemExit('快照失败 (%s):\n%s' % (ptype, err))
        print('SNAP %-10s -> %s rows=%s' % (ptype, stable, out.strip().split('\n')[-1].strip()))


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit('用法: subscribed_reports_to_rds.py <csv|dir> ...')
    files = []
    scan_keys = [frag for frag, _ in REPORT_TYPE_MAP]
    for a in args:
        if os.path.isdir(a):
            for fn in os.listdir(a):
                if any(k in fn for k in scan_keys):
                    files.append(os.path.join(a, fn))
        else:
            files.append(a)
    if not files:
        raise SystemExit('未找到可加载的订阅报告文件')
    # 每次加载 = 1 个 run_id, 串联本批所有文件 + 快照(血缘可追溯)
    run_id = str(uuid.uuid4())
    snapshot_date = datetime.date.today()
    total = 0
    for f in files:
        st = load_file(f, run_id, snapshot_date)
        if st:
            total += st['loaded']
    print('全部完成 | run_id=%s snapshot_date=%s 累计 %d 行' % (run_id, snapshot_date, total))
    # 归因漂移研究: 把 campaign / product 事实表整表状态存档
    take_snapshots(run_id, snapshot_date)


if __name__ == '__main__':
    main()
