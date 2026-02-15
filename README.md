# Motoboys WebApp

Este repositório usa **`motoboys-webapp/app` como diretório canônico da aplicação FastAPI**.

> UI (HTMX/Jinja) está em **`/ui/*`**.

## P2 — Rodar tudo com 1 comando (piloto)

Requisitos: Docker + Docker Compose.

```bash
cp .env.example .env
docker compose up -d --build
```

Abra:

- UI: `http://localhost:8000/ui/imports/new`
- API docs: `http://localhost:8000/docs`

### Seed (entregadores semanais)

O arquivo padrão já existe em `motoboys-webapp/data/entregadores_semanais.json`.

Para popular o banco (uma vez):

```bash
docker compose exec web python scripts/seed_weekly_from_file.py
```

Smoke test:

```bash
docker compose exec web python scripts/smoke.py
```

> Se você já tinha um volume antigo do Postgres (e o schema não foi aplicado via init script),
> rode `docker compose down -v` e suba novamente.

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

- `motoboys-webapp/app/`: código fonte canônico do backend (APIs, serviços, modelos, schemas e UI).
- `archive/root-app-legacy/app/`: histórico de migração (não editar).
- `db/` e `docker-compose.yml` na raiz: infraestrutura local (Postgres) e, no P2, também o serviço `web`.
