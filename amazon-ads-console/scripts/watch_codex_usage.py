#!/usr/bin/env python3
"""Private SSH notification stream. No account credentials, prompts or device keys."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
import run_rds
from app.services.auth import _connect


async def watch():
    conn = await _connect()
    changed = asyncio.Event()
    def listener(*_):
        changed.set()
    def emit(event):
        print(json.dumps({'event':event}), flush=True)
    try:
        await conn.add_listener('codex_usage_changed', listener)
        emit('ready')
        while not conn.is_closed():
            try:
                await asyncio.wait_for(changed.wait(), 20)
                changed.clear()
                emit('usage-changed')
            except asyncio.TimeoutError:
                # A bounded, read-only probe detects a lost DB connection.
                await asyncio.wait_for(conn.fetchval('SELECT 1'), 5)
                emit('alive')
    finally:
        await conn.close()


if __name__ == '__main__':
    try:
        asyncio.run(watch())
    except Exception:
        sys.exit(1)  # Never print database connection strings or upstream errors.
