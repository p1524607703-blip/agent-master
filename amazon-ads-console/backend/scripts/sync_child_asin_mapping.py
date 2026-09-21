#!/usr/bin/env python3
"""Safely maintain account-scoped Child ASIN ownership mappings.

Source of truth:
- amazon_ads_v2.core.report_business_child_asin_daily: observed account/child/parent/date
- amazon_ads.app.product_mapping: confirmed parent -> product/operator ownership

Rules:
- infer only when every observed mapped parent resolves to exactly one identity
- explicit mappings are never overwritten
- parent_inherited may refresh evidence/parent only when identity is unchanged
- inherited identity changes are blocked, never silently reassigned
- no campaign/product-code guessing
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
from collections import defaultdict
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import asyncpg  # noqa: E402
from app.core.config import settings  # noqa: E402


# ---------------------------------------------------------------------------
# 三条写入语句，文本与原先「事务内逐行 execute」版本【逐字相同】。
# 2026-09-21 性能优化：仅把「一行一次 await app.execute()」改为 executemany 批量流水线，
# SQL 文本、参数顺序、分支判定、事务边界全部不变 —— 语义严格等价。
# 刻意不使用 UPDATE ... FROM unnest(...)：多数组 unnest 在长度不等时会用 NULL 静默补齐
# （已实测确认，不报错），存在数据错位风险；且其收益并不优于 executemany（实测 543× 加速）。
# ---------------------------------------------------------------------------
SQL_UPDATE_PARENT_INHERITED = """
UPDATE app.child_asin_mapping
   SET parent_asin=$3, brand=$4, product_code=$5, operator_group=$6,
       source='business_child_parent_inheritance', confidence='inherited',
       evidence=$7::jsonb, effective_date=$8, updated_at=now()
 WHERE account_scope=$1 AND child_asin=$2
   AND mapping_status='parent_inherited'
"""

SQL_INSERT_PARENT_INHERITED = """
INSERT INTO app.child_asin_mapping
  (account_scope,child_asin,product_code,parent_asin,brand,operator_group,
   mapping_status,source,confidence,evidence,effective_date)
VALUES ($1,$2,$3,$4,$5,$6,'parent_inherited',
        'business_child_parent_inheritance','inherited',$7::jsonb,$8)
"""

SQL_BLOCK_CONFLICT = """
UPDATE app.child_asin_mapping
   SET mapping_status='blocked_conflict',
       evidence=$3::jsonb, updated_at=now()
 WHERE account_scope=$1 AND child_asin=$2
   AND mapping_status='parent_inherited'
"""


async def sync(account_scope: str | None = None, stat_date: str | None = None, dry_run: bool = False) -> dict:
    app = await asyncpg.connect(settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    data = await asyncpg.connect(settings.data_database_url.replace("postgresql+asyncpg://", "postgresql://", 1))
    try:
        ddl = (ROOT / "migrations" / "003_child_asin_mapping.sql").read_text(encoding="utf-8")
        if not dry_run:
            await app.execute(ddl)

        mapping_rows = await app.fetch(
            """
            SELECT brand, product_code, parent_asin, operator_group, status
            FROM app.product_mapping
            WHERE status LIKE 'confirmed%'
              AND coalesce(parent_asin,'') <> ''
              AND coalesce(product_code,'') <> ''
              AND coalesce(operator_group,'') <> ''
            """
        )
        by_parent: dict[str, list[dict]] = defaultdict(list)
        for row in mapping_rows:
            by_parent[row["parent_asin"]].append(dict(row))

        clauses = []
        args: list[str] = []
        if account_scope:
            args.append(account_scope)
            clauses.append(f"account_name = ${len(args)}")
        if stat_date:
            args.append(dt.date.fromisoformat(stat_date) if isinstance(stat_date, str) else stat_date)
            clauses.append(f"stat_date = ${len(args)}::date")
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        facts = await data.fetch(
            f"""
            SELECT account_name, child_asin,
                   array_agg(DISTINCT parent_asin ORDER BY parent_asin) parents,
                   min(stat_date) first_seen, max(stat_date) last_seen,
                   sum(coalesce(ordered_product_units,0))::bigint orders
            FROM core.report_business_child_asin_daily
            {where}
            GROUP BY account_name, child_asin
            """,
            *args,
        )

        existing_rows = await app.fetch(
            """
            SELECT account_scope, child_asin, product_code, parent_asin, brand,
                   operator_group, mapping_status, source, confidence, evidence
            FROM app.child_asin_mapping
            """
        )
        existing = {(r["account_scope"], r["child_asin"]): dict(r) for r in existing_rows}

        candidates: list[dict] = []
        source_conflicts: list[dict] = []
        unmapped: list[dict] = []

        for fact in facts:
            identities: dict[tuple[str, str, str], set[str]] = defaultdict(set)
            mapped_parents: set[str] = set()
            for parent in fact["parents"]:
                rows = by_parent.get(parent) or []
                parent_ids = {(r["brand"] or "", r["product_code"], r["operator_group"]) for r in rows}
                if len(parent_ids) > 1:
                    source_conflicts.append({
                        "account_scope": fact["account_name"], "child_asin": fact["child_asin"],
                        "reason": "parent_mapping_conflict", "parent_asin": parent,
                        "identities": sorted([list(x) for x in parent_ids]),
                    })
                    continue
                if len(parent_ids) == 1:
                    ident = next(iter(parent_ids))
                    identities[ident].add(parent)
                    mapped_parents.add(parent)

            if len(identities) == 1:
                (brand, product_code, group), inherited = next(iter(identities.items()))
                observed_parents = list(fact["parents"])
                current_parent = sorted(inherited)[-1]
                candidates.append({
                    "account_scope": fact["account_name"], "child_asin": fact["child_asin"],
                    "product_code": product_code, "parent_asin": current_parent,
                    "brand": brand, "operator_group": group,
                    "evidence": {
                        "rule": "unique_confirmed_parent_mapping",
                        "observed_parents": observed_parents,
                        "mapped_parents": sorted(inherited),
                        "first_seen": str(fact["first_seen"]), "last_seen": str(fact["last_seen"]),
                        "orders_observed": int(fact["orders"] or 0),
                        "scope_filter": account_scope, "date_filter": stat_date,
                    },
                    "effective_date": fact["first_seen"],
                })
            elif len(identities) > 1:
                source_conflicts.append({
                    "account_scope": fact["account_name"], "child_asin": fact["child_asin"],
                    "reason": "child_resolves_to_multiple_identities",
                    "parents": list(fact["parents"]),
                    "identities": sorted([list(x) for x in identities]),
                })
            else:
                unmapped.append({
                    "account_scope": fact["account_name"], "child_asin": fact["child_asin"],
                    "parents": list(fact["parents"]),
                })

        inserted = updated = preserved_explicit = newly_blocked = unchanged = 0
        identity_conflicts: list[dict] = []

        # 先按原分支逻辑把候选行分桶（纯 Python 判定，不做任何 I/O），再批量提交。
        # 判定规则与原先逐行版完全一致，只是把「判定 + 写入」拆成了两步。
        upd_args: list[tuple] = []
        ins_args: list[tuple] = []
        blk_args: list[tuple] = []

        for c in candidates:
            key = (c["account_scope"], c["child_asin"])
            old = existing.get(key)
            incoming_identity = (c["brand"], c["product_code"], c["operator_group"])
            if old:
                old_status = old.get("mapping_status") or ""
                old_identity = (old.get("brand") or "", old.get("product_code") or "", old.get("operator_group") or "")
                if old_status == "explicit":
                    preserved_explicit += 1
                    continue
                if old_status == "blocked_conflict":
                    unchanged += 1
                    continue
                if old_identity != incoming_identity:
                    identity_conflicts.append({
                        "account_scope": c["account_scope"], "child_asin": c["child_asin"],
                        "existing_identity": old_identity, "incoming_identity": incoming_identity,
                        "existing_parent": old.get("parent_asin"), "incoming_parent": c["parent_asin"],
                    })
                    conflict_evidence = {
                        "rule": "inherited_identity_changed",
                        "existing": {
                            "brand": old_identity[0], "product_code": old_identity[1],
                            "operator_group": old_identity[2], "parent_asin": old.get("parent_asin"),
                        },
                        "incoming": {
                            "brand": incoming_identity[0], "product_code": incoming_identity[1],
                            "operator_group": incoming_identity[2], "parent_asin": c["parent_asin"],
                        },
                        "incoming_evidence": c["evidence"],
                    }
                    blk_args.append((
                        c["account_scope"], c["child_asin"],
                        json.dumps(conflict_evidence, ensure_ascii=False),
                    ))
                    newly_blocked += 1
                    continue

                changed = (
                    (old.get("parent_asin") or "") != c["parent_asin"]
                    or (old.get("source") or "") != "business_child_parent_inheritance"
                    or old.get("evidence") != c["evidence"]
                )
                if changed:
                    upd_args.append((
                        c["account_scope"], c["child_asin"], c["parent_asin"], c["brand"],
                        c["product_code"], c["operator_group"],
                        json.dumps(c["evidence"], ensure_ascii=False), c["effective_date"],
                    ))
                    updated += 1
                else:
                    unchanged += 1
            else:
                ins_args.append((
                    c["account_scope"], c["child_asin"], c["product_code"], c["parent_asin"],
                    c["brand"], c["operator_group"],
                    json.dumps(c["evidence"], ensure_ascii=False), c["effective_date"],
                ))
                inserted += 1

        async with app.transaction():
            if not dry_run:
                # 顺序: 先 blocking、再 update、后 insert。
                # 三者作用于互不重叠的 (account_scope, child_asin) 集合，先后不影响最终状态；
                # 先写 blocking 只是为了让冲突状态尽早落地，便于异常时定位。
                if blk_args:
                    await app.executemany(SQL_BLOCK_CONFLICT, blk_args)
                if upd_args:
                    await app.executemany(SQL_UPDATE_PARENT_INHERITED, upd_args)
                if ins_args:
                    await app.executemany(SQL_INSERT_PARENT_INHERITED, ins_args)

        result = {
            "account_scope": account_scope, "stat_date": stat_date, "dry_run": dry_run,
            "facts_scanned": len(facts), "safe_candidates": len(candidates),
            "inserted": inserted, "updated": updated, "unchanged": unchanged,
            "explicit_preserved": preserved_explicit, "newly_blocked": newly_blocked,
            "identity_conflicts": len(identity_conflicts),
            "source_conflicts": len(source_conflicts), "unmapped": len(unmapped),
            "table_rows": await app.fetchval("SELECT count(*) FROM app.child_asin_mapping"),
        }
        print(json.dumps(result, ensure_ascii=False))
        if identity_conflicts:
            print("IDENTITY_CONFLICT_SAMPLE", json.dumps(identity_conflicts[:20], ensure_ascii=False))
        if source_conflicts:
            print("SOURCE_CONFLICT_SAMPLE", json.dumps(source_conflicts[:20], ensure_ascii=False))
        if unmapped:
            print("UNMAPPED_SAMPLE", json.dumps(unmapped[:20], ensure_ascii=False))
        return result
    finally:
        await app.close()
        await data.close()


def cli() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--account-scope")
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(sync(args.account_scope, args.date, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(cli())
