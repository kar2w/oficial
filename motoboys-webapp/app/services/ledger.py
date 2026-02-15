import datetime as dt
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, text as sa_text
from sqlalchemy.orm import Session

from app.models import Courier, LedgerEntry, Ride, Week

DEFAULT_LOAN_INSTALLMENTS = 3


def _parse_date(s: str) -> dt.date:
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        raise HTTPException(status_code=400, detail="effective_date must be YYYY-MM-DD")


def _ledger_entry_to_dict(le: LedgerEntry) -> Dict[str, Any]:
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


def _split_amount_cent(total_amount: float, n_installments: int) -> List[float]:
    if n_installments <= 0:
        raise ValueError("n_installments must be >= 1")

    total = Decimal(str(total_amount)).quantize(Decimal("0.01"))
    if n_installments == 1:
        return [float(total)]

    base = (total / Decimal(n_installments)).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    parts = [base for _ in range(n_installments - 1)]
    parts.append(total - base * Decimal(n_installments - 1))
    return [float(p) for p in parts]


def _create_loan_plan_with_installments(
    db: Session,
    courier_id: str,
    week: Week,
    loan_amount: float,
    note: Optional[str],
    n_installments: int = DEFAULT_LOAN_INSTALLMENTS,
) -> str:
    row = db.execute(
        sa_text(
            """
            INSERT INTO loan_plans (courier_id, total_amount, n_installments, rounding, status, start_closing_seq, note)
            VALUES (:courier_id, :total_amount, :n_installments, 'CENT', 'ACTIVE', :start_closing_seq, :note)
            RETURNING id
            """
        ),
        {
            "courier_id": courier_id,
            "total_amount": float(loan_amount),
            "n_installments": int(n_installments),
            "start_closing_seq": int(week.closing_seq),
            "note": note,
        },
    ).mappings().first()

    plan_id = str(row["id"])

    parts = _split_amount_cent(float(loan_amount), int(n_installments))

    for installment_no, amount in enumerate(parts, start=1):
        db.execute(
            sa_text(
                """
                INSERT INTO loan_installments (plan_id, installment_no, due_closing_seq, amount, paid_amount, status)
                VALUES (:plan_id, :installment_no, :due_closing_seq, :amount, 0, 'DUE')
                """
            ),
            {
                "plan_id": plan_id,
                "installment_no": installment_no,
                "due_closing_seq": int(week.closing_seq) + (installment_no - 1),
                "amount": amount,
            },
        )

    return plan_id


def list_week_ledger(db: Session, week_id: str, courier_id: Optional[str] = None) -> List[Dict[str, Any]]:
    q = db.query(LedgerEntry).filter(LedgerEntry.week_id == week_id)
    if courier_id:
        q = q.filter(LedgerEntry.courier_id == courier_id)
    rows = q.order_by(LedgerEntry.effective_date.asc(), LedgerEntry.created_at.asc()).all()
    return [_ledger_entry_to_dict(le) for le in rows]


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
    if week["status"] != "OPEN":
        raise HTTPException(status_code=409, detail={"error": "WEEK_NOT_OPEN", "status": week["status"]})

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

    requested_amount = float(amount)

    if type == "EXTRA":
        le = LedgerEntry(
            courier_id=courier_id,
            week_id=week_id,
            effective_date=d,
            type=type,
            amount=requested_amount,
            related_ride_id=related_ride_id,
            note=note,
        )
        db.add(le)
        db.commit()
        db.refresh(le)
        return {
            "ledger_entry": _ledger_entry_to_dict(le),
            "vale_amount": 0.0,
            "loan_amount": 0.0,
            "loan_plan_id": None,
            "loan_n_installments": None,
        }

    # VALE rule: do not fail on exceeding day gain; convert overflow to a loan plan.
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

    available = max(0.0, day_gain_f - existing_vales_f)
    vale_amount = min(requested_amount, available)
    loan_amount = max(0.0, requested_amount - vale_amount)

    created_le: LedgerEntry | None = None
    loan_plan_id: str | None = None

    if vale_amount > 0:
        created_le = LedgerEntry(
            courier_id=courier_id,
            week_id=week_id,
            effective_date=d,
            type="VALE",
            amount=vale_amount,
            related_ride_id=related_ride_id,
            note=note,
        )
        db.add(created_le)
        db.flush()

    if loan_amount > 0:
        loan_note = f"Empréstimo automático de excedente de VALE em {d.isoformat()}"
        if note:
            loan_note = f"{loan_note}. {note}"
        loan_plan_id = _create_loan_plan_with_installments(
            db=db,
            courier_id=courier_id,
            week=w,
            loan_amount=loan_amount,
            note=loan_note,
            n_installments=DEFAULT_LOAN_INSTALLMENTS,
        )

    db.commit()

    if created_le is not None:
        db.refresh(created_le)

    return {
        "ledger_entry": _ledger_entry_to_dict(created_le) if created_le else None,
        "vale_amount": float(vale_amount),
        "loan_amount": float(loan_amount),
        "loan_plan_id": loan_plan_id,
        "loan_n_installments": int(DEFAULT_LOAN_INSTALLMENTS) if loan_plan_id else None,
    }


def delete_ledger_entry(db: Session, ledger_id: str) -> Dict[str, Any]:
    le = db.query(LedgerEntry).filter(LedgerEntry.id == ledger_id).first()
    if not le:
        raise HTTPException(status_code=404, detail="ledger entry not found")

    db.delete(le)
    db.commit()
    return {"ok": True}
