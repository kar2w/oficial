import os

try:
    from dotenv import load_dotenv
except ImportError:  # optional during minimal environments
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv()


class _Settings:
    def __init__(self) -> None:
        self.DATABASE_URL = os.getenv("DATABASE_URL", "")
        self.TZ = os.getenv("TZ", "America/Fortaleza")


settings = _Settings()

# Backward-compatible constants
DATABASE_URL = settings.DATABASE_URL
TZ = settings.TZ

os.environ.setdefault("TZ", TZ)
