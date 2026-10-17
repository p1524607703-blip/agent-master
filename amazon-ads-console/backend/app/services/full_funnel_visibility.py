"""Brand disclosure permissions are independent of product expense ownership."""
import re
from collections import defaultdict

from .rds_query import query_rows


ROW_FIELDS = (
    'date', 'account', 'campaignId', 'campaignName', 'operatorName', 'group',
    'productCode', 'spend', 'adOrders', 'adSales', 'status',
)


def _operator_group(code):
    code = str(code or '').strip().upper()
    return code[:2] if re.fullmatch(r'[A-Z]{2}[0-9]+', code) else None


def _campaign_key(row):
    # Pending visibility requires evidence from this same account, day and campaign.
    if row.get('account') and row.get('date') and row.get('campaignId'):
        return row['account'], row['date'], str(row['campaignId'])
    return None


def _totals(rows):
    allocated = sum(float(r.get('spend') or 0) for r in rows if r.get('operatorName'))
    pending = sum(float(r.get('spend') or 0) for r in rows if not r.get('operatorName'))
    return {'spend': round(allocated + pending, 2), 'allocatedSpend': round(allocated, 2),
            'unallocatedSpend': round(pending, 2)}


def filter_full_funnel(ledger, policies, role_code, operator_code=None):
    """Return only authorized accounts; never reuse cached totals or modules."""
    management = role_code in ('management', 'super_admin')
    group = _operator_group(operator_code)
    operator = role_code == 'operator' and group is not None
    selected = []
    for policy in sorted(policies, key=lambda p: (p['display_order'], p['account_name'])):
        allowed = policy['is_active'] and (
            policy['access_scope'] == 'all_operators'
            or (policy['access_scope'] == 'operator_groups' and group in policy['allowed_groups'])
        )
        if management or (operator and allowed):
            selected.append(policy)

    rows_by_account = defaultdict(list)
    for row in ledger.get('rows') or []:
        rows_by_account[row.get('account') or ''].append({k: row[k] for k in ROW_FIELDS if k in row})
    participants = defaultdict(set)
    for rows in rows_by_account.values():
        for row in rows:
            key, owner_group = _campaign_key(row), _operator_group(row.get('group'))
            if key and owner_group and row.get('operatorName'):
                participants[key].add(owner_group)
    known_accounts = {p['account_name'] for p in policies}
    if management:
        for account in sorted(set(rows_by_account) - known_accounts):
            selected.append({'account_name': account, 'brand_name': '待核验账户',
                             'is_active': False, 'access_scope': '', 'allowed_groups': []})

    modules = []
    visible_rows = []
    for policy in selected:
        rows = rows_by_account[policy['account_name']]
        if not management:
            rows = [row for row in rows if (
                row.get('operatorName') and _operator_group(row.get('group')) == group
            ) or (
                not row.get('operatorName') and group in participants.get(_campaign_key(row), set())
            )]
            if not rows:
                continue
        visible_rows.extend(rows)
        if not policy['is_active']:
            visibility = '仅管理层可见'
        elif policy['access_scope'] == 'all_operators':
            visibility = '按实际归属运营组可见'
        else:
            visibility = '、'.join(policy['allowed_groups']) + ' 组内按实际归属可见'
        modules.append({'account': policy['account_name'], 'brandName': policy['brand_name'],
                        'visibilityLabel': visibility, 'rows': rows, **_totals(rows)})
    return {'label': '全流域广告活动', 'scope': 'brand_policy_and_confirmed_operator_group',
            'rows': visible_rows, 'modules': modules, **_totals(visible_rows),
            'note': '按品牌展示本组记录；待分摊仅对同日同活动有参与证据的组可见。已归属费用已含产品总费，请勿重复相加；待分摊不计入任一产品。'}


def full_funnel_for_viewer(ledger, role_code, operator_code=None):
    # Deliberately read policy for every response, including warm/stale data caches.
    # A policy read failure must propagate; never fall back to an unfiltered ledger.
    policies = query_rows('''
        SELECT account_name,brand_name,access_scope,allowed_groups,display_order,is_active
        FROM ops_products.full_funnel_visibility_policy ORDER BY display_order,account_name
    ''')
    return filter_full_funnel(ledger, policies, role_code, operator_code)
