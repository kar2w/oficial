import datetime as dt

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Ride, Week, YoogaReviewGroup, YoogaReviewItem
from app.services.week_service import get_open_week_for_date


def list_assignment(db: Session, week_id: str | None = None, source: str | None = None):
    q = db.query(Ride).filter(Ride.status == "PENDENTE_ATRIBUICAO")
    if week_id:
        q = q.filter(Ride.week_id == week_id)
    if source:
        q = q.filter(Ride.source == source)
    return q.order_by(Ride.order_dt.asc()).all()


def assign_ride(db: Session, ride_id: str, courier_id: str, pay_in_current_week: bool = True):
    ride = db.query(Ride).filter(Ride.id == ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="ride not found")

    ride.courier_id = courier_id
    ride.status = "OK"
    ride.pending_reason = None

    week = db.query(Week).filter(Week.id == ride.week_id).first()
    if not week:
        raise HTTPException(status_code=400, detail="week not found")

    if week.status in ("CLOSED", "PAID") and pay_in_current_week:
        current = get_open_week_for_date(db, dt.date.today())
        ride.paid_in_week_id = current.id
        meta = dict(ride.meta or {})
        meta["late_assignment"] = {
            "at": dt.datetime.now().isoformat(timespec="seconds"),
            "original_week_id": str(ride.week_id),
            "paid_in_week_id": str(current.id),
        }
        ride.meta = meta

    db.commit()
    return ride


def list_yooga_groups(db: Session, week_id: str | None = None, source: str | None = None):
    q = (
        db.query(
            YoogaReviewGroup.id.label("group_id"),
            YoogaReviewGroup.week_id.label("week_id"),
            YoogaReviewGroup.signature_key.label("signature_key"),
            func.count(YoogaReviewItem.ride_id).label("items"),
        )
        .join(YoogaReviewItem, YoogaReviewItem.group_id == YoogaReviewGroup.id)
        .join(Ride, Ride.id == YoogaReviewItem.ride_id)
        .filter(YoogaReviewGroup.status == "PENDING")
    )
    if week_id:
        q = q.filter(YoogaReviewGroup.week_id == week_id)
    if source:
        q = q.filter(Ride.source == source)

    rows = q.group_by(YoogaReviewGroup.id, YoogaReviewGroup.week_id, YoogaReviewGroup.signature_key).order_by(YoogaReviewGroup.id.desc()).all()

    return [
        {"group_id": str(r.group_id), "week_id": str(r.week_id), "signature_key": r.signature_key, "items": int(r.items or 0)}
        for r in rows
    ]


def yooga_group_items(db: Session, group_id: str):
    return (
        db.query(Ride)
        .join(YoogaReviewItem, YoogaReviewItem.ride_id == Ride.id)
        .filter(YoogaReviewItem.group_id == group_id)
        .order_by(Ride.order_dt.asc(), Ride.delivery_dt.asc())
        .all()
    )


def resolve_yooga(db: Session, group_id: str, action: str, keep_ride_id: str | None):
    grp = db.query(YoogaReviewGroup).filter(YoogaReviewGroup.id == group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="group not found")

    rides = yooga_group_items(db, group_id)
    if action == "APPROVE_ALL":
        for r in rides:
            if r.status == "PENDENTE_REVISAO":
                if r.courier_id is not None:
                    r.status = "OK"
                    r.pending_reason = None
                else:
                    r.status = "PENDENTE_ATRIBUICAO"
                    r.pending_reason = "NOME_NAO_CADASTRADO"
        grp.status = "RESOLVED"
        db.commit()
        return {"ok": True, "resolved": "APPROVE_ALL"}

    if action == "KEEP_ONE":
        if not keep_ride_id:
            raise HTTPException(status_code=400, detail="keep_ride_id required")
        for r in rides:
            if str(r.id) == keep_ride_id:
                if r.courier_id is not None:
                    r.status = "OK"
                    r.pending_reason = None
                else:
                    r.status = "PENDENTE_ATRIBUICAO"
                    r.pending_reason = "NOME_NAO_CADASTRADO"
            else:
                r.status = "DESCARTADO"
                r.pending_reason = None
        grp.status = "RESOLVED"
        db.commit()
        return {"ok": True, "resolved": "KEEP_ONE"}

    raise HTTPException(status_code=400, detail="invalid action")
