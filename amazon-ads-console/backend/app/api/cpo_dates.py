"""Shared CPO report-date contract, checked before reading any report cache."""
import re
from datetime import date, timedelta
from typing import Optional

from fastapi import HTTPException


_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")


def validate_cpo_report_date(value: Optional[str], period: str = "daily") -> Optional[str]:
    """Omitted means latest; supplied dates must be real, full calendar dates."""
    if value is None:
        return None
    try:
        if not _DATE.fullmatch(value):
            raise ValueError
        parsed = date.fromisoformat(value)
        # The report service materializes full calendar windows; reject dates
        # whose week/month arithmetic would overflow before invoking that service.
        if period == "weekly":
            parsed - timedelta(days=parsed.weekday()) + timedelta(days=6)
        elif period == "monthly":
            parsed.replace(day=1) + timedelta(days=32)
    except (TypeError, ValueError, OverflowError):
        raise HTTPException(422, "报表日期必须是当前报表范围支持的有效 YYYY-MM-DD 日期；月报请选择该月的完整日期。") from None
    return value
