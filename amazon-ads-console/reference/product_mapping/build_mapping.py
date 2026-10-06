from pathlib import Path
import csv, collections

OPERATOR_NAMES={
    'AJ':'爱菊','DD':'丹丹','LB':'丽斌','LW':'林文','XH':'鑫华',
    'XM':'雪敏','YS':'雨珊','YT':'雅婷','ZF':'珍凤','ZJ':'子娟',
}

ROOT=Path(__file__).resolve().parents[2]
IDENTITY=Path(__file__).with_name('product_identity_summary.csv')
AUDIT=ROOT/'reference/output_v3/CPO_内部审计主表.csv'
OUT=Path(__file__).with_name('全部账户_运营产品标准映射表.csv')

identities=[]
with IDENTITY.open(encoding='utf-8-sig',newline='') as f:
    identities=list(csv.DictReader(f))

active=collections.defaultdict(list)
if AUDIT.exists():
    with AUDIT.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            active[(r['运营'],r['产品代号'])].append(r)

rows=[]
for ident in identities:
    op=ident['运营']; product=ident['产品代号']; rs=active.get((op,product),[])
    business=[]; ad=[]; parents=[]; dates=[]
    for r in rs:
        business += [x for x in (r.get('业务账户') or '').split('+') if x]
        ad += [x for x in (r.get('广告账户') or '').split('+') if x]
        parents += [x for x in (r.get('父ASIN') or '').split('|') if x]
        if r.get('日期'): dates.append(r['日期'])
    # User-confirmed XM2 account boundary: ads only in OUDESI + AMS.
    if op=='XM2':
        business=['欧德思']
        ad=['欧德思','AMS']
    business=sorted(set(business)); ad=sorted(set(ad)); parents=sorted(set(parents)); dates=sorted(set(dates))
    if rs:
        status='当前业务报告已命中'
    elif op=='AJ2':
        status='缺业务报告待确认'
    else:
        status='历史身份（当前参考日未命中）'
    rows.append({
        '运营组':op,
        '运营姓名':OPERATOR_NAMES.get(op[:2],op),
        '产品代号':product,
        '业务账户':' + '.join(business) if business else '待业务报告确认',
        '广告账户':' + '.join(ad) if ad else '待确认',
        '父ASIN':' | '.join(parents),
        'ASIN数量':ident['ASIN数量'],
        'SKU数量':ident['SKU数量'],
        '当前状态':status,
        '参考日期':' / '.join(dates),
    })

with OUT.open('w',encoding='utf-8-sig',newline='') as f:
    fields=['运营姓名','运营组','产品代号','业务账户','广告账户','父ASIN','ASIN数量','SKU数量','当前状态','参考日期']
    w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
print(OUT)
print('rows',len(rows),'active',sum(r['当前状态']=='当前业务报告已命中' for r in rows),'operators',len(set(r['运营姓名'] for r in rows)))
