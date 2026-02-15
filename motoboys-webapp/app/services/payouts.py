import datetime as dt
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, text as sa_text
from sqlalchemy.orm import Session

from app.models import Courier, LedgerEntry, Ride, Week, WeekPayout
from app.services.week_service import validate_no_week_overlap


_PENDING_STATUSES = {"PENDENTE_ATRIBUICAO", "PENDENTE_REVISAO", "PENDENTE_MATCH"}


def get_week_or_404(db: Session, week_id: str) -> Week:
    w = db.query(Week).filter(Week.id == week_id).first()
    if not w:
        raise HTTPException(status_code=404, detail="week not found")
    return w


def _scope_filter(week_id: str):
    # Paid-in-week overrides original week_id.
    return or_(
        and_(Ride.week_id == week_id, Ride.paid_in_week_id.is_(None)),
        Ride.paid_in_week_id == week_id,
    )


def _get_due_installments(db: Session, courier_id: str, closing_seq: int):
    return db.execute(
        sa_text(
            """
            SELECT li.id, li.due_closing_seq, li.amount, li.paid_amount
            FROM loan_installments li
            JOIN loan_plans lp ON lp.id = li.plan_id
            WHERE lp.courier_id = :courier_id
              AND lp.status = 'ACTIVE'
              AND li.status IN ('DUE','ROLLED','PARTIAL')
              AND li.due_closing_seq <= :closing_seq
            ORDER BY li.due_closing_seq ASC, li.installment_no ASC
            """
        ),
        {"courier_id": courier_id, "closing_seq": int(closing_seq)},
    ).mappings().all()


def _remaining_installment_amount(inst_row) -> float:
    return max(0.0, float(inst_row["amount"] or 0) - float(inst_row["paid_amount"] or 0))


def compute_week_payout_preview(db: Session, week_id: str) -> List[Dict[str, Any]]:
    """Compute payouts for a week without writing snapshot.

    Amounts use Ride.fee_type (6/10) as the payable value, not value_raw.
    """
    w = get_week_or_404(db, week_id)
    scope = _scope_filter(week_id)

    not_cancelled = or_(Ride.is_cancelled.is_(None), Ride.is_cancelled == False)  # noqa: E712

    ok_rows = (
        db.query(
            Ride.courier_id.label("courier_id"),
            func.count(Ride.id).label("rides_count"),
            func.coalesce(func.sum(Ride.fee_type), 0).label("rides_amount"),
            func.coalesce(func.sum(Ride.value_raw), 0).label("rides_value_raw_amount"),
        )
        .filter(scope, Ride.status == "OK", not_cancelled)
        .group_by(Ride.courier_id)
        .all()
    )

    pending_rows = (
        db.query(Ride.courier_id.label("courier_id"), func.count(Ride.id).label("pending_count"))
        .filter(scope, Ride.status.in_(sorted(_PENDING_STATUSES)), not_cancelled)
        .group_by(Ride.courier_id)
        .all()
    )

    ledger_rows = (
        db.query(
            LedgerEntry.courier_id.label("courier_id"),
            func.coalesce(func.sum(case((LedgerEntry.type == "EXTRA", LedgerEntry.amount), else_=0)), 0).label(
                "extras_amount"
            ),
            func.coalesce(func.sum(case((LedgerEntry.type == "VALE", LedgerEntry.amount), else_=0)), 0).label(
                "vales_amount"
            ),
        )
        .filter(LedgerEntry.week_id == week_id)
        .group_by(LedgerEntry.courier_id)
        .all()
    )

    by_id: Dict[Optional[object], Dict[str, Any]] = {}

    def ensure(cid):
        if cid not in by_id:
            by_id[cid] = {
                "week_id": str(w.id),
                "courier_id": cid,
                "courier_nome": None,
                "rides_count": 0,
                "rides_amount": 0.0,
                "rides_value_raw_amount": 0.0,
                "extras_amount": 0.0,
                "vales_amount": 0.0,
                "installments_amount": 0.0,
                "pending_count": 0,
            }
        return by_id[cid]

    for r in ok_rows:
        row = ensure(r.courier_id)
        row["rides_count"] = int(r.rides_count or 0)
        row["rides_amount"] = float(r.rides_amount or 0)
        row["rides_value_raw_amount"] = float(r.rides_value_raw_amount or 0)

    for r in pending_rows:
        row = ensure(r.courier_id)
        row["pending_count"] = int(r.pending_count or 0)

    for r in ledger_rows:
        row = ensure(r.courier_id)
        row["extras_amount"] = float(r.extras_amount or 0)
        row["vales_amount"] = float(r.vales_amount or 0)

    # Attach courier names
    courier_ids = [cid for cid in by_id.keys() if cid is not None]
    if courier_ids:
        couriers = db.query(Courier.id, Courier.nome_resumido).filter(Courier.id.in_(courier_ids)).all()
        names = {cid: nome for cid, nome in couriers}
        for cid in courier_ids:
            by_id[cid]["courier_nome"] = names.get(cid)

    out = []
    for cid, row in by_id.items():
        rides_amount = float(row["rides_amount"])
        extras_amount = float(row["extras_amount"])
        vales_amount = float(row["vales_amount"])

        installment_due_total = 0.0
        if cid is not None:
            for inst in _get_due_installments(db, str(cid), int(w.closing_seq)):
                installment_due_total += _remaining_installment_amount(inst)

        pre_installment_net = rides_amount + extras_amount - vales_amount
        installments_amount = max(0.0, min(pre_installment_net, installment_due_total))
        row["installments_amount"] = float(installments_amount)

        net = pre_installment_net - installments_amount
        row["net_amount"] = float(net)
        row["is_flag_red"] = bool(installment_due_total > installments_amount + 1e-9)

        if cid is None:
            row["courier_nome"] = row["courier_nome"] or "<SEM ATRIBUIÇÃO>"
            row["is_flag_red"] = False
        out.append(row)

    def sort_key(x):
        return (x["courier_nome"] or "").upper()

    out.sort(key=sort_key)
    return out


def close_week(db: Session, week_id: str) -> Dict[str, Any]:
    w = get_week_or_404(db, week_id)
    if w.status != "OPEN":
        raise HTTPException(status_code=409, detail={"error": "WEEK_NOT_OPEN", "status": w.status})

    validate_no_week_overlap(db, w.start_date, w.end_date, exclude_week_id=str(w.id))

    rows = compute_week_payout_preview(db, week_id)

    pending_total = sum(int(r.get("pending_count") or 0) for r in rows)
    unassigned = [r for r in rows if r.get("courier_id") is None and (r.get("rides_count") or 0) > 0]

    if pending_total > 0 or unassigned:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "WEEK_HAS_PENDINGS",
                "pending_total": pending_total,
                "unassigned_ok_rides": sum(int(r.get("rides_count") or 0) for r in unassigned),
            },
        )

    # Replace snapshot
    db.query(WeekPayout).filter(WeekPayout.week_id == w.id).delete(synchronize_session=False)

    for r in rows:
        cid = r.get("courier_id")
        if cid is None:
            continue

        # Apply loan installments with audit trail.
        to_apply = float(r.get("installments_amount") or 0)
        due_rows = _get_due_installments(db, str(cid), int(w.closing_seq))

        for inst in due_rows:
            inst_id = str(inst["id"])
            remaining = _remaining_installment_amount(inst)
            if remaining <= 0:
                continue

            applied = min(to_apply, remaining)
            if applied > 0:
                db.execute(
                    sa_text(
                        """
                        INSERT INTO loan_installment_applications (installment_id, week_id, applied_amount, note)
                        VALUES (:installment_id, :week_id, :applied_amount, :note)
                        """
                    ),
                    {
                        "installment_id": inst_id,
                        "week_id": str(w.id),
                        "applied_amount": applied,
                        "note": "Desconto automático no fechamento semanal",
                    },
                )

                db.execute(
                    sa_text(
                        """
                        UPDATE loan_installments
                        SET paid_amount = paid_amount + :applied_amount
                        WHERE id = :installment_id
                        """
                    ),
                    {"installment_id": inst_id, "applied_amount": applied},
                )

                to_apply -= applied
                remaining -= applied

            # If not fully paid this closing, roll to next closing sequence.
            if remaining <= 1e-9:
                db.execute(
                    sa_text("UPDATE loan_installments SET status = 'PAID' WHERE id = :installment_id"),
                    {"installment_id": inst_id},
                )
            else:
                next_status = "PARTIAL" if applied > 0 else "ROLLED"
                db.execute(
                    sa_text(
                        """
                        UPDATE loan_installments
                        SET status = :status,
                            due_closing_seq = due_closing_seq + 1
                        WHERE id = :installment_id
                        """
                    ),
                    {"installment_id": inst_id, "status": next_status},
                )

        # close plans without open installments
        db.execute(
            sa_text(
                """
                UPDATE loan_plans lp
                SET status = 'DONE'
                WHERE lp.courier_id = :courier_id
                  AND lp.status = 'ACTIVE'
                  AND NOT EXISTS (
                    SELECT 1 FROM loan_installments li
                    WHERE li.plan_id = lp.id
                      AND li.status IN ('DUE','ROLLED','PARTIAL')
                  )
                """
            ),
            {"courier_id": str(cid)},
        )

        db.add(
            WeekPayout(
                week_id=w.id,
                courier_id=cid,
                rides_amount=r["rides_amount"],
                extras_amount=r["extras_amount"],
                vales_amount=r["vales_amount"],
                installments_amount=r["installments_amount"],
                net_amount=r["net_amount"],
                pending_count=r["pending_count"],
                is_flag_red=bool(r.get("is_flag_red")),
            )
        )

    w.status = "CLOSED"
    db.commit()

    return {"ok": True, "week_id": str(w.id), "status": w.status, "payouts": len(rows)}


def pay_week(db: Session, week_id: str) -> Dict[str, Any]:
    w = get_week_or_404(db, week_id)
    if w.status != "CLOSED":
        raise HTTPException(status_code=409, detail={"error": "WEEK_NOT_CLOSED", "status": w.status})

    now = dt.datetime.now(dt.timezone.utc)

    w.status = "PAID"
    db.query(WeekPayout).filter(WeekPayout.week_id == w.id).update({WeekPayout.paid_at: now})
    db.commit()

    return {"ok": True, "week_id": str(w.id), "status": w.status, "paid_at": now.isoformat()}


def get_payout_snapshot(db: Session, week_id: str) -> List[Dict[str, Any]]:
    w = get_week_or_404(db, week_id)
    rows = (
        db.query(
            WeekPayout,
            Courier.nome_resumido.label("courier_nome"),
        )
        .join(Courier, Courier.id == WeekPayout.courier_id)
        .filter(WeekPayout.week_id == w.id)
        .order_by(Courier.nome_resumido.asc())
        .all()
    )

    out: List[Dict[str, Any]] = []
    for wp, nome in rows:
        out.append(
            {
                "week_id": str(w.id),
                "courier_id": str(wp.courier_id),
                "courier_nome": nome,
                "rides_amount": float(wp.rides_amount),
                "extras_amount": float(wp.extras_amount),
                "vales_amount": float(wp.vales_amount),
                "installments_amount": float(wp.installments_amount),
                "net_amount": float(wp.net_amount),
                "pending_count": int(wp.pending_count),
                "is_flag_red": bool(wp.is_flag_red),
                "computed_at": wp.computed_at.isoformat() if wp.computed_at else None,
                "paid_at": wp.paid_at.isoformat() if wp.paid_at else None,
            }
        )
    return out
