from datetime import date, timedelta
from typing import Any, Optional
from .rds_query import query_rows, query_one
from .product_mapping import product_mappings

ACCOUNTS = {
    '川鹏': ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh', 'WHITIN', '2026-08-26'),
    '欧德思': ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919', 'BLOOMNEXT', '2026-08-25'),
    '洁博利': ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh', 'JOOMRA DIRECT', None),
    'AMS': ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz', 'anac1973 (C3S8S)', '2026-08-27'),
}
BY_ID = {v[0]: (k, v[1], v[2]) for k, v in ACCOUNTS.items()}
DEFAULT_ACCOUNT_ID = ACCOUNTS['川鹏'][0]
KNOWN_L1 = ('SP', 'SB', 'SD', 'STV')

FORMULAS = {
    'ad_spend': 'SUM(CPO推广商品.总成本)',
    'ad_orders': 'SUM(CPO推广商品.已售商品数量)',
    'total_orders': 'SUM(业务报告.已订购商品数量)',
    'cpo': '广告花费 / 全部订单',
    'roas': '广告归因销售额 / 广告花费',
    'tacos_pct': '广告花费 / 业务报告总销售额 × 100%',
    'organic_orders': 'SOP V3.5 暂不计算；禁止直接使用 全部订单-广告单',
    'type_unit_cost': '广告类型花费 / 广告类型已售商品数量',
}


def _date(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return date.fromisoformat(value).isoformat()


def resolve(account_id: Optional[str], stat_date: Optional[str]):
    aid = account_id if account_id in BY_ID else DEFAULT_ACCOUNT_ID
    store, account_name, default_date = BY_ID[aid]
    day = _date(stat_date) or default_date
    if not day:
        latest = query_one(
            "SELECT max(stat_date)::text AS d FROM core.subscribed_product_cpo_daily "
            f"WHERE account_id='{aid}'"
        )
        if not latest or not latest.get('d'):
            latest = query_one(
                "SELECT max(stat_date)::text AS d FROM core.subscribed_product_daily "
                f"WHERE account_id='{aid}'"
            )
        day = latest['d'] if latest and latest.get('d') else date.today().isoformat()
    return aid, store, account_name, day


def _fact_source(aid: str, day: str):
    cpo = query_one(
        "SELECT count(*)::int AS n FROM core.subscribed_product_cpo_daily "
        f"WHERE account_id='{aid}' AND stat_date=DATE '{day}'"
    )
    if cpo and int(cpo.get('n') or 0) > 0:
        return 'core.subscribed_product_cpo_daily', 'cpo_report'
    return 'core.subscribed_product_daily', 'product_report_fallback'


def _ad_type_rows(aid: str, day: str, fact_table: str):
    # Campaign metadata is authoritative for L1. Name fallback is only used when metadata is absent.
    return query_rows(f"""
        WITH cm AS (
          SELECT account_id,campaign_id,stat_date,
                 max(ad_product) AS ad_product,
                 max(campaign_name) AS campaign_name
          FROM core.subscribed_campaign_daily
          WHERE account_id='{aid}' AND stat_date=DATE '{day}'
          GROUP BY account_id,campaign_id,stat_date
        ), f AS (
          SELECT p.cost,p.units,p.sales,p.campaign_id,p.stat_date,
                 COALESCE(cm.ad_product,'') AS ad_product,
                 COALESCE(cm.campaign_name,p.campaign_name,'') AS campaign_name
          FROM {fact_table} p
          LEFT JOIN cm ON cm.account_id=p.account_id AND cm.campaign_id=p.campaign_id AND cm.stat_date=p.stat_date
          WHERE p.account_id='{aid}' AND p.stat_date=DATE '{day}'
        ), typed AS (
          SELECT cost,units,sales,
            CASE
              WHEN ad_product='Sponsored TV' THEN 'STV'
              WHEN ad_product='Sponsored Display' THEN 'SD'
              WHEN ad_product='Sponsored Brands' THEN 'SB'
              WHEN ad_product='Sponsored Products' THEN 'SP'
              WHEN campaign_name ~* '(流媒体|streaming[ ]?tv|sponsored[ ]?tv)' THEN 'STV'
              WHEN campaign_name ~* '(sponsored[ ]?display|展示)' THEN 'SD'
              WHEN campaign_name ~* '(sponsored[ ]?brand|头条|sbv)' THEN 'SB'
              WHEN campaign_name ~* '(auto|自动|手动|广泛|精准|词组)' THEN 'SP'
              ELSE 'UNCLASSIFIED' END AS l1,
            CASE
              WHEN ad_product='Sponsored TV' OR (ad_product='' AND campaign_name ~* '(流媒体|streaming[ ]?tv|sponsored[ ]?tv)') THEN 'STV_STREAMING'
              WHEN ad_product='Sponsored Display' OR (ad_product='' AND campaign_name ~* '(sponsored[ ]?display|展示)') THEN 'SD_DISPLAY'
              WHEN ad_product='Sponsored Brands' OR (ad_product='' AND campaign_name ~* '(sponsored[ ]?brand|头条|sbv)') THEN
                   CASE WHEN campaign_name ~* '(视频|video|sbv)' THEN 'SB_VIDEO' ELSE 'SB_HEADLINE' END
              WHEN ad_product='Sponsored Products' OR (ad_product='' AND campaign_name ~* '(auto|自动|手动|广泛|精准|词组)') THEN
                   CASE WHEN campaign_name ~* '(auto|自动)' THEN 'SP_AUTO' ELSE 'SP_MANUAL' END
              ELSE 'UNCLASSIFIED' END AS l2
          FROM f
        )
        SELECT l1,l2,ROUND(SUM(cost)::numeric,2)::float8 AS spend,
               COALESCE(SUM(units),0)::float8 AS orders,
               ROUND(COALESCE(SUM(sales),0)::numeric,2)::float8 AS sales
        FROM typed GROUP BY l1,l2 ORDER BY l1,spend DESC
    """)


def _mapping_rows_for(aid: str, day: str, operator: Optional[str] = None):
    store = BY_ID.get(aid, ('', '', None))[0]
    rows=[]
    for r in product_mappings().get('rows', []):
        if r.get('status') != '当前业务报告已命中':
            continue
        if store and store not in (r.get('businessAccount') or ''):
            continue
        dates = [x.strip() for x in (r.get('referenceDate') or '').split('/') if x.strip()]
        if dates and day not in dates:
            continue
        if operator and r.get('operator') != operator:
            continue
        parent=(r.get('parentAsin') or '').strip()
        if not parent:
            continue
        rows.append(r)
    return rows


def _mapping_values_sql(rows):
    vals=[]
    seen=set()
    for r in rows:
        key=(r['operator'],r['parentAsin'])
        if key in seen: continue
        seen.add(key)
        op=r['operator'].replace("'","''")
        pa=r['parentAsin'].replace("'","''")
        vals.append(f"('{op}','{pa}')")
    return ','.join(vals)


def _operator_performance(aid: str, day: str, fact_table: str):
    # Dynamic operator scope from the independent product mapping table.
    # This removes the old ZJ/XH/XM hard-code and keeps operator identity as e.g. ZJ1/AJ1/DD1.
    mapping_rows=_mapping_rows_for(aid,day)
    values=_mapping_values_sql(mapping_rows)
    if not values:
        return []
    rows = query_rows(f"""
        WITH m(operator,parent_asin) AS (VALUES {values}), ad AS (
          SELECT advertised_product_parent_id parent_asin,
                 SUM(cost)::numeric spend,SUM(units)::numeric ad_orders,SUM(sales)::numeric ad_sales
          FROM {fact_table}
          WHERE account_id='{aid}' AND stat_date=DATE '{day}'
          GROUP BY 1
        ), biz AS (
          SELECT parent_asin,ordered_product_units::numeric total_orders,ordered_product_sales::numeric total_sales
          FROM core.business_report_parent_asin_period
          WHERE account_id='{aid}' AND report_start_date=DATE '{day}' AND report_end_date=DATE '{day}'
        )
        SELECT m.operator AS name,
               ROUND(SUM(COALESCE(ad.spend,0))::numeric,2)::float8 spend,
               SUM(COALESCE(ad.ad_orders,0))::float8 ad_orders,
               SUM(COALESCE(biz.total_orders,0))::float8 total_orders,
               ROUND(SUM(COALESCE(ad.ad_sales,0))::numeric,2)::float8 ad_sales,
               ROUND(SUM(COALESCE(biz.total_sales,0))::numeric,2)::float8 total_sales,
               COUNT(DISTINCT m.parent_asin)::int products
        FROM m JOIN biz USING(parent_asin) LEFT JOIN ad USING(parent_asin)
        GROUP BY m.operator ORDER BY m.operator
    """)
    result=[]
    for r in rows:
        spend=float(r['spend'] or 0); ad_orders=float(r['ad_orders'] or 0); total=float(r['total_orders'] or 0)
        ad_sales=float(r['ad_sales'] or 0); total_sales=float(r['total_sales'] or 0)
        result.append({
            'name':r['name'],'spend':round(spend,2),'adOrders':round(ad_orders,2),'totalOrders':round(total,2),
            'organic':None,'cpo':round(spend/total,2) if total else None,
            'roas':round(ad_sales/spend,2) if spend else None,
            'tacos':round(spend/total_sales*100,2) if total_sales else None,
            'products':int(r.get('products') or 0),
            'maturity':None,'change':None,'status':'映射预览','scope':'product_mapping_parent_preview',
        })
    return result


def dashboard_overview(account_id: Optional[str] = None, stat_date: Optional[str] = None) -> dict[str, Any]:
    aid, store, account_name, day = resolve(account_id, stat_date)
    fact_table, fact_source = _fact_source(aid, day)
    metrics = query_one(f"""
        WITH ad AS (
          SELECT SUM(cost)::numeric spend,SUM(units)::numeric ad_orders,SUM(sales)::numeric ad_sales,count(*)::int ad_rows
          FROM {fact_table} WHERE account_id='{aid}' AND stat_date=DATE '{day}'
        ), biz AS (
          SELECT SUM(ordered_product_units)::numeric total_orders,
                 SUM(ordered_product_sales)::numeric total_sales,COUNT(*)::int business_rows
          FROM core.business_report_parent_asin_period
          WHERE account_id='{aid}' AND report_start_date=DATE '{day}' AND report_end_date=DATE '{day}'
        )
        SELECT ROUND(COALESCE(ad.spend,0),2)::float8 ad_spend,
               COALESCE(ad.ad_orders,0)::float8 ad_orders,
               ROUND(COALESCE(ad.ad_sales,0),2)::float8 ad_sales,
               COALESCE(ad.ad_rows,0)::int ad_rows,
               COALESCE(biz.total_orders,0)::float8 total_orders,
               ROUND(COALESCE(biz.total_sales,0),2)::float8 total_sales,
               COALESCE(biz.business_rows,0)::int business_rows
        FROM ad CROSS JOIN biz
    """) or {}
    spend=float(metrics.get('ad_spend') or 0); total=float(metrics.get('total_orders') or 0)
    ad_sales=float(metrics.get('ad_sales') or 0); total_sales=float(metrics.get('total_sales') or 0)
    typed=_ad_type_rows(aid,day,fact_table)
    by_l1={k:[] for k in KNOWN_L1}; unclassified={'spend':0.0,'orders':0.0,'sales':0.0}
    for r in typed:
        record={'name':r['l2'],'spend':float(r['spend'] or 0),'orders':float(r['orders'] or 0),'sales':float(r['sales'] or 0)}
        record['cpo']=round(record['spend']/record['orders'],2) if record['orders'] else None
        if r['l1'] in by_l1: by_l1[r['l1']].append(record)
        else:
            unclassified['spend']+=record['spend']; unclassified['orders']+=record['orders']; unclassified['sales']+=record['sales']
    ad_types=[]
    for l1 in KNOWN_L1:
        children=by_l1[l1]; sp=sum(x['spend'] for x in children); orders=sum(x['orders'] for x in children); sales=sum(x['sales'] for x in children)
        ad_types.append({'l1':l1,'spend':round(sp,2),'orders':round(orders,2),'sales':round(sales,2),
                         'cpo':round(sp/orders,2) if orders else None,'children':children})
    return {
        'data_source':'rds','fact_source':fact_source,'fact_table':fact_table,
        'account_id':aid,'account_name':account_name,'store':store,'data_date':day,
        'ad_fact_rows':int(metrics.get('ad_rows') or 0),'business_report_rows':int(metrics.get('business_rows') or 0),
        'ad_spend':round(spend,2),'total_orders':round(total,2),'ad_orders':round(float(metrics.get('ad_orders') or 0),2),
        'ad_sales':round(ad_sales,2),'total_sales':round(total_sales,2),
        'estimated_organic_orders':None,'estimated_organic_share':None,
        'cpo':round(spend/total,2) if total else None,
        'roas':round(ad_sales/spend,2) if spend else None,
        'tacos_pct':round(spend/total_sales*100,2) if total_sales else None,
        'ad_types':ad_types,'unclassified':{k:round(v,2) for k,v in unclassified.items()},
        'performance':[],
        'performance_data_source':'moved_to_operator_cpo',
        'formula_meta':FORMULAS,
        'quality_flags':[
            'organic_orders_disabled_by_sop_v3_5',
            *(['ad_only_subaccount_rollup_required'] if store=='AMS' else []),
            *(['missing_business_report_for_date'] if store!='AMS' and int(metrics.get('business_rows') or 0)==0 else []),
            *(['ad_type_unclassified_rows_present'] if unclassified['spend'] else []),
        ],
    }


def dashboard_trend(account_id: Optional[str] = None, end_date: Optional[str] = None, days: int = 14):
    aid, _, _, default_day = resolve(account_id, end_date)
    end = _date(end_date) or default_day
    start=(date.fromisoformat(end)-timedelta(days=days-1)).isoformat()
    # Use CPO table where available; do not mix an older CPO snapshot and a newer generic product fact on the same day.
    return query_rows(f"""
        WITH ad AS (
          SELECT stat_date,SUM(cost)::numeric spend,SUM(units)::numeric ad_orders,SUM(sales)::numeric ad_sales
          FROM core.subscribed_product_cpo_daily
          WHERE account_id='{aid}' AND stat_date BETWEEN DATE '{start}' AND DATE '{end}' GROUP BY stat_date
        ), biz AS (
          SELECT report_start_date stat_date,SUM(ordered_product_units)::numeric total_orders,SUM(ordered_product_sales)::numeric total_sales
          FROM core.business_report_parent_asin_period
          WHERE account_id='{aid}' AND report_start_date=report_end_date GROUP BY report_start_date
        )
        SELECT to_char(ad.stat_date,'MM/DD') date,
               CASE WHEN biz.total_orders>0 THEN ROUND((ad.spend/biz.total_orders)::numeric,2)::float8 ELSE NULL END cpo,
               ad.ad_orders::float8 "adOrders",NULL::float8 "organicOrders",
               CASE WHEN ad.spend>0 THEN ROUND((ad.ad_sales/ad.spend)::numeric,2)::float8 ELSE NULL END roas,
               CASE WHEN biz.total_sales>0 THEN ROUND((ad.spend/biz.total_sales*100)::numeric,2)::float8 ELSE NULL END tacos,
               CASE WHEN biz.total_orders IS NULL THEN '广告数据' ELSE '业务+广告' END maturity
        FROM ad LEFT JOIN biz USING(stat_date) ORDER BY ad.stat_date
    """)


def products(account_id: Optional[str] = None, stat_date: Optional[str] = None, limit: int = 50):
    aid, store, account_name, day = resolve(account_id, stat_date)
    fact_table, fact_source = _fact_source(aid,day)
    if aid == DEFAULT_ACCOUNT_ID:
        rows=query_rows(f"""
          WITH m AS (
            SELECT split_part(alias_code,'|',2) group_code,split_part(alias_code,'|',3) parent_asin,canonical_product_code
            FROM core.product_alias
            WHERE account_id='{aid}' AND alias_source='sku' AND alias_code LIKE 'OPARENT|%'
              AND resolution_status='resolved'
          ), ad AS (
            SELECT advertised_product_parent_id parent_asin,SUM(cost)::numeric spend,SUM(units)::numeric ad_orders,SUM(sales)::numeric ad_sales
            FROM {fact_table} WHERE account_id='{aid}' AND stat_date=DATE '{day}' GROUP BY 1
          ), biz AS (
            SELECT parent_asin,title,ordered_product_units::numeric total_orders,ordered_product_sales::numeric total_sales,sessions_total::numeric sessions
            FROM core.business_report_parent_asin_period
            WHERE account_id='{aid}' AND report_start_date=DATE '{day}' AND report_end_date=DATE '{day}'
          )
          SELECT m.group_code,m.canonical_product_code AS code,m.parent_asin,b.title,
                 ROUND(COALESCE(ad.spend,0)::numeric,2)::float8 spend,COALESCE(ad.ad_orders,0)::float8 ad_orders,
                 ROUND(COALESCE(ad.ad_sales,0)::numeric,2)::float8 ad_sales,
                 COALESCE(b.total_orders,0)::float8 total_orders,ROUND(COALESCE(b.total_sales,0)::numeric,2)::float8 total_sales,
                 COALESCE(b.sessions,0)::float8 sessions,
                 CASE WHEN b.total_orders>0 THEN ROUND((COALESCE(ad.spend,0)/b.total_orders)::numeric,2)::float8 END cpo,
                 CASE WHEN ad.spend>0 THEN ROUND((ad.ad_sales/ad.spend)::numeric,2)::float8 END roas,
                 CASE WHEN b.total_sales>0 THEN ROUND((COALESCE(ad.spend,0)/b.total_sales*100)::numeric,2)::float8 END tacos
          FROM m LEFT JOIN ad USING(parent_asin) LEFT JOIN biz b USING(parent_asin)
          WHERE b.parent_asin IS NOT NULL
          ORDER BY spend DESC LIMIT {max(1,min(limit,200))}
        """)
        allocation='advertised_parent_preview'
    else:
        rows=query_rows(f"""
          WITH ad AS (
            SELECT advertised_product_parent_id parent_asin,SUM(cost)::numeric spend,SUM(units)::numeric ad_orders,SUM(sales)::numeric ad_sales
            FROM {fact_table} WHERE account_id='{aid}' AND stat_date=DATE '{day}' GROUP BY 1
          ), biz AS (
            SELECT parent_asin,title,ordered_product_units::numeric total_orders,ordered_product_sales::numeric total_sales,sessions_total::numeric sessions
            FROM core.business_report_parent_asin_period
            WHERE account_id='{aid}' AND report_start_date=DATE '{day}' AND report_end_date=DATE '{day}'
          )
          SELECT NULL::text group_code,b.parent_asin AS code,b.parent_asin,b.title,
                 ROUND(COALESCE(ad.spend,0)::numeric,2)::float8 spend,COALESCE(ad.ad_orders,0)::float8 ad_orders,
                 ROUND(COALESCE(ad.ad_sales,0)::numeric,2)::float8 ad_sales,
                 COALESCE(b.total_orders,0)::float8 total_orders,ROUND(COALESCE(b.total_sales,0)::numeric,2)::float8 total_sales,
                 COALESCE(b.sessions,0)::float8 sessions,
                 CASE WHEN b.total_orders>0 THEN ROUND((COALESCE(ad.spend,0)/b.total_orders)::numeric,2)::float8 END cpo,
                 CASE WHEN ad.spend>0 THEN ROUND((ad.ad_sales/ad.spend)::numeric,2)::float8 END roas,
                 CASE WHEN b.total_sales>0 THEN ROUND((COALESCE(ad.spend,0)/b.total_sales*100)::numeric,2)::float8 END tacos
          FROM biz b LEFT JOIN ad USING(parent_asin) ORDER BY spend DESC LIMIT {max(1,min(limit,200))}
        """)
        allocation='parent_asin_preview'
    for r in rows:
        r['organic_orders']=None
    return {'data_source':'rds','fact_source':fact_source,'account_id':aid,'account_name':account_name,'store':store,'data_date':day,
            'allocation_status':allocation,'final_cpo':False,'rows':rows,'formula_meta':FORMULAS,
            'warning':'产品广告侧当前按推广父ASIN预览；Campaign特殊分摊规则完成后才能标记为最终CPO。'}


def operator_detail(operator: str, stat_date: Optional[str] = None):
    group=operator.upper()
    # Resolve account from the independent product mapping table. Prefer a row whose reference date matches request.
    candidates=[r for r in product_mappings().get('rows',[]) if r.get('operator')==group and r.get('status')=='当前业务报告已命中']
    if stat_date:
        exact=[r for r in candidates if stat_date in [x.strip() for x in (r.get('referenceDate') or '').split('/') if x.strip()]]
        if exact: candidates=exact
    if not candidates:
        return {'data_source':'mapping','operator':group,'products':[],'summary':{},'final_cpo':False,'warning':'该运营在当前参考日没有已确认的业务产品映射。'}
    # Determine main business account from mapping; AMS is never a business account.
    business=(candidates[0].get('businessAccount') or '').split('+')[0].strip()
    if business not in ACCOUNTS:
        business='川鹏'
    aid=ACCOUNTS[business][0]
    _, _, account_name, default_day=resolve(aid, stat_date)
    day=_date(stat_date) or default_day
    fact_table,fact_source=_fact_source(aid,day)
    mrows=_mapping_rows_for(aid,day,group)
    values=_mapping_values_sql(mrows)
    if not values:
        return {'data_source':'mapping','operator':group,'account':business,'range':day,'data_date':day,'products':[],'summary':{},'final_cpo':False,'warning':'该日期没有已确认的产品映射。'}
    rows=query_rows(f"""
      WITH m(operator,parent_asin) AS (VALUES {values}), ad AS (
        SELECT advertised_product_parent_id parent_asin,SUM(cost)::numeric spend,SUM(units)::numeric ad_orders,SUM(sales)::numeric ad_sales
        FROM {fact_table} WHERE account_id='{aid}' AND stat_date=DATE '{day}' GROUP BY 1
      ), biz AS (
        SELECT parent_asin,title,ordered_product_units::numeric total_orders,ordered_product_sales::numeric total_sales
        FROM core.business_report_parent_asin_period
        WHERE account_id='{aid}' AND report_start_date=DATE '{day}' AND report_end_date=DATE '{day}'
      )
      SELECT m.parent_asin,b.title,ROUND(COALESCE(ad.spend,0)::numeric,2)::float8 spend,
             COALESCE(ad.ad_orders,0)::float8 ad_orders,ROUND(COALESCE(ad.ad_sales,0)::numeric,2)::float8 ad_sales,
             COALESCE(b.total_orders,0)::float8 total_orders,ROUND(COALESCE(b.total_sales,0)::numeric,2)::float8 total_sales,
             CASE WHEN b.total_orders>0 THEN ROUND((COALESCE(ad.spend,0)/b.total_orders)::numeric,2)::float8 END cpo,
             CASE WHEN ad.spend>0 THEN ROUND((ad.ad_sales/ad.spend)::numeric,2)::float8 END roas,
             CASE WHEN b.total_sales>0 THEN ROUND((COALESCE(ad.spend,0)/b.total_sales*100)::numeric,2)::float8 END tacos
      FROM m JOIN biz b USING(parent_asin) LEFT JOIN ad USING(parent_asin) ORDER BY spend DESC
    """)
    code_by_parent={r['parentAsin']:r['product'] for r in mrows}
    ad_type=query_rows(f"""
      WITH m(operator,parent_asin) AS (VALUES {values}), cm AS (
        SELECT account_id,campaign_id,stat_date,max(ad_product) ad_product,max(campaign_name) campaign_name
        FROM core.subscribed_campaign_daily WHERE account_id='{aid}' AND stat_date=DATE '{day}' GROUP BY 1,2,3
      ), f AS (
        SELECT m.parent_asin,p.cost,p.units,COALESCE(cm.ad_product,'') ad_product,COALESCE(cm.campaign_name,p.campaign_name,'') campaign_name
        FROM {fact_table} p JOIN m ON m.parent_asin=p.advertised_product_parent_id
        LEFT JOIN cm ON cm.account_id=p.account_id AND cm.campaign_id=p.campaign_id AND cm.stat_date=p.stat_date
        WHERE p.account_id='{aid}' AND p.stat_date=DATE '{day}'
      )
      SELECT parent_asin,
        ROUND(COALESCE(SUM(cost) FILTER (WHERE ad_product='Sponsored Products' OR (ad_product='' AND campaign_name ~* '(auto|自动|手动|广泛|精准|词组)')),0)::numeric,2)::float8 sp,
        ROUND(COALESCE(SUM(cost) FILTER (WHERE ad_product='Sponsored Brands' OR (ad_product='' AND campaign_name ~* '(sponsored[ ]?brand|头条|sbv)')),0)::numeric,2)::float8 sb,
        ROUND(COALESCE(SUM(cost) FILTER (WHERE ad_product='Sponsored Display' OR (ad_product='' AND campaign_name ~* '(sponsored[ ]?display|展示)')),0)::numeric,2)::float8 sd,
        ROUND(COALESCE(SUM(cost) FILTER (WHERE ad_product='Sponsored TV' OR (ad_product='' AND campaign_name ~* '(流媒体|streaming[ ]?tv)')),0)::numeric,2)::float8 stv,
        COALESCE(SUM(units) FILTER (WHERE ad_product='Sponsored Products' OR (ad_product='' AND campaign_name ~* '(auto|自动|手动|广泛|精准|词组)')),0)::float8 sp_orders,
        COALESCE(SUM(units) FILTER (WHERE ad_product='Sponsored Brands' OR (ad_product='' AND campaign_name ~* '(sponsored[ ]?brand|头条|sbv)')),0)::float8 sb_orders,
        COALESCE(SUM(units) FILTER (WHERE ad_product='Sponsored Display' OR (ad_product='' AND campaign_name ~* '(sponsored[ ]?display|展示)')),0)::float8 sd_orders,
        COALESCE(SUM(units) FILTER (WHERE ad_product='Sponsored TV' OR (ad_product='' AND campaign_name ~* '(流媒体|streaming[ ]?tv)')),0)::float8 stv_orders
      FROM f GROUP BY parent_asin
    """)
    types={r['parent_asin']:{'spend':{'DSP':None,'SP':float(r['sp'] or 0),'SB':float(r['sb'] or 0),'SD':float(r['sd'] or 0),'STV':float(r['stv'] or 0)},'orders':{'DSP':None,'SP':float(r['sp_orders'] or 0),'SB':float(r['sb_orders'] or 0),'SD':float(r['sd_orders'] or 0),'STV':float(r['stv_orders'] or 0)}} for r in ad_type}
    products_out=[]
    for r in rows:
        spend=float(r['spend'] or 0); ad_orders=float(r['ad_orders'] or 0); total=float(r['total_orders'] or 0); parent=r['parent_asin']
        products_out.append({'code':code_by_parent.get(parent,parent),'parentAsin':parent,'title':r['title'],'spend':round(spend,2),'totalOrders':round(total,2),'adOrders':round(ad_orders,2),'organic':None,'cpo':r['cpo'],'roas':r['roas'],'tacos':r['tacos'],'maturity':None,'adTypeSpend':types.get(parent,{'spend':{'DSP':None,'SP':0,'SB':0,'SD':0,'STV':0}})['spend'],'adTypeOrders':types.get(parent,{'orders':{'DSP':None,'SP':0,'SB':0,'SD':0,'STV':0}})['orders'],'daily':[{'period':day[5:].replace('-','/'),'spend':round(spend,2),'adOrders':round(ad_orders,2),'totalOrders':round(total,2),'organic':None,'cpo':r['cpo'],'maturity':None,'status':'映射预览'}],'weekly':[]})
    s_spend=sum(float(r['spend'] or 0) for r in rows); s_ad=sum(float(r['ad_orders'] or 0) for r in rows); s_total=sum(float(r['total_orders'] or 0) for r in rows); s_adsales=sum(float(r['ad_sales'] or 0) for r in rows); s_sales=sum(float(r['total_sales'] or 0) for r in rows)
    return {'data_source':'rds','fact_source':fact_source,'allocation_status':'product_mapping_parent_preview','final_cpo':False,'operator':group,'account':f'{business}（映射预览）','range':day,'data_date':day,'summary':{'spend':round(s_spend,2),'totalOrders':round(s_total,2),'adOrders':round(s_ad,2),'organic':None,'organicShare':None,'cpo':round(s_spend/s_total,2) if s_total else None,'roas':round(s_adsales/s_spend,2) if s_spend else None,'tacos':round(s_spend/s_sales*100,2) if s_sales else None,'maturity':None},'products':products_out,'formula_meta':FORMULAS,'warning':'当前按独立产品映射表 + 推广父ASIN预览；特殊 Campaign/AMS 回卷完成后才能标记最终 CPO。'}


def reports():
    specs=[('广告活动','core.subscribed_campaign_daily','stat_date'),('推广的商品','core.subscribed_product_daily','stat_date'),
           ('CPO推广商品','core.subscribed_product_cpo_daily','stat_date'),('搜索词','core.subscribed_search_term_daily','stat_date'),
           ('广告位','core.subscribed_placement_daily','stat_date')]
    result=[]
    for label,table,dcol in specs:
        for r in query_rows(f"SELECT account_id,account_name,min({dcol})::text min_date,max({dcol})::text max_date,count(*)::int rows FROM {table} GROUP BY account_id,account_name ORDER BY account_name"):
            result.append({'account':r['account_name'],'account_id':r['account_id'],'type':label,'date':r['max_date'],'min_date':r['min_date'],'rows':r['rows'],'status':'READY','source':'rds'})
    for r in query_rows("SELECT account_id,account_name,min(report_start_date)::text min_date,max(report_end_date)::text max_date,count(*)::int rows FROM core.business_report_parent_asin_period GROUP BY account_id,account_name ORDER BY account_name"):
        result.append({'account':r['account_name'],'account_id':r['account_id'],'type':'业务报告','date':r['max_date'],'min_date':r['min_date'],'rows':r['rows'],'status':'READY','source':'rds'})
    return result
