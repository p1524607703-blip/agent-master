"""No-RDS unit and API contract checks for operator CPO Excel/ZIP exports."""
import io
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.auth import require_session
from app.api.operator_exports import router
from app.services.operator_export_workbooks import detail_xlsx, summary_xlsx


def app_as(role="management", code=None):
    app=FastAPI()
    app.include_router(router,prefix="/api")
    app.dependency_overrides[require_session]=lambda:("mock",{"roleCode":role,"operatorCode":code})
    return TestClient(app)


SUMMARY={"data_date":"2026-10-17","period":"daily","final_cpo":False,
         "operators":[
             {"name":"子娟","spend":500,"adOrders":6,"totalOrders":8,"cpo":None,"dataProducts":1,"products":2,"status":"广告来源不完整"},
             {"name":"雪敏","spend":200,"adOrders":3,"totalOrders":5,"cpo":40,"dataProducts":1,"products":1,"status":"已配对"}],
         "apiKey":"PRIVATE_TOKEN_NOT_FOR_EXPORT"}
DETAIL={"operator":"子娟","period":"daily","data_date":"2026-10-17","final_cpo":False,
        "summary":{"spend":500,"adOrders":6,"totalOrders":8,"cpo":None,"roas":None,"tacos":None},
        "products":[{"code":"=1+1","dataStatus":"仅广告数据","adTypeSpend":{"SP":400,"SB":100},
                     "adTypeOrders":{"SP":5,"SB":1},"spend":500,"adOrders":6,
                     "totalOrders":8,"cpo":None,"roas":None,"tacos":None}],
        "apiKey":"PRIVATE_TOKEN_NOT_FOR_EXPORT"}


def _xlsx_xml(content):
    with ZipFile(io.BytesIO(content)) as z:
        assert "xl/worksheets/sheet1.xml" in z.namelist()
        sheet=z.read("xl/worksheets/sheet1.xml")
        ET.fromstring(sheet)
        return sheet


def test_actual_excel_zip_structure_and_no_forged_values():
    payload=detail_xlsx(DETAIL)
    sheet=_xlsx_xml(payload)
    assert b"<f>" not in sheet  # strings are inlineStr, never executable formulas
    assert b"PRIVATE_TOKEN_NOT_FOR_EXPORT" not in sheet
    assert b"400" in sheet and b"500" in sheet
    assert b"=1+1" in sheet
    assert b'<c r="R5"' in sheet or b'<c r="S5"' in sheet
    assert b"<v>0</v>" not in sheet  # missing CPO/ROAS should be blank, not zero
    _xlsx_xml(summary_xlsx(SUMMARY))


def test_operator_can_export_only_own_detail():
    with patch("app.api.operator_exports.cached_detail", return_value=DETAIL) as cache:
        assert app_as("operator","ZJ1").get("/api/operator-reports/operators/%E5%AD%90%E5%A8%9F.xlsx?date=2026-10-17").status_code==200
        cache.reset_mock()
        response=app_as("operator","ZJ1").get("/api/operator-reports/operators/%E9%9B%AA%E6%95%8F.xlsx?date=2026-10-17")
        assert response.status_code==403
        cache.assert_not_called()
        assert app_as("operator","NONE").get("/api/operator-reports/operators/%E5%AD%90%E5%A8%9F.xlsx?date=2026-10-17").status_code==403


def test_team_summary_and_archive_are_management_only():
    with patch("app.api.operator_exports.cached_summary",return_value=SUMMARY), \
         patch("app.api.operator_exports.cached_detail",return_value=DETAIL):
        operator=app_as("operator","ZJ1")
        resp=operator.get("/api/operator-reports/summary.xlsx?period=daily&date=2026-10-17")
        assert resp.status_code==403
        assert operator.get("/api/operator-reports/all.zip?date=2026-10-17").status_code==403
        manager=app_as("management")
        bundle=manager.get("/api/operator-reports/all.zip?period=daily&date=2026-10-17")
        assert bundle.status_code==200
        with ZipFile(io.BytesIO(bundle.content)) as z:
            files=z.namelist()
            assert len(files)==3
            assert files[0].startswith("00_全部运营汇总_")
            assert all(f.endswith(".xlsx") for f in files)
            for f in files:_xlsx_xml(z.read(f))


def test_bad_period_and_date_rejected_before_query():
    with patch("app.api.operator_exports.cached_summary") as cached:
        c=app_as("management")
        assert c.get("/api/operator-reports/summary.xlsx?date=2026-13-99").status_code==422
        assert c.get("/api/operator-reports/summary.xlsx?period=quarterly").status_code==422
        cached.assert_not_called()


def test_manager_downloads_other_operator_data():
    with patch("app.api.operator_exports.cached_detail",return_value=DETAIL):
        assert app_as("super_admin").get("/api/operator-reports/operators/%E9%9B%AA%E6%95%8F.xlsx?date=2026-10-17").status_code==200


def test_bulk_reuses_one_source_build_for_missing_daily_snapshots():
    with patch("app.api.operator_exports.cached_summary",return_value=SUMMARY), \
         patch("app.api.operator_exports.cached_detail",return_value=None), \
         patch("app.api.operator_exports._build",return_value={"sourceDays":{}}) as build, \
         patch("app.api.operator_exports.operator_cpo_detail",return_value=DETAIL) as detail:
        response=app_as("management").get("/api/operator-reports/all.zip?period=daily&date=2026-10-17")
        assert response.status_code==200
        build.assert_called_once()
        assert detail.call_count==2
