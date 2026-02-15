import datetime as dt
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text as sa_text

from app.db import get_db
from app.models import Import, Ride, Courier, CourierAlias, CourierPayment
from app.services.couriers import create_courier, list_couriers, patch_courier, add_alias, delete_alias, upsert_payment
from app.services.import_saipos import import_saipos
from app.services.import_yooga import import_yooga
from app.services.payouts import close_week, compute_week_payout_preview, pay_week, get_week_or_404
from app.services.pendings import list_assignment, assign_ride, list_yooga_groups, yooga_group_items, resolve_yooga
from app.services.utils import read_upload_bytes, sha256_bytes
from app.services.week_service import get_open_week_for_date
from app.schemas import CourierPaymentIn

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router = APIRouter(prefix="/ui", include_in_schema=False)


def _ui_redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def _list_weeks(db: Session):
    rows = db.execute(sa_text(
        """
        SELECT id, start_date, end_date, status, closing_seq
        FROM weeks
        ORDER BY start_date DESC
        """
    )).mappings().all()
    return [dict(r) for r in rows]


@router.get("/", response_class=HTMLResponse)
def ui_home():
    return _ui_redirect("/ui/imports/new")


# -----------------------------
# Imports UI
# -----------------------------
@router.get("/imports/new", response_class=HTMLResponse)
def imports_new(request: Request):
    return templates.TemplateResponse(
        "imports_new.html",
        {"request": request, "result": None},
    )


@router.post("/imports/new", response_class=HTMLResponse)
async def imports_new_post(
    request: Request,
    source: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    source = source.upper().strip()
    if source not in ("SAIPOS", "YOOGA"):
        raise HTTPException(status_code=400, detail="source must be SAIPOS or YOOGA")

    data = await read_upload_bytes(file)
    file_hash = sha256_bytes(data)

    if source == "SAIPOS":
        import_id, inserted, pend_assign, pend_review, redirected_closed_week, week_ids_touched = import_saipos(
            db, data, file.filename, file_hash
        )
    else:
        import_id, inserted, pend_assign, pend_review, redirected_closed_week, week_ids_touched = import_yooga(
            db, data, file.filename, file_hash
        )

    result = {
        "import_id": import_id,
        "source": source,
        "filename": file.filename,
        "inserted": inserted,
        "pendente_atribuicao": pend_assign,
        "pendente_revisao": pend_review,
        "redirected_closed_week": redirected_closed_week,
        "week_ids_touched": week_ids_touched,
    }

    return templates.TemplateResponse(
        "imports_new.html",
        {"request": request, "result": result},
    )


@router.get("/imports", response_class=HTMLResponse)
def imports_list(
    request: Request,
    source: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Import)
    if source:
        q = q.filter(Import.source == source.upper().strip())
    rows = q.order_by(Import.imported_at.desc()).limit(limit).all()
    imports = [
        {
            "id": str(i.id),
            "source": i.source,
            "filename": i.filename,
            "imported_at": i.imported_at.isoformat(timespec="seconds") if i.imported_at else None,
            "status": i.status,
        }
        for i in rows
    ]
    return templates.TemplateResponse(
        "imports_list.html",
        {"request": request, "imports": imports, "source": (source or "")},
    )


@router.get("/imports/{import_id}", response_class=HTMLResponse)
def imports_detail(request: Request, import_id: str, db: Session = Depends(get_db)):
    imp = db.query(Import).filter(Import.id == import_id).first()
    if not imp:
        raise HTTPException(status_code=404, detail="import not found")

    counts = dict(
        db.query(Ride.status, func.count(Ride.id)).filter(Ride.import_id == imp.id).group_by(Ride.status).all()
    )
    detail = {
        "id": str(imp.id),
        "source": imp.source,
        "filename": imp.filename,
        "imported_at": imp.imported_at.isoformat(timespec="seconds") if imp.imported_at else None,
        "status": imp.status,
        "counts": {k: int(v) for k, v in counts.items()},
        "meta": imp.meta or {},
    }
    return templates.TemplateResponse("imports_detail.html", {"request": request, "imp": detail})


# -----------------------------
# Pendências UI
# -----------------------------
@router.get("/pendencias", response_class=HTMLResponse)
def pendencias(
    request: Request,
    tab: str = Query(default="atribuicao"),
    week_id: str | None = Query(default=None),
    source: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not week_id:
        week_id = str(get_open_week_for_date(db, dt.date.today()).id)

    weeks = _list_weeks(db)

    couriers = list_couriers(db, active=True, categoria=None, q=None)
    courier_opts = [{"id": str(c.id), "nome": c.nome_resumido, "categoria": c.categoria} for c in couriers]

    assignment_items = []
    yooga_groups = []
    yooga_first_group_id = None
    yooga_items = []

    if tab == "yooga":
        yooga_groups = list_yooga_groups(db, week_id=week_id, source=source)
        if yooga_groups:
            yooga_first_group_id = yooga_groups[0]["group_id"]
            yooga_items_models = yooga_group_items(db, yooga_first_group_id)
            yooga_items = [
                {
                    "id": str(r.id),
                    "order_dt": r.order_dt.isoformat(timespec="seconds"),
                    "delivery_dt": r.delivery_dt.isoformat(timespec="seconds") if r.delivery_dt else None,
                    "courier_name_raw": r.courier_name_raw,
                    "value_raw": float(r.value_raw),
                    "fee_type": r.fee_type,
                    "status": r.status,
                    "pending_reason": r.pending_reason,
                    "courier_id": str(r.courier_id) if r.courier_id else None,
                }
                for r in yooga_items_models
            ]
    else:
        rides = list_assignment(db, week_id=week_id, source=source)
        assignment_items = [
            {
                "id": str(r.id),
                "source": r.source,
                "order_dt": r.order_dt.isoformat(timespec="seconds"),
                "order_date": str(r.order_date),
                "value_raw": float(r.value_raw),
                "fee_type": r.fee_type,
                "courier_name_raw": r.courier_name_raw,
                "pending_reason": r.pending_reason,
            }
            for r in rides
        ]

    return templates.TemplateResponse(
        "pendencias.html",
        {
            "request": request,
            "tab": tab,
            "weeks": weeks,
            "week_id": week_id,
            "source": source,
            "assignment_items": assignment_items,
            "courier_opts": courier_opts,
            "yooga_groups": yooga_groups,
            "yooga_first_group_id": yooga_first_group_id,
            "yooga_items": yooga_items,
        },
    )


@router.post("/pendencias/assign", response_class=HTMLResponse)
def pendencias_assign(
    request: Request,
    ride_id: str = Form(...),
    courier_id: str = Form(...),
    pay_in_current_week: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    try:
        assign_ride(db, ride_id=ride_id, courier_id=courier_id, pay_in_current_week=pay_in_current_week)
        return templates.TemplateResponse(
            "partials/assignment_row_done.html",
            {"request": request, "ride_id": ride_id},
        )
    except Exception as e:
        return templates.TemplateResponse(
            "partials/assignment_row_error.html",
            {"request": request, "ride_id": ride_id, "error": str(e)},
        )


@router.get("/pendencias/yooga/{group_id}", response_class=HTMLResponse)
def pendencias_yooga_group(
    request: Request,
    group_id: str,
    week_id: str = Query(...),
    db: Session = Depends(get_db),
):
    items_models = yooga_group_items(db, group_id)
    items = [
        {
            "id": str(r.id),
            "order_dt": r.order_dt.isoformat(timespec="seconds"),
            "delivery_dt": r.delivery_dt.isoformat(timespec="seconds") if r.delivery_dt else None,
            "courier_name_raw": r.courier_name_raw,
            "value_raw": float(r.value_raw),
            "fee_type": r.fee_type,
            "status": r.status,
            "pending_reason": r.pending_reason,
            "courier_id": str(r.courier_id) if r.courier_id else None,
        }
        for r in items_models
    ]

    return templates.TemplateResponse(
        "partials/yooga_detail.html",
        {"request": request, "group_id": group_id, "items": items, "week_id": week_id},
    )


@router.post("/pendencias/yooga/{group_id}/resolve", response_class=HTMLResponse)
def pendencias_yooga_resolve(
    request: Request,
    group_id: str,
    week_id: str = Form(...),
    action: str = Form(...),
    keep_ride_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    # action: APPROVE_ALL | KEEP_ONE
    resolve_yooga(db, group_id=group_id, action=action, keep_ride_id=keep_ride_id)
    return _ui_redirect(f"/ui/pendencias?tab=yooga&week_id={week_id}&ok=1")


# -----------------------------
# Weeks UI
# -----------------------------
@router.get("/weeks/current", response_class=HTMLResponse)
def weeks_current(
    request: Request,
    week_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    weeks = _list_weeks(db)
    if not week_id:
        wk = get_open_week_for_date(db, dt.date.today())
        week_id = str(wk.id)

    week = get_week_or_404(db, week_id)

    preview = compute_week_payout_preview(db, week_id=week_id)
    rows = []
    pending_total = 0
    for r in preview["rows"]:
        pending_total += int(r.get("pending_count") or 0)
        rows.append(r)

    return templates.TemplateResponse(
        "week_current.html",
        {
            "request": request,
            "weeks": weeks,
            "week_id": week_id,
            "week": week,
            "rows": rows,
            "pending_total": pending_total,
        },
    )


@router.post("/weeks/{week_id}/close")
def weeks_close_ui(week_id: str, db: Session = Depends(get_db)):
    close_week(db, week_id=week_id)
    return _ui_redirect(f"/ui/weeks/current?week_id={week_id}&ok=1")


@router.post("/weeks/{week_id}/pay")
def weeks_pay_ui(week_id: str, db: Session = Depends(get_db)):
    pay_week(db, week_id=week_id)
    return _ui_redirect(f"/ui/weeks/current?week_id={week_id}&ok=1")


# -----------------------------
# Couriers UI
# -----------------------------
@router.get("/couriers", response_class=HTMLResponse)
def couriers_list_ui(
    request: Request,
    q: str | None = Query(default=None),
    active: bool | None = Query(default=True),
    categoria: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    couriers = list_couriers(db, active=active, categoria=categoria, q=q)
    rows = []
    for c in couriers:
        payment = db.query(CourierPayment).filter_by(courier_id=c.id).first()
        rows.append(
            {
                "id": str(c.id),
                "nome_resumido": c.nome_resumido,
                "categoria": c.categoria,
                "active": c.active,
                "payment": {
                    "key_type": payment.key_type if payment else None,
                    "key_value_raw": payment.key_value_raw if payment else None,
                    "bank": payment.bank if payment else None,
                },
            }
        )

    return templates.TemplateResponse(
        "couriers_list.html",
        {
            "request": request,
            "rows": rows,
            "q": q or "",
            "active": active,
            "categoria": categoria or "",
        },
    )


@router.post("/couriers")
def couriers_create_ui(
    nome_resumido: str = Form(...),
    nome_completo: str = Form(default=""),
    categoria: str = Form(default="SEMANAL"),
    db: Session = Depends(get_db),
):
    c = create_courier(
        db,
        nome_resumido=nome_resumido,
        nome_completo=nome_completo or None,
        categoria=categoria,
    )
    return _ui_redirect(f"/ui/couriers/{c.id}?ok=1")


@router.post("/couriers/quick-create", response_class=HTMLResponse)
def couriers_quick_create_ui(
    request: Request,
    nome_resumido: str = Form(...),
    nome_completo: str = Form(default=""),
    categoria: str = Form(default="SEMANAL"),
    db: Session = Depends(get_db),
):
    create_courier(
        db,
        nome_resumido=nome_resumido,
        nome_completo=nome_completo or None,
        categoria=categoria,
    )

    couriers = list_couriers(db, active=True, categoria=None, q=None)
    courier_opts = [{"id": str(c.id), "nome": c.nome_resumido, "categoria": c.categoria} for c in couriers]
    return templates.TemplateResponse(
        "partials/courier_options.html",
        {"request": request, "courier_opts": courier_opts},
    )


@router.get("/couriers/{courier_id}", response_class=HTMLResponse)
def courier_detail_ui(request: Request, courier_id: str, db: Session = Depends(get_db)):
    c = db.query(Courier).filter(Courier.id == courier_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="courier not found")

    aliases = db.query(CourierAlias).filter_by(courier_id=c.id).order_by(CourierAlias.alias_raw.asc()).all()
    payment = db.query(CourierPayment).filter_by(courier_id=c.id).first()

    return templates.TemplateResponse(
        "courier_detail.html",
        {
            "request": request,
            "courier": {
                "id": str(c.id),
                "nome_resumido": c.nome_resumido,
                "nome_completo": c.nome_completo,
                "categoria": c.categoria,
                "active": c.active,
            },
            "aliases": [{"id": str(a.id), "alias_raw": a.alias_raw} for a in aliases],
            "payment": {
                "key_type": payment.key_type if payment else "",
                "key_value_raw": payment.key_value_raw if payment else "",
                "bank": payment.bank if payment else "",
            },
        },
    )


@router.post("/couriers/{courier_id}")
def courier_patch_ui(
    courier_id: str,
    nome_resumido: str = Form(...),
    nome_completo: str = Form(default=""),
    categoria: str = Form(default="SEMANAL"),
    active: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    patch_courier(
        db,
        courier_id=courier_id,
        nome_resumido=nome_resumido,
        nome_completo=nome_completo or None,
        categoria=categoria,
        active=active,
    )
    return _ui_redirect(f"/ui/couriers/{courier_id}?ok=1")


@router.post("/couriers/{courier_id}/aliases", response_class=HTMLResponse)
def courier_add_alias_ui(
    request: Request,
    courier_id: str,
    alias_raw: str = Form(...),
    db: Session = Depends(get_db),
):
    add_alias(db, courier_id=courier_id, alias_raw=alias_raw)
    aliases = db.query(CourierAlias).filter_by(courier_id=courier_id).order_by(CourierAlias.alias_raw.asc()).all()
    return templates.TemplateResponse(
        "partials/alias_list.html",
        {"request": request, "courier_id": courier_id, "aliases": [{"id": str(a.id), "alias_raw": a.alias_raw} for a in aliases]},
    )


@router.post("/couriers/{courier_id}/aliases/{alias_id}/delete", response_class=HTMLResponse)
def courier_delete_alias_ui(request: Request, courier_id: str, alias_id: str, db: Session = Depends(get_db)):
    delete_alias(db, courier_id=courier_id, alias_id=alias_id)
    aliases = db.query(__import__("app.models", fromlist=["CourierAlias"]).CourierAlias).filter_by(courier_id=courier_id).order_by(
        __import__("app.models", fromlist=["CourierAlias"]).CourierAlias.alias_raw.asc()
    ).all()
    return templates.TemplateResponse(
        "partials/alias_list.html",
        {"request": request, "courier_id": courier_id, "aliases": [{"id": str(a.id), "alias_raw": a.alias_raw} for a in aliases]},
    )


@router.post("/couriers/{courier_id}/payment")
def courier_payment_ui(
    courier_id: str,
    key_type: str = Form(default=""),
    key_value_raw: str = Form(default=""),
    bank: str = Form(default=""),
    db: Session = Depends(get_db),
):
    body = CourierPaymentIn(key_type=key_type or None, key_value_raw=key_value_raw or None, bank=bank or None)
    upsert_payment(db, courier_id=courier_id, key_type=body.key_type, key_value_raw=body.key_value_raw, bank=body.bank)
    return _ui_redirect(f"/ui/couriers/{courier_id}?ok=1")
