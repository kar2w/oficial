import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/motoboys")
TZ = os.getenv("TZ", "America/Fortaleza")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")


def cors_origins_list() -> list[str]:
    return [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]
