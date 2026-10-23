"""Authenticated CPO XLSX exports; returns exactly the existing UI snapshot semantics."""
from __future__ import annotations

import io
import re
from typing import Optional, Literal
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from app.api.auth import require_session, require_management_session
from app.api.cpo_dates import validate_cpo_report_date
from app.services.operator_cpo import OPERATOR_NAMES, canonical_operator_name, operator_group_of, operator_cpo_summary, operator_cpo_detail, _build, _period_range
from app.services.cache import cache


def cached_summary(day,sb_attribution_mode='name'):
    if day is None:
        return None
    return cache.get(f"operator:summary:{sb_attribution_mode}:daily:{day}")


def cached_detail(name,day,sb_attribution_mode='name'):
    if day is None:
        return None
    return cache.get(f"operator:detail:{name}:{sb_attribution_mode}:daily:{day}")
from app.services.operator_export_workbooks import (
    summary_xlsx,detail_xlsx,MAX_OPERATORS,MAX_ARCHIVE_BYTES,
)

router = APIRouter(prefix="/operator-reports", tags=["operator-reports"])


def _who(session):
    return (session[1] or {})


def _manager(user):
    return user.get("roleCode") in ("management","super_admin")


def _authorized_detail(user,name):
    if _manager(user):
        return canonical_operator_name(name)
    code = operator_group_of(user.get("operatorCode") or user.get("operator_code") or "")
    own = OPERATOR_NAMES.get(code)
    if user.get("roleCode")!="operator" or not own or canonical_operator_name(name)!=own:
        raise HTTPException(403,"Not allowed to export another operator's details")
    return own


def _load_summary(day,period,sb_attribution_mode):
    result=cached_summary(day,sb_attribution_mode) if period=="daily" else None
    return result if result is not None else operator_cpo_summary(day,period,sb_attribution_mode)


def _load_detail(name,day,period,sb_attribution_mode):
    result=cached_detail(name,day,sb_attribution_mode) if period=="daily" else None
    return result if result is not None else operator_cpo_detail(name,day,period,sb_attribution_mode=sb_attribution_mode)


def _download(content, filename, media_type):
    return Response(content=content,media_type=media_type,headers={
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control":"private, no-store",
        "X-Content-Type-Options":"nosniff",
    })


@router.get("/summary.xlsx")
def download_shared_summary(period:Literal["daily","weekly","monthly"]="daily",
                            sb_attribution_mode:Literal['name','asin']='name',
                            date:Optional[str]=None, session=Depends(require_management_session)):
    validate_cpo_report_date(date, period)
    data=_load_summary(date,period,sb_attribution_mode)
    name=f"all_operators_{(data.get('data_date') or date or 'latest')}_sb-{sb_attribution_mode}.xlsx"
    return _download(summary_xlsx(data),name,
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/operators/{operator}.xlsx")
def download_operator(operator:str,period:Literal["daily","weekly","monthly"]="daily",
                      sb_attribution_mode:Literal['name','asin']='name',
                      date:Optional[str]=None,session=Depends(require_session)):
    who=_who(session)
    canonical=_authorized_detail(who,operator)
    validate_cpo_report_date(date, period)
    data=_load_detail(canonical,date,period,sb_attribution_mode)
    name=f"operator_{(data.get('data_date') or date or 'latest')}_sb-{sb_attribution_mode}.xlsx"
    return _download(detail_xlsx(data),name,
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@router.get("/all.zip")
def download_all_reports(period:Literal["daily","weekly","monthly"]="daily",
                         sb_attribution_mode:Literal['name','asin']='name',
                         date:Optional[str]=None,session=Depends(require_session)):
    if not _manager(_who(session)):
        raise HTTPException(403,"Only management can export all operator reports")
    validate_cpo_report_date(date, period)
    summary=_load_summary(date,period,sb_attribution_mode)
    names=[canonical_operator_name(str(x.get("name") or "").strip())
           for x in (summary.get("operators") or []) if x.get("name")]
    names=list(dict.fromkeys(n for n in names if n and n != "未归属"))
    if len(names)>MAX_OPERATORS:
        raise HTTPException(413,"Too many operators to export")
    stamp=summary.get("data_date") or date or "latest"
    out=io.BytesIO()
    anchor=date or summary.get("data_date")
    prebuilt=None
    total_rows=0
    with ZipFile(out,"w",ZIP_DEFLATED,compresslevel=5) as archive:
        archive.writestr(f"00_全部运营汇总_{stamp}.xlsx",summary_xlsx(summary))
        for index,name in enumerate(names,1):
            detail=cached_detail(name,anchor,sb_attribution_mode) if period=="daily" else None
            if detail is None:
                if prebuilt is None:
                    if not anchor:
                        raise HTTPException(422,"No report date available")
                    start,end=_period_range(anchor,period)
                    prebuilt=_build(start,end,sb_attribution_mode)
                detail=operator_cpo_detail(name,anchor,period,_prebuilt=prebuilt,sb_attribution_mode=sb_attribution_mode)
            total_rows+=len(detail.get("products") or [])
            if total_rows>20000:
                raise HTTPException(413,"Too many rows for one-click export")
            safe="".join(ch if (ch.isalnum() or ch in "_-") else "_" for ch in name)[:25]
            archive.writestr(f"{index:02d}_{safe}_运营明细_{stamp}.xlsx",detail_xlsx(detail))
            if out.tell()>MAX_ARCHIVE_BYTES:
                raise HTTPException(413,"CPO report archive exceeds size limit")
    if len(out.getvalue())>MAX_ARCHIVE_BYTES:
        raise HTTPException(413,"CPO report archive exceeds size limit")
    return _download(out.getvalue(),f"all_operator_reports_{stamp}_sb-{sb_attribution_mode}.zip","application/zip")
