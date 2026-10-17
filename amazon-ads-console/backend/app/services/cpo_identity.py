"""Evidence-scoped identity fallback; never allocates a multi-product campaign."""
from collections import defaultdict
import re


def token_match(text: str, token: str) -> bool:
    return bool(token and re.search(r'(?<![A-Z0-9\u4e00-\u9fff])'+re.escape(token)+r'(?![A-Z0-9\u4e00-\u9fff])', text or '', re.I))


class AdIdentityResolver:
    def __init__(self, child_mapping, business_products, ownership, registry=()):
        self.candidates = defaultdict(dict)
        self.confirmed_gender = {(r['operator_group'],r['product_code']) for r in ownership
            if r.get('confirmation_source') and r.get('gender_segment') and r.get('owner_resolution')=='parent_confirmation'}
        for (scope,_),meta in child_mapping.items():
            self.add(scope,meta)
        for p in business_products:
            for scope in p['businessAccounts']:
                self.add(scope,{'group':p['group'],'productCode':p['code'],'operatorName':p['operatorName'],
                    'parentAsin':next(iter(p['parentAsins'])) if len(p['parentAsins'])==1 else '',
                    'brand':p.get('brand',''),'mappingStatus':p.get('mappingStatus','confirmed')})
        self.source_aliases = defaultdict(set)
        for r in registry:
            self.source_aliases[(r['operator_group'],r.get('source_product_code') or r['canonical_product_code'])].add(r['canonical_product_code'])
        self.period = defaultdict(dict)
        self.daily = defaultdict(dict)

    def add(self,scope,meta):
        self.candidates[scope][(meta['group'],meta['productCode'])]=meta

    def observe(self,row,scope,meta):
        if not meta or not scope or scope.startswith('__'): return
        ident=(scope,meta['group'],meta['productCode'])
        key=(row['account_name'],row['campaign_id'])
        self.period[key][ident]=meta
        self.daily[(row['stat_date'],)+key][ident]=meta

    def resolve(self,row,scope):
        key=(row['account_name'],row['campaign_id'])
        period=self.period[key];daily=self.daily[(row['stat_date'],)+key]
        if len(period)==len(daily)==1 and set(period)==set(daily):
            ident=next(iter(period))
            if ident[0]==scope: return period[ident],'campaign_same_day_unique_advertised_identity'
        return self.resolve_name(row,scope)

    def resolve_name(self,row,scope):
        gm=re.search(r'(?<![A-Z0-9])([A-Z]{2}\d+)[-_]',row['campaign_name'] or '',re.I)
        group=gm.group(1).upper() if gm else None
        options={(g,c):m for (g,c),m in self.candidates[scope].items() if (not group or g==group) and token_match(row['campaign_name'],c)}
        methods={identity:'group_exact_unicode' if group else 'account_unique_exact_product' for identity in options}
        for (g,alias),canonical in self.source_aliases.items():
            if len(canonical)!=1 or (group and g!=group) or not token_match(row['campaign_name'],alias): continue
            code=next(iter(canonical));identity=(g,code)
            if identity in self.candidates[scope]:
                options[identity]=self.candidates[scope][identity]
                methods.setdefault(identity,'confirmed_source_product_alias')
        if group:
            for (g,c),m in self.candidates[scope].items():
                if g==group and c.endswith(('男','女')) and (g,c) in self.confirmed_gender and token_match(row['campaign_name'],c[:-1]):
                    options[(g,c)]=m;methods.setdefault((g,c),'confirmed_group_gender_alias')
        if len(options)==1:
            identity=next(iter(options));return options[identity],methods[identity]
        return None,'unresolved'


    def cost_review(self, row, scope, source_meta):
        """A name mismatch is a review signal, never permission to move costs."""
        if row['ad_product'] != 'Sponsored Brands' or not source_meta or abs(float(row.get('spend') or 0)) <= 0.005:
            return None
        target, _ = self.resolve_name(row, scope)
        if not target or (target['group'], target['productCode']) == (source_meta['group'], source_meta['productCode']):
            return None
        return {'date':row['stat_date'],'account':row['account_name'],'campaignId':row['campaign_id'],
                'campaignName':row['campaign_name'],'sourceGroup':source_meta['group'],
                'sourceProduct':source_meta['productCode'],'nameGroup':target['group'],
                'nameProduct':target['productCode'],'spend':round(float(row.get('spend') or 0),2)}


class CampaignOwnerRules:
    """Confirmed accounting overrides, separate from actual product identities."""

    def __init__(self, rules, scoped_candidates, parent_mapping):
        self.rules = defaultdict(list)
        self.scoped_candidates = scoped_candidates
        self.parent_mapping = parent_mapping
        for rule in rules:
            if rule.get('active'):
                self.rules[(rule['account_name'], rule['campaign_id'], rule['ad_product'])].append(rule)

    def resolve(self, row, scope, source_meta):
        day = str(row['stat_date'])
        rules = [r for r in self.rules[(row['account_name'], row['campaign_id'], row['ad_product'])]
                 if str(r['valid_from']) <= day and (not r.get('valid_to') or day <= str(r['valid_to']))]
        if not rules:
            return None, '', None
        # A matching but invalid rule must not silently fall back to source identity.
        rule = rules[0]
        if len(rules) != 1:
            return None, 'campaign_owner_rule_conflict', rule
        identity = (rule['operator_group'], rule['product_code'])
        target = self.parent_mapping.get(rule['parent_asin'])
        valid = (
            rule['allocation_mode'] == 'campaign_owner'
            and row['ad_product'] == 'Sponsored Brands'
            and row['campaign_name'] == rule['expected_campaign_name']
            and scope == rule['business_account']
            and source_meta is not None
            and source_meta['group'] == rule['operator_group']
            and source_meta['productCode'] in rule['allowed_source_products']
            and identity in self.scoped_candidates.get(scope, {})
            and target is not None
            and (target['group'], target['productCode']) == identity
        )
        if not valid:
            return None, 'campaign_owner_rule_needs_review', rule
        return dict(target), 'campaign_owner_confirmed', rule


class FullFunnelLedger:
    """A disclosure ledger; allocated amounts stay in product totals exactly once."""
    def __init__(self):self.rows={}

    def add(self,row,meta):
        owner=meta.get('operatorName') if meta else None
        code=meta.get('productCode') if meta else None
        key=(row['stat_date'],row['account_name'],row['campaign_id'],meta.get('group') if meta else None,code)
        if key not in self.rows:
            self.rows[key]={'date':row['stat_date'],'account':row['account_name'],'campaignId':row['campaign_id'],
                'campaignName':row['campaign_name'],'operatorName':owner,'group':meta.get('group') if meta else None,
                'productCode':code,'spend':0.0,'adOrders':0.0,'adSales':0.0,
                'status':'已归属，已计入产品总费用' if meta else '混合活动待分摊'}
        target=self.rows[key]
        for k,col in [('spend','spend'),('adOrders','ad_orders'),('adSales','ad_sales')]:target[k]+=float(row.get(col) or 0)

    def result(self,owner=None):
        rows=[dict(r) for r in self.rows.values() if (owner is None or r['operatorName']==owner)
            and (abs(r['spend'])>0.000001 or r['adOrders']!=0 or abs(r['adSales'])>0.000001)]
        for r in rows:
            for f in ('spend','adOrders','adSales'):r[f]=round(r[f],2)
        rows.sort(key=lambda r:(r['date'],r['operatorName'] or '',r['campaignId'],r['productCode'] or ''))
        allocated=sum(r['spend'] for r in rows if r['operatorName'])
        pending=sum(r['spend'] for r in rows if not r['operatorName'])
        return {'label':'全流域广告活动','rows':rows,'spend':round(allocated+pending,2),
            'allocatedSpend':round(allocated,2),'unallocatedSpend':round(pending,2),
            'note':'拆分列示；已归属费用已包含在对应产品总费用中，待分摊费用单独保留。'}
