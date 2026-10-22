#!/usr/bin/env python3
"""Refresh persisted exact report coverage outside HTTP workers.

Standard library + psql only. Run as the dedicated warehouse maintenance owner
over a local socket. Apply the warehouse migration separately. Unchanged
revisions are skipped; failed/interrupted attempts back off for 15 minutes.
This command never changes source facts or prints source values/SQL errors.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.report_coverage_sql import TABLES, maintenance_sql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", default="postgresql:///amazon_ads_v2", help="Dedicated maintenance connection")
    parser.add_argument("--table", action="append", choices=TABLES, help="Refresh one source, repeatable")
    parser.add_argument("--force", action="store_true", help="Bypass unchanged-revision and failure cooldown checks")
    parser.add_argument("--statement-timeout-seconds", type=int, default=300, choices=range(1,601), metavar="1..600")
    parser.add_argument("--max-runtime-seconds", type=int, default=1200, choices=range(30,1201), metavar="30..1200")
    parser.add_argument("--cooldown-seconds", type=int, default=900, choices=range(60,86401), metavar="60..86400")
    args = parser.parse_args()
    sql = maintenance_sql(args.table or TABLES, force=args.force,
                          statement_timeout_ms=args.statement_timeout_seconds*1000,
                          cooldown_seconds=args.cooldown_seconds)
    try:
        process = subprocess.run(
            ["psql","--dbname",args.dsn,"-X","-q","-t","-A","-v","ON_ERROR_STOP=1"],
            input=sql,capture_output=True,text=True,timeout=args.max_runtime_seconds,
        )
        if process.returncode:
            raise RuntimeError("Maintenance failed")
        result = json.loads(process.stdout.strip())
    except subprocess.TimeoutExpired:
        # PostgreSQL also bounds each statement and checks client disconnects.
        # A committed REFRESHING marker becomes visibly interrupted after 15m.
        result = {"status":"FAILED","code":"COVERAGE_MAINTENANCE_TIMEOUT"}
    except Exception:
        result = {"status":"FAILED","code":"COVERAGE_MAINTENANCE_UNAVAILABLE"}
    print(json.dumps(result))
    return 1 if result["status"] == "FAILED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
