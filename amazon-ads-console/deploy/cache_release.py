"""Operate only derived CPO Redis snapshots while the application is stopped.

No sessions, business records, distributed locks, or PostgreSQL data are deleted.
The selected release's environment and query implementation are used for warming.
"""
import argparse
import json
import os
import sys
from pathlib import Path


def load_release(release):
    backend = release / 'amazon-ads-console/backend'
    sys.path.insert(0, str(backend))
    from dotenv import load_dotenv
    load_dotenv(os.getenv('CPO_ENV_FILE', str(backend / '.env')), override=False)
    import run_rds  # Configures both PostgreSQL channels without starting a server.
    from app.services.build_cache import build_cache
    return build_cache


def clear_snapshots(client):
    """SCAN in bounded batches, retaining every live or abandoned lock key."""
    client.ping()
    deleted = locks = 0
    for pattern in ('cpo:build:v1:*', 'cpo:complete-days:v1:*'):
        batch = []
        for key in client.scan_iter(match=pattern, count=200):
            raw = key.encode() if isinstance(key, str) else key
            if raw.endswith(b':lock'):
                locks += 1
                continue
            batch.append(key)
            if len(batch) >= 200:
                deleted += int(client.delete(*batch))
                batch.clear()
        if batch:
            deleted += int(client.delete(*batch))
    return {'deleted_snapshots': deleted, 'preserved_locks': locks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release', type=Path)
    parser.add_argument('action', choices=('clear', 'prewarm'))
    args = parser.parse_args()
    try:
        cache = load_release(args.release)
        client = cache._get_client()
        if client is None:
            print(json.dumps({'action': args.action, 'redis_enabled': False}))
            return
        if args.action == 'clear':
            result = clear_snapshots(client)
        else:
            client.ping()
            from app.services.operator_cpo import operator_cpo_summary
            warmed = []
            # Same public read model as startup/UI. No imports, seeds or mutations.
            for period in ('daily', 'monthly'):
                result = operator_cpo_summary(None, period)
                warmed.append({'period': period, 'date': result.get('date') or result.get('stat_date')})
            result = {'warmed': warmed}
        print(json.dumps({'action': args.action, 'healthy': True, **result}))
    except Exception as error:
        # Exceptions from Redis/DSNs can contain credentials. Emit only the class.
        print(json.dumps({'action': args.action, 'healthy': False,
                          'error_class': type(error).__name__}), file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
