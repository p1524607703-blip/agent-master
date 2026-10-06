import sys,json,csv,collections
sys.path.insert(0,'backend')
import run_rds
from app.services.rds_query import query_rows
from app.services.app_db import query_rows as app_rows
for t in ['report_campaign_daily','report_advertised_product_daily','report_purchased_product_daily','report_business_parent_asin_period']:
    print('TABLE',t)
    print(json.dumps(query_rows(f"SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='core' AND table_name='{t}' ORDER BY ordinal_position"),ensure_ascii=False))
print('CONSTRAINTS',json.dumps(app_rows("SELECT conname,pg_get_constraintdef(oid) AS def FROM pg_constraint WHERE conrelid='app.asin_parent_map'::regclass ORDER BY conname"),ensure_ascii=False))
print('INDEXES',json.dumps(app_rows("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='app' AND tablename='asin_parent_map' ORDER BY indexname"),ensure_ascii=False))
for t in ['report_campaign_daily','report_advertised_product_daily','report_purchased_product_daily']:
    print('COVERAGE',t,json.dumps(query_rows(f"SELECT account_id,max(account_name) account_name,count(*)::int rows FROM core.{t} WHERE stat_date=DATE '2026-09-13' GROUP BY account_id ORDER BY rows DESC"),ensure_ascii=False))
print('BUSINESS',json.dumps(query_rows("SELECT account_id,max(account_name) account_name,count(*)::int rows,sum(ordered_product_units)::float8 orders FROM core.report_business_parent_asin_period WHERE report_start_date=DATE '2026-09-13' AND report_end_date=DATE '2026-09-13' GROUP BY account_id ORDER BY rows DESC"),ensure_ascii=False))
rows=list(csv.DictReader(open('reference/product_mapping/全部账户_运营产品标准映射表.csv',encoding='utf-8-sig',newline='')))
active=[r for r in rows if r.get('当前状态')=='当前业务报告已命中' and (r.get('父ASIN') or '').strip()]
parents=collections.defaultdict(list)
for r in active:
    for a in [x.strip() for x in (r.get('父ASIN') or '').split('|') if x.strip()]: parents[a].append((r['产品代号'],r['运营组'],r['运营姓名'],r['业务账户'],r['广告账户']))
conf={a:v for a,v in parents.items() if len(set((x[0],x[1]) for x in v))>1}
print('STANDARD',json.dumps({'rows':len(rows),'active_parent_rows':len(active),'unique_parents':len(parents),'conflict_parents':len(conf),'conflicts':conf},ensure_ascii=False))
