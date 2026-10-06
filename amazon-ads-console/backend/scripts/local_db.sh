#!/usr/bin/env bash
set -euo pipefail

# Keep the project-local PostgreSQL deterministic on macOS and avoid invalid inherited locale aliases.
export LC_ALL=C
export LANG=C

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_DIR="$BACKEND_DIR/.local"
PGDATA="$LOCAL_DIR/postgres"
LOG_FILE="$LOCAL_DIR/postgres.log"
PORT=55432
HOST=127.0.0.1
DB_NAME=adsight_local
APP_USER=adsight_dev
BOOTSTRAP_USER="${USER:-$(id -un)}"
DATABASE_URL="postgresql+asyncpg://$APP_USER@$HOST:$PORT/$DB_NAME"

mkdir -p "$LOCAL_DIR"

init_cluster() {
  if [[ ! -f "$PGDATA/PG_VERSION" ]]; then
    echo "Initializing isolated PostgreSQL cluster at $PGDATA"
    initdb -D "$PGDATA" --auth=trust --username="$BOOTSTRAP_USER" --locale=C --encoding=UTF8 >/dev/null
  fi
}

start_cluster() {
  init_cluster
  if pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
    echo "Local PostgreSQL already running on project cluster"
  else
    pg_ctl -D "$PGDATA" -l "$LOG_FILE" -o "-p $PORT -h $HOST -k $LOCAL_DIR" start >/dev/null
  fi
  for _ in {1..30}; do
    if pg_isready -h "$HOST" -p "$PORT" >/dev/null 2>&1; then break; fi
    sleep 0.2
  done
  pg_isready -h "$HOST" -p "$PORT" >/dev/null

  if [[ "$(psql -h "$HOST" -p "$PORT" -U "$BOOTSTRAP_USER" -d postgres -Atqc "SELECT 1 FROM pg_roles WHERE rolname='$APP_USER'")" != "1" ]]; then
    createuser -h "$HOST" -p "$PORT" -U "$BOOTSTRAP_USER" "$APP_USER"
  fi
  if [[ "$(psql -h "$HOST" -p "$PORT" -U "$BOOTSTRAP_USER" -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'")" != "1" ]]; then
    createdb -h "$HOST" -p "$PORT" -U "$BOOTSTRAP_USER" -O "$APP_USER" "$DB_NAME"
  fi
  if [[ ! -f "$BACKEND_DIR/.env" ]]; then
    printf 'DATABASE_URL=%s
' "$DATABASE_URL" > "$BACKEND_DIR/.env"
  fi
  echo "Ready: $HOST:$PORT/$DB_NAME (project-local only)"
}

case "${1:-start}" in
  init|start) start_cluster ;;
  status)
    if [[ -f "$PGDATA/PG_VERSION" ]] && pg_ctl -D "$PGDATA" status; then
      pg_isready -h "$HOST" -p "$PORT"
    else
      echo "Project-local PostgreSQL is not running"
      exit 1
    fi
    ;;
  stop)
    if [[ -f "$PGDATA/PG_VERSION" ]] && pg_ctl -D "$PGDATA" status >/dev/null 2>&1; then
      pg_ctl -D "$PGDATA" stop -m fast >/dev/null
      echo "Stopped project-local PostgreSQL"
    else
      echo "Project-local PostgreSQL already stopped"
    fi
    ;;
  *) echo "Usage: $0 {init|start|status|stop}"; exit 2 ;;
esac
