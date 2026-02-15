import datetime as dt
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session


def _parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(value))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="effective_date must be YYYY-MM-DD") from exc


def list_week_ledger(db: Session, week_id: str, courier_id: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT id, courier_id, week_id, effective_date, type, amount, related_ride_id, note, created_at
        FROM ledger_entries
        WHERE week_id::text = :week_id
    """
    params: dict[str, Any] = {"week_id": week_id}
    if courier_id:
        sql += " AND courier_id::text = :courier_id"
        params["courier_id"] = courier_id
    sql += " ORDER BY effective_date ASC, created_at ASC"

    rows = db.execute(sa_text(sql), params).mappings().all()
    return [
        {
            "id": str(r["id"]),
            "courier_id": str(r["courier_id"]),
            "week_id": str(r["week_id"]),
            "effective_date": str(r["effective_date"]),
            "type": r["type"],
            "amount": float(r["amount"]),
            "related_ride_id": str(r["related_ride_id"]) if r["related_ride_id"] else None,
            "note": r["note"],
            "created_at": r["created_at"].isoformat() if r["created_at"] else None,
        }
        for r in rows
    ]


def create_ledger_entry(
    db: Session,
    courier_id: str,
    week_id: str,
    effective_date,
    type: str,
    amount: float,
    related_ride_id=None,
    note=None,
):
    week = db.execute(
        sa_text("SELECT id, start_date, end_date, status FROM weeks WHERE id::text = :week_id"),
        {"week_id": week_id},
    ).mappings().first()
    if not week:
        raise HTTPException(status_code=404, detail="week not found")
    if week["status"] != "OPEN":
        raise HTTPException(status_code=409, detail={"error": "WEEK_NOT_OPEN", "status": week["status"]})

    courier_exists = db.execute(
        sa_text("SELECT 1 FROM couriers WHERE id::text = :courier_id"), {"courier_id": courier_id}
    ).first()
    if not courier_exists:
        raise HTTPException(status_code=404, detail="courier not found")

    d = _parse_date(effective_date)
    if d < week["start_date"] or d > week["end_date"]:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "DATE_OUTSIDE_WEEK",
                "week_start": str(week["start_date"]),
                "week_end": str(week["end_date"]),
                "effective_date": str(d),
            },
        )

    if type not in ("EXTRA", "VALE"):
        raise HTTPException(status_code=400, detail="type must be EXTRA or VALE")

    if amount is None or float(amount) <= 0:
        raise HTTPException(status_code=400, detail="amount must be > 0")

    if type == "VALE":
        day_gain = db.execute(
            sa_text(
                """
                SELECT COALESCE(SUM(r.fee_type), 0)
                FROM rides r
                WHERE (
                        (r.week_id::text = :week_id AND r.paid_in_week_id IS NULL)
                        OR r.paid_in_week_id::text = :week_id
                    )
                  AND r.courier_id::text = :courier_id
                  AND r.status = 'OK'
                  AND (r.is_cancelled IS NULL OR r.is_cancelled = false)
                  AND r.order_date = :effective_date
                """
            ),
            {"week_id": week_id, "courier_id": courier_id, "effective_date": d},
        ).scalar_one()
        existing_vales = db.execute(
            sa_text(
                """
                SELECT COALESCE(SUM(le.amount), 0)
                FROM ledger_entries le
                WHERE le.week_id::text = :week_id
                  AND le.courier_id::text = :courier_id
                  AND le.type = 'VALE'
                  AND le.effective_date = :effective_date
                """
            ),
            {"week_id": week_id, "courier_id": courier_id, "effective_date": d},
        ).scalar_one()

        if float(existing_vales or 0) + float(amount) > float(day_gain or 0):
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "VALE_EXCEEDS_DAY_GAIN",
                    "day_gain": float(day_gain or 0),
                    "existing_vales": float(existing_vales or 0),
                    "requested": float(amount),
                },
            )

    row = db.execute(
        sa_text(
            """
            INSERT INTO ledger_entries (
                courier_id, week_id, effective_date, type, amount, related_ride_id, note
            ) VALUES (
                :courier_id, :week_id, :effective_date, :type, :amount, :related_ride_id, :note
            )
            RETURNING id, courier_id, week_id, effective_date, type, amount, related_ride_id, note, created_at
            """
        ),
        {
            "courier_id": courier_id,
            "week_id": week_id,
            "effective_date": d,
            "type": type,
            "amount": float(amount),
            "related_ride_id": related_ride_id,
            "note": note,
        },
    ).mappings().one()
    db.commit()

    return {
        "id": str(row["id"]),
        "courier_id": str(row["courier_id"]),
        "week_id": str(row["week_id"]),
        "effective_date": str(row["effective_date"]),
        "type": row["type"],
        "amount": float(row["amount"]),
        "related_ride_id": str(row["related_ride_id"]) if row["related_ride_id"] else None,
        "note": row["note"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def delete_ledger_entry(db: Session, ledger_id: str):
    entry = db.execute(
        sa_text(
            """
            SELECT le.id, w.status
            FROM ledger_entries le
            JOIN weeks w ON w.id = le.week_id
            WHERE le.id::text = :ledger_id
            """
        ),
        {"ledger_id": ledger_id},
    ).mappings().first()
    if not entry:
        raise HTTPException(status_code=404, detail="ledger entry not found")

    if entry["status"] != "OPEN":
        raise HTTPException(status_code=409, detail={"error": "WEEK_NOT_OPEN", "status": entry["status"]})

    db.execute(
        sa_text("DELETE FROM ledger_entries WHERE id = :ledger_id"),
        {"ledger_id": entry["id"]},
    )
    db.commit()
    return {"ok": True}
