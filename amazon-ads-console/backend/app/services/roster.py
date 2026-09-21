"""Five-field product mapping service for the console."""
from __future__ import annotations

from typing import Any
from .app_db import query_rows

SOURCE_TABLE = "app.product_mapping"


def product_mappings() -> dict[str, Any]:
    rows = query_rows(f"""
        SELECT brand, product_code, parent_asin, operator_group, status
        FROM {SOURCE_TABLE}
        ORDER BY operator_group, product_code, parent_asin
    """)

    out_rows = [
        {
            "brand": r["brand"],
            "productCode": r["product_code"],
            "parentAsin": r["parent_asin"],
            "operatorGroup": r["operator_group"],
            "status": r["status"],
        }
        for r in rows
    ]

    def counter(field: str) -> list[dict[str, Any]]:
        counts: dict[str, int] = {}
        for row in out_rows:
            value = row[field] or "（空）"
            counts[value] = counts.get(value, 0) + 1
        return [
            {"name": name, "count": count}
            for name, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    return {
        "data_source": SOURCE_TABLE,
        "rows": out_rows,
        "summary": {
            "total": len(out_rows),
            "confirmed": sum(1 for r in out_rows if r["status"] == "confirmed"),
            "missingBusiness": sum(1 for r in out_rows if r["status"] == "confirmed_no_business"),
            "brands": len({r["brand"] for r in out_rows}),
            "operatorGroups": len({r["operatorGroup"] for r in out_rows}),
            "byBrand": counter("brand"),
            "byOperatorGroup": counter("operatorGroup"),
            "byStatus": counter("status"),
        },
        "filters": {
            "brands": sorted({r["brand"] for r in out_rows}),
            "operatorGroups": sorted({r["operatorGroup"] for r in out_rows}),
            "statuses": sorted({r["status"] for r in out_rows}),
        },
        "note": (
            "正式产品映射仅保留品牌、产品号、父ASIN、运营组、状态五个字段。"
            "confirmed_no_business 表示产品身份已确认，但当前数据库缺少对应业务报告，因此不能生成完整 CPO。"
        ),
    }


def not_supported(op: str) -> dict[str, Any]:
    return {
        "status": "GONE",
        "code": "PRODUCT_MAPPING_READONLY",
        "message": f"{op} 已停用：正式产品映射由开发端核验后只读展示。",
        "hint": "如需变更映射，请先核验产品身份与当前父 ASIN，再更新 app.product_mapping。",
    }
