"""SB financial-owner comparisons preserve source identities, totals and scope."""
from collections import defaultdict
from copy import deepcopy
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.services import operator_cpo as service
from app.services.cpo_identity import AdIdentityResolver, CampaignOwnerRules, resolve_sb_accounting
from test_operator_report_access_v1 import app_as
from test_operator_exports_v1 import app_as as exports_as, DETAIL, _xlsx_xml


DAY = '2026-10-19'
SOURCE = {'group':'ZF1','productCode':'P100','parentAsin':'PARENT100','operatorName':'珍凤'}
TARGET = {'group':'ZF1','productCode':'P200','parentAsin':'PARENT200','operatorName':'珍凤'}
ROW = {'stat_date':DAY,'account_id':'a','account_name':'WHITIN','campaign_id':'c1',
       'campaign_name':'ZF1-P200 SB','child_asin':'CHILD100','parent_asin':'PARENT100',
       'ad_product':'Sponsored Brands','spend':50.0,'ad_orders':5.0,'ad_purchases':3.0,'ad_sales':100.0,'rows':1}


def resolver():
    return AdIdentityResolver({('WHITIN','CHILD100'):SOURCE,('WHITIN','CHILD200'):TARGET},[],[])


def test_name_owner_and_actual_owner_differ_without_mutating_actual_identity():
    actual = deepcopy(SOURCE)
    identities = resolver()
    rules = CampaignOwnerRules([],identities.candidates,{})
    assert resolve_sb_accounting(ROW,'WHITIN',actual,'child_exact',identities,rules,'name')[0] == TARGET
    assert resolve_sb_accounting(ROW,'WHITIN',actual,'child_exact',identities,rules,'asin')[0] == SOURCE
    assert actual == SOURCE


def test_missing_or_ambiguous_name_never_falls_back_to_actual_owner_in_name_mode():
    identities = resolver()
    rules = CampaignOwnerRules([],identities.candidates,{})
    for name in ('Unmapped SB', 'ZF1-P100-P200 SB', 'ZF1-P100 AJ1-P200 SB'):
        assert resolve_sb_accounting({**ROW,'campaign_name':name},'WHITIN',SOURCE,'child_exact',identities,rules,'name')[0] is None
    # An otherwise unique name in the wrong seller scope cannot claim the expense.
    assert resolve_sb_accounting(ROW,'OTHER',SOURCE,'child_exact',identities,rules,'name')[0] is None


def test_asin_mode_cannot_reintroduce_name_or_financial_override_when_actual_missing():
    identities = resolver()
    rules = CampaignOwnerRules([],identities.candidates,{})
    assert resolve_sb_accounting(ROW,'WHITIN',None,'unmapped',identities,rules,'asin')[0] is None
    identities.observe(ROW,'WHITIN',SOURCE)
    missing = {**ROW,'child_asin':'-1','parent_asin':'-1'}
    assert resolve_sb_accounting(missing,'WHITIN',None,'unmapped',identities,rules,'asin')[0] == SOURCE
    unknown = {**ROW,'child_asin':'CHILD999','parent_asin':'-1'}
    assert resolve_sb_accounting(unknown,'WHITIN',None,'unmapped',identities,rules,'asin')[0] is None
    assert resolve_sb_accounting(ROW,'WHITIN',None,'unmapped',identities,rules,'asin',blocked_source=True)[0] is None
    with patch.object(rules,'resolve',side_effect=AssertionError('ASIN must bypass financial overrides')):
        assert resolve_sb_accounting(ROW,'WHITIN',SOURCE,'child_exact',identities,rules,'asin')[0] == SOURCE


def test_name_mode_preserves_explicit_approved_rule_review_conditions():
    identities = resolver()
    approved = {'rule_id':1,'active':True,'account_name':'WHITIN','campaign_id':'c1',
                'ad_product':'Sponsored Brands','expected_campaign_name':ROW['campaign_name'],
                'allocation_mode':'campaign_owner','business_account':'WHITIN',
                'operator_group':'ZF1','product_code':'P200','parent_asin':'PARENT200',
                'allowed_source_products':['P100','P200'],'valid_from':DAY,'valid_to':None}
    rules = CampaignOwnerRules([approved],identities.candidates,{'PARENT200':TARGET})
    assert resolve_sb_accounting(ROW,'WHITIN',SOURCE,'child_exact',identities,rules,'name')[0] == TARGET
    target,method,matched = resolve_sb_accounting(ROW,'WHITIN',None,'unmapped',identities,rules,'name')
    assert target is None
    assert method == 'campaign_owner_rule_needs_review' and matched['rule_id'] == 1
    # The explicit ASIN comparison remains independent of that financial rule.
    assert resolve_sb_accounting(ROW,'WHITIN',SOURCE,'child_exact',identities,rules,'asin')[0] == SOURCE


def build(mode, sb_name=ROW['campaign_name'], actual=True, sb_spends=(50.0,)):
    ads = [{**ROW,'campaign_name':sb_name,'spend':spend,
            'child_asin':'CHILD100' if actual else '-1','parent_asin':'PARENT100' if actual else '-1'}
           for spend in sb_spends]
    ads.append({**ROW,'campaign_id':'sp','ad_product':'Sponsored Products','spend':20.0})
    business = [{'account_name':'WHITIN','account_id':'a','child_asin':child,
                 'parent_asin':meta['parentAsin'],'title':meta['productCode'],
                 'total_orders':10.0,'total_sales':100.0,'sessions':10.0,'rows':1}
                for child,meta in [('CHILD100',SOURCE),('CHILD200',TARGET)]]
    def query(sql):
        if 'core.report_advertised_product_daily r' in sql:
            return ads
        if 'core.report_purchased_product_daily r' in sql:
            return [{**r,'purchases':r['ad_purchases'],'sales':r['ad_sales']} for r in ads]
        if 'SELECT stat_date::text d' in sql:
            return [{'d':DAY}]
        if 'core.report_business_child_asin_daily' in sql and 'max(title)' in sql:
            return business
        if 'core.report_business_child_asin_daily' in sql:
            return [{**r,'stat_date':DAY} for r in business]
        return []
    with patch.object(service,'query_rows',side_effect=query), \
         patch.object(service,'_mapping',return_value={'PARENT100':SOURCE,'PARENT200':TARGET}), \
         patch.object(service,'_child_mapping',return_value={('WHITIN','CHILD100'):SOURCE,('WHITIN','CHILD200'):TARGET}), \
         patch.object(service,'_portfolio',return_value=defaultdict(set)), \
         patch.object(service,'_complete_days',return_value=[DAY]), \
         patch.object(service,'_source_days',return_value={'completeDays':1}), \
         patch.object(service,'_direct_prefix_scopes',return_value={}):
        return service._build_uncached(DAY,DAY,'fixture',mode)


def total(data):
    return sum(p['spend'] for p in data['products'])+data['unmappedAd']['spend']+data['fullFunnel']['unallocatedSpend']


def test_pipeline_only_sb_moves_and_denominators_and_source_asins_are_preserved():
    named, actual = build('name'), build('asin')
    n = {p['code']:p for p in named['products']}
    a = {p['code']:p for p in actual['products']}
    assert total(named) == total(actual) == 70
    assert n['P200']['spend'] == 50 and n['P100']['spend'] == 20
    assert a['P100']['spend'] == 70 and a['P200']['spend'] == 0
    assert n['P100']['totalOrders'] == a['P100']['totalOrders'] == 10
    assert n['P200']['totalOrders'] == a['P200']['totalOrders'] == 10
    assert 'CHILD100' not in n['P200']['childAsins']
    assert 'PARENT100' not in n['P200']['parentAsins']
    assert n['P200']['campaignCostAllocations'][0]['sourceProduct'] == 'P100'
    assert n['P200']['purchasedValidationOrders'] == 3
    assert not a['P100']['campaignCostReviews']


def test_unresolved_names_and_missing_asins_keep_expenses_in_company_pending_total():
    missing_name = build('name',sb_name='unknown')
    assert missing_name['unmappedAd']['spend'] == 50
    assert total(missing_name) == 70
    missing_asin = build('asin',actual=False)
    assert missing_asin['unmappedAd']['spend'] == 50
    assert total(missing_asin) == 70
    assert build('name',actual=False)['unmappedAd']['spend'] == 0


def test_multiple_cent_denomination_rows_conserve_amount_when_sb_owner_changes():
    named = build('name', sb_spends=(0.1, 0.2, 1.01))
    actual = build('asin', sb_spends=(0.1, 0.2, 1.01))
    assert round(total(named), 2) == round(total(actual), 2) == 21.31
    assert next(p for p in named['products'] if p['code'] == 'P200')['spend'] == 1.31


def test_mode_cache_keys_are_separate_but_source_revision_is_unchanged():
    calls = []
    def cached(start,end,revision,loader):
        calls.append(revision)
        return loader()
    with patch.object(service,'_data_revision',return_value='revision42'), \
         patch.object(service.build_cache,'get_or_set',side_effect=cached), \
         patch.object(service,'_build_uncached',return_value={}) as loader:
        service._build(DAY,DAY,'name')
        service._build(DAY,DAY,'asin')
        assert calls[0] != calls[1]
        assert loader.call_args_list[0].args == (DAY,DAY,'revision42','name')
        assert loader.call_args_list[1].args == (DAY,DAY,'revision42','asin')


def test_modes_validated_before_service_and_cross_group_permissions_still_apply():
    with patch('app.api.routes.cache.get_or_set',side_effect=lambda key,loader,ttl:loader()), \
         patch('app.api.routes.operator_cpo_summary',return_value={'operators':[],'sbAttributionMode':'asin'}) as summary:
        client = app_as('operator','ZF1')
        assert client.get('/api/operator-cpo?sb_attribution_mode=bad').status_code == 422
        summary.assert_not_called()
        response = client.get('/api/operator-cpo?sb_attribution_mode=asin')
        assert response.status_code == 200
        assert response.json()['sbAttributionMode'] == 'asin'
        summary.assert_called_once_with(None,'daily','asin')
        assert client.get('/api/operators/雪敏?sb_attribution_mode=asin').status_code == 403


def test_export_uses_selected_mode_and_labels_workbook():
    payload = {**DETAIL,'sbAttributionMode':'asin'}
    with patch('app.api.operator_exports.cached_detail',return_value=payload) as cached:
        response = exports_as('management').get('/api/operator-reports/operators/珍凤.xlsx?date='+DAY+'&sb_attribution_mode=asin')
        assert response.status_code == 200
        cached.assert_called_once_with('珍凤',DAY,'asin')
        assert 'sb-asin' in response.headers['content-disposition']
        assert 'SB费用归属：按推广ASIN'.encode() in _xlsx_xml(response.content)
