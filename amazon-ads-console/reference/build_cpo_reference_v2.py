from pathlib import Path
import csv,json,re,collections
from decimal import Decimal, ROUND_HALF_UP

ROOT=Path('/Users/panjinlong/Documents/agent-master/amazon-ads-console')
SKU=Path('/Users/panjinlong/Downloads/运营测试数据报告/广告单双数据/川鹏美站 运营 SKU 产品 表.csv')
WH_BIZ=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/川鹏业务报告/川鹏业务报告8月26日.csv')
WH_ADS=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/CPO计算/川鹏推广的商品_每日CPO单双计算_26日.csv')
WH_ADS30=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/推广的商品 30D 日期.csv')
WH_CHILD=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/川鹏2号/川鹏子asin-2年.csv')
WH_CMAP=ROOT/'reference/source/whitin_campaign_map_2026-08-26.json'
OU_BIZ=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/欧德思美站/欧德思业务报告8月25号当天.csv')
OU_ADS=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/欧德思美站/欧德思推广的商品8月25号.csv')
OU_MANUAL=Path('/Users/panjinlong/Downloads/欧德思_8月25日_14产品_CPO记录.csv')
AMS_0826=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/美国AMS/AMS CPO计算/AMS_推广的商品_每日CPO单双计算 (1).csv')
JIE_ADS=Path('/Users/panjinlong/Library/Application Support/ziniaobrowserdatas/ziniao browser/洁博利美站/洁博利 推广的商品 每日CPO单双计算.csv')

TYPES=['手动','自动','头条','视频','展示','流媒体']

def D(v):
    if v is None:return Decimal('0')
    if isinstance(v, Decimal):return v
    if isinstance(v, (int,float)):return Decimal(str(v))
    s=str(v).strip().replace(',','')
    if not s:return Decimal('0')
    m=re.search(r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?', s)
    if not m:return Decimal('0')
    try:return Decimal(m.group(0))
    except:return Decimal('0')

def clean_id(v):
    s=(v or '').strip()
    m=re.match(r'^="?(.*?)"?$',s)
    return m.group(1) if m else s

def q2(x): return x.quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)
def pct(v):
    return D(v)

def biz_load(path):
    out={}
    with path.open(encoding='utf-8-sig',errors='replace',newline='') as f:
        for r in csv.DictReader(f):
            p=(r.get('（父）ASIN') or '').strip()
            if p:out[p]=r
    return out

def title_matches(style,title):
    token=re.sub(r'(男|女)$','',style.rstrip('-'))
    return bool(token and re.search(r'(?<![A-Za-z0-9])'+re.escape(token)+r'(?![A-Za-z0-9])',title or '',re.I))

def build_whitin_map():
    ids=collections.defaultdict(lambda:{'asins':set(),'skus':set()})
    with SKU.open(encoding='utf-8-sig',errors='replace',newline='') as f:
        for r in csv.DictReader(f):
            g=(r.get('小组') or '').strip();st=(r.get('款式') or '').strip()
            if not g or not st:continue
            if r.get('ASIN'):ids[(g,st)]['asins'].add(r['ASIN'].strip())
            if r.get('SKU'):ids[(g,st)]['skus'].add(r['SKU'].strip())
    biz=biz_load(WH_BIZ)
    ap=collections.defaultdict(collections.Counter);sp=collections.defaultdict(collections.Counter)
    with WH_ADS30.open(encoding='utf-8-sig',errors='replace',newline='') as f:
        for r in csv.DictReader(f):
            a=(r.get('推广的商品编号') or '').strip();s=(r.get('推广的商品 SKU-Advertised product SKU') or '').strip();p=(r.get('推广的商品父级编号') or '').strip()
            if a and p:ap[a][p]+=1
            if s and p:sp[s][p]+=1
    c2p=collections.defaultdict(set)
    with WH_CHILD.open(encoding='utf-8-sig',errors='replace',newline='') as f:
        for r in csv.DictReader(f):
            c=(r.get('（子）ASIN') or '').strip();p=(r.get('（父）ASIN') or '').strip()
            if c and p:c2p[c].add(p)
    final={}; audit=[]
    for (g,st),d in sorted(ids.items()):
        ev=collections.Counter()
        for a in d['asins']:
            for p,n in ap.get(a,{}).items():
                if p in biz:ev[p]+=n
        for s in d['skus']:
            for p,n in sp.get(s,{}).items():
                if p in biz:ev[p]+=n
        p=None;src=None
        if len(ev)==1:
            p=next(iter(ev));src='ads_asin_sku'
        elif ev:
            exact=[x for x in ev if title_matches(st,biz[x].get('标题',''))]
            if len(exact)==1:p=exact[0];src='ads_plus_title'
        if not p:
            hist=collections.Counter()
            for a in d['asins']:
                for hp in c2p.get(a,set()):
                    if hp in biz:hist[hp]+=1
            exact=[x for x in hist if title_matches(st,biz[x].get('标题',''))]
            if len(exact)==1:p=exact[0];src='child_history_plus_title'
        if p:
            final[(g,st)]={'parent':p,'source':src}
        else:
            audit.append({'业务账户':'川鹏','日期':'2026-08-26','运营':g,'产品代号':st,'问题':'SKU身份未与当日业务报告形成唯一可靠父ASIN','金额':'','广告单':'','状态':'NOT_EFFECTIVE_OR_UNRESOLVED'})
    # Parent-ASIN cannot be counted twice within one business-account daily output.
    rev=collections.defaultdict(list)
    for k,v in final.items():rev[v['parent']].append(k)
    dup={p:v for p,v in rev.items() if len(v)>1}
    if dup:raise RuntimeError('WHITIN duplicate business parents: '+repr(dup))
    return final,biz,audit

WH_ALIAS={
 ('DD1','W822'):'W822男',
 ('LB1','NVW87'):'W87女',('LB1','W87'):'W87男',('LB1','W872'):'W872女',
 ('XH1','W81'):'W81女',
 ('ZF1','NVW601'):'W601',('ZF1','NVW882'):'W882女',('ZF1','W882'):'W882男',
 ('ZJ1','W51'):'W51男',('ZJ1','W8K2'):'W8K2-',('ZJ1','WTNVW823'):'W823女',('ZJ1','WTW823'):'W823男',
}
WH_MIXED={'19027149623806':['W8K2-','WK102'],'269172420948556':['W20','W30'],'278929760566914':['W20','W30'],'203273711641212':['W20','W30'],'328352666637596':['W20','W30']}

def ad_type(ad_product,name):
    ap=ad_product or '';n=name or '';low=n.lower()
    if ap=='Sponsored TV' or '流媒体' in n or 'streaming tv' in low:return '流媒体'
    if ap=='Sponsored Display' or (not ap and '展示' in n):return '展示'
    if ap=='Sponsored Brands' or (not ap and ('头条' in n or '视频' in n or 'sbv' in low)):
        return '视频' if ('视频' in n or 'video' in low or 'sbv' in low) else '头条'
    if 'auto' in low or '自动' in n:return '自动'
    return '手动'

def add_alloc(A,account,operator,product,source,typ,cost,units,sales,method,campaign_id,name):
    k=(account,operator,product)
    x=A[k];x['spend'][typ]+=cost;x['units'][typ]+=units;x['ad_sales']+=sales;x['ad_accounts'].add(source);x['methods'].add(method)
    x['campaigns'].add(campaign_id)

def alloc_whitin(A,product_map,audit):
    cmap={str(r['campaign_id']):r for r in json.load(WH_CMAP.open())}
    parent_lookup={(g,v['parent']):st for (g,st),v in product_map.items()}
    source_cost=source_units=source_sales=Decimal('0');unalloc=collections.defaultdict(lambda:[Decimal('0'),Decimal('0'),Decimal('0')])
    with WH_ADS.open(encoding='utf-8-sig',errors='replace',newline='') as f:
        for r in csv.DictReader(f):
            cid=clean_id(r['广告活动编号']);cost=D(r['总成本']);units=D(r['已售商品数量']);sales=D(r['销售额'])
            source_cost+=cost;source_units+=units;source_sales+=sales
            cm=cmap.get(cid)
            if not cm:
                unalloc[('NO_CAMPAIGN_MAP',cid,r['广告活动名称'])][0]+=cost;unalloc[('NO_CAMPAIGN_MAP',cid,r['广告活动名称'])][1]+=units;unalloc[('NO_CAMPAIGN_MAP',cid,r['广告活动名称'])][2]+=sales;continue
            g=cm.get('operator_group');typ=ad_type(cm.get('ad_product'),r['广告活动名称'])
            if cid in WH_MIXED:
                p=parent_lookup.get((g,(r.get('推广的商品父级编号') or '').strip()))
                if p in WH_MIXED[cid]:
                    add_alloc(A,'川鹏',g,p,'川鹏',typ,cost,units,sales,'mixed_split',cid,r['广告活动名称'])
                else:
                    # only rows with real metrics need a deterministic fallback; equal split by rule whitelist
                    targets=WH_MIXED[cid]
                    for i,t in enumerate(targets):
                        den=Decimal(len(targets));
                        add_alloc(A,'川鹏',g,t,'川鹏',typ,cost/den,units/den,sales/den,'mixed_split_equal_fallback',cid,r['广告活动名称'])
                continue
            code=cm.get('canonical_product_code')
            if g=='DD1' and cm.get('product_map_status')=='excluded' and r['广告活动名称'].startswith('DD1-C10'):
                p='C10';method='override_valid_c10'
            elif g=='YT1' and not code and r['广告活动名称'].startswith('YT1-WK103'):
                p='WK103';method='override_wk103'
            else:
                p=WH_ALIAS.get((g,code),code);method='campaign_code'
            if p and (g,p) in product_map:
                add_alloc(A,'川鹏',g,p,'川鹏',typ,cost,units,sales,method,cid,r['广告活动名称'])
            else:
                unalloc[(g,cid,r['广告活动名称'],p)][0]+=cost;unalloc[(g,cid,r['广告活动名称'],p)][1]+=units;unalloc[(g,cid,r['广告活动名称'],p)][2]+=sales
    for k,v in unalloc.items():
        if v[0] or v[1]:audit.append({'业务账户':'川鹏','日期':'2026-08-26','运营':k[0] if k else '', '产品代号':'','问题':'主账户广告未归属: '+str(k),'金额':str(q2(v[0])),'广告单':str(v[1]),'状态':'BLOCKED_UNALLOCATED_AD'})
    return source_cost,source_units,source_sales,unalloc

OU_PRODUCTS={
 ('XM1','Y10'):'B0FX2TG8CW',('XM2','S71女'):'B0DK7YD2KT',('XM2','KD7'):'B0CFF747QG',('XM2','S600'):'B0H41HL3M6',
 ('XM1','Y180'):'B0FX2Q73Q6',('XM2','Y90B'):'B0GKCKCSMJ',('XM2','Y71B'):'B0H1M9KJLC',('XM2','S7K1'):'B0DCMSZ2YJ',
 ('XM1','KD5'):'B0CL6ZRY16',('XM1','S71男'):'B0DGCM33J2',('XM1','S73'):'B0D2NDY5DD',('XM2','S75'):'B0DCV7KQJM',
 ('XM2','W8K4'):'B0CPPS6RJ2',('XM1','J100'):'B0H14MSYXF',
}
# Historical 14-product scope aliases confirmed by 8/25 manual CPO table.
def ou_owner(name):
    direct=[('XM1-J100','XM1','J100'),('XM1-KD5','XM1','KD5'),('XM1-S71','XM1','S71男'),('XM1-S73','XM1','S73'),('XM1-Y10','XM1','Y10'),('XM1-Y180','XM1','Y180'),
            ('XM2-KD7','XM2','KD7'),('XM2-S600','XM2','S600'),('XM2-S71','XM2','S71女'),('XM2-S75','XM2','S75'),('XM2-S7K1','XM2','S7K1'),('XM2-W8K4','XM2','W8K4'),('XM2-Y71B','XM2','Y71B'),('XM2-Y90B','XM2','Y90B')]
    for pre,g,p in direct:
        if name.startswith(pre):return g,p,'campaign_code'
    if name.startswith('XM1-S713'):return 'XM1','S71男','historical_campaign_code'
    if name.startswith('XM2-S713'):return 'XM2','S71女','historical_campaign_code'
    return None
OU_BLOCK_IDS={'132763011090925':'XM2-KD系列-自动捡漏','112593123026332':'XM2-S7系列-手动捡漏-动态'}

def alloc_oudesi(A,audit):
    src_cost=src_units=src_sales=Decimal('0');outside=[Decimal('0'),Decimal('0'),Decimal('0')];blocked=[Decimal('0'),Decimal('0'),Decimal('0')]
    with OU_ADS.open(encoding='utf-8-sig',errors='replace',newline='') as f:
        for r in csv.DictReader(f):
            cid=clean_id(r['广告活动编号']);name=r['广告活动名称'];cost=D(r['总成本']);units=D(r['已售商品数量']);sales=D(r['销售额'])
            src_cost+=cost;src_units+=units;src_sales+=sales
            if cid in OU_BLOCK_IDS:
                blocked[0]+=cost;blocked[1]+=units;blocked[2]+=sales;continue
            own=ou_owner(name)
            if own:
                g,p,m=own;add_alloc(A,'欧德思',g,p,'欧德思',ad_type('',name),cost,units,sales,m,cid,name)
            elif name.startswith('DD1-J102'):
                outside[0]+=cost;outside[1]+=units;outside[2]+=sales
            else:
                audit.append({'业务账户':'欧德思','日期':'2026-08-25','运营':'','产品代号':'','问题':'未识别Campaign '+cid+' '+name,'金额':str(q2(cost)),'广告单':str(units),'状态':'BLOCKED_UNALLOCATED_AD'})
    if blocked[0] or blocked[1]:audit.append({'业务账户':'欧德思','日期':'2026-08-25','运营':'XM2','产品代号':'','问题':'2条历史未确认混合Campaign: XM2-KD系列 / XM2-S7系列','金额':str(q2(blocked[0])),'广告单':str(blocked[1]),'状态':'BLOCKED_SPECIAL_CAMPAIGN'})
    if outside[0] or outside[1]:audit.append({'业务账户':'欧德思','日期':'2026-08-25','运营':'DD1','产品代号':'J102','问题':'J102有广告和业务数据，但不在已确认14产品历史CPO范围','金额':str(q2(outside[0])),'广告单':str(outside[1]),'状态':'OUTSIDE_CONFIRMED_SCOPE'})
    return src_cost,src_units,src_sales,blocked,outside

# AMS 8/26: cross-account ad-only source. Product owner determined by campaign code unless explicit V3.5 rule.
ZJ_FIXED={'479537915429061':['W85','W81','W63','W51男']}
ZJ_EQUAL={'1775045260101':['W30','W20','W63','W81']}
def split(total,n):return [total/Decimal(n)]*n

def ams_owner(name,parent):
    # business account + operator + product + method; None => blocked/missing business source
    rules=[
      ('DD1-W8K7','川鹏','DD1','W8K7'),('XM1-S71W','川鹏','XM1','S71W'),('XM1-V202','川鹏','XM1','V202'),('XM1-YG02','川鹏','XM1','YG02'),
      ('XM1-Y10','欧德思','XM1','Y10'),('XM2-KD7','欧德思','XM2','KD7'),('XM2-S71','欧德思','XM2','S71女'),
      ('YS1-Z10','川鹏','YS1','Z10'),('YT1-W702','川鹏','YT1','W702'),('YT1-WK101','川鹏','YT1','WK101'),('YT1-WK103','川鹏','YT1','WK103'),
      ('ZJ1-DU08','川鹏','ZJ1','DU08'),('ZJ1-W30','川鹏','ZJ1','W30'),('ZJ1-W51女','川鹏','ZJ1','W51女'),('ZJ1-W51男','川鹏','ZJ1','W51男'),('ZJ1-W63','川鹏','ZJ1','W63'),
      ('ZJ1-W75V2','川鹏','ZJ1','W75V2'),('ZJ1-W81 ','川鹏','ZJ1','W81'),('ZJ1-W823男','川鹏','ZJ1','W823男'),('ZJ1-W85','川鹏','ZJ1','W85'),('ZJ1-W8K2-','川鹏','ZJ1','W8K2-'),('ZJ1-WK102','川鹏','ZJ1','WK102')]
    for pre,a,g,p in rules:
        if name.startswith(pre):return a,g,p,'campaign_code'
    if name.startswith('XM2-KD75') and parent=='B0CFF747QG':return '欧德思','XM2','KD7','advertised_product_fallback'
    return None

def alloc_ams(A,audit,wh_map):
    # aggregate only fixed/equal campaign as whole; normal campaigns can safely sum raw rows to campaign_code.
    rows=[]
    with AMS_0826.open(encoding='utf-8-sig',errors='replace',newline='') as f:rows=list(csv.DictReader(f))
    src_cost=sum((D(r['总成本']) for r in rows),Decimal('0'));src_units=sum((D(r['已售商品数量']) for r in rows),Decimal('0'));src_sales=sum((D(r['销售额']) for r in rows),Decimal('0'))
    groups=collections.defaultdict(list)
    for r in rows:groups[(clean_id(r['广告活动编号']),r['广告活动名称'])].append(r)
    blocked=[Decimal('0'),Decimal('0'),Decimal('0')]
    for (cid,name),rs in groups.items():
        cost=sum((D(r['总成本']) for r in rs),Decimal('0'));units=sum((D(r['已售商品数量']) for r in rs),Decimal('0'));sales=sum((D(r['销售额']) for r in rs),Decimal('0'))
        typ=ad_type('Sponsored Brands',name)
        if cid in ZJ_FIXED:
            ts=ZJ_FIXED[cid]
            for p in ts:add_alloc(A,'川鹏','ZJ1',p,'AMS',typ,cost/len(ts),units/len(ts),sales/len(ts),'fixed_equal_split',cid,name)
            continue
        if cid in ZJ_EQUAL:
            ts=ZJ_EQUAL[cid]
            for p in ts:add_alloc(A,'川鹏','ZJ1',p,'AMS',typ,cost/len(ts),units/len(ts),sales/len(ts),'mixed_split_equal_fallback',cid,name)
            continue
        if cid=='79897800480005':
            add_alloc(A,'川鹏','ZJ1','W51女','AMS',typ,cost,units,sales,'campaign_code_special',cid,name);continue
        if cid=='73789533007579':
            blocked[0]+=cost;blocked[1]+=units;blocked[2]+=sales
            audit.append({'业务账户':'川鹏','日期':'2026-08-26','运营':'ZJ1','产品代号':'W75V2/Z32','问题':'V3.5明确要求确认：73789533007579 是 campaign_code→W75V2 还是 mixed_split→W75V2+Z32','金额':str(q2(cost)),'广告单':str(units),'状态':'BLOCKED_CAMPAIGN_RULE_CONFIRMATION'})
            continue
        # All W8K2 AMS campaigns remain W8K2- by campaign_code; advertised WK102/W8K23 is audit-only.
        parent=next(((r.get('推广的商品父级编号') or '').strip() for r in rs if (r.get('推广的商品父级编号') or '').strip()),'')
        own=ams_owner(name,parent)
        if own:
            a,g,p,m=own
            add_alloc(A,a,g,p,'AMS',typ,cost,units,sales,m,cid,name)
        else:
            blocked[0]+=cost;blocked[1]+=units;blocked[2]+=sales
            if cost or units:
                audit.append({'业务账户':'洁博利/待确认','日期':'2026-08-26','运营':re.match(r'^([A-Z]{2}\d+)',name).group(1) if re.match(r'^([A-Z]{2}\d+)',name) else '', '产品代号':'','问题':'AMS Campaign无法回卷到已有完整业务账户: '+name,'金额':str(q2(cost)),'广告单':str(units),'状态':'BLOCKED_BUSINESS_REPORT_MISSING'})
    return src_cost,src_units,src_sales,blocked

def new_bucket():return {'spend':{t:Decimal('0') for t in TYPES},'units':{t:Decimal('0') for t in TYPES},'ad_sales':Decimal('0'),'ad_accounts':set(),'methods':set(),'campaigns':set()}

def build_rows(A,wh_map,wh_biz,ou_biz):
    out=[]
    # WHITIN 100 mapped effective products
    for (g,p),meta in sorted(wh_map.items()):
        b=wh_biz[meta['parent']];a=A[('川鹏',g,p)]
        out.append(final_row('川鹏','2026-08-26',g,p,meta['parent'],b,a,'READY',meta['source']))
    # OUDESI confirmed 14 historical scope only
    for (g,p),parent in OU_PRODUCTS.items():
        b=ou_biz[parent];a=A[('欧德思',g,p)]
        out.append(final_row('欧德思','2026-08-25',g,p,parent,b,a,'READY_CONFIRMED_SCOPE','historical_14_scope'))
    out.sort(key=lambda r:(r['业务账户'],r['运营'],r['产品代号']))
    return out

def final_row(account,date,g,p,parent,b,a,status,map_source):
    total_sp=sum(a['spend'].values(),Decimal('0'));total_u=sum(a['units'].values(),Decimal('0'));orders=D(b.get('已订购商品数量'));biz_sales=D(b.get('已订购商品销售额'))
    r={'业务账户':account,'运营':g,'产品代号':p,'父ASIN':parent,'日期':date,'广告账户':'+'.join(sorted(a['ad_accounts'],key=lambda x:{'川鹏':1,'欧德思':1,'AMS':2}.get(x,9)))}
    for t in TYPES:r[t+'费用']=str(q2(a['spend'][t]))
    for t in TYPES:r[t+'广告单']=str(a['units'][t].quantize(Decimal('0.0001')).normalize())
    for t in TYPES:r[t+'单均费用']=str(q2(a['spend'][t]/a['units'][t])) if a['units'][t] else '0.00'
    natural=orders-total_u
    final_status=status if natural>=0 else 'BLOCKED_AD_ORDERS_GT_TOTAL'
    r.update({'总费用':str(q2(total_sp)),'总广告单':str(total_u.quantize(Decimal('0.0001')).normalize()),'全部订单':str(orders.normalize()),'综合CPO':str(q2(total_sp/orders)) if orders else '0.00',
              '广告归因销售额':str(q2(a['ad_sales'])),'业务销售额':str(q2(biz_sales)),'ROAS':str(q2(a['ad_sales']/total_sp)) if total_sp else '',
              'TACOS_pct':str(q2(total_sp/biz_sales*100)) if biz_sales else '', 'Sessions':str(D(b.get('会话数 - 总计')).normalize()),'CVR_pct':str(D(b.get('商品会话百分比')).normalize()),
              '自然单':str(natural.quantize(Decimal('0.0001')).normalize()),'状态':final_status,'业务映射来源':map_source,'广告归属方法':'|'.join(sorted(a['methods']))})
    return r

def write_csv(path,rows,cols=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not rows:return
    fields=cols or list(rows[0].keys())
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
    wh_map,wh_biz,audit=build_whitin_map();ou_biz=biz_load(OU_BIZ)
    A=collections.defaultdict(new_bucket)
    whsrc=alloc_whitin(A,wh_map,audit)
    ousrc=alloc_oudesi(A,audit)
    amssrc=alloc_ams(A,audit,wh_map)
    rows=build_rows(A,wh_map,wh_biz,ou_biz)
    outdir=ROOT/'reference/output_v2'
    write_csv(outdir/'CPO_参考答案_全账户_重新计算.csv',rows)
    write_csv(outdir/'CPO_异常与未纳入项_重新计算.csv',audit)
    # account/operator summary
    sm=[]
    for (acc,date),rr in sorted(collections.defaultdict(list,{}).items()):pass
    by=collections.defaultdict(list)
    for r in rows:by[(r['业务账户'],r['日期'],r['运营'])].append(r)
    for (acc,date,g),rr in sorted(by.items()):
        sm.append({'业务账户':acc,'日期':date,'运营':g,'产品数':len(rr),'总费用':str(q2(sum((D(x['总费用']) for x in rr),Decimal('0')))),'总广告单':str(sum((D(x['总广告单']) for x in rr),Decimal('0')).normalize()),'全部订单':str(sum((D(x['全部订单']) for x in rr),Decimal('0')).normalize())})
    write_csv(outdir/'CPO_运营汇总_重新计算.csv',sm)
    # audit/conservation
    ready_wh=[r for r in rows if r['业务账户']=='川鹏'];ready_ou=[r for r in rows if r['业务账户']=='欧德思']
    wh_product_sp=sum((D(r['总费用']) for r in ready_wh),Decimal('0'));wh_product_u=sum((D(r['总广告单']) for r in ready_wh),Decimal('0'))
    ou_product_sp=sum((D(r['总费用']) for r in ready_ou),Decimal('0'));ou_product_u=sum((D(r['总广告单']) for r in ready_ou),Decimal('0'))
    info={
      'whitin_effective_products':len(ready_wh),'oudesi_confirmed_products':len(ready_ou),
      'whitin_main_raw':{'spend':str(q2(whsrc[0])),'units':str(whsrc[1]),'sales':str(q2(whsrc[2])),'unallocated_groups':len(whsrc[3])},
      'oudesi_main_raw':{'spend':str(q2(ousrc[0])),'units':str(ousrc[1]),'sales':str(q2(ousrc[2])),'blocked_special_spend':str(q2(ousrc[3][0])),'outside_scope_spend':str(q2(ousrc[4][0]))},
      'ams_raw':{'spend':str(q2(amssrc[0])),'units':str(amssrc[1]),'sales':str(q2(amssrc[2])),'blocked_missing_business_spend':str(q2(amssrc[3][0])),'blocked_units':str(amssrc[3][1])},
      'reference_product_totals':{'川鹏_spend':str(q2(wh_product_sp)),'川鹏_units':str(wh_product_u),'欧德思_spend':str(q2(ou_product_sp)),'欧德思_units':str(ou_product_u)},
      'audit_rows':len(audit)
    }
    (outdir/'audit.json').write_text(json.dumps(info,ensure_ascii=False,indent=2))
    print(json.dumps(info,ensure_ascii=False,indent=2))
    print('outputs',outdir)

if __name__=='__main__':main()
