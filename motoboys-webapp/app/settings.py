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

APP_ENV = os.getenv("APP_ENV", "dev").strip().lower()

_db = os.getenv("DATABASE_URL", "").strip()
if not _db:
    raise RuntimeError("Missing DATABASE_URL. Configure DATABASE_URL=postgresql+psycopg://...")

if _db.lower().startswith("sqlite") or not (
    _db.lower().startswith("postgresql://") or _db.lower().startswith("postgresql+psycopg://")
):
    raise RuntimeError("Invalid DATABASE_URL for this project. Use postgresql+psycopg://...")

_tz = os.getenv("TZ", "America/Fortaleza")
os.environ.setdefault("TZ", _tz)

_here = Path(__file__).resolve()
_default_weekly = str((_here.parents[1] / "data" / "entregadores_semanais.json").resolve())
_weekly_path = os.getenv("WEEKLY_COURIERS_JSON_PATH", _default_weekly).strip() or _default_weekly

_default_secret = "dev-secret-change-me"
_session_secret = os.getenv("SESSION_SECRET", _default_secret).strip() or _default_secret

_admin_user = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
_admin_pass = os.getenv("ADMIN_PASSWORD", "admin").strip() or "admin"

if APP_ENV == "prod":
    if _session_secret == _default_secret:
        raise RuntimeError("SESSION_SECRET default is not allowed in prod. Set SESSION_SECRET in environment.")
    if _admin_pass == "admin":
        raise RuntimeError("ADMIN_PASSWORD default is not allowed in prod. Set ADMIN_PASSWORD in environment.")


@dataclass(frozen=True)
class Settings:
    APP_ENV: str
    DATABASE_URL: str
    TZ: str
    cors_origins_list: list[str]
    WEEKLY_COURIERS_JSON_PATH: str
    SESSION_SECRET: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str


settings = Settings(
    APP_ENV=APP_ENV,
    DATABASE_URL=_db,
    TZ=_tz,
    cors_origins_list=_parse_cors_origins(os.getenv("CORS_ORIGINS")),
    WEEKLY_COURIERS_JSON_PATH=_weekly_path,
    SESSION_SECRET=_session_secret,
    ADMIN_USERNAME=_admin_user,
    ADMIN_PASSWORD=_admin_pass,
)

DATABASE_URL = settings.DATABASE_URL
TZ = settings.TZ
WEEKLY_COURIERS_JSON_PATH = settings.WEEKLY_COURIERS_JSON_PATH
