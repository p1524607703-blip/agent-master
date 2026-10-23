"""Group-known costs stay conserved without guessing a product or sharing a ledger."""
from copy import deepcopy
from unittest.mock import patch

from app.services import operator_cpo as service
from app.services.cpo_group_pending import pending_group_expense, merge_pending_expenses, pending_total
from app.services.operator_export_workbooks import detail_xlsx, summary_xlsx
from test_sb_attribution_modes import build, DAY, SOURCE, TARGET, ROW, resolver
from test_operator_report_access_v1 import app_as
from test_operator_exports_v1 import _xlsx_xml, app_as as exports_as


def pending_build():
    return build('name', sb_name='ZF1-P100 P200 collection')


def test_exact_group_requires_maintained_scope_no_source_conflict_and_no_rule_blocker():
    candidates=resolver().candidates
    named={**ROW,'campaign_name':'ZF1-P100 P200 collection'}
    item=pending_group_expense(named,'WHITIN',SOURCE,candidates)
    assert item['group']=='ZF1' and item['operatorName']=='珍凤'
    assert item['reason']=='MULTIPLE_NAMED_PRODUCTS'
    assert item['knownNameCandidates']==[{'group':'ZF1','productCode':'P100'},{'group':'ZF1','productCode':'P200'}]
    assert 'productCode' not in item and item['status']=='GROUP_KNOWN_PRODUCT_PENDING'
    for kwargs in ({'blocked':True},{'rule':{'rule_id':1}}):
        assert pending_group_expense(named,'WHITIN',SOURCE,candidates,**kwargs) is None
    for scope,source,name in [('OTHER',SOURCE,named['campaign_name']),
                             ('WHITIN',{**SOURCE,'group':'XM1'},named['campaign_name']),
                             ('WHITIN',SOURCE,'ZF1-P100 XM1-P200'),
                             ('WHITIN',SOURCE,'unscoped P100 P200'),
                             ('WHITIN',SOURCE,'XX1-P100 P200')]:
        assert pending_group_expense({**named,'campaign_name':name},scope,source,candidates) is None


def test_composite_name_can_confirm_only_group_and_rows_aggregate_once():
    item=pending_group_expense({**ROW,'campaign_name':'ZF1-COMPOSITE collection'},'WHITIN',SOURCE,resolver().candidates)
    assert item['reason']=='CONFIRMED_ALIAS_REQUIRED' and not item['knownNameCandidates']
    merged=merge_pending_expenses([{**item,'spend':0.1},{**item,'spend':0.2}])
    assert len(merged)==1 and merged[0]['spend']==0.3


def test_pipeline_group_bridge_conserves_money_without_mutating_products_or_asin_mode():
    data=pending_build()
    assert data['unmappedAd']['spend']==0
    assert pending_total(data)==50
    assert sum(p['spend'] for p in data['products'])==20
    assert sum(p['spend'] for p in data['products'])+pending_total(data)+data['unmappedAd']['spend']+data['fullFunnel']['unallocatedSpend']==70
    assert all(p['code'] in ('P100','P200') for p in data['products'])
    actual=build('asin', sb_name='ZF1-P100 P200 collection')
    assert not actual['groupPendingExpenses']
    assert sum(p['spend'] for p in actual['products'])==70
    assert not build('asin', sb_name='ZF1-P100 P200 collection', actual=False)['groupPendingExpenses']


def test_summary_detail_my_and_exports_include_pending_once_and_keep_cpo_unfinal():
    data=pending_build()
    with patch.object(service,'_build',return_value=data), \
         patch.object(service,'full_funnel_for_viewer',return_value={'rows':[]}):
        summary=service.operator_cpo_summary(DAY)
        detail=service.operator_cpo_detail('珍凤',DAY)
        mine=service.my_cpo_summary('ZF1',DAY)
    assert summary['companyTotalSpend']==70 and summary['operatorPendingSpend']==50
    row=next(row for row in summary['operators'] if row['name']=='珍凤')
    assert row['spend']==70 and row['pendingProductSpend']==50
    assert row['cpo'] is None and row['finalCpo'] is False
    assert detail['summary']['spend']==mine['detailSummary']['spend']==70
    assert detail['summary']['operatorPendingSpend']==mine['detailSummary']['operatorPendingSpend']==50
    assert detail['summary']['totalOrders']==20 and detail['summary']['cpo'] is None
    assert not detail['final_cpo'] and not summary['final_cpo'] and not mine['final_cpo']
    assert detail['groupPendingExpenses']==mine['groupPendingExpenses']==data['groupPendingExpenses']
    assert any('尚未确定承担款式' in reason for reason in detail['qualityReasons'])
    sheet=_xlsx_xml(detail_xlsx(detail))
    assert '组内待分摊费用（独立台账'.encode() in sheet
    assert 'ZF1-P100 P200 collection'.encode() in sheet
    # Comprehensive total includes the bridge while product costs remain 20.
    assert b'<c r="N5" s="2" t="n"><v>70.0</v>' in sheet
    assert b'<c r="E5" s="2" t="n"><v>50.0</v>' in sheet
    assert b'<c r="G10" s="3" t="n"><v>5.0</v>' in sheet
    assert b'<c r="F10" s="2" t="n"><v>50.0</v>' in sheet
    assert '其中组内待分摊'.encode() in _xlsx_xml(summary_xlsx(summary))


def test_own_detail_and_my_ledger_exclude_other_group_pending_amounts():
    data=pending_build()
    other={**data['groupPendingExpenses'][0],'group':'XM1','operatorName':'雪敏','spend':178.45}
    data['groupPendingExpenses'].append(other)
    with patch.object(service,'_build',return_value=data), \
         patch.object(service,'full_funnel_for_viewer',return_value={'rows':[]}):
        own=service.operator_cpo_detail('珍凤',DAY)
        mine=service.my_cpo_summary('ZF1',DAY)
    assert len(own['groupPendingExpenses'])==len(mine['groupPendingExpenses'])==1
    assert all(row['name']=='珍凤' for row in mine['operators'])
    assert own['summary']['operatorPendingSpend']==mine['detailSummary']['operatorPendingSpend']==50
    assert '178.45' not in str(own) and '178.45' not in str(mine)


def test_shared_summary_keeps_existing_totals_but_new_pending_detail_is_own_only():
    payload={'operators':[
        {'name':'珍凤','groups':['ZF1'],'spend':70,'pendingProductSpend':50},
        {'name':'雪敏','groups':['XM1'],'spend':602.3,'pendingProductSpend':178.45}],
        'operatorPendingSpend':228.45,'groupPendingExpenses':[{'PRIVATE_CAMPAIGN':'do-not-share'}]}
    with patch('app.api.routes.cache.get_or_set',return_value=deepcopy(payload)):
        response=app_as('operator','ZF1').get('/api/operator-cpo')
    assert response.status_code==200
    result=response.json()
    assert result['operators'][0]['pendingProductSpend']==50
    assert 'pendingProductSpend' not in result['operators'][1]
    assert 'groupPendingExpenses' not in result and 'operatorPendingSpend' not in result
    with patch('app.api.operator_exports.cached_summary',return_value=deepcopy(payload)):
        response=exports_as('operator','ZF1').get('/api/operator-reports/summary.xlsx?date='+DAY)
    assert response.status_code==200
    assert b'178.45' not in _xlsx_xml(response.content)
