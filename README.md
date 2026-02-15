# Motoboys WebApp

Este repositório usa **`motoboys-webapp/app` como diretório canônico da aplicação FastAPI**.

## Entry point único

Execute a API sempre apontando para o módulo canônico:

```bash
uvicorn --app-dir motoboys-webapp app.main:app --reload --host 0.0.0.0 --port 8000
```

## Setup rápido (raiz do repositório)

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r motoboys-webapp/requirements.txt

docker compose up -d
docker exec -i motoboys-db psql -U postgres -d motoboys < db/schema.sql
```

## Nota de arquitetura

- `motoboys-webapp/app/`: código fonte canônico do backend (APIs, serviços, modelos, schemas).
- `archive/root-app-legacy/app/`: cópia antiga da pasta `app/` da raiz, mantida apenas como histórico de migração para reduzir drift.
- `db/` e `docker-compose.yml` na raiz: infraestrutura local de banco para desenvolvimento.

A partir desta mudança, alterações de backend devem acontecer exclusivamente em `motoboys-webapp/app`.
