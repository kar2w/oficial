import json
from pathlib import Path

from app.db import SessionLocal
from app.services.seed import seed_weekly_couriers
from app.settings import settings


def main() -> None:
    path = Path(settings.WEEKLY_COURIERS_JSON_PATH)
    if not path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload = {"entregadores": payload}
    if not isinstance(payload, dict):
        raise RuntimeError("Invalid payload in weekly couriers json")

    db = SessionLocal()
    try:
        result = seed_weekly_couriers(db, payload)
        print("SEED_WEEKLY_OK", result)
    finally:
        db.close()


if __name__ == "__main__":
    main()
