import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_dotenvs() -> None:
    # 1) .env do cwd (se você rodar pela raiz, pega a raiz)
    load_dotenv(override=False)

    # 2) .env do motoboys-webapp (se existir)
    here = Path(__file__).resolve()
    webapp_env = here.parents[2] / ".env"  # .../motoboys-webapp/.env
    if webapp_env.exists():
        load_dotenv(webapp_env, override=False)


def _parse_cors_origins(raw: str | None) -> list[str]:
    if not raw or not raw.strip():
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]


_load_dotenvs()

_db = os.getenv("DATABASE_URL", "").strip()
if not _db:
    raise RuntimeError("Missing DATABASE_URL. Configure DATABASE_URL=postgresql+psycopg://...")

if _db.lower().startswith("sqlite") or not (
    _db.lower().startswith("postgresql://") or _db.lower().startswith("postgresql+psycopg://")
):
    raise RuntimeError("Invalid DATABASE_URL for this project. Use postgresql+psycopg://...")

_tz = os.getenv("TZ", "America/Fortaleza")
os.environ.setdefault("TZ", _tz)

# Seed (entregadores semanais)
_here = Path(__file__).resolve()
_default_weekly = str((_here.parents[1] / "data" / "entregadores_semanais.json").resolve())
_weekly_path = os.getenv("WEEKLY_COURIERS_JSON_PATH", _default_weekly).strip() or _default_weekly


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str
    TZ: str
    cors_origins_list: list[str]
    WEEKLY_COURIERS_JSON_PATH: str


settings = Settings(
    DATABASE_URL=_db,
    TZ=_tz,
    cors_origins_list=_parse_cors_origins(os.getenv("CORS_ORIGINS")),
    WEEKLY_COURIERS_JSON_PATH=_weekly_path,
)

# compat
DATABASE_URL = settings.DATABASE_URL
TZ = settings.TZ

WEEKLY_COURIERS_JSON_PATH = settings.WEEKLY_COURIERS_JSON_PATH
