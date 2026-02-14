import os
from dataclasses import dataclass
from pathlib import Path

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
