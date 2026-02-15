#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

: "${DATABASE_URL:=postgresql+psycopg://postgres:postgres@localhost:5432/motoboys}"
: "${SESSION_SECRET:=ci-session-secret}"
: "${ADMIN_USERNAME:=admin}"
: "${ADMIN_PASSWORD:=admin}"
: "${WEEKLY_COURIERS_JSON_PATH:=motoboys-webapp/data/entregadores_semanais.json}"

export DATABASE_URL SESSION_SECRET ADMIN_USERNAME ADMIN_PASSWORD WEEKLY_COURIERS_JSON_PATH

python -m pip install --upgrade pip
pip install -r motoboys-webapp/requirements.txt
pip install pytest

pytest -q motoboys-webapp/tests
python scripts/smoke_desktop.py --database-url "$DATABASE_URL"
