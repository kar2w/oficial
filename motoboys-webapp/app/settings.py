import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
TZ = os.getenv("TZ", "America/Fortaleza")
os.environ.setdefault("TZ", TZ)
