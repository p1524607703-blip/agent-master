#!/usr/bin/env bash
# Only isolated UNIX socket temporary PostgreSQL. No existing database or credentials.
set -euo pipefail
export LC_ALL=C LANG=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TMP="$(mktemp -d /tmp/cpo-pg-driver-XXXXXXXX)"
chmod 700 "$TMP"
mkdir "$TMP/socket"
cleanup() {
  if [ -f "$TMP/db/postmaster.pid" ]; then pg_ctl -D "$TMP/db" -m immediate stop >/dev/null 2>&1 || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT
initdb -D "$TMP/db" --auth-local=trust --auth-host=reject --no-instructions >"$TMP/init.log" 2>&1 || { cat "$TMP/init.log"; exit 1; }
pg_ctl -D "$TMP/db" -l "$TMP/pg.log" -o "-k $TMP/socket -p 55491 -h ''" -w start >"$TMP/start.log" 2>&1 || { cat "$TMP/start.log"; tail -60 "$TMP/pg.log"; exit 1; }
export PGHOST="$TMP/socket" PGPORT=55491 PGUSER="$(id -un)" PGDATABASE=postgres
for n in 001_schema.sql 002_guardrails.sql; do
  psql -X -v ON_ERROR_STOP=1 -f "$ROOT/backend/migrations/allocation/$n" >"$TMP/$n.log" 2>&1 || { tail -80 "$TMP/$n.log"; exit 1; }
done
export CPO_TEST_PG_SOCKET="$TMP/socket" CPO_TEST_PG_PORT=55491 CPO_TEST_PG_USER="$PGUSER"
cd "$ROOT/backend"
./.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_allocation_pg_driver_integration.py
echo 'ISOLATED_ASYNCPG_ADAPTER_VERIFIED'
