"""SOP V3.5 reference calculator for the 2026-08-26 CPO baseline.

This module is intentionally date-scoped: it is the audited answer key used to
realign the web UI. It does not silently generalize the 8/26 identity mapping to
other dates.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Any, Optional
from .rds_query import query_rows

REFERENCE_DATE = '2026-08-26'
# Invalidated 2026-09-07: previous baseline hard-coded only ZJ/XH/XM while the SKU identity table has 12 operator groups.
REFERENCE_INVALIDATED = True
WHITIN = 'amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh'
AMS = 'amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz'

# operator, group, exact SKU-table style, business parent ASIN
REFERENCE_PRODUCTS = [
    ('ZJ','ZJ1','Z32','B0GX1MVGZ9'),('ZJ','ZJ1','WK102','B0G6FTJCT6'),('ZJ','ZJ1','DU08','B0GS5LHJMY'),
    ('ZJ','ZJ1','W81V5','B0DKBQTXWN'),('ZJ','ZJ1','W51女','B0DZ2D5GR4'),('ZJ','ZJ1','W51男','B0D4Z6F57R'),
    ('ZJ','ZJ1','W8K23','B0D9NRT9Q8'),('ZJ','ZJ1','W20','B0D4F33NRM'),('ZJ','ZJ1','W823女','B0D6XNS31X'),
    ('ZJ','ZJ1','W823男','B0D86MWK4H'),('ZJ','ZJ1','W8K2-','B0D4Z7RX58'),('ZJ','ZJ1','W8SO','B0CNTHY16W'),
    ('ZJ','ZJ1','W63','B0D3ZRW4D6'),('ZJ','ZJ1','W30','B0DRV4NG1P'),('ZJ','ZJ1','W85','B0CLV667HH'),
    ('ZJ','ZJ1','W81','B0D4DS7M7G'),('ZJ','ZJ1','W75V2','B0DPWWH9LH'),('ZJ','ZJ1','W81V2','B0CW13XPHN'),
    ('ZJ','ZJ1','DU06','B0D52DTGBB'),('ZJ','ZJ1','W826','B0DGL12FGY'),
    ('XH','XH1','W71V5','B0919CZ9SY'),('XH','XH1','W75V2','B0BW4783S9'),('XH','XH1','W81K','B0C8T8PB6T'),
    ('XH','XH1','W81V2','B0FRNCXHZC'),('XH','XH1','W81V5','B0DLB3VG96'),('XH','XH1','W81女','B09K6LDQHM'),
    ('XH','XH1','W8K21','B0DB5QQ62V'),('XH','XH1','W8K3','B0CS72FMGX'),('XH','XH1','W8K6','B0D5GF9F2X'),
    ('XH','XH1','W8K8','B0D9B7N51G'),('XH','XH1','Z1K02','B0DXVG7N23'),('XH','XH1','Z21','B0F376YB87'),
    ('XM','XM1','S71W','B0FXB6C8SC'),('XM','XM1','V202','B0F3CMW6JR'),('XM','XM1','Y70','B0DM5SPQPR'),
    ('XM','XM1','Y71','B0GJ5HP2F4'),('XM','XM1','YG02','B0CLRS15J4'),('XM','XM1','YG10','B0DRX21M4T'),
]

MIXED_BY_PROMOTED_PARENT = {
    '19027149623806',
    '203273711641212','269172420948556','278929760566914','328352666637596',
}
FIXED_EQUAL = {'479537915429061': ['W85','W81','W63','W51男']}
EQUAL_FALLBACK = {'1775045260101': ['W30','W20','W63','W81']}
FORCED_CAMPAIGN = {'79897800480005': 'W51女'}
# Historical 8/26 operator CPO record assigns this exact $18.53 / 4 units to W75V2.
MANUAL_CONFIRMED = {'73789533007579': 'W75V2'}

TYPES = ['手动','自动','头条','视频','展示','流媒体']


def D(v: Any) -> Decimal:
    return Decimal(str(v or 0))


def split_money(total: Decimal, count: int):
    """Two-decimal deterministic split; last item absorbs the rounding remainder."""
    if count <= 0:
        return []
    share = (total / count).quantize(Decimal('0.01'))
    vals = [share for _ in range(count - 1)]
    vals.append(total - sum(vals, Decimal(0)))
    return vals


def split_units(total: Decimal, count: int):
    if count <= 0:
        return []
    share = (total / count).quantize(Decimal('0.0001'))
    vals = [share for _ in range(count - 1)]
    vals.append(total - sum(vals, Decimal(0)))
    return vals


def classify(ad_product: str, campaign_name: str) -> str:
    ap = ad_product or ''
    name = campaign_name or ''
    lower = name.lower()
    if ap == 'Sponsored TV' or '流媒体' in name or 'streaming tv' in lower:
        return '流媒体'
    if ap == 'Sponsored Display' or (not ap and '展示' in name):
        return '展示'
    if ap == 'Sponsored Brands':
        return '视频' if ('视频' in name or 'video' in lower or 'sbv' in lower) else '头条'
    if ap == 'Sponsored Products':
        return '自动' if ('auto' in lower or '自动' in name) else '手动'
    if 'auto' in lower or '自动' in name:
        return '自动'
    return '手动'


def whitin_product(operator: str, canonical: str) -> str:
    if operator == 'ZJ':
        return {'W8K2':'W8K2-','W51':'W51男','WTNVW823':'W823女','WTW823':'W823男'}.get(canonical, canonical)
    if operator == 'XH' and canonical == 'W81':
        return 'W81女'
    return canonical


def ams_product(operator: str, campaign_name: str) -> Optional[str]:
    name = campaign_name or ''
    if operator == 'ZJ':
        prefixes = [
            ('ZJ1-DU08','DU08'),('ZJ1-W30','W30'),('ZJ1-W51女','W51女'),('ZJ1-W51男','W51男'),
            ('ZJ1-W63','W63'),('ZJ1-W75V2','W75V2'),('ZJ1-W81 ','W81'),('ZJ1-W823男','W823男'),
            ('ZJ1-W85','W85'),('ZJ1-W8K2-','W8K2-'),('ZJ1-WK102','WK102'),
        ]
    else:
        prefixes = [('XM1-S71W','S71W'),('XM1-V202','V202'),('XM1-YG02','YG02'),('XM1-Y10','Y10')]
    for prefix, product in prefixes:
        if name.startswith(prefix):
            return product
    return None


def reference_rows(day: str = REFERENCE_DATE) -> list[dict[str, Any]]:
    if REFERENCE_INVALIDATED:
        raise RuntimeError('invalidated incomplete baseline: operator scope must be rebuilt from full SKU table')
    if day != REFERENCE_DATE:
        raise ValueError(f'reference calculator is locked to {REFERENCE_DATE}')

    effective = {(op, product): parent for op, _, product, parent in REFERENCE_PRODUCTS}
    parent_to_zj = {parent: product for op, _, product, parent in REFERENCE_PRODUCTS if op == 'ZJ'}

    parent_list = ','.join("'%s'" % p for _,_,_,p in REFERENCE_PRODUCTS)
    business = query_rows(f"""
        SELECT parent_asin,title,ordered_product_units::float8 total_orders,sessions_total::float8 sessions,
               unit_session_pct::float8 cvr_pct,ordered_product_sales::float8 total_sales
        FROM core.business_report_parent_asin_period
        WHERE account_id='{WHITIN}' AND report_start_date=DATE '{day}' AND report_end_date=DATE '{day}'
          AND parent_asin IN ({parent_list})
    """)
    biz = {r['parent_asin']: r for r in business}

    whitin = query_rows(f"""
        WITH cm AS (
          SELECT account_id,campaign_id,stat_date,max(ad_product) ad_product
          FROM core.subscribed_campaign_daily
          WHERE account_id='{WHITIN}' AND stat_date=DATE '{day}' GROUP BY 1,2,3
        ), r AS (
          SELECT DISTINCT campaign_id,canonical_product_code
          FROM analytics.v_campaign_daily_product_resolved
          WHERE account_id='{WHITIN}' AND stat_date=DATE '{day}'
        )
        SELECT p.campaign_id,p.campaign_name,substring(p.campaign_name from '^([A-Z]{{2}})1-') operator_code,
               p.advertised_product_parent_id,coalesce(cm.ad_product,'') ad_product,r.canonical_product_code,
               sum(p.cost)::float8 spend,sum(p.units)::float8 units,sum(p.sales)::float8 ad_sales
        FROM core.subscribed_product_cpo_daily p
        LEFT JOIN cm ON cm.account_id=p.account_id AND cm.campaign_id=p.campaign_id AND cm.stat_date=p.stat_date
        LEFT JOIN r ON r.campaign_id=p.campaign_id
        WHERE p.account_id='{WHITIN}' AND p.stat_date=DATE '{day}' AND p.campaign_name ~ '^(ZJ1|XH1|XM1)-'
        GROUP BY p.campaign_id,p.campaign_name,operator_code,p.advertised_product_parent_id,cm.ad_product,r.canonical_product_code
    """)
    ams = query_rows(f"""
        WITH cm AS (
          SELECT account_id,campaign_id,stat_date,max(ad_product) ad_product
          FROM core.subscribed_campaign_daily
          WHERE account_id='{AMS}' AND stat_date=DATE '{day}' GROUP BY 1,2,3
        )
        SELECT p.campaign_id,p.campaign_name,substring(p.campaign_name from '^([A-Z]{{2}})1-') operator_code,
               p.advertised_product_parent_id,coalesce(cm.ad_product,'') ad_product,
               sum(p.cost)::float8 spend,sum(p.units)::float8 units,sum(p.sales)::float8 ad_sales
        FROM core.subscribed_product_cpo_daily p
        LEFT JOIN cm ON cm.account_id=p.account_id AND cm.campaign_id=p.campaign_id AND cm.stat_date=p.stat_date
        WHERE p.account_id='{AMS}' AND p.stat_date=DATE '{day}' AND p.campaign_name ~ '^(ZJ1|XM1)-'
        GROUP BY p.campaign_id,p.campaign_name,operator_code,p.advertised_product_parent_id,cm.ad_product
    """)

    allocations: list[dict[str, Any]] = []

    def add(source: str, op: str, product: str, campaign_id: str, name: str, ad_type: str,
            spend: Decimal, units: Decimal, sales: Decimal, method: str):
        if (op, product) not in effective:
            return
        allocations.append({'source':source,'operator':op,'product':product,'campaign_id':campaign_id,
            'campaign_name':name,'ad_type':ad_type,'spend':spend,'units':units,'sales':sales,'method':method})

    # WHITIN main account: operator isolation first, then special rules/default campaign_code.
    for r in whitin:
        op = r['operator_code']; cid = str(r['campaign_id']); typ = classify(r['ad_product'], r['campaign_name'])
        if cid in MIXED_BY_PROMOTED_PARENT:
            product = parent_to_zj.get(r['advertised_product_parent_id'])
            if product:
                add('川鹏',op,product,cid,r['campaign_name'],typ,D(r['spend']),D(r['units']),D(r['ad_sales']),'mixed_split')
            continue
        product = whitin_product(op, r.get('canonical_product_code'))
        if product:
            add('川鹏',op,product,cid,r['campaign_name'],typ,D(r['spend']),D(r['units']),D(r['ad_sales']),'campaign_code')

    # AMS ad-only account: special allocation rules override name/default mapping.
    grouped = defaultdict(lambda: {'rows':[], 'spend':Decimal(0), 'units':Decimal(0), 'sales':Decimal(0)})
    for r in ams:
        g = grouped[(r['operator_code'],str(r['campaign_id']),r['campaign_name'],r['ad_product'])]
        g['rows'].append(r); g['spend'] += D(r['spend']); g['units'] += D(r['units']); g['sales'] += D(r['ad_sales'])
    for (op,cid,name,ad_product), g in grouped.items():
        typ = classify(ad_product,name)
        if cid in FIXED_EQUAL:
            targets = FIXED_EQUAL[cid]
            ss=split_money(g['spend'],len(targets)); uu=split_units(g['units'],len(targets)); vv=split_money(g['sales'],len(targets))
            for i,product in enumerate(targets):
                add('AMS',op,product,cid,name,typ,ss[i],uu[i],vv[i],'fixed_equal_split')
        elif cid in EQUAL_FALLBACK:
            targets = EQUAL_FALLBACK[cid]
            ss=split_money(g['spend'],len(targets)); uu=split_units(g['units'],len(targets)); vv=split_money(g['sales'],len(targets))
            for i,product in enumerate(targets):
                add('AMS',op,product,cid,name,typ,ss[i],uu[i],vv[i],'mixed_split_equal_fallback')
        elif cid in FORCED_CAMPAIGN:
            add('AMS',op,FORCED_CAMPAIGN[cid],cid,name,typ,g['spend'],g['units'],g['sales'],'campaign_code_special')
        elif cid in MANUAL_CONFIRMED:
            add('AMS',op,MANUAL_CONFIRMED[cid],cid,name,typ,g['spend'],g['units'],g['sales'],'manual_confirmed_historical')
        else:
            product = ams_product(op,name)
            # Y10 has no 8/26 business-report match, so SOP effective-product intersection excludes it.
            if product and (op,product) in effective:
                add('AMS',op,product,cid,name,typ,g['spend'],g['units'],g['sales'],'campaign_code')

    agg = defaultdict(lambda: {
        'spend': {t:Decimal(0) for t in TYPES}, 'units': {t:Decimal(0) for t in TYPES},
        'sales':Decimal(0), 'accounts':set(), 'methods':set()
    })
    for a in allocations:
        k=(a['operator'],a['product']); x=agg[k]
        x['spend'][a['ad_type']] += a['spend']; x['units'][a['ad_type']] += a['units']; x['sales'] += a['sales']
        x['accounts'].add(a['source']); x['methods'].add(a['method'])

    rows=[]
    for op, group, product, parent in REFERENCE_PRODUCTS:
        b=biz.get(parent)
        if not b:
            continue
        a=agg[(op,product)]
        total_spend=sum(a['spend'].values(),Decimal(0)); total_units=sum(a['units'].values(),Decimal(0))
        total_orders=D(b['total_orders']); total_sales=D(b['total_sales'])
        row={'运营':op,'运营小组':group,'产品代号':product,'业务账户':'川鹏',
             '广告账户':' + '.join(sorted(a['accounts'], key=lambda x: 0 if x=='川鹏' else 1)),'父ASIN':parent,'日期':day}
        for t in TYPES:
            row[f'{t}费用']=float(a['spend'][t].quantize(Decimal('0.01')))
        for t in TYPES:
            row[f'{t}广告单']=float(a['units'][t].quantize(Decimal('0.0001')))
        for t in TYPES:
            row[f'{t}单均费用']=float((a['spend'][t]/a['units'][t]).quantize(Decimal('0.01'))) if a['units'][t] else 0.0
        row.update({
            '总费用':float(total_spend.quantize(Decimal('0.01'))),'总广告单':float(total_units.quantize(Decimal('0.0001'))),
            '全部订单':float(total_orders),'自然单':None,
            '综合CPO':float((total_spend/total_orders).quantize(Decimal('0.01'))) if total_orders else 0.0,
            'Sessions':float(D(b['sessions'])),'CVR_pct':float(D(b['cvr_pct'])),
            '广告归因销售额':float(a['sales'].quantize(Decimal('0.01'))),'业务销售额':float(total_sales),
            'ROAS':float((a['sales']/total_spend).quantize(Decimal('0.01'))) if total_spend else None,
            'TACOS_pct':float((total_spend/total_sales*100).quantize(Decimal('0.01'))) if total_sales else None,
            '已购买':None,'归属方法':','.join(sorted(a['methods'])) if a['methods'] else 'no_ad',
        })
        rows.append(row)
    rows.sort(key=lambda x: ({'ZJ':1,'XH':2,'XM':3}[x['运营']],x['产品代号']))
    return rows


def audit_reference(rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues=[]
    for r in rows:
        spend_sum=sum(D(r[f'{t}费用']) for t in TYPES)
        units_sum=sum(D(r[f'{t}广告单']) for t in TYPES)
        if abs(spend_sum-D(r['总费用'])) > Decimal('0.02'):
            issues.append((r['运营'],r['产品代号'],'spend_conservation'))
        if abs(units_sum-D(r['总广告单'])) > Decimal('0.0002'):
            issues.append((r['运营'],r['产品代号'],'units_conservation'))
        expected=(D(r['总费用'])/D(r['全部订单'])).quantize(Decimal('0.01')) if D(r['全部订单']) else Decimal(0)
        if abs(expected-D(r['综合CPO'])) > Decimal('0.01'):
            issues.append((r['运营'],r['产品代号'],'cpo_formula'))
    return {'rows':len(rows),'issues':issues,'ok':not issues}
