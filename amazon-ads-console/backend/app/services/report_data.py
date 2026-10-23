"""Read the persisted report catalog; fact aggregation runs in maintenance."""
from .report_coverage import coverage_catalog


def reports():
    return coverage_catalog()
