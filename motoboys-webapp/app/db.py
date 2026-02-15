import datetime as dt

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.settings import settings

def _engine_kwargs() -> dict:
    if settings.APP_MODE == "desktop" and settings.DATABASE_URL.lower().startswith("sqlite"):
        return {
            "connect_args": {"check_same_thread": False},
            "pool_pre_ping": False,
        }
    return {"pool_pre_ping": True}


engine = create_engine(settings.DATABASE_URL, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(Session, "before_flush")
def _touch_timestamps(session: Session, flush_context, instances):
    """Maintain updated_at (and created_at when missing) on ORM objects."""
    now = dt.datetime.now(dt.timezone.utc)

    for obj in session.new:
        if hasattr(obj, "created_at") and getattr(obj, "created_at") is None:
            setattr(obj, "created_at", now)
        if hasattr(obj, "updated_at"):
            setattr(obj, "updated_at", now)

    for obj in session.dirty:
        if hasattr(obj, "updated_at"):
            setattr(obj, "updated_at", now)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
