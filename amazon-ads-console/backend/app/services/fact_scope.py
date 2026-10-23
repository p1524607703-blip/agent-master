"""Canonical fact consumption scope.

Raw fact tables retain every lineage row. Formal CPO/dashboard/conservation
queries must join core.import_batches and consume only clean successful batches.
"""

CLEAN_BATCH_FILTER_SQL = (
    "ib.import_status = 'success' "
    "AND COALESCE(ib.metadata->>'excluded_from_cpo','false') <> 'true' "
    "AND COALESCE(ib.metadata->>'quarantined','false') <> 'true'"
)


def clean_batch_join(fact_alias: str = "r", batch_alias: str = "ib") -> str:
    """SQL JOIN fragment for formal fact consumption."""
    return (
        f"JOIN core.import_batches {batch_alias} "
        f"ON {batch_alias}.batch_id={fact_alias}.batch_id "
        f"AND {CLEAN_BATCH_FILTER_SQL.replace('ib.', batch_alias + '.')}"
    )


def clean_fact_source(table: str, alias: str) -> str:
    """Aliased subquery exposing only canonical/clean fact rows."""
    raw_alias = f"{alias}_raw"
    batch_alias = f"{alias}_batch"
    batch_filter = CLEAN_BATCH_FILTER_SQL.replace("ib.", batch_alias + ".")
    return (
        f"(SELECT {raw_alias}.* FROM {table} {raw_alias} "
        f"JOIN core.import_batches {batch_alias} "
        f"ON {batch_alias}.batch_id={raw_alias}.batch_id "
        f"AND {batch_filter}) {alias}"
    )
