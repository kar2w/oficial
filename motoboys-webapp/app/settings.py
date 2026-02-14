import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

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
