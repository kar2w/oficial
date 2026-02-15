#!/usr/bin/env bash
set -euo pipefail

MODE="${DB_MODE:-server}"
DATABASE_URL="${DATABASE_URL:-}"

if [[ -z "$DATABASE_URL" ]]; then
  echo "Missing DATABASE_URL"
  exit 1
fi

if [[ "$MODE" == "server" ]]; then
  SCHEMA_FILE="db/schema.sql"
  : "${PGHOST:=localhost}"
  : "${PGPORT:=5432}"
  : "${PGUSER:=postgres}"
  : "${PGDATABASE:=motoboys}"
  if [[ -n "${PGPASSWORD:-}" ]]; then
    export PGPASSWORD
  fi
  psql "host=$PGHOST port=$PGPORT user=$PGUSER dbname=$PGDATABASE" -f "$SCHEMA_FILE"
  echo "Schema server aplicado: $SCHEMA_FILE"
elif [[ "$MODE" == "desktop" ]]; then
  SCHEMA_FILE="db/schema_sqlite.sql"
  DB_PATH="${SQLITE_PATH:-}"
  if [[ -z "$DB_PATH" ]]; then
    DB_PATH="${DATABASE_URL#sqlite:///}"
  fi
  sqlite3 "$DB_PATH" < "$SCHEMA_FILE"
  echo "Schema desktop aplicado: $SCHEMA_FILE em $DB_PATH"
else
  echo "Invalid DB_MODE: $MODE (use server|desktop)"
  exit 1
fi
