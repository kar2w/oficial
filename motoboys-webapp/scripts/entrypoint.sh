#!/bin/sh
set -eu

: "${APP_ENV:=dev}"
: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"
: "${UVICORN_WORKERS:=2}"

if [ "$APP_ENV" = "dev" ]; then
  exec uvicorn app.main:app --host "$HOST" --port "$PORT" --reload
else
  exec uvicorn app.main:app --host "$HOST" --port "$PORT" --workers "$UVICORN_WORKERS"
fi
