import datetime as dt
from sqlalchemy.orm import Session
from app.models import Week

def thursday_start(d: dt.date) -> dt.date:
    offset = (d.weekday() - 3) % 7
    return d - dt.timedelta(days=offset)

def get_or_create_week_for_date(db: Session, d: dt.date) -> Week:
    w = db.query(Week).filter(Week.start_date <= d, Week.end_date >= d).first()
    if w:
        return w
    start = thursday_start(d)
    end = start + dt.timedelta(days=6)
    w = Week(start_date=start, end_date=end, status="OPEN", note=None)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w

def get_current_week(db: Session, today: dt.date) -> Week:
    return get_or_create_week_for_date(db, today)
