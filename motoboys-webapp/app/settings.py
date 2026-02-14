import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Project default timezone (company ops): Fortaleza
TZ = os.getenv("TZ", "America/Fortaleza")

# Best-effort propagate to process (affects app-local date/time ops only)
os.environ.setdefault("TZ", TZ)
