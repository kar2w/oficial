# Motoboys WebApp (MVP)

Backend FastAPI com suporte a modo server (Postgres) e modo desktop (SQLite local por padrão).

> Fonte única de verdade do schema SQL: `../db/schema.sql` (arquivo na raiz do repositório).

MVP cobre:
- Semanas (Qui->Qua) com ajuste futuro (DB já bloqueia overlap)
- Import Saipos/Yooga
- Pendências:
  - Atribuição manual (nomes não cadastrados / vazios / não encontrado)
  - Revisão Yooga (colisão de assinatura)
- Regra fixa: `valor_raw == 10.00 -> fee_type=10`, senão `fee_type=6`

## Requisitos
- Python 3.11+
- Docker + Docker Compose (apenas para modo `server`)

## Modos da aplicação (`APP_MODE`)
- `server` (padrão): usa `DATABASE_URL` (tipicamente `postgresql+psycopg://...`) e fluxo com Docker/Postgres.
- `desktop`: permite execução local sem Docker.
  - **Estratégia adotada (opção A): SQLite local** via `sqlite+pysqlite:///...`.
  - Fallback automático quando `DATABASE_URL` não for definido: arquivo `motoboys.db` no diretório de dados do usuário.
    - Windows: `%APPDATA%/Motoboys/motoboys.db`
    - Linux/macOS: `~/.local/share/Motoboys/motoboys.db`
  - Opcional: sobrescreva o diretório com `APP_DATA_DIR=/caminho/para/dados`.

### Opções de banco para desktop
- **Opção A (implementada): SQLite local**, simples para empacotar e rodar offline.
- **Opção B (alternativa): Postgres embarcado no instalador**, mantém máxima paridade com produção, porém aumenta complexidade de instalação/distribuição.


### CORS_ORIGINS (credenciais/cookies)
- O backend usa `allow_credentials=True` **somente** quando `CORS_ORIGINS` estiver configurado com uma lista explícita de origens confiáveis.
- Se `CORS_ORIGINS` estiver vazio/não definido, o app inicia com CORS sem credenciais (`allow_credentials=False`).
- Não use `*` quando precisar de autenticação por cookie/header com credenciais.

Exemplos:
```env
# Desenvolvimento (frontend local)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Produção (somente domínios confiáveis)
CORS_ORIGINS=https://app.seudominio.com,https://admin.seudominio.com
```


## Rodar em modo desktop (sem Docker)
```bash
cd motoboys-webapp
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# habilita modo desktop
echo "APP_MODE=desktop" >> .env

uvicorn --app-dir . app.main:app --reload --host 0.0.0.0 --port 8000
```

### Desktop no Windows PowerShell
```powershell
cd motoboys-webapp
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r .\requirements.txt

Add-Content .env "APP_MODE=desktop"

uvicorn --app-dir . app.main:app --reload --host 0.0.0.0 --port 8000
```

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

## Modo de banco (server x desktop)
- `DB_MODE=server` (padrão): usa Postgres e `db/schema.sql`.
- `DB_MODE=desktop`: usa SQLite e `db/schema_sqlite.sql`.

Bootstrap por modo:
```bash
DB_MODE=server DATABASE_URL=postgresql+psycopg://... ./scripts/bootstrap_db_by_mode.sh
DB_MODE=desktop DATABASE_URL=sqlite:///./motoboys.db ./scripts/bootstrap_db_by_mode.sh
```

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
