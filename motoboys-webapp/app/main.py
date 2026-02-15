import datetime as dt
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from sqlalchemy import func, text as sa_text
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CourierAlias, CourierPayment, Import, Ride
from app.schemas import (
    AssignRideBody,
    CourierAliasCreate,
    CourierAliasOut,
    CourierCreate,
    CourierOut,
    CourierPatch,
    CourierPaymentIn,
    CourierPaymentOut,
    ImportResponse,
    LedgerEntryCreate,
    LedgerEntryOut,
    LedgerCreateOut,
    ResolveYoogaBody,
    SeedRequest,
    WeekPayoutPreviewRow,
    WeekPayoutSnapshotRow,
)
from app.services.couriers import add_alias, create_courier, delete_alias, list_couriers, patch_courier, upsert_payment
from app.services.import_saipos import import_saipos
from app.services.import_yooga import import_yooga
from app.services.ledger import create_ledger_entry, delete_ledger_entry, list_week_ledger
from app.services.payouts import close_week, compute_week_payout_preview, get_payout_snapshot, get_week_or_404, pay_week
from app.services.pendings import assign_ride, list_assignment, list_yooga_groups, resolve_yooga, yooga_group_items
from app.services.seed import seed_weekly_couriers
from app.services.utils import read_upload_bytes, sha256_bytes
from app.services.week_service import get_current_week, get_open_week_for_date
from app.settings import settings
from app.web.router import router as web_router

app = FastAPI(title="Motoboys WebApp API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# -------------------------
# Web UI (Jinja2 + HTMX)
# -------------------------
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "web" / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(web_router)

@app.get("/", include_in_schema=False)
def root_redirect():
    return RedirectResponse(url="/ui/imports/new", status_code=302)


def _couriers_to_out(db: Session, couriers):
    ids = [c.id for c in couriers]
    aliases_by: dict = {str(i): [] for i in ids}
    payment_by: dict = {}
    if ids:
        for a in db.query(CourierAlias).filter(CourierAlias.courier_id.in_(ids)).all():
            aliases_by.setdefault(str(a.courier_id), []).append(
                CourierAliasOut(
                    id=str(a.id),
                    courier_id=str(a.courier_id),
                    alias_raw=a.alias_raw,
                    alias_norm=a.alias_norm,
                )
            )
        for p in db.query(CourierPayment).filter(CourierPayment.courier_id.in_(ids)).all():
            payment_by[str(p.courier_id)] = CourierPaymentOut(
                courier_id=str(p.courier_id),
                key_type=p.key_type,
                key_value_raw=p.key_value_raw,
                bank=p.bank,
            )

    out = []
    for c in couriers:
        out.append(
            CourierOut(
                id=str(c.id),
                nome_resumido=c.nome_resumido,
                nome_completo=c.nome_completo,
                categoria=c.categoria,
                active=c.active,
                payment=payment_by.get(str(c.id)),
                aliases=sorted(aliases_by.get(str(c.id), []), key=lambda x: x.alias_raw.upper()),
            )
        )
    return out


@app.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(sa_text("SELECT 1"))
    return {"ok": True}


@app.get("/couriers", response_model=list[CourierOut])
def couriers_list(
    active: bool | None = Query(default=None),
    categoria: str | None = Query(default=None, description="SEMANAL|DIARISTA"),
    q: str | None = Query(default=None, description="search by nome_resumido"),
    db: Session = Depends(get_db),
):
    rows = list_couriers(db, active=active, categoria=categoria, q=q)
    return _couriers_to_out(db, rows)


@app.post("/couriers", response_model=CourierOut)
def couriers_create(body: CourierCreate, db: Session = Depends(get_db)):
    c = create_courier(
        db,
        nome_resumido=body.nome_resumido,
        nome_completo=body.nome_completo,
        categoria=body.categoria,
        active=body.active,
    )
    return _couriers_to_out(db, [c])[0]


@app.patch("/couriers/{courier_id}", response_model=CourierOut)
def couriers_patch(courier_id: str, body: CourierPatch, db: Session = Depends(get_db)):
    c = patch_courier(
        db,
        courier_id,
        nome_resumido=body.nome_resumido,
        nome_completo=body.nome_completo,
        categoria=body.categoria,
        active=body.active,
    )
    return _couriers_to_out(db, [c])[0]


@app.post("/couriers/{courier_id}/aliases", response_model=CourierAliasOut)
def couriers_add_alias(courier_id: str, body: CourierAliasCreate, db: Session = Depends(get_db)):
    a = add_alias(db, courier_id=courier_id, alias_raw=body.alias_raw)
    return CourierAliasOut(id=str(a.id), courier_id=str(a.courier_id), alias_raw=a.alias_raw, alias_norm=a.alias_norm)


@app.delete("/couriers/{courier_id}/aliases/{alias_id}")
def couriers_delete_alias(courier_id: str, alias_id: str, db: Session = Depends(get_db)):
    delete_alias(db, courier_id=courier_id, alias_id=alias_id)
    return {"ok": True}


@app.put("/couriers/{courier_id}/payment", response_model=CourierPaymentOut)
def couriers_put_payment(courier_id: str, body: CourierPaymentIn, db: Session = Depends(get_db)):
    p = upsert_payment(db, courier_id=courier_id, key_type=body.key_type, key_value_raw=body.key_value_raw, bank=body.bank)
    return CourierPaymentOut(courier_id=str(p.courier_id), key_type=p.key_type, key_value_raw=p.key_value_raw, bank=p.bank)


@app.get("/weeks")
def list_weeks(db: Session = Depends(get_db)):
    rows = db.execute(
        sa_text(
            """SELECT id, start_date, end_date, status, closing_seq
             FROM weeks
             ORDER BY start_date DESC"""
        )
    ).mappings().all()
    return [dict(r) for r in rows]


@app.get("/weeks/current")
def current_week(db: Session = Depends(get_db)):
    w = get_current_week(db, dt.date.today())
    return {"id": str(w.id), "start_date": str(w.start_date), "end_date": str(w.end_date), "status": w.status}


@app.get("/weeks/{week_id}/payouts/preview", response_model=list[WeekPayoutPreviewRow])
def week_payout_preview(week_id: str, db: Session = Depends(get_db)):
    rows = compute_week_payout_preview(db, week_id)
    return [
        WeekPayoutPreviewRow(
            courier_id=str(r.get("courier_id")) if r.get("courier_id") is not None else None,
            courier_nome=r.get("courier_nome"),
            rides_count=int(r.get("rides_count") or 0),
            rides_amount=float(r.get("rides_amount") or 0),
            rides_value_raw_amount=float(r.get("rides_value_raw_amount") or 0),
            extras_amount=float(r.get("extras_amount") or 0),
            vales_amount=float(r.get("vales_amount") or 0),
            installments_amount=float(r.get("installments_amount") or 0),
            net_amount=float(r.get("net_amount") or 0),
            pending_count=int(r.get("pending_count") or 0),
            is_flag_red=bool(r.get("is_flag_red") or False),
        )
        for r in rows
    ]


@app.post("/weeks/{week_id}/close")
def week_close(week_id: str, db: Session = Depends(get_db)):
    return close_week(db, week_id)


@app.post("/weeks/{week_id}/pay")
def week_pay(week_id: str, db: Session = Depends(get_db)):
    return pay_week(db, week_id)


@app.get("/weeks/{week_id}/payouts", response_model=list[WeekPayoutSnapshotRow])
def week_payout_snapshot(week_id: str, db: Session = Depends(get_db)):
    rows = get_payout_snapshot(db, week_id)
    return [
        WeekPayoutSnapshotRow(
            courier_id=r["courier_id"],
            courier_nome=r["courier_nome"],
            rides_amount=float(r["rides_amount"]),
            extras_amount=float(r["extras_amount"]),
            vales_amount=float(r["vales_amount"]),
            installments_amount=float(r["installments_amount"]),
            net_amount=float(r["net_amount"]),
            pending_count=int(r["pending_count"]),
            is_flag_red=bool(r["is_flag_red"]),
            computed_at=r.get("computed_at") or "",
            paid_at=r.get("paid_at"),
        )
        for r in rows
    ]


@app.get("/weeks/{week_id}/payouts.csv")
def week_payout_csv(week_id: str, db: Session = Depends(get_db)):
    import csv
    import io

    w = get_week_or_404(db, week_id)
    if w.status in ("CLOSED", "PAID"):
        rows = get_payout_snapshot(db, week_id)
        header = [
            "courier_nome",
            "courier_id",
            "rides_amount",
            "extras_amount",
            "vales_amount",
            "installments_amount",
            "net_amount",
            "pending_count",
            "is_flag_red",
            "computed_at",
            "paid_at",
        ]
        data_rows = [
            {
                "courier_nome": r["courier_nome"],
                "courier_id": r["courier_id"],
                "rides_amount": r["rides_amount"],
                "extras_amount": r["extras_amount"],
                "vales_amount": r["vales_amount"],
                "installments_amount": r["installments_amount"],
                "net_amount": r["net_amount"],
                "pending_count": r["pending_count"],
                "is_flag_red": r.get("is_flag_red"),
                "computed_at": r.get("computed_at"),
                "paid_at": r.get("paid_at"),
            }
            for r in rows
        ]
    else:
        rows = compute_week_payout_preview(db, week_id)
        header = [
            "courier_nome",
            "courier_id",
            "rides_count",
            "rides_amount",
            "extras_amount",
            "vales_amount",
            "installments_amount",
            "net_amount",
            "pending_count",
            "is_flag_red",
        ]
        data_rows = [
            {
                "courier_nome": r.get("courier_nome"),
                "courier_id": str(r.get("courier_id")) if r.get("courier_id") is not None else "",
                "rides_count": r.get("rides_count"),
                "rides_amount": r.get("rides_amount"),
                "extras_amount": r.get("extras_amount"),
                "vales_amount": r.get("vales_amount"),
                "installments_amount": r.get("installments_amount"),
                "net_amount": r.get("net_amount"),
                "pending_count": r.get("pending_count"),
                "is_flag_red": r.get("is_flag_red"),
            }
            for r in rows
        ]

    buf = io.StringIO()
    wr = csv.DictWriter(buf, fieldnames=header)
    wr.writeheader()
    for row in data_rows:
        wr.writerow(row)

    filename = f"week_{w.start_date}_to_{w.end_date}_payouts.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/weeks/{week_id}/ledger", response_model=list[LedgerEntryOut])
def week_ledger(week_id: str, courier_id: str | None = Query(default=None), db: Session = Depends(get_db)):
    return list_week_ledger(db, week_id=week_id, courier_id=courier_id)


@app.post("/ledger", response_model=LedgerCreateOut)
def ledger_create(body: LedgerEntryCreate, db: Session = Depends(get_db)):
    return create_ledger_entry(
        db,
        courier_id=body.courier_id,
        week_id=body.week_id,
        effective_date=body.effective_date,
        type=body.type,
        amount=body.amount,
        related_ride_id=body.related_ride_id,
        note=body.note,
    )


@app.delete("/ledger/{ledger_id}")
def ledger_delete(ledger_id: str, db: Session = Depends(get_db)):
    return delete_ledger_entry(db, ledger_id)


@app.post("/imports", response_model=ImportResponse)
async def do_import(source: str = Form(...), file: UploadFile = File(...), db: Session = Depends(get_db)):
    source = source.upper().strip()
    if source not in ("SAIPOS", "YOOGA"):
        raise HTTPException(status_code=400, detail="source must be SAIPOS or YOOGA")

    data = await read_upload_bytes(file)
    file_hash = sha256_bytes(data)

    if source == "SAIPOS":
        import_id, inserted, pend_assign, pend_review, redirected_closed_week, week_ids_touched = import_saipos(db, data, file.filename, file_hash)
    else:
        import_id, inserted, pend_assign, pend_review, redirected_closed_week, week_ids_touched = import_yooga(db, data, file.filename, file_hash)

    return ImportResponse(
        import_id=import_id,
        source=source,
        filename=file.filename,
        inserted=inserted,
        pendente_atribuicao=pend_assign,
        pendente_revisao=pend_review,
        redirected_closed_week=redirected_closed_week,
        week_ids_touched=week_ids_touched,
    )


@app.get("/imports")
def list_imports(
    source: str | None = Query(default=None),
    after: str | None = Query(default=None),
    before: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Import)
    if source:
        q = q.filter(Import.source == source.upper().strip())
    if after:
        q = q.filter(Import.imported_at >= after)
    if before:
        q = q.filter(Import.imported_at <= before)

    rows = q.order_by(Import.imported_at.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": str(i.id),
            "source": i.source,
            "filename": i.filename,
            "imported_at": i.imported_at.isoformat() if i.imported_at else None,
            "meta": i.meta or {},
            "status": i.status,
        }
        for i in rows
    ]


@app.get("/imports/{import_id}")
def get_import_detail(import_id: str, db: Session = Depends(get_db)):
    imp = db.query(Import).filter(Import.id == import_id).first()
    if not imp:
        raise HTTPException(status_code=404, detail="import not found")

    counts = dict(db.query(Ride.status, func.count(Ride.id)).filter(Ride.import_id == imp.id).group_by(Ride.status).all())
    return {
        "id": str(imp.id),
        "source": imp.source,
        "filename": imp.filename,
        "imported_at": imp.imported_at.isoformat() if imp.imported_at else None,
        "meta": imp.meta or {},
        "status": imp.status,
        "counts": {
            "inserted_ok": int(counts.get("OK", 0)),
            "pending_assignment": int(counts.get("PENDENTE_ATRIBUICAO", 0)),
            "pending_review": int(counts.get("PENDENTE_REVISAO", 0)),
            "discarded": int(counts.get("DESCARTADO", 0)),
        },
    }


@app.get("/pendings/assignment")
def pendings_assignment(
    week_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not week_id:
        week_id = str(get_open_week_for_date(db, dt.date.today()).id)
    rides = list_assignment(db, week_id=week_id, source=source)
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "order_dt": r.order_dt.isoformat(),
            "order_date": str(r.order_date),
            "value_raw": float(r.value_raw),
            "fee_type": r.fee_type,
            "courier_name_raw": r.courier_name_raw,
            "pending_reason": r.pending_reason,
            "week_id": str(r.week_id),
        }
        for r in rides
    ]


@app.post("/pendings/assignment/{ride_id}/assign")
def pendings_assign(ride_id: str, body: AssignRideBody, db: Session = Depends(get_db)):
    r = assign_ride(db, ride_id=ride_id, courier_id=body.courier_id, pay_in_current_week=body.pay_in_current_week)
    return {"ok": True, "ride_id": str(r.id), "paid_in_week_id": str(r.paid_in_week_id) if r.paid_in_week_id else None}


@app.get("/pendings/yooga")
def pendings_yooga(
    week_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not week_id:
        week_id = str(get_open_week_for_date(db, dt.date.today()).id)
    return list_yooga_groups(db, week_id=week_id, source=source)


@app.get("/pendings/yooga/{group_id}")
def pendings_yooga_items(group_id: str, db: Session = Depends(get_db)):
    rides = yooga_group_items(db, group_id)
    return [
        {
            "id": str(r.id),
            "order_dt": r.order_dt.isoformat(),
            "delivery_dt": r.delivery_dt.isoformat() if r.delivery_dt else None,
            "courier_name_raw": r.courier_name_raw,
            "value_raw": float(r.value_raw),
            "fee_type": r.fee_type,
            "status": r.status,
            "pending_reason": r.pending_reason,
            "courier_id": str(r.courier_id) if r.courier_id else None,
            "week_id": str(r.week_id),
        }
        for r in rides
    ]


@app.post("/pendings/yooga/{group_id}/resolve")
def pendings_yooga_resolve(group_id: str, body: ResolveYoogaBody, db: Session = Depends(get_db)):
    return resolve_yooga(db, group_id=group_id, action=body.action, keep_ride_id=body.keep_ride_id)


@app.get("/rides")
def list_rides(
    week_id: str | None = Query(default=None),
    courier_id: str | None = Query(default=None),
    status: str | None = Query(default=None),
    date: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    q = db.query(Ride)
    if week_id:
        q = q.filter(Ride.week_id == week_id)
    if courier_id:
        q = q.filter(Ride.courier_id == courier_id)
    if status:
        q = q.filter(Ride.status == status)
    if date:
        q = q.filter(Ride.order_date == date)

    rows = q.order_by(Ride.order_dt.desc()).offset(offset).limit(limit).all()
    return [
        {
            "id": str(r.id),
            "source": r.source,
            "import_id": str(r.import_id),
            "order_dt": r.order_dt.isoformat(),
            "delivery_dt": r.delivery_dt.isoformat() if r.delivery_dt else None,
            "order_date": str(r.order_date),
            "week_id": str(r.week_id),
            "paid_in_week_id": str(r.paid_in_week_id) if r.paid_in_week_id else None,
            "courier_id": str(r.courier_id) if r.courier_id else None,
            "courier_name_raw": r.courier_name_raw,
            "value_raw": float(r.value_raw),
            "fee_type": int(r.fee_type),
            "status": r.status,
            "pending_reason": r.pending_reason,
        }
        for r in rows
    ]


@app.get("/weeks/{week_id}/couriers/{courier_id}/breakdown")
def week_courier_breakdown(week_id: str, courier_id: str, db: Session = Depends(get_db)):
    rides = db.execute(
        sa_text(
            """
            SELECT id, source, order_dt, value_raw, fee_type, status, week_id, paid_in_week_id
            FROM rides
            WHERE courier_id = :courier_id
              AND ((week_id = :week_id AND paid_in_week_id IS NULL) OR paid_in_week_id = :week_id)
              AND (is_cancelled IS NULL OR is_cancelled = false)
            ORDER BY order_dt ASC
            """
        ),
        {"courier_id": courier_id, "week_id": week_id},
    ).mappings().all()

    ledger_entries = db.execute(
        sa_text(
            """
            SELECT id, effective_date, type, amount, note
            FROM ledger_entries
            WHERE courier_id = :courier_id AND week_id = :week_id
            ORDER BY effective_date ASC
            """
        ),
        {"courier_id": courier_id, "week_id": week_id},
    ).mappings().all()

    week = get_week_or_404(db, week_id)
    installments_due = db.execute(
        sa_text(
            """
            SELECT li.id, li.installment_no, li.due_closing_seq, li.amount, li.paid_amount, li.status
            FROM loan_installments li
            JOIN loan_plans lp ON lp.id = li.plan_id
            WHERE lp.courier_id = :courier_id
              AND lp.status = 'ACTIVE'
              AND li.status IN ('DUE','ROLLED','PARTIAL')
              AND li.due_closing_seq <= :closing_seq
            ORDER BY li.due_closing_seq ASC, li.installment_no ASC
            """
        ),
        {"courier_id": courier_id, "closing_seq": int(week.closing_seq)},
    ).mappings().all()

    rides_amount = float(sum(float(r["fee_type"] or 0) for r in rides))
    extras_amount = float(sum(float(l["amount"] or 0) for l in ledger_entries if l["type"] == "EXTRA"))
    vales_amount = float(sum(float(l["amount"] or 0) for l in ledger_entries if l["type"] == "VALE"))
    installments_due_amount = float(sum(max(0.0, float(i["amount"] or 0) - float(i["paid_amount"] or 0)) for i in installments_due))
    pre_net = rides_amount + extras_amount - vales_amount
    installments_applied = max(0.0, min(pre_net, installments_due_amount))

    return {
        "week_id": week_id,
        "courier_id": courier_id,
        "rides": [dict(r) for r in rides],
        "ledger_entries": [dict(l) for l in ledger_entries],
        "installments_due": [
            {**dict(i), "remaining_amount": max(0.0, float(i["amount"] or 0) - float(i["paid_amount"] or 0))} for i in installments_due
        ],
        "preview": {
            "rides_amount": rides_amount,
            "extras_amount": extras_amount,
            "vales_amount": vales_amount,
            "installments_due_amount": installments_due_amount,
            "installments_applied_amount": installments_applied,
            "net_amount": pre_net - installments_applied,
        },
    }


@app.post("/seed/weekly-couriers")
def seed_weekly(body: SeedRequest, db: Session = Depends(get_db)):
    return seed_weekly_couriers(db, payload=body.model_dump())


@app.post("/seed/weekly-couriers/from-file")
def seed_weekly_from_file(db: Session = Depends(get_db)):
    import json
    from pathlib import Path

    path = Path(settings.WEEKLY_COURIERS_JSON_PATH)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Seed file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload = {"entregadores": payload}
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid weekly couriers file format")
    return seed_weekly_couriers(db, payload=payload)
