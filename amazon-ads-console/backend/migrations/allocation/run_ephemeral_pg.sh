#!/usr/bin/env bash
# Ephemeral PostgreSQL contract test. Never connects to remote or existing PG.
set -euo pipefail
export LC_ALL=C LANG=C
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TMP="$(mktemp -d /tmp/cpo-alloc-pg-XXXXXXXX)"
chmod 700 "$TMP"
mkdir -p "$TMP/socket"
cleanup() {
  if [ -f "$TMP/db/postmaster.pid" ]; then pg_ctl -D "$TMP/db" -m immediate stop >/dev/null 2>&1 || true; fi
  rm -rf "$TMP"
}
trap cleanup EXIT
initdb -D "$TMP/db" --auth-local=trust --auth-host=reject --no-instructions >"$TMP/init.log" 2>&1 || {
  cat "$TMP/init.log"; exit 1;
}
if ! pg_ctl -D "$TMP/db" -l "$TMP/server.log" -o "-k $TMP/socket -p 55489 -h ''" -w start >"$TMP/start.log" 2>&1; then
  cat "$TMP/start.log"; tail -50 "$TMP/server.log"; exit 1;
fi
export PGHOST="$TMP/socket" PGPORT=55489 PGUSER="$(id -un)" PGDATABASE=postgres
for file in 001_schema.sql 002_guardrails.sql test_ephemeral_pg.sql; do
  if ! psql -X -v ON_ERROR_STOP=1 -f "$ROOT/backend/migrations/allocation/$file" >"$TMP/$file.log" 2>&1; then
    echo "Migration/acceptance failed: $file" >&2
    tail -70 "$TMP/$file.log" >&2
    exit 1
  fi
done
tail -24 "$TMP/test_ephemeral_pg.sql.log"
echo "EPHEMERAL_ALLOCATION_PG_TESTS_PASSED (server stopped and files removed at exit)"
