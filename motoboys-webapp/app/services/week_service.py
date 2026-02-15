import datetime as dt

from fastapi import HTTPException
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.models import Week


def thursday_start(d: dt.date) -> dt.date:
    offset = (d.weekday() - 3) % 7
    return d - dt.timedelta(days=offset)


def validate_no_week_overlap(
    db: Session,
    start_date: dt.date,
    end_date: dt.date,
    *,
    exclude_week_id: str | None = None,
) -> None:
    overlap_q = db.query(Week).filter(and_(Week.start_date <= end_date, Week.end_date >= start_date))
    if exclude_week_id is not None:
        overlap_q = overlap_q.filter(Week.id != exclude_week_id)

    hit = overlap_q.first()
    if hit:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "WEEK_OVERLAP",
                "new_range": [str(start_date), str(end_date)],
                "conflict_week_id": str(hit.id),
                "conflict_range": [str(hit.start_date), str(hit.end_date)],
            },
        )


def _next_closing_seq(db: Session) -> int:
    curr = db.query(func.max(Week.closing_seq)).scalar()
    return int(curr or 0) + 1


def get_or_create_week_for_date(db: Session, d: dt.date) -> Week:
    w = db.query(Week).filter(Week.start_date <= d, Week.end_date >= d).first()
    if w:
        return w
    start = thursday_start(d)
    end = start + dt.timedelta(days=6)
    validate_no_week_overlap(db, start, end)
    w = Week(start_date=start, end_date=end, closing_seq=_next_closing_seq(db), status="OPEN", note=None)
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


def get_current_week(db: Session, today: dt.date) -> Week:
    return get_or_create_week_for_date(db, today)


def get_open_week_for_date(db: Session, d: dt.date) -> Week:
    """Return an OPEN week on/after the week containing `d`."""
    w = get_or_create_week_for_date(db, d)
    if w.status == "OPEN":
        return w

    cursor = w.end_date + dt.timedelta(days=1)
    ww = w
    for _ in range(26):
        ww = get_or_create_week_for_date(db, cursor)
        if ww.status == "OPEN":
            return ww
        cursor = ww.end_date + dt.timedelta(days=1)

    return ww
