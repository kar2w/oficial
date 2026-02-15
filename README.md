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
- UI: http://localhost:8000/ui/imports/new
- API docs: http://localhost:8000/docs

## P4 — Caixa + Auditoria + Export PIX

Perfis:
- ADMIN: acesso total.
- CASHIER (caixa): acesso limitado (sem telas administrativas).

Variáveis adicionais no `.env`:
- `CASHIER_USERNAME`
- `CASHIER_PASSWORD`

Auditoria:
- Tela: http://localhost:8000/ui/audit (somente ADMIN).

Export PIX (CSV):
- Endpoint: `GET /weeks/{week_id}/payouts_pix.csv`.
- Também disponível na tela da semana.

## P5 — Hardening leve (paginação + rate-limit + reset de senha)

Paginação:
- `GET /ui/imports`: suporta `page` e `page_size`.
- `GET /ui/audit`: suporta `page` e `page_size`.

Rate-limit de login:
- Janela: 10 min
- Máx.: 10 tentativas por IP e por usuário

Reset de senha via CLI:
```bash
python scripts/reset_passwords.py --env .env --rotate-admin
python scripts/reset_passwords.py --env .env --rotate-all
```


## Pipeline desktop (local/release)

Checks integrados para build desktop:

```bash
# local (dev/CI)
./scripts/ci_desktop_local.sh

# release (wrapper para o mesmo pipeline)
./scripts/ci_desktop_release.sh
```

O pipeline executa:
- suíte mínima de testes críticos (`pytest -q motoboys-webapp/tests`),
- smoke desktop (`scripts/smoke_desktop.py`) validando:
  - inicialização do banco via `db/schema.sql`,
  - subida da aplicação,
  - resposta de `/health`,
  - abertura da rota principal de UI (`/ui/login`).

## Checklist de release

1. **Pré-checks**
   - Executar `./scripts/ci_desktop_local.sh` sem falhas.
   - Confirmar que variáveis obrigatórias de ambiente estão definidas.
2. **Instalação limpa (clean install)**
   - Subir banco novo (`docker compose down -v && docker compose up -d`).
   - Aplicar schema (`db/schema.sql`).
   - Subir aplicação e validar `/health` e `/ui/login`.
3. **Upgrade de versão (base existente)**
   - Realizar backup do banco (ver política abaixo).
   - Atualizar artefato/binário/serviço para a nova versão.
   - Reaplicar schema quando necessário.
   - Validar login, importações e fechamento/pagamento da semana atual.
4. **Backup/restore (teste obrigatório)**
   - Gerar backup.
   - Restaurar em banco de homologação/local limpo.
   - Validar consistência mínima (contagem de semanas, corridas e entregadores).

## Política de backup antes de atualizar versão

- **Obrigatório**: sempre gerar backup do banco local **antes** de qualquer upgrade.
- **Formato recomendado**: `pg_dump` custom (`-Fc`) com timestamp.
- **Retenção mínima**: manter pelo menos os últimos 7 backups locais.
- **Validação**: todo backup precisa ser testado por restore ao menos em ambiente local/homologação.
- **Exemplo**:

```bash
# backup
pg_dump "postgresql://postgres:postgres@localhost:5432/motoboys" -Fc -f backup_$(date +%Y%m%d_%H%M%S).dump

# restore (em banco alvo limpo)
pg_restore --clean --if-exists --no-owner --no-privileges   -d "postgresql://postgres:postgres@localhost:5432/motoboys"   backup_YYYYMMDD_HHMMSS.dump
```
