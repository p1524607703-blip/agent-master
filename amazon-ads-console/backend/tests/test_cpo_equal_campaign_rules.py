"""Approved financial splits conserve campaign metrics without changing identity."""
from copy import deepcopy
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.services import operator_cpo as service
from app.services.cpo_identity import CampaignOwnerRules, expand_equal_campaign_rows
from app.services.operator_export_workbooks import detail_xlsx, summary_xlsx
from test_sb_attribution_modes import build, resolver, SOURCE, TARGET, ROW, DAY
from test_operator_exports_v1 import _xlsx_xml


NAME = 'ZF1-P100 P200 collection'


def approved():
    return {'rule_id':17,'active':True,'account_name':'WHITIN','campaign_id':'c1',
            'ad_product':'Sponsored Brands','expected_campaign_name':NAME,
            'allocation_mode':'multi_owner_equal','business_account':'WHITIN',
            'operator_group':'ZF1','product_code':'P100','parent_asin':'PARENT100',
            'allowed_source_products':['P100','P200'],'valid_from':DAY,'valid_to':None,
            'rule_config':{'expected_account_id':'a','targets':[
                {'operator_group':'ZF1','product_code':'P200','parent_asin':'PARENT200','weight':1},
                {'operator_group':'ZF1','product_code':'P100','parent_asin':'PARENT100','weight':1}]}}


def rules_for(rule=None, extra=None):
    parent={'PARENT100':{**SOURCE,'brand':'WHITIN'},'PARENT200':{**TARGET,'brand':'WHITIN'}}
    candidates=deepcopy(resolver().candidates)
    if extra:
        parent['PARENT300']={**extra,'brand':'WHITIN'}
        candidates['WHITIN'][('ZF1','P300')]=extra
    return CampaignOwnerRules([rule or approved()],candidates,parent)


def contexts(rows, source=SOURCE):
    return {id(row):{'scope':'WHITIN','source_meta':source,'source_method':'child_exact','blocked':False} for row in rows}


def prepare(rows, rule=None, mode='name', supplied_contexts=None):
    return expand_equal_campaign_rows(rows,supplied_contexts or contexts(rows),rules_for(rule),mode,
                                      {'spend':2,'ad_orders':2,'ad_purchases':2,'ad_sales':2})


def pipeline(mode='name', rule=None, spends=(50.01,)):
    real=CampaignOwnerRules
    supplied=approved() if rule is None else rule
    with patch.object(service,'CampaignOwnerRules',side_effect=lambda _,candidates,parents: real([supplied],candidates,{key:{**value,'brand':'WHITIN'} for key,value in parents.items()})):
        return build(mode,sb_name=NAME,sb_spends=spends)


def test_campaign_is_aggregated_before_cent_allocation_and_input_order_is_irrelevant():
    rows=[{**ROW,'campaign_name':NAME,'spend':'.01'}, {**ROW,'campaign_name':NAME,'spend':'.01','child_asin':'CHILD200'}]
    original=deepcopy(rows)
    expanded,ctx=prepare(rows)
    assert [row['spend'] for row in expanded]==['0.01','0.01']
    assert [ctx[id(row)]['financial_meta']['productCode'] for row in expanded]==['P100','P200']
    assert all(ctx[id(row)]['original_totals']['spend']=='0.02' for row in expanded)
    reverse,reverse_ctx=prepare(list(reversed(rows)))
    assert [(reverse_ctx[id(row)]['financial_meta']['productCode'],row['spend']) for row in reverse]==[('P100','0.01'),('P200','0.01')]
    assert sum(row['_audit_rows'] for row in expanded)==2
    assert rows==original


def test_three_way_visible_units_sales_and_signed_corrections_all_conserve():
    third={'group':'ZF1','productCode':'P300','parentAsin':'PARENT300','operatorName':'珍凤'}
    rule=approved()
    rule['rule_config']['targets'].append({'operator_group':'ZF1','product_code':'P300','parent_asin':'PARENT300','weight':1})
    rows=[{**ROW,'campaign_name':NAME,'spend':'-0.05','ad_orders':'5','ad_purchases':'1','ad_sales':'10.01'}]
    expanded,ctx=expand_equal_campaign_rows(rows,contexts(rows),rules_for(rule,third),'name',
                                           {'spend':2,'ad_orders':2,'ad_purchases':2,'ad_sales':2})
    assert [row['spend'] for row in expanded]==['-0.02','-0.02','-0.01']
    assert [row['ad_orders'] for row in expanded]==['1.67','1.67','1.66']
    for metric in ('spend','ad_orders','ad_purchases','ad_sales'):
        assert sum(Decimal(row[metric]) for row in expanded)==Decimal(rows[0][metric])
    assert all(ctx[id(row)]['allocation_weight']=={'numerator':1,'denominator':3} for row in expanded)


@pytest.mark.parametrize('change',[
    lambda rule:rule.update(expected_campaign_name='renamed'),
    lambda rule:rule.update(business_account='OTHER'),
    lambda rule:rule.update(allowed_source_products=['P999']),
    lambda rule:rule['rule_config'].update(expected_account_id='other'),
    lambda rule:rule['rule_config']['targets'][0].update(operator_group='XM1'),
    lambda rule:rule['rule_config']['targets'][0].update(parent_asin='PARENT999'),
    lambda rule:rule['rule_config']['targets'][0].update(weight=2),
    lambda rule:rule['rule_config']['targets'].append(deepcopy(rule['rule_config']['targets'][0])),
    lambda rule:rule['rule_config'].update(targets=[]),
])
def test_invalid_rule_never_allocates_a_valid_subset_or_falls_back_to_name(change):
    rule=approved();change(rule)
    rows=[{**ROW,'campaign_name':NAME}]
    expanded,ctx=prepare(rows,rule)
    assert expanded==rows and not ctx[id(rows[0])].get('financial_meta')
    owner,method,matched=rules_for(rule).resolve(rows[0],'WHITIN',SOURCE)
    assert owner is None and method=='campaign_owner_rule_needs_review' and matched['rule_id']==17


def test_new_or_blocked_source_invalidates_whole_campaign_and_dates_do_not_cross_mix():
    rows=[{**ROW,'campaign_name':NAME,'spend':'1.01'}, {**ROW,'campaign_name':NAME,'spend':'0.01','child_asin':'NEW'}]
    context=contexts(rows)
    context[id(rows[1])]['source_meta']={**SOURCE,'productCode':'P999'}
    expanded,ctx=prepare(rows,supplied_contexts=context)
    assert expanded==rows and all(not ctx[id(row)].get('financial_meta') for row in rows)
    context=contexts(rows);context[id(rows[1])]['blocked']=True
    expanded,ctx=prepare(rows,supplied_contexts=context)
    assert expanded==rows and all(not ctx[id(row)].get('financial_meta') for row in rows)
    rows=[{**ROW,'campaign_name':NAME,'spend':'0.01'}, {**ROW,'campaign_name':NAME,'spend':'0.01','stat_date':'2026-10-20'}]
    expanded,ctx=prepare(rows)
    assert len(expanded)==4
    assert [(row['stat_date'],row['spend']) for row in expanded]==[(DAY,'0.01'),(DAY,'0.00'),('2026-10-20','0.01'),('2026-10-20','0.00')]


def test_same_group_and_product_in_another_brand_cannot_authorize_target_parent():
    rows=[{**ROW,'campaign_name':NAME}]
    rules=rules_for()
    # Merely having the same group/code in the seller scope does not establish
    # that an independently referenced parent belongs to that seller.
    rules.parent_mapping['PARENT200']={**TARGET,'brand':'OTHER'}
    expanded,ctx=expand_equal_campaign_rows(rows,contexts(rows),rules,'name',{'spend':2})
    assert expanded==rows and not ctx[id(rows[0])].get('financial_meta')


def test_inactive_outside_validity_conflicting_rules_and_asin_mode_cannot_apply():
    rows=[{**ROW,'campaign_name':NAME}]
    for mutation in ({'active':False},{'valid_from':'2026-10-20'},{'valid_to':'2026-10-18'}):
        rule=approved();rule.update(mutation)
        expanded,ctx=prepare(rows,rule)
        assert expanded==rows and not ctx[id(rows[0])].get('financial_meta')
    rules=rules_for()
    rules.rules[('WHITIN','c1','Sponsored Brands')].append({**approved(),'rule_id':18})
    expanded,ctx=expand_equal_campaign_rows(rows,contexts(rows),rules,'name',{'spend':2})
    assert expanded==rows and not ctx[id(rows[0])].get('financial_meta')
    with patch.object(rules,'matching',side_effect=AssertionError('ASIN mode must never inspect financial rules')):
        expanded,ctx=expand_equal_campaign_rows(rows,contexts(rows),rules,'asin',{'spend':2})
        assert expanded==rows


def test_pipeline_preserves_denominators_and_ownership_but_clears_resolved_pending():
    data=pipeline()
    products={row['code']:row for row in data['products']}
    assert data['unmappedAd']['spend']==0 and not data['groupPendingExpenses']
    assert products['P100']['spend']==45.01 and products['P200']['spend']==25
    assert sum(Decimal(str(row['spend'])) for row in data['products'])==Decimal('70.01')
    assert products['P100']['totalOrders']==products['P200']['totalOrders']==10
    assert products['P200']['childAsins']==['CHILD200']
    assert products['P200']['parentAsins']==['PARENT200']
    note=products['P200']['campaignCostAllocations'][0]
    assert note['method']=='campaign_multi_owner_equal_confirmed' and note['ruleId']==17
    assert note['weight']=={'numerator':1,'denominator':2}
    assert note['originalCampaignTotals']['spend']=='50.01'
    assert products['P100']['purchasedValidationOrders']==4.5
    assert products['P200']['purchasedValidationOrders']==1.5
    assert pipeline('asin')==build('asin',sb_name=NAME,sb_spends=(50.01,))


def test_summary_own_detail_and_xlsx_take_same_split_result_and_totals():
    data=pipeline()
    with patch.object(service,'_build',return_value=data),patch.object(service,'full_funnel_for_viewer',return_value={'rows':[]}):
        summary=service.operator_cpo_summary(DAY)
        detail=service.operator_cpo_detail('珍凤',DAY)
        mine=service.my_cpo_summary('ZF1',DAY)
    assert summary['companyTotalSpend']==detail['summary']['spend']==mine['detailSummary']['spend']==70.01
    assert summary['operatorPendingSpend']==detail['summary']['operatorPendingSpend']==0
    assert not detail['groupPendingExpenses'] and not mine['groupPendingExpenses']
    for payload in (detail_xlsx(detail),summary_xlsx(summary)):
        sheet=_xlsx_xml(payload)
        assert b'70.01' in sheet
    assert b'45.01' in _xlsx_xml(detail_xlsx(detail))
    assert b'<v>25.0</v>' in _xlsx_xml(detail_xlsx(detail))
