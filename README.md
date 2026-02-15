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

## Desktop build (Windows)

Veja `motoboys-webapp/desktop/` e a seção **Desktop (Windows)** em `motoboys-webapp/README.md` para gerar `MotoboysWebApp.exe` com PyInstaller, incluindo templates/static/assets e metadata de versão.
