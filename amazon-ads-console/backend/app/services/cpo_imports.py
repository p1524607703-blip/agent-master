from __future__ import annotations

import csv
import datetime as dt
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

from .product_mapping import product_mappings
from .rds_query import query_one, query_rows
from .cache import invalidate_data_read_models

PROJECT_ROOT = Path(__file__).resolve().parents[3]
UPLOAD_ROOT = PROJECT_ROOT / 'backend' / '.cpo_uploads'
AD_IMPORTER_PATH = Path(os.environ.get('AD_IMPORTER_PATH', str(PROJECT_ROOT.parent / 'ad-reports-export' / 'subscribed_reports_to_rds.py')))

ACCOUNTS = {
    '川鹏': ('amzn1.ads-account.g.42jh8psyvhiiiitpm4rnj4qhh', 'WHITIN'),
    '欧德思': ('amzn1.ads-account.g.dfa7o7cwdl371d634ew58i919', 'BLOOMNEXT'),
    '洁博利': ('amzn1.ads-account.g.6wudif27px024b6yk7v98vtwh', 'JOOMRA DIRECT'),
    'AMS': ('amzn1.ads-account.g.95u2uh57eqgxov6ga8j0l0xlz', 'anac1973 (C3S8S)'),
}
REPORT_DB_TYPE = {'业务报告': 'business_report', 'CPO推广商品': 'cpo'}
MAX_UPLOAD_BYTES = 120 * 1024 * 1024


def _sqlq(value: str) -> str:
    return (value or '').replace("'", "''")


def _decode(data: bytes) -> str:
    for enc in ('utf-8-sig', 'gb18030'):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode('utf-8', errors='replace')


def _num(value: str) -> str:
    s=(value or '').strip().replace(',', '').replace('US$', '').replace('$', '').replace('%','')
    return s


def _id(value: str) -> str:
    s=(value or '').strip()
    if s.startswith('="') and s.endswith('"'):
        return s[2:-1]
    if s.startswith('='):
        return s[1:].strip('"')
    return s


def _esc_copy(value: Any) -> str:
    if value is None or value == '':
        return ''
    return str(value).replace('\\','\\\\').replace('\t','\\t').replace('\n','\\n').replace('\r','')


@lru_cache(maxsize=1)
def _ad_importer():
    spec=importlib.util.spec_from_file_location('shared_subscribed_reports_importer', str(AD_IMPORTER_PATH))
    if not spec or not spec.loader:
        raise RuntimeError('无法加载现有广告报告 importer')
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _duplicate(account_id: str, db_type: str, fhash: str) -> dict[str,Any] | None:
    # Current warehouse lineage table is core.import_batches.  File hash is
    # the safest cross-importer duplicate key because historical business
    # batches may not have account_id populated.
    return query_one(
        "SELECT batch_id,file_name AS source_file_name,"
        "report_start_date::text AS exported_at,imported_at::text "
        "FROM core.import_batches "
        f"WHERE file_hash='{_sqlq(fhash)}' "
        "ORDER BY batch_id DESC LIMIT 1"
    )


def _known_parents(account: str) -> set[str]:
    result=set()
    for r in product_mappings().get('rows',[]):
        accounts=[x.strip() for x in (r.get('businessAccount') or '').split('+') if x.strip()]
        if account in accounts and r.get('parentAsin'):
            result.update(x.strip() for x in r['parentAsin'].split('|') if x.strip())
    return result


def _business_columns(header: list[str]) -> dict[str,int | None]:
    hm={h.strip():i for i,h in enumerate(header)}
    def pick(*names):
        for n in names:
            if n in hm: return hm[n]
        return None
    return {
        'parent_asin': pick('（父）ASIN','(父)ASIN','(父) ASIN','ASIN'),
        'title': pick('标题','Title'),
        'sessions_total': pick('会话数 - 总计','Sessions','会话数'),
        'sessions_b2b': pick('会话 - 总计 - B2B'),
        'mobile_app_conversion_rate_b2b_pct': pick('转化率 - 移动应用 - B2B'),
        'mobile_app_session_pct': pick('会话百分比 - 移动应用'),
        'browser_session_pct': pick('会话百分比 - 浏览器'),
        'browser_session_b2b_pct': pick('会话百分比 - 浏览器 - B2B'),
        'ordered_product_units': pick('已订购商品数量','Units Ordered'),
        'ordered_product_units_b2b': pick('已订购商品数量 - B2B'),
        'unit_session_pct': pick('商品会话百分比'),
        'unit_session_b2b_pct': pick('商品会话百分比 - B2B'),
        'ordered_product_sales': pick('已订购商品销售额','Ordered Product Sales'),
        'ordered_product_sales_b2b': pick('已订购商品销售额 - B2B'),
        'total_order_items': pick('订单商品总数'),
        'total_order_items_b2b': pick('订单商品总数 - B2B'),
    }


def _infer_date_from_filename(filename: str, target_date: str) -> str | None:
    """Infer report date from known filenames; business-report CSV content has no date column."""
    name=(filename or '').replace('／','/').replace('－','-')
    target=dt.date.fromisoformat(target_date)

    # Amazon's raw download name is commonly BusinessReport-DD-M-YY.csv
    # (e.g. BusinessReport-17-9-26.csv == 2026-09-17).  Handle this
    # before generic month/day patterns so the trailing "9-26" is never
    # misread as September 26.
    raw=re.search(r'BusinessReport-(\d{1,2})[-_.](\d{1,2})[-_.](\d{2})(?=\.csv$)', name, re.I)
    if raw:
        try:
            yy=int(raw.group(3))
            year=2000+yy
            return dt.date(year,int(raw.group(2)),int(raw.group(1))).isoformat()
        except ValueError:
            return None

    candidates=[]
    patterns=[
        r'(?<!\d)(20\d{2})[-_.年/](\d{1,2})[-_.月/](\d{1,2})(?:日)?(?!\d)',
        r'(?<!\d)(\d{1,2})月(\d{1,2})(?:日)?',
        r'(?<!\d)(\d{1,2})[-_.](\d{1,2})(?!\d)',
    ]
    for idx,pat in enumerate(patterns):
        for m in re.finditer(pat,name):
            try:
                if idx==0:
                    d=dt.date(int(m.group(1)),int(m.group(2)),int(m.group(3)))
                else:
                    d=dt.date(target.year,int(m.group(1)),int(m.group(2)))
                candidates.append((m.start(),d))
            except ValueError:
                continue
    if not candidates:
        return None
    # Prefer the last explicit date in normalized/custom filenames.
    return sorted(candidates,key=lambda x:x[0])[-1][1].isoformat()


def _date_decision(actual_dates: list[str], target_date: str) -> tuple[str,bool,str]:
    actual=sorted(set(actual_dates))
    future=[d for d in actual if dt.date.fromisoformat(d)>dt.date.today()]
    if future:
        return 'BLOCKED',False,f'检测到未来数据日期：{", ".join(future)}'
    if target_date in actual:
        return 'READY',False,'文件数据日期与当前目标日期相符'
    if len(actual)==1:
        return 'CONFIRM_REQUIRED',True,f'当前目标数据日为 {target_date}，文件实际数据日为 {actual[0]}；将按 {actual[0]} 历史补录，不会写入 {target_date}'
    return 'CONFIRM_REQUIRED',True,f'当前目标数据日为 {target_date}，文件实际覆盖 {actual[0]} ~ {actual[-1]}；将按文件内各日期分别入库，不会写入页面目标日'


def _parse_business(data: bytes, account: str, actual_date: str) -> dict[str,Any]:
    text=_decode(data); reader=csv.reader(io.StringIO(text))
    try: header=[x.strip().replace('\ufeff','') for x in next(reader)]
    except StopIteration: return {'status':'BLOCKED','code':'EMPTY_FILE','message':'文件为空'}
    cols=_business_columns(header)
    child_idx=None
    for name in ('（子）ASIN','(子)ASIN','(Child) ASIN','Child ASIN'):
        if name in header: child_idx=header.index(name); break
    is_child=child_idx is not None
    required=['parent_asin','title','sessions_total','ordered_product_units','ordered_product_sales','total_order_items']
    missing=[c for c in required if cols.get(c) is None]
    if missing:
        return {'status':'BLOCKED','code':'MISSING_COLUMNS','message':'业务报告缺少必需字段','missing':missing}
    raw=[]
    for row in reader:
        if not any((x or '').strip() for x in row): continue
        def cell(name):
            idx=cols.get(name); return row[idx].strip() if idx is not None and idx < len(row) else ''
        parent=_id(cell('parent_asin'))
        if not parent: continue
        child=_id(row[child_idx].strip()) if is_child and child_idx < len(row) else ''
        if is_child and not child: continue
        raw.append({
            'child_asin':child,'parent_asin':parent,'title':cell('title') or child or parent,
            'sessions_total':_num(cell('sessions_total')),'sessions_b2b':_num(cell('sessions_b2b')),
            'mobile_app_conversion_rate_b2b_pct':_num(cell('mobile_app_conversion_rate_b2b_pct')),
            'mobile_app_session_pct':_num(cell('mobile_app_session_pct')),'browser_session_pct':_num(cell('browser_session_pct')),
            'browser_session_b2b_pct':_num(cell('browser_session_b2b_pct')),'ordered_product_units':_num(cell('ordered_product_units')),
            'ordered_product_units_b2b':_num(cell('ordered_product_units_b2b')),'unit_session_pct':_num(cell('unit_session_pct')),
            'unit_session_b2b_pct':_num(cell('unit_session_b2b_pct')),'ordered_product_sales':_num(cell('ordered_product_sales')),
            'ordered_product_sales_b2b':_num(cell('ordered_product_sales_b2b')),'total_order_items':_num(cell('total_order_items')),
            'total_order_items_b2b':_num(cell('total_order_items_b2b')),
        })
    if not raw:
        return {'status':'BLOCKED','code':'NO_DATA_ROWS','message':'业务报告没有有效ASIN数据行'}
    key=(lambda r:r['child_asin']) if is_child else (lambda r:r['parent_asin'])
    dedup={key(r):r for r in raw}
    known=_known_parents(account); parents={r['parent_asin'] for r in dedup.values()}
    overlap=len(parents & known) if known else 0
    required_overlap=max(1,min(5,(len(known)+4)//5)) if known else 0
    if known and overlap < required_overlap:
        return {'status':'BLOCKED','code':'ACCOUNT_MISMATCH_SUSPECTED','message':f'文件与{account}标准产品映射仅命中 {overlap} 个父ASIN，低于最低校验值 {required_overlap}，疑似上传错账户','rows':len(raw),'overlap':overlap,'required_overlap':required_overlap}
    level='child_asin_daily' if is_child else 'legacy_parent_asin_daily'
    return {'status':'READY','rows':len(raw),'unique_rows':len(dedup),'dropped':len(raw)-len(dedup),'overlap':overlap,'required_overlap':required_overlap,'parsed_rows':list(dedup.values()),'date':actual_date,'actual_data_date':actual_date,'detected_dates':[actual_date],'business_level':level}


def _parse_cpo(data: bytes, expected_account_id: str, target_date: str) -> dict[str,Any]:
    mod=_ad_importer()
    text=_decode(data)
    reader=csv.reader(io.StringIO(text))
    try: header=[mod.norm(x) for x in next(reader)]
    except StopIteration: return {'status':'BLOCKED','code':'EMPTY_FILE','message':'文件为空'}
    hidx={mod.norm(c):i for i,c in enumerate(header)}
    missing=[]
    for cn,_,_ in mod.SPECS['cpo']:
        if mod.norm(cn) not in hidx: missing.append(cn)
    if missing:
        return {'status':'BLOCKED','code':'MISSING_COLUMNS','message':'CPO推广商品报告缺少现有 importer 必需字段','missing':missing[:20]}
    ai=hidx[mod.norm('广告主账户 ID')]; di=hidx[mod.norm('日期')]
    accounts=set(); dates=set(); rows=0
    for row in reader:
        if not any((x or '').strip() for x in row): continue
        rows+=1
        if ai < len(row): accounts.add(mod.clean_id(row[ai]))
        if di < len(row):
            d=mod.clean_date(row[di])
            if d: dates.add(d)
    if not rows: return {'status':'BLOCKED','code':'NO_DATA_ROWS','message':'CPO推广商品报告没有数据行'}
    if accounts != {expected_account_id}:
        return {'status':'BLOCKED','code':'ACCOUNT_MISMATCH','message':'广告报告账户与上传卡片不一致','detected_accounts':sorted(accounts)}
    if not dates:
        return {'status':'BLOCKED','code':'DATE_NOT_DETECTED','message':'广告报告没有识别到有效日期'}
    decision,requires_confirmation,date_message=_date_decision(sorted(dates),target_date)
    if decision=='BLOCKED':
        return {'status':'BLOCKED','code':'FUTURE_DATE','message':date_message,'detected_dates':sorted(dates),'target_date':target_date}
    return {'status':decision,'rows':rows,'unique_rows':rows,'dropped':0,
            'date':max(dates),'actual_data_date':max(dates),'detected_dates':sorted(dates),
            'date_start':min(dates),'date_end':max(dates),'requires_confirmation':requires_confirmation,
            'date_message':date_message,'detected_accounts':sorted(accounts)}

def validate_upload(account: str, report_type: str, target_date: str, filename: str, data: bytes) -> dict[str,Any]:
    if account not in ACCOUNTS: return {'status':'BLOCKED','code':'UNKNOWN_ACCOUNT','message':'未知账户'}
    if report_type not in REPORT_DB_TYPE: return {'status':'BLOCKED','code':'UNKNOWN_REPORT_TYPE','message':'未知报告类型'}
    try: dt.date.fromisoformat(target_date)
    except Exception: return {'status':'BLOCKED','code':'INVALID_DATE','message':'目标日期格式错误'}
    if report_type=='业务报告' and account=='AMS': return {'status':'BLOCKED','code':'NOT_REQUIRED','message':'AMS无需业务报告'}
    if not filename.lower().endswith('.csv'): return {'status':'BLOCKED','code':'INVALID_FILE_TYPE','message':'当前只接受CSV报告'}
    if not data: return {'status':'BLOCKED','code':'EMPTY_FILE','message':'文件为空'}
    if len(data)>MAX_UPLOAD_BYTES: return {'status':'BLOCKED','code':'FILE_TOO_LARGE','message':'文件超过120MB限制'}
    aid,_=ACCOUNTS[account]; db_type=REPORT_DB_TYPE[report_type]
    fhash=hashlib.sha256(data).hexdigest()

    if report_type=='业务报告':
        actual_date=_infer_date_from_filename(filename,target_date)
        date_source='file_name' if actual_date else 'explicit_target_date'
        # Seller Central's business-report CSV has no date column.  When the
        # filename also has no trustworthy date, the page target date is only
        # a candidate: parse against it but require an explicit confirmation
        # before commit.  Never infer from file mtime or local/server clock.
        if not actual_date:
            actual_date=target_date
        if dt.date.fromisoformat(actual_date)>dt.date.today():
            return {'status':'BLOCKED','code':'FUTURE_DATE','message':f'识别到未来数据日期 {actual_date}，已阻断','actual_data_date':actual_date,'target_date':target_date,'date_source':date_source}
        parsed=_parse_business(data,account,actual_date)
        parsed['date_source']=date_source
        if parsed.get('status')=='READY':
            if date_source=='explicit_target_date':
                parsed.update({
                    'status':'CONFIRM_REQUIRED',
                    'requires_confirmation':True,
                    'date_source':date_source,
                    'date_message':f'业务报告 CSV 和文件名都没有可验证的数据日期。当前页面目标数据日是 {target_date}；请确认这份报告确实对应 {target_date}，确认后才会按该日入库。',
                })
            else:
                decision,requires_confirmation,date_message=_date_decision([actual_date],target_date)
                parsed.update({'status':decision,'requires_confirmation':requires_confirmation,'date_source':date_source,'date_message':date_message})
    else:
        parsed=_parse_cpo(data,aid,target_date)

    result={k:v for k,v in parsed.items() if k!='parsed_rows'}
    result.update({'account':account,'account_id':aid,'report_type':report_type,'target_date':target_date,'file_name':filename,'file_hash':fhash,'size_bytes':len(data)})
    if parsed.get('status')=='BLOCKED': return result

    # Parse date before duplicate check so duplicate feedback still reports the real data date/range.
    dup=_duplicate(aid,db_type,fhash)
    if dup:
        result.update({'status':'DUPLICATE','code':'DUPLICATE_FILE','message':f"该文件已导入，无需重复提交；数据库记录的数据日期为 {dup.get('exported_at') or result.get('actual_data_date') or '已识别日期'}",'duplicate_batch':dup})
        return result

    token=str(uuid.uuid4())
    folder=UPLOAD_ROOT/token; folder.mkdir(parents=True,exist_ok=False)
    path=folder/'upload.csv'; path.write_bytes(data)
    meta={**result,'token':token}
    (folder/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    result['token']=token
    return result

def _business_rows_from_path(path: Path) -> tuple[list[dict[str,str]],str]:
    data=path.read_bytes(); parsed=_parse_business(data,'川鹏',dt.date.today().isoformat())
    # account validation from the temporary parse is irrelevant here; re-read via stored parsed shape below if it blocked only for account overlap.
    text=_decode(data); reader=csv.reader(io.StringIO(text)); header=[x.strip().replace('\ufeff','') for x in next(reader)]; cols=_business_columns(header)
    child_idx=None
    for name in ('（子）ASIN','(子)ASIN','(Child) ASIN','Child ASIN'):
        if name in header: child_idx=header.index(name); break
    level='child_asin_daily' if child_idx is not None else 'legacy_parent_asin_daily'
    rows=[]
    for row in reader:
        if not any((x or '').strip() for x in row): continue
        def cell(name):
            idx=cols.get(name); return row[idx].strip() if idx is not None and idx < len(row) else ''
        parent=_id(cell('parent_asin')); child=_id(row[child_idx].strip()) if child_idx is not None and child_idx < len(row) else ''
        if not parent or (child_idx is not None and not child): continue
        rows.append({'child_asin':child,'parent_asin':parent,'title':cell('title') or child or parent,
            'sessions_total':_num(cell('sessions_total')),'sessions_b2b':_num(cell('sessions_b2b')),
            'mobile_app_conversion_rate_b2b_pct':_num(cell('mobile_app_conversion_rate_b2b_pct')),
            'mobile_app_session_pct':_num(cell('mobile_app_session_pct')),'browser_session_pct':_num(cell('browser_session_pct')),
            'browser_session_b2b_pct':_num(cell('browser_session_b2b_pct')),'ordered_product_units':_num(cell('ordered_product_units')),
            'ordered_product_units_b2b':_num(cell('ordered_product_units_b2b')),'unit_session_pct':_num(cell('unit_session_pct')),
            'unit_session_b2b_pct':_num(cell('unit_session_b2b_pct')),'ordered_product_sales':_num(cell('ordered_product_sales')),
            'ordered_product_sales_b2b':_num(cell('ordered_product_sales_b2b')),'total_order_items':_num(cell('total_order_items')),
            'total_order_items_b2b':_num(cell('total_order_items_b2b'))})
    k='child_asin' if level=='child_asin_daily' else 'parent_asin'
    return list({r[k]:r for r in rows}.values()),level


def _commit_business(path: Path, meta: dict[str,Any]) -> dict[str,Any]:
    rows,level=_business_rows_from_path(path)
    aid,account_name=ACCOUNTS[meta['account']]; day=meta.get('actual_data_date') or meta['target_date']; run_id=str(uuid.uuid4())
    lineage_meta=json.dumps({'upload_source':'cpo_console_manual','target_date':meta.get('target_date'),'actual_data_date':day,'date_source':meta.get('date_source') or 'file_name','business_level':level,'confirmation_required':bool(meta.get('requires_confirmation')),'confirmed':bool(meta.get('requires_confirmation'))},ensure_ascii=False)
    if level=='child_asin_daily':
        cols=['account_id','account_name','stat_date','child_asin','parent_asin','title','sessions_total','sessions_b2b','ordered_product_units','ordered_product_units_b2b','ordered_product_sales','ordered_product_sales_b2b','total_order_items','total_order_items_b2b','currency_code','source_file_name','source_file_hash']
        copy_lines=[]
        for r in rows:
            vals=[aid,account_name,day,r['child_asin'],r['parent_asin'],r['title'],r['sessions_total'],r['sessions_b2b'],r['ordered_product_units'],r['ordered_product_units_b2b'],r['ordered_product_sales'],r['ordered_product_sales_b2b'],r['total_order_items'],r['total_order_items_b2b'],'USD',meta['file_name'],meta['file_hash']]
            copy_lines.append('\t'.join(_esc_copy(x) for x in vals))
        sql_head=("BEGIN;\nCREATE TEMP TABLE biz_tmp ("+','.join(c+' text' for c in cols)+") ON COMMIT DROP;\n"+f"COPY biz_tmp ({','.join(cols)}) FROM STDIN WITH (DELIMITER E'\\t', NULL '');\n")
        update=[c for c in cols if c not in ('account_id','stat_date','child_asin')]
        select_expr=[]
        for c in cols:
            if c=='stat_date': select_expr.append('stat_date::date')
            elif c in ('sessions_total','sessions_b2b','ordered_product_units','ordered_product_units_b2b','total_order_items','total_order_items_b2b'): select_expr.append(f"nullif({c},'')::bigint")
            elif c in ('ordered_product_sales','ordered_product_sales_b2b'): select_expr.append(f"nullif({c},'')::numeric")
            else: select_expr.append(c)
        sql_tail=("\\.\n"+f"INSERT INTO core.report_business_child_asin_daily ({','.join(cols)}) SELECT {','.join(select_expr)} FROM biz_tmp ON CONFLICT (account_id,stat_date,child_asin) DO UPDATE SET "+','.join(f"{c}=EXCLUDED.{c}" for c in update)+",updated_at=now();\n"+"INSERT INTO core.import_batches (file_name,file_hash,source_path,report_type,report_start_date,report_end_date,exported_at,export_time_source,source_row_count,valid_row_count,failed_row_count,import_status,metadata,account_id,account_name,source_kind,data_level,target_table,schema_version) VALUES ("+f"'{_sqlq(meta['file_name'])}','{_sqlq(meta['file_hash'])}','cpo_console_manual','report_business_child_asin_daily',DATE '{day}',DATE '{day}',now(),'{_sqlq(meta.get('date_source') or 'file_name')}',{meta.get('rows',len(rows))},{len(rows)},0,'success','{_sqlq(lineage_meta)}'::jsonb,'{_sqlq(aid)}','{_sqlq(account_name)}','cpo_console_manual','child_asin_daily','core.report_business_child_asin_daily','business_child_daily_v1');\nCOMMIT;\n")
        table='core.report_business_child_asin_daily'
    else:
        cols=['account_id','account_name','report_start_date','report_end_date','parent_asin','title','sessions_total','sessions_b2b','mobile_app_conversion_rate_b2b_pct','mobile_app_session_pct','browser_session_pct','browser_session_b2b_pct','ordered_product_units','ordered_product_units_b2b','unit_session_pct','unit_session_b2b_pct','ordered_product_sales','ordered_product_sales_b2b','total_order_items','total_order_items_b2b','currency_code']
        copy_lines=[]
        for r in rows:
            vals=[aid,account_name,day,day,r['parent_asin'],r['title'],r['sessions_total'],r['sessions_b2b'],r['mobile_app_conversion_rate_b2b_pct'],r['mobile_app_session_pct'],r['browser_session_pct'],r['browser_session_b2b_pct'],r['ordered_product_units'],r['ordered_product_units_b2b'],r['unit_session_pct'],r['unit_session_b2b_pct'],r['ordered_product_sales'],r['ordered_product_sales_b2b'],r['total_order_items'],r['total_order_items_b2b'],'USD']
            copy_lines.append('\t'.join(_esc_copy(x) for x in vals))
        update=[c for c in cols if c not in ('account_id','report_start_date','report_end_date','parent_asin')]
        sql_head=("BEGIN;\nCREATE TEMP TABLE biz_tmp (LIKE core.business_report_parent_asin_period INCLUDING DEFAULTS) ON COMMIT DROP;\n"+f"COPY biz_tmp ({','.join(cols)}) FROM STDIN WITH (DELIMITER E'\\t', NULL '');\n")
        sql_tail=("\\.\n"+f"INSERT INTO core.business_report_parent_asin_period ({','.join(cols)}) SELECT {','.join(cols)} FROM biz_tmp ON CONFLICT (account_id,report_start_date,report_end_date,parent_asin) DO UPDATE SET "+','.join(f"{c}=EXCLUDED.{c}" for c in update)+",updated_at=now();\n"+"INSERT INTO core.import_batches (file_name,file_hash,source_path,report_type,report_start_date,report_end_date,exported_at,export_time_source,source_row_count,valid_row_count,failed_row_count,import_status,metadata,account_id,account_name,source_kind,data_level,target_table,schema_version) VALUES ("+f"'{_sqlq(meta['file_name'])}','{_sqlq(meta['file_hash'])}','cpo_console_manual','report_business_parent_asin_period',DATE '{day}',DATE '{day}',now(),'{_sqlq(meta.get('date_source') or 'file_name')}',{meta.get('rows',len(rows))},{len(rows)},0,'success','{_sqlq(lineage_meta)}'::jsonb,'{_sqlq(aid)}','{_sqlq(account_name)}','cpo_console_manual','legacy_parent_asin_daily','core.business_report_parent_asin_period','business_parent_legacy_v1');\nCOMMIT;\n")
        table='core.business_report_parent_asin_period'
    env=os.environ.copy(); proc=subprocess.run(['psql','-h',os.environ.get('RDS_PGHOST',os.environ.get('PGHOST','')),'-p',os.environ.get('RDS_PGPORT',os.environ.get('PGPORT','5432')),'-U',os.environ.get('RDS_PGUSER',os.environ.get('PGUSER','')),'-d',os.environ.get('RDS_PGDATABASE','amazon_ads_v2'),'-X','-q','-v','ON_ERROR_STOP=1','-w'],input=sql_head+'\n'.join(copy_lines)+'\n'+sql_tail,text=True,capture_output=True,env=env,timeout=60)
    if proc.returncode!=0: raise RuntimeError(proc.stderr.strip() or '业务报告入库失败')
    return {'loaded':len(rows),'table':table,'run_id':run_id,'business_level':level}


def commit_upload(token: str, confirm_historical: bool=False) -> dict[str,Any]:
    folder=UPLOAD_ROOT/token; meta_path=folder/'meta.json'; path=folder/'upload.csv'
    if not meta_path.exists() or not path.exists(): return {'status':'BLOCKED','code':'TOKEN_NOT_FOUND','message':'上传校验凭证不存在或已失效'}
    meta=json.loads(meta_path.read_text(encoding='utf-8'))
    if meta.get('requires_confirmation') and not confirm_historical:
        code='BUSINESS_TARGET_DATE_CONFIRM_REQUIRED' if meta.get('date_source')=='explicit_target_date' else 'HISTORICAL_BACKFILL_CONFIRM_REQUIRED'
        return {'status':'CONFIRM_REQUIRED','code':code,'message':meta.get('date_message') or '检测到需要人工确认的数据日期','token':token,'target_date':meta.get('target_date'),'actual_data_date':meta.get('actual_data_date'),'detected_dates':meta.get('detected_dates',[]),'date_source':meta.get('date_source')}
    actual=hashlib.sha256(path.read_bytes()).hexdigest()
    if actual!=meta['file_hash']: return {'status':'BLOCKED','code':'HASH_MISMATCH','message':'暂存文件校验失败'}
    dup=_duplicate(meta['account_id'],REPORT_DB_TYPE[meta['report_type']],meta['file_hash'])
    if dup: return {'status':'DUPLICATE','code':'DUPLICATE_FILE','message':'文件已由其他入口导入','duplicate_batch':dup}
    try:
        if meta['report_type']=='CPO推广商品':
            mod=_ad_importer()
            snapshot=dt.date.fromisoformat(meta.get('actual_data_date') or meta.get('target_date'))
            st=mod.load_file(str(path),str(uuid.uuid4()),snapshot,ptype_override='cpo',source_file_name_override=meta['file_name'])
            result={'loaded':st['loaded'] if st else 0,'table':st['table'] if st else 'core.subscribed_product_cpo_daily'}
        else:
            result=_commit_business(path,meta)
    except BaseException as e:
        return {'status':'BLOCKED','code':'IMPORT_FAILED','message':str(e)}
    meta['committed_at']=dt.datetime.now(dt.timezone.utc).isoformat();meta['commit_result']=result
    meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    invalidate_data_read_models()
    return {'status':'IMPORTED','account':meta['account'],'report_type':meta['report_type'],'target_date':meta['target_date'],'actual_data_date':meta.get('actual_data_date'),'detected_dates':meta.get('detected_dates',[]),'date_source':meta.get('date_source'),'file_name':meta['file_name'],**result}


def source_status(target_date: str) -> dict[str,Any]:
    dt.date.fromisoformat(target_date)
    items=[]
    for account,(aid,_) in ACCOUNTS.items():
        if account!='AMS':
            child=query_one("SELECT count(*)::int rows FROM core.report_business_child_asin_daily " f"WHERE account_id='{_sqlq(aid)}' AND stat_date=DATE '{target_date}'") or {'rows':0}
            child_rows=int(child.get('rows') or 0)
            if child_rows>0:
                items.append({'account':account,'reportType':'业务报告','date':target_date,'rows':child_rows,'status':'CHILD_READY','businessLevel':'child_asin_daily','detail':'子ASIN业务报告（正式口径）'})
            else:
                parent=query_one("SELECT count(*)::int rows FROM core.report_business_parent_asin_period " f"WHERE account_id='{_sqlq(aid)}' AND report_start_date=DATE '{target_date}' AND report_end_date=DATE '{target_date}'") or {'rows':0}
                parent_rows=int(parent.get('rows') or 0)
                items.append({'account':account,'reportType':'业务报告','date':target_date,'rows':parent_rows,'status':'LEGACY_PARENT_READY' if parent_rows>0 else 'MISSING','businessLevel':'legacy_parent_asin_daily' if parent_rows>0 else 'missing','detail':'父ASIN业务报告（兼容旧口径）' if parent_rows>0 else '缺少子ASIN业务报告'})
        else:
            items.append({'account':account,'reportType':'业务报告','date':target_date,'rows':0,'status':'NOT_REQUIRED','businessLevel':'not_required'})
        r=query_one("SELECT count(*)::int rows FROM core.report_advertised_product_daily " f"WHERE account_id='{_sqlq(aid)}' AND stat_date=DATE '{target_date}'") or {'rows':0}
        items.append({'account':account,'reportType':'CPO推广商品','date':target_date,'rows':int(r.get('rows') or 0),'status':'READY' if int(r.get('rows') or 0)>0 else 'MISSING','detail':'正式推广商品事实表状态；网页手动广告上传仍待接canonical importer'})
    ready_status={'READY','CHILD_READY','LEGACY_PARENT_READY'}
    return {'data_date':target_date,'items':items,'required':7,'ready':sum(1 for x in items if x['status'] in ready_status),'blockers':sorted(set(x['account'] for x in items if x['status']=='MISSING'))}
