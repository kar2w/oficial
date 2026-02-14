import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _load_dotenvs() -> None:
    load_dotenv(override=False)

    here = Path(__file__).resolve()
    webapp_env = here.parents[2] / ".env"
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

_default_weekly_json = str((Path(__file__).resolve().parents[1] / "data" / "entregadores_semanais.json"))


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
    WEEKLY_COURIERS_JSON_PATH=os.getenv("WEEKLY_COURIERS_JSON_PATH", _default_weekly_json).strip() or _default_weekly_json,
)

DATABASE_URL = settings.DATABASE_URL
TZ = settings.TZ
