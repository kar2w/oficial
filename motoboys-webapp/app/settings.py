import os

try:
    from dotenv import load_dotenv
except ImportError:  # optional during minimal environments
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


def _parse_origins(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return ["*"]
    parts = [p.strip() for p in value.split(",") if p.strip()]
    return parts or ["*"]


class _Settings:
    def __init__(self) -> None:
        self.DATABASE_URL = os.getenv("DATABASE_URL", "")
        self.TZ = os.getenv("TZ", "America/Fortaleza")
        self.CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

    @property
    def cors_origins_list(self) -> list[str]:
        return _parse_origins(self.CORS_ORIGINS)


settings = _Settings()

# Backward-compatible constants
DATABASE_URL = settings.DATABASE_URL
TZ = settings.TZ
CORS_ORIGINS = settings.CORS_ORIGINS

os.environ.setdefault("TZ", TZ)
