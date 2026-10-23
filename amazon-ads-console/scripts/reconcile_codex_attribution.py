#!/usr/bin/env python3
"""Run after sanitized quota/host upload; no model requests or credential changes."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
import run_rds  # Configure the existing application database channel.
from app.services.codex_auto_attribution import reconcile

if __name__ == '__main__':
    try:
        print(json.dumps(asyncio.run(reconcile())))
    except Exception:
        # No connection strings, upstream errors or credentials in collector logs.
        print(json.dumps({'status':'paused', 'reason':'attribution-reconciliation-unavailable'}))
        sys.exit(1)
