import os
from dataclasses import dataclass
from pathlib import Path
from dataclasses import dataclass, field

from dotenv import load_dotenv


def _load_dotenvs() -> None:
    # Load default .env from cwd first, then repo-root .env for resilience.
    load_dotenv(override=False)
    here = Path(__file__).resolve()
    repo_env = here.parents[2] / ".env"  # motoboys-webapp/.env
    if repo_env.exists():
        load_dotenv(repo_env, override=False)


def _parse_cors_origins(raw: str | None) -> list[str]:
    if raw is None or raw.strip() == "":
        return ["*"]
    return [x.strip() for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str
    TZ: str
    cors_origins_list: list[str]


_load_dotenvs()

_db = os.getenv("DATABASE_URL", "").strip()
if not _db:
    raise RuntimeError("Missing DATABASE_URL. Configure DATABASE_URL=postgresql+psycopg://...")

if _db.lower().startswith("sqlite") or not (_db.lower().startswith("postgresql://") or _db.lower().startswith("postgresql+psycopg://")):
    raise RuntimeError("Invalid DATABASE_URL for this project. Configure DATABASE_URL=postgresql+psycopg://...")

_tz = os.getenv("TZ", "America/Fortaleza")
os.environ.setdefault("TZ", _tz)

settings = Settings(
    DATABASE_URL=_db,
    TZ=_tz,
    cors_origins_list=_parse_cors_origins(os.getenv("CORS_ORIGINS")),
)
_DEFAULT_DATABASE_URL = "sqlite:///./motoboys.db"
_DEFAULT_TZ = "America/Fortaleza"
_DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"


@dataclass(slots=True)
class Settings:
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", _DEFAULT_DATABASE_URL).strip() or _DEFAULT_DATABASE_URL)
    TZ: str = field(default_factory=lambda: os.getenv("TZ", _DEFAULT_TZ).strip() or _DEFAULT_TZ)
    cors_origins_list: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        raw_origins = os.getenv("CORS_ORIGINS", _DEFAULT_CORS_ORIGINS)
        self.cors_origins_list = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]


settings = Settings()

# Backward compatibility for direct constant imports.
DATABASE_URL = settings.DATABASE_URL
TZ = settings.TZ

# Best-effort propagate to process (affects app-local date/time ops only)
os.environ.setdefault("TZ", settings.TZ)
