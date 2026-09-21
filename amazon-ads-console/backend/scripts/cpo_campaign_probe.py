import sys,json
sys.path.insert(0,'backend')
import run_rds
from app.services.rds_query import query_rows
ids=['1775045260101','479537915429061','79897800480005','73789533007579']
q=','.join("'"+x+"'" for x in ids)
rows=query_rows(f"""SELECT account_name,campaign_id,max(campaign_name) campaign_name,ad_product,sum(spend)::float8 spend,sum(purchases)::float8 purchases,count(*)::int rows,array_agg(DISTINCT advertised_product_parent_id) parents,array_agg(DISTINCT advertised_product_id) advertised_ids FROM core.report_advertised_product_daily WHERE stat_date=DATE '2026-09-13' AND campaign_id::text IN ({q}) GROUP BY account_name,campaign_id,ad_product ORDER BY campaign_id,ad_product""")
print(json.dumps(rows,ensure_ascii=False,default=str,indent=2))
