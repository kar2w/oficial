import datetime as dt
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, and_
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Week, Courier, Ride


def _parse_date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        raise HTTPException(status_code=400, detail="effective_date must be YYYY-MM-DD")


def list_week_ledger(db: Session, week_id: str, courier_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q = db.query(LedgerEntry).filter(LedgerEntry.week_id == week_id)
    if courier_id:
        q = q.filter(LedgerEntry.courier_id == courier_id)
    rows = q.order_by(LedgerEntry.effective_date.asc(), LedgerEntry.created_at.asc()).all()
    out = []
    for le in rows:
        out.append(
            {
                "id": str(le.id),
                "courier_id": str(le.courier_id),
                "week_id": str(le.week_id),
                "effective_date": str(le.effective_date),
                "type": le.type,
                "amount": float(le.amount),
                "related_ride_id": str(le.related_ride_id) if le.related_ride_id else None,
                "note": le.note,
                "created_at": le.created_at.isoformat() if le.created_at else None,
            }
        )
    return out


def create_ledger_entry(
    db: Session,
    courier_id: str,
    week_id: str,
    effective_date: str,
    type: str,
    amount: float,
    related_ride_id: Optional[str] = None,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    w = db.query(Week).filter(Week.id == week_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="week not found")

    c = db.query(Courier).filter(Courier.id == courier_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="courier not found")

    d = _parse_date(effective_date)
    if d < w.start_date or d > w.end_date:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "DATE_OUTSIDE_WEEK",
                "week_start": str(w.start_date),
                "week_end": str(w.end_date),
                "effective_date": str(d),
            },
        )

    if type not in ("EXTRA", "VALE"):
        raise HTTPException(status_code=400, detail="type must be EXTRA or VALE")

    if amount is None or float(amount) <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    # v1 rule: VALE per day limited to that day's ride earnings.
    if type == "VALE":
        not_cancelled = or_(Ride.is_cancelled.is_(None), Ride.is_cancelled == False)  # noqa: E712

        day_gain = (
            db.query(func.coalesce(func.sum(Ride.fee_type), 0))
            .filter(
                Ride.week_id == week_id,
                Ride.paid_in_week_id.is_(None),
                Ride.courier_id == courier_id,
                Ride.status == "OK",
                not_cancelled,
                Ride.order_date == d,
            )
            .scalar()
        )
        day_gain_f = float(day_gain or 0)

        existing_vales = (
            db.query(func.coalesce(func.sum(LedgerEntry.amount), 0))
            .filter(
                LedgerEntry.week_id == week_id,
                LedgerEntry.courier_id == courier_id,
                LedgerEntry.type == "VALE",
                LedgerEntry.effective_date == d,
            )
            .scalar()
        )
        existing_vales_f = float(existing_vales or 0)

        if existing_vales_f + float(amount) > day_gain_f:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "VALE_EXCEEDS_DAY_GAIN",
                    "day_gain": day_gain_f,
                    "existing_vales": existing_vales_f,
                    "requested": float(amount),
                },
            )

    le = LedgerEntry(
        courier_id=courier_id,
        week_id=week_id,
        effective_date=d,
        type=type,
        amount=float(amount),
        related_ride_id=related_ride_id,
        note=note,
    )
    db.add(le)
    db.commit()
    db.refresh(le)

    return {
        "id": str(le.id),
        "courier_id": str(le.courier_id),
        "week_id": str(le.week_id),
        "effective_date": str(le.effective_date),
        "type": le.type,
        "amount": float(le.amount),
        "related_ride_id": str(le.related_ride_id) if le.related_ride_id else None,
        "note": le.note,
        "created_at": le.created_at.isoformat() if le.created_at else None,
    }


def delete_ledger_entry(db: Session, ledger_id: str) -> Dict[str, Any]:
    le = db.query(LedgerEntry).filter(LedgerEntry.id == ledger_id).first()
    if not le:
        raise HTTPException(status_code=404, detail="ledger entry not found")

    db.delete(le)
    db.commit()
    return {"ok": True}
