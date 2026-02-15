import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# Project default timezone (company ops): Fortaleza
TZ = os.getenv("TZ", "America/Fortaleza")

# Best-effort propagate to process (affects app-local date/time ops only)
os.environ.setdefault("TZ", TZ)


class Settings:
    DATABASE_URL = DATABASE_URL
    TZ = TZ
    CORS_ORIGINS = CORS_ORIGINS

    @property
    def cors_origins_list(self) -> list[str]:
        raw = (self.CORS_ORIGINS or "*").strip()
        if raw == "*":
            return ["*"]
        return [item.strip() for item in raw.split(",") if item.strip()]


settings = Settings()
