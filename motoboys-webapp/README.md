# Motoboys WebApp (MVP)

Backend FastAPI + Postgres (Docker).

> Fonte única de verdade do schema SQL: `../db/schema.sql` (arquivo na raiz do repositório).

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

## Rodar (Linux/Codespaces) a partir da raiz do repositório (`/workspace/oficial`)
```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r motoboys-webapp/requirements.txt

docker compose up -d

# opcional: reaplicar schema em banco já existente
docker exec -i motoboys-db psql -U postgres -d motoboys < ./db/schema.sql

uvicorn --app-dir motoboys-webapp app.main:app --reload --host 0.0.0.0 --port 8000
```

### Alternativa: rodar iniciando em `motoboys-webapp/`
```bash
cd motoboys-webapp
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# docker-compose e schema ficam na raiz do repositório
cd ..
docker compose up -d
docker exec -i motoboys-db psql -U postgres -d motoboys < ./db/schema.sql

# volte para a pasta da aplicação para comandos locais
cd motoboys-webapp
uvicorn --app-dir . app.main:app --reload --host 0.0.0.0 --port 8000
```

## Rodar (Windows PowerShell) a partir da raiz do repositório (`/workspace/oficial`)
```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r motoboys-webapp/requirements.txt

docker compose up -d

# opcional: reaplicar schema em banco já existente
docker exec -i motoboys-db psql -U postgres -d motoboys < .\db\schema.sql

uvicorn --app-dir motoboys-webapp app.main:app --reload --host 0.0.0.0 --port 8000
```

### Alternativa: rodar iniciando em `motoboys-webapp/`
```powershell
cd motoboys-webapp
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements.txt

# docker-compose e schema ficam na raiz do repositório
cd ..
docker compose up -d
docker exec -i motoboys-db psql -U postgres -d motoboys < .\db\schema.sql

# volte para a pasta da aplicação para comandos locais
cd motoboys-webapp
uvicorn --app-dir . app.main:app --reload --host 0.0.0.0 --port 8000
```

### Bootstrap do banco
- O `docker-compose.yml` monta automaticamente `./db/schema.sql` em `/docker-entrypoint-initdb.d/00-schema.sql`.
- Esse bootstrap automático roda apenas quando o volume do Postgres é criado do zero.
- Para reinicializar totalmente: `docker compose down -v && docker compose up -d`.
## Arquitetura (canônico)
- Código da aplicação: `motoboys-webapp/app`
- Entry point da API: `app.main:app` com `--app-dir motoboys-webapp`

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

## Desktop (Windows)

Foi adicionada a pasta `desktop/` com:
- `launcher.py`: inicia a API local, escolhe porta livre e abre `/ui/login` no navegador.
- `build.ps1`: gera executável com PyInstaller (onefile/windowed) incluindo templates, static e seed JSON.
- `requirements-build.txt`: dependências para build desktop.

### Dados do usuário e logs locais
Por padrão, a execução desktop usa:
- Dados: `%LOCALAPPDATA%\MotoboysWebApp`
- Logs: `%LOCALAPPDATA%\MotoboysWebApp\logs\app.log` e `desktop-launcher.log`

Variáveis configuráveis:
- `USER_DATA_DIR`
- `LOG_DIR`
- `WEEKLY_COURIERS_JSON_PATH`

### Build do executável (.exe)
No PowerShell, a partir de `motoboys-webapp/`:

```powershell
cd desktop
./build.ps1 -Version "1.0.0" -AppName "MotoboysWebApp" -CompanyName "Motoboys" -Description "Motoboys WebApp Desktop" -IconPath "desktop/app.ico"
```

Saída esperada:
- `dist/MotoboysWebApp.exe`

### Atualização do app desktop
1. Feche o app aberto.
2. Substitua o executável antigo pelo novo (`dist/MotoboysWebApp.exe`).
3. Reabra o app.

A pasta de dados/logs em `%LOCALAPPDATA%\MotoboysWebApp` é preservada entre versões.
