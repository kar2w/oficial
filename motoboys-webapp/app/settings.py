import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


APP_DIR_NAME = "MotoboysWebApp"


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


def _default_user_data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(os.getenv("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / APP_DIR_NAME


_load_dotenvs()

APP_ENV = os.getenv("APP_ENV", "dev").strip().lower()
APP_MODE = os.getenv("APP_MODE", "server").strip().lower()

if APP_MODE not in {"server", "desktop"}:
    raise RuntimeError("Invalid APP_MODE. Use APP_MODE=server or APP_MODE=desktop.")


def _default_user_data_dir() -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / "Motoboys"
    return Path.home() / ".local" / "share" / "Motoboys"


def _resolve_database_url() -> str:
    db_env = os.getenv("DATABASE_URL", "").strip()
    if db_env:
        return db_env

    if APP_MODE == "desktop":
        data_dir = Path(os.getenv("APP_DATA_DIR", "").strip() or _default_user_data_dir())
        data_dir.mkdir(parents=True, exist_ok=True)
        db_path = (data_dir / "motoboys.db").resolve()
        return f"sqlite+pysqlite:///{db_path}"

    raise RuntimeError("Missing DATABASE_URL. Configure DATABASE_URL (e.g. postgresql+psycopg://...).")

_db = _resolve_database_url()

if not _db.lower().startswith(("postgresql://", "postgresql+psycopg://", "sqlite://", "sqlite+pysqlite://")):
    raise RuntimeError(
        "Invalid DATABASE_URL. Supported schemes: postgresql://, postgresql+psycopg://, sqlite://, sqlite+pysqlite://"
    )

_tz = os.getenv("TZ", "America/Fortaleza")
os.environ.setdefault("TZ", _tz)

_default_user_data = _default_user_data_dir()
_user_data_dir = Path(os.getenv("USER_DATA_DIR", str(_default_user_data))).expanduser().resolve()
_log_dir = Path(os.getenv("LOG_DIR", str(_user_data_dir / "logs"))).expanduser().resolve()
_user_data_dir.mkdir(parents=True, exist_ok=True)
_log_dir.mkdir(parents=True, exist_ok=True)

_here = Path(__file__).resolve()
_default_weekly = str((_here.parents[1] / "data" / "entregadores_semanais.json").resolve())
_weekly_path = os.getenv("WEEKLY_COURIERS_JSON_PATH", _default_weekly).strip() or _default_weekly

_default_secret = "dev-secret-change-me"
_session_secret = os.getenv("SESSION_SECRET", _default_secret).strip() or _default_secret

_admin_user = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
_admin_pass = os.getenv("ADMIN_PASSWORD", "admin").strip() or "admin"

_cashier_user = os.getenv("CASHIER_USERNAME", "caixa").strip() or "caixa"
_cashier_pass = os.getenv("CASHIER_PASSWORD", "caixa").strip() or "caixa"

if APP_ENV == "prod":
    if _session_secret == _default_secret:
        raise RuntimeError("SESSION_SECRET default is not allowed in prod. Set SESSION_SECRET in environment.")
    if _admin_pass == "admin":
        raise RuntimeError("ADMIN_PASSWORD default is not allowed in prod. Set ADMIN_PASSWORD in environment.")
    if _cashier_pass == "caixa":
        raise RuntimeError("CASHIER_PASSWORD default is not allowed in prod. Set CASHIER_PASSWORD in environment.")


@dataclass(frozen=True)
class Settings:
    APP_ENV: str
    APP_MODE: str
    DATABASE_URL: str
    TZ: str
    cors_origins_list: list[str]
    USER_DATA_DIR: str
    LOG_DIR: str
    WEEKLY_COURIERS_JSON_PATH: str
    SESSION_SECRET: str
    ADMIN_USERNAME: str
    ADMIN_PASSWORD: str
    CASHIER_USERNAME: str
    CASHIER_PASSWORD: str


settings = Settings(
    APP_ENV=APP_ENV,
    APP_MODE=APP_MODE,
    DATABASE_URL=_db,
    TZ=_tz,
    cors_origins_list=_parse_cors_origins(os.getenv("CORS_ORIGINS")),
    USER_DATA_DIR=str(_user_data_dir),
    LOG_DIR=str(_log_dir),
    WEEKLY_COURIERS_JSON_PATH=_weekly_path,
    SESSION_SECRET=_session_secret,
    ADMIN_USERNAME=_admin_user,
    ADMIN_PASSWORD=_admin_pass,
    CASHIER_USERNAME=_cashier_user,
    CASHIER_PASSWORD=_cashier_pass,
)

DATABASE_URL = settings.DATABASE_URL
APP_MODE = settings.APP_MODE
TZ = settings.TZ
WEEKLY_COURIERS_JSON_PATH = settings.WEEKLY_COURIERS_JSON_PATH
