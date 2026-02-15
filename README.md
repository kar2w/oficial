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
