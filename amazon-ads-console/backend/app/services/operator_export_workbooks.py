"""Dependency-free, genuine .xlsx exports for the existing CPO summary/detail snapshots.

Export is presentation only: it must never recompute or infer CPO attribution.
"""
from __future__ import annotations

import io
import math
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

MAX_ROWS = 5000
MAX_OPERATORS = 100
MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
AD_TYPES = ("SP", "SB", "SD", "STV", "DSP")
_SUMMARY_COLUMNS = ("运营", "有数据产品", "应有产品", "广告花费", "广告单", "全部订单", "综合CPO", "ROAS", "TACOS(%)", "状态")
_DETAIL_COLUMNS = (
    "产品", "报告日期/区间", "数据状态",
    *(f"{t}花费" for t in AD_TYPES),
    *(f"{t}广告单" for t in AD_TYPES),
    "总花费", "总广告单", "全部订单", "综合CPO", "ROAS", "TACOS(%)",
)


def _clean(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            return None
        return value
    # OOXML inline strings cannot be executed as formulas.
    return str(value).replace("\x00", "").replace("\r", " ").replace("\n", " ")[:32000]


def _column(index):
    result = ""
    while index:
        index, remainder = divmod(index-1, 26)
        result = chr(65+remainder)+result
    return result


def _cell(value, addr, style=0):
    value = _clean(value)
    if value is None:
        return f'<c r="{addr}" s="{style}"/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{addr}" s="{style}" t="n"><v>{value}</v></c>'
    return f'<c r="{addr}" s="{style}" t="inlineStr"><is><t xml:space="preserve">{escape(value)}</t></is></c>'


def workbook(rows, *, money_columns=(), numeric_columns=()):
    """Create a one-sheet XLSX with frozen headers and Excel numbers."""
    if not 1 <= len(rows) <= MAX_ROWS:
        raise ValueError("export row limit exceeded")
    width = max(map(len, rows))
    if width > 100:
        raise ValueError("export column limit exceeded")
    content = []
    for n, row in enumerate(rows, 1):
        cells = []
        for i, value in enumerate(row, 1):
            style = 1 if n == 4 else 4 if n == 1 else 2 if i in money_columns else 3 if i in numeric_columns else 0
            cells.append(_cell(value, f"{_column(i)}{n}", style))
        content.append(f'<row r="{n}">{"".join(cells)}</row>')
    sheet = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
             '<sheetViews><sheetView workbookViewId="0"><pane ySplit="4" topLeftCell="A5" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
             '<sheetFormatPr defaultRowHeight="19"/>'
             '<cols><col min="1" max="1" width="20" customWidth="1"/><col min="2" max="3" width="19" customWidth="1"/>'
             f'<col min="4" max="{width}" width="16" customWidth="1"/></cols>'
             '<sheetData>'+"".join(content)+'</sheetData><autoFilter ref="A4:'+_column(width)+str(len(rows))+'"/>'
             '</worksheet>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="3"><font><sz val="11"/><name val="Aptos"/></font>'
              '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/></font>'
              '<font><b/><sz val="14"/><color rgb="FF1D354F"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill>'
              '<fill><patternFill patternType="gray125"/></fill>'
              '<fill><patternFill patternType="solid"><fgColor rgb="FF21598D"/></patternFill></fill></fills>'
              '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<numFmts count="2"><numFmt numFmtId="164" formatCode="&quot;$&quot;#,##0.00"/>'
              '<numFmt numFmtId="165" formatCode="#,##0.00"/></numFmts>'
              '<cellXfs count="5"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1" applyFont="1"/>'
              '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
              '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
              '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs>'
              '</styleSheet>')
    out=io.BytesIO()
    with ZipFile(out,"w",ZIP_DEFLATED,compresslevel=6) as z:
        z.writestr("[Content_Types].xml",'<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
        z.writestr("_rels/.rels",'<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>')
        z.writestr("xl/workbook.xml",'<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
            ' xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="CPO报表" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels",'<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
            '</Relationships>')
        z.writestr("xl/styles.xml",styles)
        z.writestr("xl/worksheets/sheet1.xml",sheet)
    return out.getvalue()


def _meta(payload, subject):
    return [
        [f"AdSight · {subject}"],
        [f"报告周期：{payload.get('period','daily')}  日期：{payload.get('data_date','')}  来源：CPO控制台同口径快照"],
        ["数据完整性：" + ("待核验 / 非最终口径" if payload.get("final_cpo") is False else "按页面数据状态判定") +
         "；DSP暂无正式并入口径时留空，不参与总花费；任何缺失值保留为空。"],
    ]


def summary_xlsx(payload):
    rows=_meta(payload,"共用运营汇总")+[list(_SUMMARY_COLUMNS)]
    for r in payload.get("operators") or []:
        rows.append([r.get("name"),r.get("dataProducts"),r.get("products"),r.get("spend"),
                     r.get("adOrders"),r.get("totalOrders"),r.get("cpo"),r.get("roas"),
                     r.get("tacos"),r.get("status")])
    return workbook(rows,money_columns=(4,7),numeric_columns=(2,3,5,6,8,9))


def _type_sum(products, field, typ):
    vals=[(p.get(field) or {}).get(typ) for p in products]
    vals=[float(x) for x in vals if x is not None]
    return round(sum(vals),2) if vals else None


def detail_xlsx(payload):
    name=str(payload.get("operator") or "运营")
    ps=payload.get("products") or []
    if len(ps)>MAX_ROWS-5:
        raise ValueError("too many detail rows")
    period=payload.get("period","daily")
    label=payload.get("data_date") if period=="daily" else f"{payload.get('period_start','')}~{payload.get('period_end','')}"
    summary=payload.get("summary") or {}
    rows=_meta(payload,name+"产品广告明细")+[list(_DETAIL_COLUMNS)]
    rows.append(["综合情况",label,"非完整口径" if payload.get("final_cpo") is False else "完整口径",
                 *(_type_sum(ps,"adTypeSpend",t) for t in AD_TYPES),
                 *(_type_sum(ps,"adTypeOrders",t) for t in AD_TYPES),
                 summary.get("spend"),summary.get("adOrders"),summary.get("totalOrders"),
                 summary.get("cpo"),summary.get("roas"),summary.get("tacos")])
    for p in ps:
        rows.append([p.get("code"),label,p.get("dataStatus"),
                     *((p.get("adTypeSpend") or {}).get(t) for t in AD_TYPES),
                     *((p.get("adTypeOrders") or {}).get(t) for t in AD_TYPES),
                     p.get("spend"),p.get("adOrders"),p.get("totalOrders"),
                     p.get("cpo"),p.get("roas"),p.get("tacos")])
    return workbook(rows,money_columns=(4,5,6,7,8,14,17),numeric_columns=(9,10,11,12,13,15,16,18,19))
