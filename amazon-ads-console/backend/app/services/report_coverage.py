"""Persisted exact report coverage. HTTP readers never aggregate fact tables.

Only the separately scheduled maintenance process aggregates source facts.
Import batch IDs are freshness markers, never substitutes for fact row counts.
"""
from __future__ import annotations

from .rds_query import query_one, query_rows
from .report_coverage_sql import REPORT_SPECS, SNAPSHOT_TABLE, SNAPSHOT_VERSION, TABLES


def _unknown(label: str, table: str, status: str = "PENDING") -> dict:
    return {"account": "全部账户", "account_id": None, "type": label, "table": table,
            "min_date": None, "date": None, "rows": None, "lineage": "尚未统计",
            "status": status, "source": "rds", "snapshot_at": None,
            "snapshot_revision": None, "source_revision": None,
            "refresh_state": "PENDING", "refresh_started_at": None,
            "refresh_finished_at": None, "error_code": None}


def coverage_catalog() -> list[dict]:
    """Read only a tiny materialized catalog and the import ledger.

    Missing migration/snapshot is an explicit pending state. A database failure
    propagates so clients cannot mistake an unavailable catalog for empty facts.
    """
    exists = query_one(f"SELECT to_regclass('{SNAPSHOT_TABLE}')::text AS relation") or {}
    if not exists.get("relation"):
        return [_unknown(label, table) for label, table, _ in REPORT_SPECS]
    tables = ",".join("'" + table + "'" for table in TABLES)
    snapshots = query_rows(f"""
        WITH revisions AS (
            SELECT target_table, max(batch_id)::bigint AS source_revision
            FROM core.import_batches
            WHERE target_table IN ({tables}) AND import_status='success'
            GROUP BY target_table
        )
        SELECT s.*, COALESCE(r.source_revision,0)::bigint AS source_revision,
               (s.refresh_state='REFRESHING' AND
                s.refresh_started_at < clock_timestamp()-interval '15 minutes') AS interrupted
        FROM {SNAPSHOT_TABLE} s
        LEFT JOIN revisions r ON r.target_table=s.table_name
    """)
    by_table = {row["table_name"]: row for row in snapshots}
    result = []
    for label, table, _ in REPORT_SPECS:
        snapshot = by_table.get(table)
        if not snapshot:
            result.append(_unknown(label, table))
            continue
        payload = snapshot.get("payload")
        state = snapshot.get("refresh_state", "PENDING")
        if snapshot.get("interrupted"):
            state = "FAILED"
        error_code = "REFRESH_INTERRUPTED" if snapshot.get("interrupted") else snapshot.get("error_code")
        ready = (snapshot.get("snapshot_at") is not None and isinstance(payload, list)
                 and snapshot.get("snapshot_version") == SNAPSHOT_VERSION)
        if not ready:
            item = _unknown(label, table, "FAILED" if state == "FAILED" else "PENDING")
            item.update(refresh_state=state, error_code=error_code,
                        refresh_started_at=snapshot.get("refresh_started_at"),
                        refresh_finished_at=snapshot.get("refresh_finished_at"))
            result.append(item)
            continue
        current = (snapshot.get("source_revision") == snapshot.get("source_revision_at_refresh"))
        status = "READY" if current and state == "READY" else "STALE"
        # A successfully counted empty fact table really has zero rows. This is
        # distinct from a missing snapshot, whose count remains null.
        accounts = payload or [{"account_id": None, "account_name": "全部账户",
                                "min_date": None, "max_date": None, "rows": 0, "lineage_rows": 0}]
        for row in accounts:
            result.append({
                "account": row.get("account_name") or row.get("account_id") or "全部账户",
                "account_id": row.get("account_id"), "type": label, "table": table,
                "min_date": row.get("min_date"), "date": row.get("max_date"),
                "rows": row["rows"], "status": status, "source": "rds",
                "lineage": "完整（source_file_name 已回填）" if row["lineage_rows"] == row["rows"] else "缺失",
                "snapshot_at": snapshot["snapshot_at"],
                "snapshot_revision": snapshot.get("source_revision_at_refresh"),
                "source_revision": snapshot.get("source_revision"),
                "refresh_state": state, "refresh_started_at": snapshot.get("refresh_started_at"),
                "refresh_finished_at": snapshot.get("refresh_finished_at"), "error_code": error_code,
            })
    return result

