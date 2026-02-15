# Motoboys WebApp

Este repositório usa **`motoboys-webapp/app` como diretório canônico da aplicação FastAPI**.

> UI (HTMX/Jinja) está em **`/ui/*`**.

## P3 — hardening operacional + segurança mínima

Requisitos: Docker + Docker Compose.

```bash
cp .env.example .env
docker compose up -d --build
```

Abra:

- UI: `http://localhost:8000/ui/login`
- API docs: `http://localhost:8000/docs`

### Login da UI

A UI (`/ui/*`) exige autenticação por sessão. Configure no `.env`:

- `SESSION_SECRET`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`

### Seed (entregadores semanais)

```bash
docker compose exec web python scripts/seed_weekly_from_file.py
```

Smoke test:

```bash
docker compose exec web python scripts/smoke.py
```

Smoke test com validação HTTP (`/healthz`):

```bash
docker compose exec web python scripts/smoke.py --health-url http://localhost:8000/healthz
```

## "Prod" local (sem volume do código + workers)

Ajuste no `.env`: `APP_ENV=prod`, `SESSION_SECRET` forte e `ADMIN_PASSWORD` forte.

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

## Rodar local (sem Docker para o app)

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r motoboys-webapp/requirements.txt

docker compose up -d

uvicorn --app-dir motoboys-webapp app.main:app --reload --host 0.0.0.0 --port 8000
```

## Nota de arquitetura

- `motoboys-webapp/app/`: backend canônico (APIs, serviços, modelos, schemas e UI).
- `archive/root-app-legacy/app/`: histórico de migração (não editar).
- `db/` e `docker-compose*.yml` na raiz: infraestrutura local (Postgres + web).

## CI smoke check (DB + startup + healthz)

O workflow `.github/workflows/smoke.yml` valida automaticamente:

- conexão com Postgres;
- inicialização da API;
- resposta HTTP `200` com `{ "ok": true }` em `/healthz`.

Para rodar localmente um fluxo equivalente:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r motoboys-webapp/requirements.txt

export DATABASE_URL='postgresql+psycopg://postgres:postgres@localhost:5432/motoboys'
export TZ='America/Fortaleza'
export CORS_ORIGINS='*'
export SESSION_SECRET='dev-secret-change-me'
export ADMIN_USERNAME='admin'
export ADMIN_PASSWORD='admin'
export WEEKLY_COURIERS_JSON_PATH='motoboys-webapp/data/entregadores_semanais.json'

docker compose up -d db
psql "$DATABASE_URL" -f db/schema.sql

python -m uvicorn --app-dir motoboys-webapp app.main:app --host 0.0.0.0 --port 8000
# em outro terminal:
python motoboys-webapp/scripts/smoke.py --health-url http://127.0.0.1:8000/healthz
```

Se a conexão com DB ou o healthcheck falhar, o comando `smoke.py` retorna erro e o pipeline falha.
