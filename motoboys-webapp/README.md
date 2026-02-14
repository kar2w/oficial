# Motoboys WebApp (MVP)

Backend FastAPI + Postgres (Docker).

MVP cobre:
- Semanas (Qui->Qua) com ajuste futuro (DB já bloqueia overlap)
- Import Saipos/Yooga
- Pendências:
  - Atribuição manual (nomes não cadastrados / vazios / não encontrado)
  - Revisão Yooga (colisão de assinatura)
- Regra fixa: `valor_raw == 10.00 -> fee_type=10`, senão `fee_type=6`

## Requisitos
- Docker + Docker Compose
- Python 3.11+

## Rodar (Linux/Codespaces)
```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

docker compose up -d
docker exec -i motoboys-db psql -U postgres -d motoboys < db/schema.sql

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Rodar (Windows PowerShell)
```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

docker compose up -d
docker exec -i motoboys-db psql -U postgres -d motoboys < db/schema.sql

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Swagger
- http://localhost:8000/docs

## Endpoints principais
- GET /health
- GET /weeks
- GET /weeks/current
- POST /imports  (multipart: source=SAIPOS|YOOGA, file)
- GET /pendings/assignment
- POST /pendings/assignment/{ride_id}/assign
- GET /pendings/yooga
- GET /pendings/yooga/{group_id}
- POST /pendings/yooga/{group_id}/resolve
- POST /seed/weekly-couriers
