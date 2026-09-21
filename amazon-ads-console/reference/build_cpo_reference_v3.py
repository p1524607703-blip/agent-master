from pathlib import Path
import csv,collections,json,re,sys
from decimal import Decimal, ROUND_HALF_UP
sys.path.insert(0,str(Path(__file__).parent))
import build_cpo_reference_v2 as b

ROOT=Path('/Users/panjinlong/Documents/agent-master/amazon-ads-console')
OUT=ROOT/'reference/output_v3'
TYPES=b.TYPES
D=b.D
q2=b.q2

# Exact OU identity-to-business-parent mappings supported by business title/manual history.
# S71 keeps the SKU-table original code; operator separates male/female identities.
OU_PRODUCTS={
 ('XM1','Y10'):'B0FX2TG8CW',('XM2','S71'):'B0DK7YD2KT',('XM2','KD7'):'B0CFF747QG',('XM2','S600'):'B0H41HL3M6',
 ('XM1','Y180'):'B0FX2Q73Q6',('XM2','Y90B'):'B0GKCKCSMJ',('XM2','Y71B'):'B0H1M9KJLC',('XM2','S7K1'):'B0DCMSZ2YJ',
 ('XM1','KD5'):'B0CL6ZRY16',('XM1','S71'):'B0DGCM33J2',('XM1','S73'):'B0D2NDY5DD',('XM2','S75'):'B0DCV7KQJM',
 ('XM2','W8K4'):'B0CPPS6RJ2',('XM1','J100'):'B0H14MSYXF',('DD1','J101'):'B0H14S4VPX',('DD1','J102'):'B0H14KPJDF',
}
# Same operator|product already exists in WHITIN business; OU rows add business metrics only.
OU_BUSINESS_SUPPLEMENT={('XM1','Y70'):'B0DM5SPQPR',('XM1','YG10'):'B0DRX21M4T'}
AMS_0825=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/美国AMS/AMS 推广的商品 每日CPO单双计算.csv')

BLOCK_PRODUCT={
 ('2026-08-26','ZJ1','W75V2'):'BLOCKED_CAMPAIGN_RULE_CONFIRMATION',
 ('2026-08-26','ZJ1','Z32'):'BLOCKED_CAMPAIGN_RULE_CONFIRMATION',
 ('2026-08-25','XM2','KD7'):'BLOCKED_SPECIAL_CAMPAIGN',
 ('2026-08-25','XM2','S71'):'BLOCKED_SPECIAL_CAMPAIGN',
 ('2026-08-25','XM2','S75'):'BLOCKED_SPECIAL_CAMPAIGN',
}

def new_bucket(): return b.new_bucket()

def add(A,account,op,product,source,typ,cost,units,sales,method,cid,name):
    b.add_alloc(A,account,op,product,source,typ,cost,units,sales,method,cid,name)

def ou_owner(name):
    direct=[
      ('DD1-J101','DD1','J101'),('DD1-J102','DD1','J102'),
      ('XM1-J100','XM1','J100'),('XM1-KD5','XM1','KD5'),('XM1-S71','XM1','S71'),('XM1-S73','XM1','S73'),('XM1-Y10','XM1','Y10'),('XM1-Y180','XM1','Y180'),
      ('XM2-KD7','XM2','KD7'),('XM2-S600','XM2','S600'),('XM2-S71','XM2','S71'),('XM2-S75','XM2','S75'),('XM2-S7K1','XM2','S7K1'),('XM2-W8K4','XM2','W8K4'),('XM2-Y71B','XM2','Y71B'),('XM2-Y90B','XM2','Y90B')]
    for pre,g,p in direct:
        if name.startswith(pre):return g,p,'campaign_code'
    if name.startswith('XM1-S713'):return 'XM1','S71','historical_campaign_code'
    if name.startswith('XM2-S713'):return 'XM2','S71','historical_campaign_code'
    return None

OU_BLOCK={'132763011090925':'XM2-KD系列-自动捡漏','112593123026332':'XM2-S7系列-手动捡漏-动态'}

def alloc_oudesi(A,audit):
    src=[Decimal(0),Decimal(0),Decimal(0)];blocked=[Decimal(0),Decimal(0),Decimal(0)];unknown=[Decimal(0),Decimal(0),Decimal(0)]
    with b.OU_ADS.open(encoding='utf-8-sig',errors='replace',newline='') as f:
      for r in csv.DictReader(f):
        cid=b.clean_id(r['广告活动编号']);name=r['广告活动名称'];cost=D(r['总成本']);units=D(r['已售商品数量']);sales=D(r['销售额'])
        src[0]+=cost;src[1]+=units;src[2]+=sales
        if cid in OU_BLOCK:
          blocked[0]+=cost;blocked[1]+=units;blocked[2]+=sales;continue
        own=ou_owner(name)
        if own:
          g,p,m=own;add(A,'欧德思',g,p,'欧德思',b.ad_type('',name),cost,units,sales,m,cid,name)
        else:
          unknown[0]+=cost;unknown[1]+=units;unknown[2]+=sales
          if cost or units:audit.append({'范围':'欧德思','运营':'','产品代号':'','问题':f'未识别 Campaign {cid} {name}','金额':str(q2(cost)),'广告单':str(units),'状态':'BLOCKED_UNALLOCATED_AD'})
    audit.append({'范围':'欧德思','运营':'XM2','产品代号':'KD7/S71/S75','问题':'两条未确认特殊 Campaign：XM2-KD系列、XM2-S7系列','金额':str(q2(blocked[0])),'广告单':str(blocked[1]),'状态':'BLOCKED_SPECIAL_CAMPAIGN'})
    return src,blocked,unknown

def ams_owner(name,parent):
    rules=[
      ('DD1-W8K7','川鹏','DD1','W8K7'),('XM1-S71W','川鹏','XM1','S71W'),('XM1-V202','川鹏','XM1','V202'),('XM1-YG02','川鹏','XM1','YG02'),
      ('XM1-Y10','欧德思','XM1','Y10'),('XM2-KD7','欧德思','XM2','KD7'),('XM2-S71','欧德思','XM2','S71'),
      ('YS1-Z10','川鹏','YS1','Z10'),('YT1-W702','川鹏','YT1','W702'),('YT1-WK101','川鹏','YT1','WK101'),('YT1-WK103','川鹏','YT1','WK103'),
      ('ZJ1-DU08','川鹏','ZJ1','DU08'),('ZJ1-W30','川鹏','ZJ1','W30'),('ZJ1-W51女','川鹏','ZJ1','W51女'),('ZJ1-W51男','川鹏','ZJ1','W51男'),('ZJ1-W63','川鹏','ZJ1','W63'),
      ('ZJ1-W75V2','川鹏','ZJ1','W75V2'),('ZJ1-W81 ','川鹏','ZJ1','W81'),('ZJ1-W823男','川鹏','ZJ1','W823男'),('ZJ1-W85','川鹏','ZJ1','W85'),('ZJ1-W8K2-','川鹏','ZJ1','W8K2-'),('ZJ1-WK102','川鹏','ZJ1','WK102')]
    for pre,a,g,p in rules:
      if name.startswith(pre):return a,g,p,'campaign_code'
    if name.startswith('XM2-KD75') and parent=='B0CFF747QG':return '欧德思','XM2','KD7','advertised_product_fallback'
    return None

def alloc_ams(A,audit):
    # Daily CPO must align ad date with the business-report date.
    # 8/26 AMS -> only WHITIN/川鹏 products; 8/25 AMS -> only 欧德思 products.
    runs=[('2026-08-26',b.AMS_0826,'川鹏'),('2026-08-25',AMS_0825,'欧德思')]
    summary=[]
    for day,path,target_account in runs:
      rows=list(csv.DictReader(path.open(encoding='utf-8-sig',errors='replace',newline='')))
      raw=[sum((D(r['总成本']) for r in rows),Decimal(0)),sum((D(r['已售商品数量']) for r in rows),Decimal(0)),sum((D(r['销售额']) for r in rows),Decimal(0))]
      groups=collections.defaultdict(list)
      for r in rows:groups[(b.clean_id(r['广告活动编号']),r['广告活动名称'])].append(r)
      selected=[Decimal(0),Decimal(0),Decimal(0)];blocked_rule=[Decimal(0),Decimal(0),Decimal(0)];missing=[Decimal(0),Decimal(0),Decimal(0)];date_mismatch=[Decimal(0),Decimal(0),Decimal(0)]
      for (cid,name),rs in groups.items():
        cost=sum((D(r['总成本']) for r in rs),Decimal(0));units=sum((D(r['已售商品数量']) for r in rs),Decimal(0));sales=sum((D(r['销售额']) for r in rs),Decimal(0));typ=b.ad_type('Sponsored Brands',name)
        parent=next(((r.get('推广的商品父级编号') or '').strip() for r in rs if (r.get('推广的商品父级编号') or '').strip()),'')
        own=ams_owner(name,parent)
        # V3.5 unresolved W75V2/Z32 belongs to WHITIN 8/26.
        if cid=='73789533007579':
          if target_account=='川鹏':
            blocked_rule[0]+=cost;blocked_rule[1]+=units;blocked_rule[2]+=sales
            audit.append({'范围':'川鹏+AMS','运营':'ZJ1','产品代号':'W75V2/Z32','问题':'V3.5要求人工确认 73789533007579：campaign_code→W75V2 或 mixed_split→W75V2+Z32','金额':str(q2(cost)),'广告单':str(units),'状态':'BLOCKED_CAMPAIGN_RULE_CONFIRMATION'})
          else:
            date_mismatch[0]+=cost;date_mismatch[1]+=units;date_mismatch[2]+=sales
          continue
        # Known WHITIN-only special campaigns are ignored on 8/25 and processed on 8/26.
        if cid in {'479537915429061','1775045260101','79897800480005'}:
          if target_account!='川鹏':
            date_mismatch[0]+=cost;date_mismatch[1]+=units;date_mismatch[2]+=sales;continue
          selected[0]+=cost;selected[1]+=units;selected[2]+=sales
          if cid=='479537915429061':
            for p in ['W85','W81','W63','W51男']:add(A,'川鹏','ZJ1',p,'AMS',typ,cost/4,units/4,sales/4,'fixed_equal_split',cid,name)
          elif cid=='1775045260101':
            for p in ['W30','W20','W63','W81']:add(A,'川鹏','ZJ1',p,'AMS',typ,cost/4,units/4,sales/4,'mixed_split_equal_fallback',cid,name)
          else:
            add(A,'川鹏','ZJ1','W51女','AMS',typ,cost,units,sales,'campaign_code_special',cid,name)
          continue
        if own:
          a,g,p,m=own
          if a!=target_account:
            date_mismatch[0]+=cost;date_mismatch[1]+=units;date_mismatch[2]+=sales;continue
          selected[0]+=cost;selected[1]+=units;selected[2]+=sales
          add(A,a,g,p,'AMS',typ,cost,units,sales,m,cid,name)
        else:
          # No business report exists for these owners in the current reference set.
          missing[0]+=cost;missing[1]+=units;missing[2]+=sales
          if cost or units:
            audit.append({'范围':f'AMS {day}','运营':(re.match(r'^([A-Z]{2}\d+)',name).group(1) if re.match(r'^([A-Z]{2}\d+)',name) else ''),'产品代号':'','问题':'Campaign无法回卷到本轮有业务报告的运营产品：'+name,'金额':str(q2(cost)),'广告单':str(units),'状态':'BLOCKED_BUSINESS_REPORT_MISSING'})
      summary.append({'date':day,'target':target_account,'raw':raw,'selected':selected,'blocked_rule':blocked_rule,'missing':missing,'date_mismatch':date_mismatch})
    return summary

def biz_record(r):
    return {'orders':D(r.get('已订购商品数量')),'sessions':D(r.get('会话数 - 总计')),'sales':D(r.get('已订购商品销售额'))}

def merge_bucket(dst,src):
    for t in TYPES:dst['spend'][t]+=src['spend'][t];dst['units'][t]+=src['units'][t]
    dst['ad_sales']+=src['ad_sales'];dst['ad_accounts']|=src['ad_accounts'];dst['methods']|=src['methods'];dst['campaigns']|=src['campaigns']

def fmt_units(x):
    s=format(x.quantize(Decimal('0.0001')), 'f')
    return s.rstrip('0').rstrip('.') if '.' in s else s
def pct2(x):return f"{q2(x)}%"

def main():
    wh_map,wh_biz,_=b.build_whitin_map();ou_biz=b.biz_load(b.OU_BIZ)
    audit=[];A=collections.defaultdict(new_bucket)
    whsrc=b.alloc_whitin(A,wh_map,audit)
    ousrc=alloc_oudesi(A,audit)
    amssrc=alloc_ams(A,audit)

    # Daily record grain = date + operator|product. Identity itself remains operator|product.
    BM=collections.defaultdict(lambda:{'orders':Decimal(0),'sessions':Decimal(0),'sales':Decimal(0),'parents':set(),'business_accounts':set(),'map_sources':set()})
    for (g,p),meta in wh_map.items():
      key=('2026-08-26',g,p);z=BM[key];br=biz_record(wh_biz[meta['parent']])
      for f in ['orders','sessions','sales']:z[f]+=br[f]
      z['parents'].add(meta['parent']);z['business_accounts'].add('川鹏');z['map_sources'].add(meta['source'])
    for (g,p),parent in OU_PRODUCTS.items():
      key=('2026-08-25',g,p);z=BM[key];br=biz_record(ou_biz[parent])
      for f in ['orders','sessions','sales']:z[f]+=br[f]
      z['parents'].add(parent);z['business_accounts'].add('欧德思');z['map_sources'].add('oudesi_business_exact_or_historical_confirmed')
    for (g,p),parent in OU_BUSINESS_SUPPLEMENT.items():
      key=('2026-08-25',g,p);z=BM[key];br=biz_record(ou_biz[parent])
      for f in ['orders','sessions','sales']:z[f]+=br[f]
      z['parents'].add(parent);z['business_accounts'].add('欧德思');z['map_sources'].add('business_title_plus_known_global_parent')

    audit.append({'范围':'欧德思','运营':'LB1/ZF1','产品代号':'Y15','问题':'同一业务父ASIN标题可对应两套独立运营SKU，缺子ASIN业务报告，无法锁定 operator_product_key','金额':'','广告单':'','状态':'BLOCKED_OPERATOR_PRODUCT_IDENTITY'})

    # Ad target-account determines matching daily business date in this reference run.
    MA=collections.defaultdict(new_bucket)
    account_date={'川鹏':'2026-08-26','欧德思':'2026-08-25'}
    for (acc,g,p),src in A.items():
      if acc not in account_date:continue
      merge_bucket(MA[(account_date[acc],g,p)],src)

    internal=[]
    for key in sorted(BM):
      day,g,p=key;bm=BM[key];ad=MA[key];sp=sum(ad['spend'].values(),Decimal(0));u=sum(ad['units'].values(),Decimal(0));orders=bm['orders'];est_nat=orders-u
      statuses=[]
      if key in BLOCK_PRODUCT:statuses.append(BLOCK_PRODUCT[key])
      if u>orders:statuses.append('BLOCKED_AD_ORDERS_GT_TOTAL')
      if orders==0 and sp>0:statuses.append('BLOCKED_ZERO_BUSINESS_ORDERS_WITH_AD_SPEND')
      status='|'.join(dict.fromkeys(statuses)) if statuses else ('READY_ZERO_ORDERS' if orders==0 else 'READY')
      row={'运营':g,'产品代号':p,'日期':day,'业务账户':'+'.join(sorted(bm['business_accounts'])),'广告账户':'+'.join(sorted(ad['ad_accounts'])),'父ASIN':'|'.join(sorted(bm['parents']))}
      for t in TYPES:row[t+'费用']=str(q2(ad['spend'][t]));row[t+'广告单']=fmt_units(ad['units'][t]);row[t+'单均费用']=str(q2(ad['spend'][t]/ad['units'][t])) if ad['units'][t] else '0.00'
      row.update({'总费用':str(q2(sp)),'总广告单':fmt_units(u),'全部订单':fmt_units(orders),'估算自然单_审计':fmt_units(est_nat),'综合CPO':str(q2(sp/orders)) if orders else '0.00','广告归因销售额':str(q2(ad['ad_sales'])),'业务销售额':str(q2(bm['sales'])),'ROAS':str(q2(ad['ad_sales']/sp)) if sp else '','TACOS_pct':str(q2(sp/bm['sales']*100)) if bm['sales'] else '','Sessions':fmt_units(bm['sessions']),'CVR_pct':str(q2(orders/bm['sessions']*100)) if bm['sessions'] else '0.00','状态':status,'广告归属方法':'|'.join(sorted(ad['methods'])),'业务映射来源':'|'.join(sorted(bm['map_sources']))})
      internal.append(row)
      if 'BLOCKED_AD_ORDERS_GT_TOTAL' in status:audit.append({'范围':row['业务账户'],'运营':g,'产品代号':p,'问题':f"{day} 广告单 {row['总广告单']} > 全部订单 {row['全部订单']}，阻断正式发布",'金额':row['总费用'],'广告单':row['总广告单'],'状态':'BLOCKED_AD_ORDERS_GT_TOTAL'})
      if status=='READY_ZERO_ORDERS':audit.append({'范围':row['业务账户'],'运营':g,'产品代号':p,'问题':f'{day} 业务订单为0，按V3.5整体平均费用填0.00','金额':row['总费用'],'广告单':row['总广告单'],'状态':'WARNING_ZERO_BUSINESS_ORDERS'})

    OUT.mkdir(parents=True,exist_ok=True)
    # internal audit master
    with (OUT/'CPO_内部审计主表.csv').open('w',encoding='utf-8-sig',newline='') as f:
      w=csv.DictWriter(f,fieldnames=list(internal[0].keys()));w.writeheader();w.writerows(internal)
    with (OUT/'CPO_异常与阻断项.csv').open('w',encoding='utf-8-sig',newline='') as f:
      fields=['范围','运营','产品代号','问题','金额','广告单','状态'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(audit)

    # Strict V3.5 28-field files, one file per operator; blocked rows withheld.
    h1=['产品代号','','广告费用','','','','','','广告单量','','','','','','平均费用/单','','','','','','CPO单双费用','','','自然单','','产品链接','','已购买']
    h2=['','日期','手动','自动','头条','视频','展示','流媒体','手动','自动','头条','视频','展示','流媒体','手动','自动','头条','视频','展示','流媒体','总费用','总广告单','全部订单','','平均费用','流量','转化率','']
    pubdir=OUT/'标准28字段';pubdir.mkdir(exist_ok=True)
    counts={}
    byop=collections.defaultdict(list)
    for r in internal:byop[r['运营']].append(r)
    for op,rr in sorted(byop.items()):
      publish=[r for r in rr if not r['状态'].startswith('BLOCKED')]
      counts[op]={'all':len(rr),'published':len(publish),'blocked':len(rr)-len(publish)}
      with (pubdir/f'{op}_CPO_V3.5_标准28字段.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(h1);w.writerow(h2)
        for r in publish:
          vals=[r['产品代号'],r['日期']]
          vals += [r[t+'费用'] for t in TYPES]
          vals += [r[t+'广告单'] for t in TYPES]
          vals += [r[t+'单均费用'] for t in TYPES]
          vals += [r['总费用'],r['总广告单'],r['全部订单'],'',r['综合CPO'],r['Sessions'],pct2(D(r['CVR_pct'])),'']
          assert len(vals)==28
          w.writerow(vals)

    # Conservation summary.
    internal_sp=sum((D(r['总费用']) for r in internal),Decimal(0));internal_u=sum((D(r['总广告单']) for r in internal),Decimal(0))
    allocated_exact_sp=sum((sum(x['spend'].values(),Decimal(0)) for x in A.values()),Decimal(0));allocated_exact_u=sum((sum(x['units'].values(),Decimal(0)) for x in A.values()),Decimal(0))
    merged_exact_sp=sum((sum(x['spend'].values(),Decimal(0)) for x in MA.values()),Decimal(0));merged_exact_u=sum((sum(x['units'].values(),Decimal(0)) for x in MA.values()),Decimal(0))
    ams_json=[]
    for x in amssrc:
      ams_json.append({'date':x['date'],'target':x['target'],'raw_spend':str(q2(x['raw'][0])),'raw_units':str(x['raw'][1]),'selected_spend':str(q2(x['selected'][0])),'selected_units':str(x['selected'][1]),'blocked_rule_spend':str(q2(x['blocked_rule'][0])),'blocked_rule_units':str(x['blocked_rule'][1]),'missing_business_spend':str(q2(x['missing'][0])),'missing_business_units':str(x['missing'][1]),'date_mismatch_spend':str(q2(x['date_mismatch'][0])),'date_mismatch_units':str(x['date_mismatch'][1])})
    summary={'records':len(internal),'unique_operator_products':len(set((r['运营'],r['产品代号']) for r in internal)),'operators':counts,
             'whitin_main_raw_spend':str(q2(whsrc[0])),'whitin_main_raw_units':str(whsrc[1]),'oudesi_main_raw_spend':str(q2(ousrc[0][0])),'oudesi_raw_units':str(ousrc[0][1]),'oudesi_blocked_special_spend':str(q2(ousrc[1][0])),'oudesi_blocked_special_units':str(ousrc[1][1]),'oudesi_unknown_spend':str(q2(ousrc[2][0])),
             'ams_by_date':ams_json,'allocated_exact_spend':str(allocated_exact_sp),'allocated_exact_units':str(allocated_exact_u),'merged_exact_spend':str(merged_exact_sp),'merged_exact_units':str(merged_exact_u),'internal_product_spend_rounded_sum':str(q2(internal_sp)),'internal_product_units':str(internal_u),'audit_rows':len(audit)}
    (OUT/'audit_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    print('OUT',OUT)

if __name__=='__main__':main()
