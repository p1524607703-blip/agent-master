from pathlib import Path
import csv
from typing import Any
from .rds_query import query_rows
from .cache import cache

PROJECT_ROOT = Path(__file__).resolve().parents[3]
MAPPING_FILE = PROJECT_ROOT / 'reference' / 'product_mapping' / '全部账户_运营产品标准映射表.csv'

OPERATOR_NAMES = {
    'AJ':'爱菊','DD':'丹丹','LB':'丽斌','LW':'林文','XH':'鑫华',
    'XM':'雪敏','YS':'雨珊','YT':'雅婷','ZF':'珍凤','ZJ':'子娟',
}


def operator_name(group: str) -> str:
    value=(group or '').strip()
    if value in OPERATOR_NAMES.values():
        return value
    return OPERATOR_NAMES.get(value[:2].upper(), value)


def _load_product_mappings() -> dict[str, Any]:
    rows=[]
    if MAPPING_FILE.exists():
        with MAPPING_FILE.open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                group=r.get('运营组') or r.get('运营') or ''
                name=r.get('运营姓名') or operator_name(group)
                rows.append({
                    'operatorName': name,
                    'operatorGroup': group,
                    'operator': name,  # compatibility: UI should now use the name dimension.
                    'product': r.get('产品代号') or '',
                    'analyticsProduct': r.get('产品代号') or '',
                    'businessAccount': r.get('业务账户') or '',
                    'adAccount': r.get('广告账户') or '',
                    'parentAsin': r.get('父ASIN') or '',
                    'asinCount': int(r.get('ASIN数量') or 0),
                    'skuCount': int(r.get('SKU数量') or 0),
                    'status': r.get('当前状态') or '',
                    'referenceDate': r.get('参考日期') or '',
                })
    # 正规在售清单是当前责任范围的权威层；允许尚未出现业务父ASIN的新品先进入在售责任范围。
    try:
        roster_rows=query_rows("""
          SELECT brand,business_account,operator_name,operator_group,product_code,analytics_product_code,
                 front_asin,parent_asin,source_file
          FROM chatgpt_ops.product_roster
          WHERE is_active=true
          ORDER BY operator_name,business_account,product_code
        """)
    except Exception:
        roster_rows=[]
    roster_keys=set()
    for r in roster_rows:
        item={
            'operatorName':r.get('operator_name') or '',
            'operatorGroup':r.get('operator_group') or '',
            'operator':r.get('operator_name') or '',
            'product':r.get('product_code') or '',
            'analyticsProduct':r.get('analytics_product_code') or r.get('product_code') or '',
            'businessAccount':r.get('business_account') or '',
            'adAccount':r.get('business_account') or '',
            'parentAsin':r.get('parent_asin') or '',
            'frontAsin':r.get('front_asin') or '',
            'asinCount':0,'skuCount':0,
            'status':'当前在售（在售清单）',
            'referenceDate':'',
            'source':r.get('source_file') or 'product_roster',
            'brand':r.get('brand') or '',
        }
        roster_keys.add((item['operatorName'],item['businessAccount'],item['product']))
        rows.append(item)

    # 网页人工维护层保存在 chatgpt_ops，core/基础映射仍保持只读事实来源。
    try:
        manual_rows=query_rows("""
          SELECT operator_name,operator_group,product_code,business_account,ad_account,parent_asin,
                 asin_count,sku_count,mapping_status,effective_date::text reference_date,source
          FROM chatgpt_ops.product_mapping_overrides
          WHERE is_active=true
          ORDER BY operator_name,product_code
        """)
    except Exception:
        manual_rows=[]
    existing={(x['operatorName'],x['product'],x['businessAccount'],x['parentAsin']) for x in rows}
    for r in manual_rows:
        item={
            'operatorName': r.get('operator_name') or '',
            'operatorGroup': r.get('operator_group') or '',
            'operator': r.get('operator_name') or '',
            'product': r.get('product_code') or '',
            'analyticsProduct': r.get('product_code') or '',
            'businessAccount': r.get('business_account') or '',
            'adAccount': r.get('ad_account') or '',
            'parentAsin': r.get('parent_asin') or '',
            'asinCount': int(r.get('asin_count') or 0),
            'skuCount': int(r.get('sku_count') or 0),
            'status': r.get('mapping_status') or '当前在售（手动确认）',
            'referenceDate': r.get('reference_date') or '',
            'source': r.get('source') or 'manual_ui',
        }
        key=(item['operatorName'],item['product'],item['businessAccount'],item['parentAsin'])
        if key not in existing:
            rows.append(item); existing.add(key)
    deduped=[]
    seen=set()
    priority=sorted(rows,key=lambda r:(0 if (r.get('status') or '').startswith('当前在售') else 1, 0 if r.get('source') else 1))
    for r in priority:
        key=(r.get('operatorName'),r.get('product'),r.get('businessAccount'),r.get('parentAsin'),r.get('status'))
        if key in seen: continue
        seen.add(key); deduped.append(r)
    rows=deduped
    operators=sorted({r['operatorName'] for r in rows if r['operatorName']})
    business_accounts=sorted({r['businessAccount'] for r in rows if r['businessAccount']})
    statuses=sorted({r['status'] for r in rows if r['status']})
    return {
        'data_source': 'product_identity_plus_business_report_mapping',
        'rows': rows,
        'summary': {
            'total': len(rows),
            'active': sum(1 for r in rows if r['status']=='当前业务报告已命中' or r['status'].startswith('当前在售')),
            'history': sum(1 for r in rows if r['status'].startswith('历史身份')),
            'missingBusiness': sum(1 for r in rows if r['status']=='缺业务报告待确认'),
            'operators': len(operators),
        },
        'filters': {
            'operators': operators,
            'businessAccounts': business_accounts,
            'statuses': statuses,
        },
        'operatorNames': OPERATOR_NAMES,
        'note': '产品SKU运营表负责历史身份；运营维度统一使用姓名，AJ1/AJ2、XM1/XM2分别归并为同一运营；当天是否进入CPO仍由业务报告决定。',
    }


def product_mappings() -> dict[str, Any]:
    return cache.get_or_set('product-mappings:service', _load_product_mappings, 300)
