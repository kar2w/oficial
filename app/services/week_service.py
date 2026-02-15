import datetime as dt
from types import SimpleNamespace


def get_current_week(db, day: dt.date):
    return SimpleNamespace(id="1", start_date=day, end_date=day, status="OPEN")
