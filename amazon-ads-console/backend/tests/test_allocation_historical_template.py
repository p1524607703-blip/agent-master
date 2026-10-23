import hashlib
import zipfile
import pytest
from app.services.allocation_historical_template import (
  file_sha256,inspect_historical_xlsx,HistoricalTemplateError)

WORKBOOK="""<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
 <sheets><sheet name="广告费用核对" sheetId="1" r:id="rId1"/></sheets></workbook>"""
RELS="""<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
 <Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="x"/></Relationships>"""
SHEET="""<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
 <dimension ref="A1:B2"/><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>款号</t></is></c></row>
 <row r="2"><c r="A2"><v>3</v></c><c r="B2"><f>A2*2</f><v>6</v></c></row></sheetData></worksheet>"""


def sample(tmp_path):
    p=tmp_path/"reference.xlsx"
    with zipfile.ZipFile(p,"w",compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/workbook.xml",WORKBOOK)
        z.writestr("xl/_rels/workbook.xml.rels",RELS)
        z.writestr("xl/worksheets/sheet1.xml",SHEET)
    return p


def test_file_hash_and_oooxml_contract_without_approval(tmp_path):
    p=sample(tmp_path)
    r=inspect_historical_xlsx(p,file_sha256(p),expected_sheets=1)
    assert r["sheet_count"]==1 and r["sheets"][0]["formula_cells"]==1
    assert r["sheets"][0]["first_two_rows"][0]["cells"]["A1"]=="款号"
    assert r["file_identity_verified"] and not r["formula_semantics_approved"]
    assert not r["may_publish"]


def test_wrong_original_sha_blocks(tmp_path):
    p=sample(tmp_path)
    with pytest.raises(HistoricalTemplateError,match="SHA256"):
        inspect_historical_xlsx(p,"0"*64,expected_sheets=1)


def test_wrong_sheet_count_blocks(tmp_path):
    p=sample(tmp_path)
    with pytest.raises(HistoricalTemplateError,match="SHEET_COUNT"):
        inspect_historical_xlsx(p,file_sha256(p),expected_sheets=11)
