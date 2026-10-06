from __future__ import annotations

from datetime import date
from typing import Any, Optional
import re

from .product_mapping import OPERATOR_NAMES, product_mappings, operator_name
from .operator_cpo import BUSINESS_ACCOUNTS
from .rds_query import query_rows, query_one, mutate_one

NAME_TO_PREFIX = {v:k for k,v in OPERATOR_NAMES.items()}
DEDICATED_ACCOUNT_OPERATORS = {
    '洁博利': ('爱菊', 'AJ'),
}


def _safe(v: str) -> str:
    return (v or '').replace("'", "''")


def _current_status(status: str) -> bool:
    value=(status or '').strip()
    return value == '当前业务报告已命中' or value.startswith('当前在售')


def latest_business_date() -> str:
    r=query_one("""
      SELECT max(report_start_date)::text d
      FROM core.business_report_parent_asin_period
      WHERE report_start_date=report_end_date
    """)
    return (r or {}).get('d') or date.today().isoformat()


def discover_new_products(target_date: Optional[str]=None, account: Optional[str]=None) -> dict[str,Any]:
    """Read-only discovery. Never writes product mapping automatically."""
    if target_date:
        date.fromisoformat(target_date)
    account_filter=''
    if account:
        aid=BUSINESS_ACCOUNTS.get(account)
        if not aid:
            return {'status':'BLOCKED','message':'未知业务账户','candidates':[]}
        account_filter=f"AND b.account_id='{_safe(aid)}'"

    if target_date:
        date_filter=f"AND b.report_start_date=DATE '{target_date}' AND b.report_end_date=DATE '{target_date}'"
        scan_date=target_date
        biz=query_rows(f"""
          SELECT b.account_id,b.account_name,b.parent_asin,b.title,b.report_start_date::text report_date,
                 b.ordered_product_units::float8 ordered_units,b.sessions_total::float8 sessions
          FROM core.business_report_parent_asin_period b
          WHERE 1=1 {account_filter} {date_filter}
          ORDER BY b.account_id,b.parent_asin
        """)
    else:
        scan_date='各账户最新业务报告'
        biz=query_rows(f"""
          WITH latest AS (
            SELECT account_id,max(report_start_date) d
            FROM core.business_report_parent_asin_period
            WHERE report_start_date=report_end_date
            GROUP BY account_id
          )
          SELECT b.account_id,b.account_name,b.parent_asin,b.title,b.report_start_date::text report_date,
                 b.ordered_product_units::float8 ordered_units,b.sessions_total::float8 sessions
          FROM core.business_report_parent_asin_period b
          JOIN latest l ON l.account_id=b.account_id AND l.d=b.report_start_date
          WHERE b.report_start_date=b.report_end_date {account_filter}
          ORDER BY b.account_id,b.parent_asin
        """)

    mapped={
        (r.get('businessAccount') or '', (r.get('parentAsin') or '').strip())
        for r in product_mappings().get('rows',[]) if (r.get('parentAsin') or '').strip()
    }
    id_to_account={v:k for k,v in BUSINESS_ACCOUNTS.items()}
    raw=[]
    for b in biz:
        account_name=id_to_account.get(b.get('account_id'), b.get('account_name') or '')
        parent=(b.get('parent_asin') or '').strip()
        if (account_name,parent) in mapped:
            continue
        raw.append({**b,'businessAccount':account_name})

    # Use ad Campaign naming only as a suggestion. It never finalizes ownership.
    if raw:
        parent_keys=','.join("'%s'" % _safe(x['parent_asin']) for x in raw)
        ad=query_rows(f"""
          SELECT p.account_id,p.advertised_product_parent_id parent_asin,
                 max(p.campaign_name) campaign_name,
                 sum(p.cost)::float8 spend
          FROM core.subscribed_product_cpo_daily p
          WHERE p.advertised_product_parent_id IN ({parent_keys})
          GROUP BY p.account_id,p.advertised_product_parent_id
        """)
    else:
        ad=[]
    ad_map={(x.get('account_id'),x.get('parent_asin')):x for x in ad}

    out=[]
    for idx,b in enumerate(raw,1):
        a=ad_map.get((b.get('account_id'),b.get('parent_asin'))) or {}
        campaign=a.get('campaign_name') or ''
        group=''; product=''; op=''
        m=re.match(r'^([A-Za-z]{2}\d*)[-_\s]+([A-Za-z0-9]+)',campaign)
        if m:
            group=m.group(1).upper(); product=m.group(2); op=operator_name(group)
        dedicated=DEDICATED_ACCOUNT_OPERATORS.get(b.get('businessAccount') or '')
        if dedicated and not op:
            op, group = dedicated
        confidence='高' if product and op else ('中' if op else '低')
        out.append({
            'id':f"{b.get('account_id')}:{b.get('parent_asin')}",
            'businessAccount':b.get('businessAccount') or '',
            'parentAsin':b.get('parent_asin') or '',
            'title':b.get('title') or '',
            'reportDate':b.get('report_date') or '',
            'orderedUnits':b.get('ordered_units') or 0,
            'sessions':b.get('sessions') or 0,
            'operatorCandidate':op,
            'operatorGroupCandidate':group,
            'productCandidate':product,
            'campaignEvidence':campaign,
            'adSpendEvidence':round(float(a.get('spend') or 0),2),
            'confidence':confidence,
            'status':'待确认',
        })
    return {
        'status':'OK','scanDate':scan_date,'account':account or '全部业务账户',
        'count':len(out),'candidates':out,
        'note':'自动扫描只生成候选；必须人工确认后才进入正式产品映射。',
    }


def create_manual_mapping(payload: dict[str,Any]) -> dict[str,Any]:
    name=(payload.get('operatorName') or '').strip()
    product=(payload.get('product') or '').strip()
    business=(payload.get('businessAccount') or '').strip()
    parent=(payload.get('parentAsin') or '').strip().upper()
    ad=(payload.get('adAccount') or business).strip()
    group=(payload.get('operatorGroup') or NAME_TO_PREFIX.get(name,'')).strip().upper()
    status=(payload.get('status') or '当前在售（手动确认）').strip()
    ref_date=(payload.get('referenceDate') or date.today().isoformat()).strip()
    if not name or not product or not business or not parent:
        return {'status':'BLOCKED','code':'MISSING_REQUIRED','message':'运营姓名、产品代号、业务账户、父ASIN为必填'}
    if name not in OPERATOR_NAMES.values():
        return {'status':'BLOCKED','code':'UNKNOWN_OPERATOR','message':'运营姓名不在标准运营字典中'}
    if not re.fullmatch(r'B0[A-Z0-9]{8}',parent):
        return {'status':'BLOCKED','code':'INVALID_PARENT_ASIN','message':'父ASIN格式不正确'}

    existing=product_mappings().get('rows',[])
    for r in existing:
        if r.get('operatorName')==name and r.get('product')==product and r.get('businessAccount')==business and (r.get('parentAsin') or '').upper()==parent:
            return {'status':'DUPLICATE','message':'该产品映射已经存在','row':r}

    result=mutate_one(f"""
      INSERT INTO chatgpt_ops.product_mapping_overrides
        (operator_name,operator_group,product_code,business_account,ad_account,parent_asin,asin_count,sku_count,mapping_status,effective_date,source,is_active)
      VALUES
        ('{_safe(name)}','{_safe(group)}','{_safe(product)}','{_safe(business)}','{_safe(ad)}','{_safe(parent)}',
         {int(payload.get('asinCount') or 0)},{int(payload.get('skuCount') or 0)},'{_safe(status)}',DATE '{_safe(ref_date)}','manual_ui',true)
      ON CONFLICT (operator_name,product_code,business_account,parent_asin)
      DO UPDATE SET ad_account=EXCLUDED.ad_account,operator_group=EXCLUDED.operator_group,
                    mapping_status=EXCLUDED.mapping_status,effective_date=EXCLUDED.effective_date,
                    is_active=true,updated_at=now()
      RETURNING mapping_id
    """)
    return {'status':'CREATED','message':'人工产品映射已保存到 RDS','mappingId':(result or {}).get('mapping_id')}
