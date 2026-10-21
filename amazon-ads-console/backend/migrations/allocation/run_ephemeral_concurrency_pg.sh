#!/usr/bin/env bash
# Native asyncpg concurrency/CAS test on socket-only ephemeral PostgreSQL.
set -euo pipefail
export LC_ALL=C LANG=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TMP="$(mktemp -d /tmp/cpo-pg-race-XXXXXXXX)"
chmod 700 "$TMP"
mkdir "$TMP/socket"
cleanup() {
  if [ -f "$TMP/db/postmaster.pid" ]; then pg_ctl -D "$TMP/db" -m immediate stop >/dev/null 2>&1 || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT
initdb -D "$TMP/db" --auth-local=trust --auth-host=reject --no-instructions >"$TMP/init.log" 2>&1 || { cat "$TMP/init.log"; exit 1; }
pg_ctl -D "$TMP/db" -l "$TMP/server.log" -o "-k $TMP/socket -p 55493 -h ''" -w start >"$TMP/start.log" 2>&1 || { cat "$TMP/start.log"; tail -50 "$TMP/server.log"; exit 1; }
export PGHOST="$TMP/socket" PGPORT=55493 PGUSER="$(id -un)" PGDATABASE=postgres
for file in 001_schema.sql 002_guardrails.sql test_ephemeral_pg.sql; do
 psql -X -v ON_ERROR_STOP=1 -f "$ROOT/backend/migrations/allocation/$file" >"$TMP/$file.log" 2>&1 || { tail -75 "$TMP/$file.log"; exit 1; }
done
export CPO_TEST_PG_SOCKET="$TMP/socket" CPO_TEST_PG_PORT=55493 CPO_TEST_PG_USER="$PGUSER"
cd "$ROOT/backend"
./.venv/bin/python -m pytest -q -p no:cacheprovider tests/test_allocation_pg_concurrency.py
echo EPHEMERAL_POSTGRES_CONCURRENCY_CAS_PASSED
