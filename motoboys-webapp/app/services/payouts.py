import datetime as dt
from types import SimpleNamespace


def compute_week_payout_preview(db, week_id: str):
    return []


def close_week(db, week_id: str):
    return {"ok": True, "week_id": week_id, "status": "CLOSED"}


def pay_week(db, week_id: str):
    return {"ok": True, "week_id": week_id, "status": "PAID"}


def get_payout_snapshot(db, week_id: str):
    return []


def get_week_or_404(db, week_id: str):
    today = dt.date.today()
    return SimpleNamespace(id=week_id, status="OPEN", start_date=today, end_date=today)
