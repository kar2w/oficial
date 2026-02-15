import datetime as dt
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Ride, Week, LedgerEntry, YoogaReviewGroup, YoogaReviewItem
from app.services.week_service import get_current_week


def list_assignment(db: Session):
    return db.query(Ride).filter(Ride.status=="PENDENTE_ATRIBUICAO").order_by(Ride.order_dt.asc()).all()

def assign_ride(db: Session, ride_id: str, courier_id: str, pay_in_current_week: bool = True):
    ride = db.query(Ride).filter(Ride.id==ride_id).first()
    if not ride:
        raise HTTPException(status_code=404, detail="ride not found")

    ride.courier_id = courier_id
    ride.status = "OK"
    ride.pending_reason = None

    week = db.query(Week).filter(Week.id==ride.week_id).first()
    if not week:
        raise HTTPException(status_code=400, detail="week not found")

    if week.status in ("CLOSED","PAID") and pay_in_current_week:
        current = get_current_week(db, dt.date.today())
        le = LedgerEntry(
            courier_id=courier_id,
            week_id=current.id,
            effective_date=dt.date.today(),
            type="EXTRA",
            amount=float(ride.fee_type),
            related_ride_id=ride.id,
            note=f"Corrida atribuída tardiamente (origem week_id={ride.week_id})",
        )
        db.add(le)
        ride.paid_in_week_id = current.id

    db.commit()
    return ride

def list_yooga_groups(db: Session):
    groups = db.query(YoogaReviewGroup).filter(YoogaReviewGroup.status=="PENDING").order_by(YoogaReviewGroup.id.desc()).all()
    out = []
    for g in groups:
        count = db.query(YoogaReviewItem).filter(YoogaReviewItem.group_id==g.id).count()
        out.append({"group_id": str(g.id), "week_id": str(g.week_id), "signature_key": g.signature_key, "items": count})
    return out

def yooga_group_items(db: Session, group_id: str):
    items = db.query(YoogaReviewItem).filter(YoogaReviewItem.group_id==group_id).all()
    rides = []
    for it in items:
        r = db.query(Ride).filter(Ride.id==it.ride_id).first()
        if r:
            rides.append(r)
    rides.sort(key=lambda x: (x.order_dt, x.delivery_dt or x.order_dt))
    return rides

def resolve_yooga(db: Session, group_id: str, action: str, keep_ride_id: str | None):
    grp = db.query(YoogaReviewGroup).filter(YoogaReviewGroup.id==group_id).first()
    if not grp:
        raise HTTPException(status_code=404, detail="group not found")

    rides = yooga_group_items(db, group_id)
    if action == "APPROVE_ALL":
        for r in rides:
            if r.status == "PENDENTE_REVISAO":
                # Only OK if courier is already known; otherwise it must go back to assignment.
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

        keep_ride = next((r for r in rides if str(r.id) == keep_ride_id), None)
        if keep_ride is None:
            raise HTTPException(status_code=400, detail="keep_ride_id not found in group")

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
