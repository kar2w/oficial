import datetime as dt
import sys
from pathlib import Path

from sqlalchemy import text as sa_text


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    import app.main  # noqa: F401

    from app.db import SessionLocal
    from app.services.week_service import get_current_week

    db = SessionLocal()
    try:
        db.execute(sa_text("SELECT 1"))
        w = get_current_week(db, dt.date.today())
        print(f"SMOKE_OK week_id={w.id} status={w.status}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
