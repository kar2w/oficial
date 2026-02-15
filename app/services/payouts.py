import datetime as dt
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session


_PENDING_STATUSES = ("PENDENTE_ATRIBUICAO", "PENDENTE_REVISAO", "PENDENTE_MATCH")


def get_week_or_404(db: Session, week_id: str):
    w = db.execute(
        sa_text("SELECT id, start_date, end_date, status FROM weeks WHERE id::text = :week_id"),
        {"week_id": week_id},
    ).mappings().first()
    if not w:
        raise HTTPException(status_code=404, detail="week not found")
    return w


def compute_week_payout_preview(db: Session, week_id: str) -> list[dict[str, Any]]:
    w = get_week_or_404(db, week_id)

    rows = db.execute(
        sa_text(
            """
            WITH ride_scope AS (
                SELECT r.*
                FROM rides r
                WHERE (r.week_id::text = :week_id AND r.paid_in_week_id IS NULL)
                   OR r.paid_in_week_id::text = :week_id
            ),
            ok AS (
                SELECT
                    courier_id,
                    COUNT(*) AS rides_count,
                    COALESCE(SUM(fee_type), 0) AS rides_amount,
                    COALESCE(SUM(value_raw), 0) AS rides_value_raw_amount
                FROM ride_scope
                WHERE status = 'OK'
                  AND (is_cancelled IS NULL OR is_cancelled = false)
                GROUP BY courier_id
            ),
            pend AS (
                SELECT
                    courier_id,
                    COUNT(*) AS pending_count
                FROM ride_scope
                WHERE status = ANY(:pending_statuses)
                  AND (is_cancelled IS NULL OR is_cancelled = false)
                GROUP BY courier_id
            ),
            led AS (
                SELECT
                    courier_id,
                    COALESCE(SUM(CASE WHEN type = 'EXTRA' THEN amount ELSE 0 END), 0) AS extras_amount,
                    COALESCE(SUM(CASE WHEN type = 'VALE' THEN amount ELSE 0 END), 0) AS vales_amount
                FROM ledger_entries
                WHERE week_id::text = :week_id
                GROUP BY courier_id
            ),
            all_ids AS (
                SELECT courier_id FROM ok
                UNION
                SELECT courier_id FROM pend
                UNION
                SELECT courier_id FROM led
            )
            SELECT
                :week_id AS week_id,
                ai.courier_id,
                c.nome_resumido AS courier_nome,
                COALESCE(ok.rides_count, 0) AS rides_count,
                COALESCE(ok.rides_amount, 0) AS rides_amount,
                COALESCE(ok.rides_value_raw_amount, 0) AS rides_value_raw_amount,
                COALESCE(led.extras_amount, 0) AS extras_amount,
                COALESCE(led.vales_amount, 0) AS vales_amount,
                0::numeric AS installments_amount,
                COALESCE(pend.pending_count, 0) AS pending_count
            FROM all_ids ai
            LEFT JOIN ok ON ok.courier_id IS NOT DISTINCT FROM ai.courier_id
            LEFT JOIN pend ON pend.courier_id IS NOT DISTINCT FROM ai.courier_id
            LEFT JOIN led ON led.courier_id IS NOT DISTINCT FROM ai.courier_id
            LEFT JOIN couriers c ON c.id = ai.courier_id
            ORDER BY UPPER(COALESCE(c.nome_resumido, '<SEM ATRIBUIÇÃO>'))
            """
        ),
        {"week_id": str(w["id"]), "pending_statuses": list(_PENDING_STATUSES)},
    ).mappings().all()

    out: list[dict[str, Any]] = []
    for r in rows:
        rides_amount = float(r["rides_amount"] or 0)
        extras_amount = float(r["extras_amount"] or 0)
        vales_amount = float(r["vales_amount"] or 0)
        installments_amount = float(r["installments_amount"] or 0)
        out.append(
            {
                "week_id": str(r["week_id"]),
                "courier_id": r["courier_id"],
                "courier_nome": r["courier_nome"] or "<SEM ATRIBUIÇÃO>",
                "rides_count": int(r["rides_count"] or 0),
                "rides_amount": rides_amount,
                "rides_value_raw_amount": float(r["rides_value_raw_amount"] or 0),
                "extras_amount": extras_amount,
                "vales_amount": vales_amount,
                "installments_amount": installments_amount,
                "pending_count": int(r["pending_count"] or 0),
                "net_amount": rides_amount + extras_amount - vales_amount - installments_amount,
                "is_flag_red": False,
            }
        )

    return out


def close_week(db: Session, week_id: str) -> dict[str, Any]:
    w = get_week_or_404(db, week_id)
    if w["status"] != "OPEN":
        raise HTTPException(status_code=409, detail={"error": "WEEK_NOT_OPEN", "status": w["status"]})

    rows = compute_week_payout_preview(db, week_id)
    pending_total = sum(int(r.get("pending_count") or 0) for r in rows)
    unassigned = [r for r in rows if r.get("courier_id") is None and int(r.get("rides_count") or 0) > 0]
    if pending_total > 0 or unassigned:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "WEEK_HAS_PENDINGS",
                "pending_total": pending_total,
                "unassigned_ok_rides": sum(int(r.get("rides_count") or 0) for r in unassigned),
            },
        )

    db.execute(sa_text("DELETE FROM week_payouts WHERE week_id::text = :week_id"), {"week_id": week_id})
    for r in rows:
        if r.get("courier_id") is None:
            continue
        db.execute(
            sa_text(
                """
                INSERT INTO week_payouts (
                    week_id, courier_id, rides_amount, extras_amount, vales_amount,
                    installments_amount, net_amount, pending_count, is_flag_red
                ) VALUES (
                    :week_id, :courier_id, :rides_amount, :extras_amount, :vales_amount,
                    :installments_amount, :net_amount, :pending_count, :is_flag_red
                )
                """
            ),
            {
                "week_id": week_id,
                "courier_id": str(r["courier_id"]),
                "rides_amount": r["rides_amount"],
                "extras_amount": r["extras_amount"],
                "vales_amount": r["vales_amount"],
                "installments_amount": r["installments_amount"],
                "net_amount": r["net_amount"],
                "pending_count": r["pending_count"],
                "is_flag_red": False,
            },
        )

    db.execute(sa_text("UPDATE weeks SET status = 'CLOSED' WHERE id::text = :week_id"), {"week_id": week_id})
    db.commit()
    return {"ok": True, "week_id": str(w["id"]), "status": "CLOSED", "payouts": len(rows)}


def pay_week(db: Session, week_id: str) -> dict[str, Any]:
    w = get_week_or_404(db, week_id)
    if w["status"] != "CLOSED":
        raise HTTPException(status_code=409, detail={"error": "WEEK_NOT_CLOSED", "status": w["status"]})

    now = dt.datetime.now(dt.timezone.utc)
    db.execute(sa_text("UPDATE weeks SET status = 'PAID' WHERE id::text = :week_id"), {"week_id": week_id})
    db.execute(
        sa_text("UPDATE week_payouts SET paid_at = :paid_at WHERE week_id::text = :week_id"),
        {"week_id": week_id, "paid_at": now},
    )
    db.commit()
    return {"ok": True, "week_id": str(w["id"]), "status": "PAID", "paid_at": now.isoformat()}


def get_payout_snapshot(db: Session, week_id: str) -> list[dict[str, Any]]:
    w = get_week_or_404(db, week_id)
    rows = db.execute(
        sa_text(
            """
            SELECT
                wp.courier_id,
                c.nome_resumido AS courier_nome,
                wp.rides_amount,
                wp.extras_amount,
                wp.vales_amount,
                wp.installments_amount,
                wp.net_amount,
                wp.pending_count,
                wp.is_flag_red,
                wp.computed_at,
                wp.paid_at
            FROM week_payouts wp
            JOIN couriers c ON c.id = wp.courier_id
            WHERE wp.week_id::text = :week_id
            ORDER BY c.nome_resumido ASC
            """
        ),
        {"week_id": str(w["id"])},
    ).mappings().all()

    return [
        {
            "week_id": str(w["id"]),
            "courier_id": str(r["courier_id"]),
            "courier_nome": r["courier_nome"],
            "rides_amount": float(r["rides_amount"]),
            "extras_amount": float(r["extras_amount"]),
            "vales_amount": float(r["vales_amount"]),
            "installments_amount": float(r["installments_amount"]),
            "net_amount": float(r["net_amount"]),
            "pending_count": int(r["pending_count"]),
            "is_flag_red": bool(r["is_flag_red"]),
            "computed_at": r["computed_at"].isoformat() if r["computed_at"] else None,
            "paid_at": r["paid_at"].isoformat() if r["paid_at"] else None,
        }
        for r in rows
    ]
