import datetime as dt

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from app.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@event.listens_for(Session, "before_flush")
def _touch_timestamps(session: Session, flush_context, instances):
    """Maintain updated_at (and created_at when missing) on ORM objects.

    The database has defaults, but this keeps `updated_at` changing on mutations,
    avoiding silent drift between schema.sql and ORM behavior.
    """
    now = dt.datetime.now(dt.timezone.utc)

    # New instances
    for obj in session.new:
        if hasattr(obj, "created_at") and getattr(obj, "created_at") is None:
            try:
                setattr(obj, "created_at", now)
            except Exception:
                pass
        if hasattr(obj, "updated_at"):
            try:
                setattr(obj, "updated_at", now)
            except Exception:
                pass

    # Dirty instances
    for obj in session.dirty:
        if hasattr(obj, "updated_at"):
            try:
                setattr(obj, "updated_at", now)
            except Exception:
                pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
