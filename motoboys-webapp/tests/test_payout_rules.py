from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import payouts


class _FakeWeekPayoutQuery:
    def __init__(self):
        self.deleted = False
        self.updated = None

    def filter(self, *args, **kwargs):
        return self

    def delete(self, synchronize_session=False):
        self.deleted = True

    def update(self, values):
        self.updated = values


class _FakeDB:
    def __init__(self):
        self.week_payout_query = _FakeWeekPayoutQuery()
        self.commits = 0

    def query(self, _model):
        return self.week_payout_query

    def add(self, _obj):
        pass

    def execute(self, *args, **kwargs):
        return None

    def commit(self):
        self.commits += 1


def test_close_week_blocks_when_has_pending_rows(monkeypatch):
    db = _FakeDB()
    week = SimpleNamespace(id="w1", status="OPEN", closing_seq=1)

    monkeypatch.setattr(payouts, "get_week_or_404", lambda *_: week)
    monkeypatch.setattr(
        payouts,
        "compute_week_payout_preview",
        lambda *_: [{"courier_id": "c1", "rides_count": 5, "pending_count": 1}],
    )

    with pytest.raises(HTTPException) as exc:
        payouts.close_week(db, "w1")

    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "WEEK_HAS_PENDINGS"


def test_close_and_pay_week_happy_path(monkeypatch):
    db = _FakeDB()
    week = SimpleNamespace(id="w1", status="OPEN", closing_seq=1)

    monkeypatch.setattr(payouts, "get_week_or_404", lambda *_: week)
    monkeypatch.setattr(
        payouts,
        "compute_week_payout_preview",
        lambda *_: [
            {
                "courier_id": "c1",
                "rides_count": 1,
                "rides_amount": 10.0,
                "extras_amount": 0.0,
                "vales_amount": 0.0,
                "installments_amount": 0.0,
                "net_amount": 10.0,
                "pending_count": 0,
                "is_flag_red": False,
            }
        ],
    )
    monkeypatch.setattr(payouts, "_get_due_installments", lambda *_: [])

    close_out = payouts.close_week(db, "w1")

    assert close_out["status"] == "CLOSED"
    assert week.status == "CLOSED"
    assert db.week_payout_query.deleted is True

    pay_out = payouts.pay_week(db, "w1")

    assert pay_out["status"] == "PAID"
    assert week.status == "PAID"
    assert db.week_payout_query.updated is not None


def test_pay_week_requires_closed(monkeypatch):
    db = _FakeDB()
    week = SimpleNamespace(id="w1", status="OPEN")

    monkeypatch.setattr(payouts, "get_week_or_404", lambda *_: week)

    with pytest.raises(HTTPException) as exc:
        payouts.pay_week(db, "w1")

    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "WEEK_NOT_CLOSED"
