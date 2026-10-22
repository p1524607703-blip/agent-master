"""Name-mode group ownership without inventing a financial product or split."""
import re

from .cpo_identity import token_match


def pending_group_expense(row, scope, source_meta, scoped_candidates, *, blocked=False, rule=None):
    """Only an exact, maintained group prefix can own an unresolved SB expense.

    A blocked source, explicit rule review or actual source in another group
    remains unresolved. This ledger never establishes a product identity.
    """
    if blocked or rule is not None or not scope or scope.startswith('__'):
        return None
    name = row.get('campaign_name') or ''
    prefix = re.match(r'^\s*([A-Z]{2}\d+)[-_]', name, re.I)
    groups = {g.upper() for g in re.findall(r'(?<![A-Z0-9])([A-Z]{2}\d+)[-_]', name, re.I)}
    if not prefix or len(groups) != 1:
        return None
    group = prefix.group(1).upper()
    candidates = scoped_candidates.get(scope, {})
    if not any(g == group for g, _ in candidates):
        return None
    if source_meta and source_meta.get('group') != group:
        return None
    if not any(abs(float(row.get(field) or 0)) > 0.000001 for field in ('spend', 'ad_orders', 'ad_sales')):
        return None
    known = sorted({code for g, code in candidates if g == group and token_match(name, code)})
    return {
        'date': row['stat_date'], 'account': row['account_name'],
        'accountId': row.get('account_id'), 'scope': scope,
        'campaignId': row['campaign_id'], 'campaignName': name,
        'group': group, 'operatorName': next(meta['operatorName'] for (g, _), meta in candidates.items() if g == group),
        'spend': float(row.get('spend') or 0), 'adOrders': float(row.get('ad_orders') or 0),
        'adSales': float(row.get('ad_sales') or 0),
        'reason': 'MULTIPLE_NAMED_PRODUCTS' if len(known) > 1 else 'CONFIRMED_ALIAS_REQUIRED',
        'knownNameCandidates': [{'group': group, 'productCode': code} for code in known],
        'status': 'GROUP_KNOWN_PRODUCT_PENDING',
    }


def pending_expenses(data, operator=None):
    return [dict(row) for row in data.get('groupPendingExpenses', [])
            if operator is None or row['operatorName'] == operator]


def pending_total(data, operator=None, field='spend'):
    return sum(float(row.get(field) or 0) for row in pending_expenses(data, operator))


def merge_pending_expenses(rows):
    """Aggregate source rows once at date/account/campaign/group boundaries."""
    merged = {}
    for source in rows:
        key = tuple(str(source.get(k) or '') for k in ('date', 'accountId', 'account', 'scope', 'campaignId', 'group'))
        if key not in merged:
            merged[key] = {**source, 'spend': 0.0, 'adOrders': 0.0, 'adSales': 0.0}
        for field in ('spend', 'adOrders', 'adSales'):
            merged[key][field] += source[field]
    return [{**merged[key], **{field: round(merged[key][field], 2) for field in ('spend', 'adOrders', 'adSales')}}
            for key in sorted(merged)]
