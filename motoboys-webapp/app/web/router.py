import datetime as dt
from pathlib import Path
from typing import Any, Optional
import time
from collections import defaultdict
import urllib.parse

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from sqlalchemy.orm import Session
from sqlalchemy import func, text as sa_text

from app.db import get_db
from app.models import Import, Ride
from app.schemas import CourierPaymentIn
from app.settings import auth_provider, settings

from app.services.audit import log_event, list_audit

from app.services.couriers import create_courier, list_couriers, patch_courier, add_alias, delete_alias, upsert_payment
from app.services.import_saipos import import_saipos
from app.services.import_yooga import import_yooga
from app.services.payouts import close_week, compute_week_payout_preview, pay_week, get_week_or_404
from app.services.pendings import list_assignment, assign_ride, list_yooga_groups, yooga_group_items, resolve_yooga
from app.services.utils import read_upload_bytes, sha256_bytes
from app.services.week_service import get_open_week_for_date

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

router_public = APIRouter(prefix="/ui", include_in_schema=False)


def _safe_internal_next(next_value: str | None) -> str | None:
    if not next_value:
        return None

    nxt = next_value.strip()
    if not nxt:
        return None

    parsed = urllib.parse.urlsplit(nxt)
    if parsed.scheme or parsed.netloc:
        return None

    if not nxt.startswith("/ui/"):
        return None

    return nxt

def _next_url(request: Request, fallback: str = "/ui/imports/new") -> str:
    qp = request.url.query
    path = request.url.path
    if qp:
        path = f"{path}?{qp}"
    return path or fallback

def _require_auth(request: Request):
    if not request.session.get("user"):
        nxt = urllib.parse.quote(_next_url(request))
        login_url = f"/ui/login?next={nxt}"

        # HTMX-friendly redirect
        if request.headers.get("HX-Request"):
            raise HTTPException(status_code=401, headers={"HX-Redirect": login_url})

        raise HTTPException(status_code=303, headers={"Location": login_url})

router_private = APIRouter(prefix="/ui", include_in_schema=False, dependencies=[Depends(_require_auth)])

def _require_admin(request: Request):
    if request.session.get("role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Acesso restrito ao ADMIN.")

def _actor_ctx(request: Request):
    actor = request.session.get("user") or "unknown"
    role = request.session.get("role")
    ip = request.client.host if request.client else None
    return actor, role, ip

router_admin = APIRouter(
    prefix="/ui",
    include_in_schema=False,
    dependencies=[Depends(_require_auth), Depends(_require_admin)],
)
# -----------------------------
# Helpers
# -----------------------------

def _ui_redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url=url, status_code=303)


def _list_weeks(db: Session):
    rows = db.execute(
        sa_text(
            """
            SELECT id, start_date, end_date, status, closing_seq
            FROM weeks
            ORDER BY start_date DESC
            """
        )
    ).mappings().all()
    return [dict(r) for r in rows]


def _friendly_error_message(exc: Exception) -> str:
    """Convert backend exceptions into short UI-friendly strings."""

    if isinstance(exc, HTTPException):
        detail = exc.detail

        # Structured errors
        if isinstance(detail, dict):
            code = detail.get("error")
            if code == "MISSING_REQUIRED_COLUMNS":
                missing = detail.get("missing") or []
                src = detail.get("source") or ""
                return f"Colunas obrigatórias ausentes ({src}): {', '.join(missing)}"

            if code == "WEEK_NOT_OPEN":
                return f"Semana não está aberta (status atual: {detail.get('status')})."

            if code == "WEEK_NOT_CLOSED":
                return f"Semana não está fechada (status atual: {detail.get('status')})."

            if code == "WEEK_HAS_PENDINGS":
                pending_total = detail.get("pending_total")
                unassigned = detail.get("unassigned_ok_rides")
                parts = []
                if pending_total:
                    parts.append(f"{pending_total} pendência(s) aberta(s)")
                if unassigned:
                    parts.append(f"{unassigned} ride(s) OK sem motoboy")
                suffix = "; ".join(parts) if parts else "pendências abertas"
                return f"Não dá pra fechar: {suffix}."

            # Fallback for dict details
            return str(detail)

        # Plain string detail
        if isinstance(detail, str):
            return detail

        return str(detail)

    return str(exc)



# -----------------------------
# Login rate limiting (P5)
# -----------------------------

_LOGIN_WINDOW_SEC = 10 * 60  # 10 min
_LOGIN_MAX_ATTEMPTS = 10     # attempts per window

# key -> list[timestamps]
_login_attempts: dict[str, list[float]] = defaultdict(list)

def _rl_prune(key: str, now: float) -> None:
    arr = _login_attempts.get(key)
    if not arr:
        return
    cutoff = now - _LOGIN_WINDOW_SEC
    i = 0
    while i < len(arr) and arr[i] < cutoff:
        i += 1
    if i:
        del arr[:i]
    if not arr:
        _login_attempts.pop(key, None)

def _rl_is_limited(key: str, now: float) -> bool:
    _rl_prune(key, now)
    return len(_login_attempts.get(key, [])) >= _LOGIN_MAX_ATTEMPTS

def _rl_record_fail(key: str, now: float) -> None:
    arr = _login_attempts.setdefault(key, [])
    arr.append(now)
    _rl_prune(key, now)

def _rl_clear(key: str) -> None:
    _login_attempts.pop(key, None)

# -----------------------------
# Auth (P3)
# -----------------------------
@router_public.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str | None = Query(default=None)):
    if auth_provider.needs_initial_setup():
        return _ui_redirect("/ui/setup-inicial")

    # If already logged, go to next
    if request.session.get("user"):
        role = request.session.get("role")
        default_home = "/ui/weeks/current" if role == "CASHIER" else "/ui/imports/new"
        return _ui_redirect(_safe_internal_next(next) or default_home)

    safe_next = _safe_internal_next(next) or "/ui/imports/new"

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": safe_next,
            "error": None,
            "desktop_mode": settings.DESKTOP_MODE,
        },
    )


@router_public.post("/login", response_class=HTMLResponse)
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/ui/imports/new"),
):
    if auth_provider.needs_initial_setup():
        return _ui_redirect("/ui/setup-inicial")

    u = username.strip()

    ip = request.client.host if request.client else "unknown"
    now = time.time()

    # Rate limit by IP + by username (both must be under limit)
    ip_key = f"ip:{ip}"
    user_key = f"user:{u.lower()}" if u else "user:"

    safe_next = _safe_internal_next(next)

    if _rl_is_limited(ip_key, now) or _rl_is_limited(user_key, now):
        # approximate retry-after (seconds until the oldest attempt exits the window)
        arr = _login_attempts.get(ip_key) or _login_attempts.get(user_key) or []
        retry_after = int(max(5, (_LOGIN_WINDOW_SEC - (now - min(arr))) if arr else _LOGIN_WINDOW_SEC))
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "next": safe_next or "/ui/imports/new",
                "error": f"Muitas tentativas. Aguarde ~{retry_after}s e tente novamente.",
                "desktop_mode": settings.DESKTOP_MODE,
            },
            status_code=429,
            headers={"Retry-After": str(retry_after)},
        )

    role = auth_provider.verify_credentials(u, password)

    if role:
        request.session["user"] = u
        request.session["role"] = role

        # Clear rate limit buckets on success
        _rl_clear(ip_key)
        _rl_clear(user_key)

        # Safety: cashier can't be redirected to admin-only pages
        default_home = "/ui/weeks/current" if role == "CASHIER" else "/ui/imports/new"
        nxt = safe_next or default_home
        if role == "CASHIER" and not (nxt.startswith("/ui/weeks") or nxt.startswith("/ui/login")):
            nxt = default_home

        return _ui_redirect(nxt)

    # record fail
    _rl_record_fail(ip_key, now)
    if u:
        _rl_record_fail(user_key, now)

    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "next": safe_next or "/ui/imports/new",
            "error": "Credenciais inválidas.",
            "desktop_mode": settings.DESKTOP_MODE,
        },
        status_code=401,
    )


@router_public.get("/setup-inicial", response_class=HTMLResponse)
def setup_inicial_page(request: Request):
    if not settings.DESKTOP_MODE:
        return _ui_redirect("/ui/login")

    if not auth_provider.needs_initial_setup():
        return _ui_redirect("/ui/login?ok=1&msg=Setup%20inicial%20j%C3%A1%20realizado")

    return templates.TemplateResponse(
        "setup_inicial.html",
        {"request": request, "error": None},
    )


@router_public.post("/setup-inicial", response_class=HTMLResponse)
def setup_inicial_post(
    request: Request,
    db: Session = Depends(get_db),
    admin_username: str = Form(...),
    admin_password: str = Form(...),
    admin_password_confirm: str = Form(...),
    cashier_username: str = Form(...),
    cashier_password: str = Form(...),
    cashier_password_confirm: str = Form(...),
):
    if not settings.DESKTOP_MODE:
        return _ui_redirect("/ui/login")

    if not auth_provider.needs_initial_setup():
        return _ui_redirect("/ui/login?ok=1&msg=Setup%20inicial%20j%C3%A1%20realizado")

    admin_username = admin_username.strip()
    cashier_username = cashier_username.strip()

    if not admin_username or not cashier_username:
        return templates.TemplateResponse(
            "setup_inicial.html",
            {"request": request, "error": "Usuários não podem ficar vazios."},
            status_code=400,
        )

    if admin_password != admin_password_confirm or cashier_password != cashier_password_confirm:
        return templates.TemplateResponse(
            "setup_inicial.html",
            {"request": request, "error": "As confirmações de senha não conferem."},
            status_code=400,
        )

    if len(admin_password) < 6 or len(cashier_password) < 6:
        return templates.TemplateResponse(
            "setup_inicial.html",
            {"request": request, "error": "As senhas devem ter no mínimo 6 caracteres."},
            status_code=400,
        )

    if admin_password == "admin" or cashier_password == "caixa":
        return templates.TemplateResponse(
            "setup_inicial.html",
            {"request": request, "error": "Troque as credenciais padrão para concluir o setup."},
            status_code=400,
        )

    auth_provider.save_initial_credentials(
        admin_username=admin_username,
        admin_password=admin_password,
        cashier_username=cashier_username,
        cashier_password=cashier_password,
        sensitive_config={"desktop_mode": True},
    )

    ip = request.client.host if request.client else None
    log_event(
        db,
        actor="setup-inicial",
        role="SYSTEM",
        ip=ip,
        action="AUTH_INITIAL_SETUP_COMPLETED",
        entity_type="LOCAL_CONFIG",
        meta={
            "changed_credentials": ["ADMIN", "CASHIER"],
            "changed_sensitive_config": ["desktop_mode"],
        },
    )

    return _ui_redirect("/ui/login?ok=1&msg=Setup%20inicial%20conclu%C3%ADdo")


@router_public.post("/logout")
def logout_post(request: Request):
    request.session.clear()
    return _ui_redirect("/ui/login?ok=1&msg=Sa%C3%ADda%20realizada")


# -----------------------------
# Home
# -----------------------------
@router_private.get("/", response_class=HTMLResponse)
def ui_home(request: Request):
    role = request.session.get("role")
    return _ui_redirect("/ui/weeks/current" if role == "CASHIER" else "/ui/imports/new")


# -----------------------------
# Imports UI
# -----------------------------
@router_admin.get("/imports/new", response_class=HTMLResponse)
def imports_new(request: Request):
    return templates.TemplateResponse(
        "imports_new.html",
        {"request": request, "result": None, "error": None},
    )


@router_admin.post("/imports/new", response_class=HTMLResponse)
async def imports_new_post(
    request: Request,
    source: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
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

        is_duplicate = bool(
            inserted == 0
            and pend_assign == 0
            and pend_review == 0
            and redirected_closed_week in (0, False, None)
            and (not week_ids_touched)
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
            "is_duplicate": is_duplicate,
        }

        actor, role, ip = _actor_ctx(request)
        log_event(
            db,
            actor=actor,
            role=role,
            ip=ip,
            action="IMPORT_DUPLICATE" if is_duplicate else "IMPORT_CREATED",
            entity_type="import",
            entity_id=import_id,
            meta={"source": source, "filename": file.filename, "inserted": inserted, "pend_assign": pend_assign, "pend_review": pend_review, "week_ids_touched": week_ids_touched, "redirected_closed_week": redirected_closed_week, "is_duplicate": is_duplicate},
        )

        return templates.TemplateResponse(
            "imports_new.html",
            {"request": request, "result": result, "error": None},
        )

    except Exception as e:
        return templates.TemplateResponse(
            "imports_new.html",
            {"request": request, "result": None, "error": _friendly_error_message(e)},
        )


@router_admin.get("/imports", response_class=HTMLResponse)
def imports_list(
    request: Request,
    source: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    src = (source or "").upper().strip() or None
    offset = (page - 1) * page_size

    q = db.query(Import)
    if src:
        q = q.filter(Import.source == src)

    rows = q.order_by(Import.imported_at.desc()).offset(offset).limit(page_size + 1).all()

    has_next = len(rows) > page_size
    if has_next:
        rows = rows[:page_size]

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

    qs_parts = []
    if src:
        qs_parts.append(f"source={urllib.parse.quote(src)}")
    qs_parts.append(f"page_size={page_size}")
    qs_common = "&".join(qs_parts)

    return templates.TemplateResponse(
        "imports_list.html",
        {
            "request": request,
            "imports": imports,
            "source": (src or ""),
            "page": page,
            "page_size": page_size,
            "has_prev": page > 1,
            "has_next": has_next,
            "qs_common": qs_common,
        },
    )


@router_admin.get("/imports/{import_id}", response_class=HTMLResponse)
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
@router_admin.get("/pendencias", response_class=HTMLResponse)
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

    assignment_items: list[dict[str, Any]] = []
    yooga_groups: list[dict[str, Any]] = []
    yooga_first_group_id: Optional[str] = None
    yooga_items: list[dict[str, Any]] = []

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
                "week_id": str(r.week_id),
            }
            for r in rides
        ]

    return templates.TemplateResponse(
        "pendencias.html",
        {
            "request": request,
            "tab": tab,
            "week_id": week_id,
            "source": source or "",
            "weeks": weeks,
            "courier_opts": courier_opts,
            "assignment_items": assignment_items,
            "yooga_groups": yooga_groups,
            "yooga_first_group_id": yooga_first_group_id,
            "yooga_items": yooga_items,
        },
    )


@router_admin.post("/pendencias/assign", response_class=HTMLResponse)
def pendencias_assign(
    request: Request,
    ride_id: str = Form(...),
    courier_id: str = Form(...),
    pay_in_current_week: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    try:
        ride = assign_ride(db, ride_id=ride_id, courier_id=courier_id, pay_in_current_week=pay_in_current_week)

        actor, role, ip = _actor_ctx(request)
        log_event(
            db,
            actor=actor,
            role=role,
            ip=ip,
            action="RIDE_ASSIGNED",
            entity_type="ride",
            entity_id=ride_id,
            meta={"courier_id": courier_id, "pay_in_current_week": bool(pay_in_current_week)},
        )

        msg = "Atribuído."
        if ride.paid_in_week_id is not None and str(ride.paid_in_week_id) != str(ride.week_id):
            msg = "Atribuído e marcado para pagamento na semana atual (semana original já estava fechada)."

        return templates.TemplateResponse(
            "partials/assignment_row_done.html",
            {"request": request, "ride_id": ride_id, "message": msg},
        )

    except Exception as e:
        return templates.TemplateResponse(
            "partials/assignment_row_error.html",
            {"request": request, "ride_id": ride_id, "error": _friendly_error_message(e)},
        )


@router_admin.get("/pendencias/yooga/{group_id}", response_class=HTMLResponse)
def pendencias_yooga_detail(
    request: Request,
    group_id: str,
    week_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    # week_id only used for resolve redirect
    week_id = week_id or ""
    rides = yooga_group_items(db, group_id)
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
        for r in rides
    ]
    return templates.TemplateResponse(
        "partials/yooga_detail.html",
        {"request": request, "group_id": group_id, "items": items, "week_id": week_id},
    )


@router_admin.post("/pendencias/yooga/{group_id}/resolve")
def pendencias_yooga_resolve(
    request: Request,
    group_id: str,
    action: str = Form(...),
    keep_ride_id: str | None = Form(default=None),
    week_id: str = Form(...),
    db: Session = Depends(get_db),
):
    resolve_yooga(db, group_id=group_id, action=action, keep_ride_id=keep_ride_id)

    actor, role, ip = _actor_ctx(request)
    log_event(
        db,
        actor=actor,
        role=role,
        ip=ip,
        action="YOOGA_REVIEW_RESOLVED",
        entity_type="yooga_group",
        entity_id=group_id,
        meta={"action": action, "keep_ride_id": keep_ride_id},
    )
    return Response(status_code=200, headers={"HX-Redirect": f"/ui/pendencias?tab=yooga&week_id={week_id}&ok=1&msg=Revis%C3%A3o%20Yooga%20resolvida"})


# -----------------------------
# Weeks UI
# -----------------------------
@router_private.get("/weeks/current", response_class=HTMLResponse)
def weeks_current(
    request: Request,
    week_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if not week_id:
        week_id = str(get_open_week_for_date(db, dt.date.today()).id)

    weeks = _list_weeks(db)
    w = get_week_or_404(db, week_id)

    preview = compute_week_payout_preview(db, week_id)
    pending_total = sum(int(r.get("pending_count") or 0) for r in preview)

    return templates.TemplateResponse(
        "week_current.html",
        {
            "request": request,
            "week_id": week_id,
            "weeks": weeks,
            "week": {"id": str(w.id), "start_date": str(w.start_date), "end_date": str(w.end_date), "status": w.status},
            "rows": preview,
            "pending_total": pending_total,
        },
    )


@router_admin.post("/weeks/{week_id}/close")
def weeks_close(request: Request, week_id: str, db: Session = Depends(get_db)):
    try:
        close_week(db, week_id)
        actor, role, ip = _actor_ctx(request)
        log_event(db, actor=actor, role=role, ip=ip, action="WEEK_CLOSED", entity_type="week", entity_id=week_id, meta=None)
        return _ui_redirect(f"/ui/weeks/current?week_id={week_id}&ok=1&msg=Semana%20fechada")
    except Exception as e:
        msg = _friendly_error_message(e)
        return _ui_redirect(f"/ui/weeks/current?week_id={week_id}&err={msg}")


@router_admin.post("/weeks/{week_id}/pay")
def weeks_pay(request: Request, week_id: str, db: Session = Depends(get_db)):
    try:
        pay_week(db, week_id)
        actor, role, ip = _actor_ctx(request)
        log_event(db, actor=actor, role=role, ip=ip, action="WEEK_PAID", entity_type="week", entity_id=week_id, meta=None)
        return _ui_redirect(f"/ui/weeks/current?week_id={week_id}&ok=1&msg=Semana%20marcada%20como%20paga")
    except Exception as e:
        msg = _friendly_error_message(e)
        return _ui_redirect(f"/ui/weeks/current?week_id={week_id}&err={msg}")


@router_private.get("/weeks/{week_id}/couriers/{courier_id}", response_class=HTMLResponse)
def week_courier_audit(
    request: Request,
    week_id: str,
    courier_id: str,
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    week = get_week_or_404(db, week_id)

    # Validate courier
    courier_row = db.execute(
        sa_text("SELECT id, nome_resumido FROM couriers WHERE id = :cid"),
        {"cid": courier_id},
    ).mappings().first()
    if not courier_row:
        raise HTTPException(status_code=404, detail="courier not found")

    # Optional date filters
    df = None
    dt_ = None
    try:
        if date_from:
            df = dt.date.fromisoformat(date_from)
        if date_to:
            dt_ = dt.date.fromisoformat(date_to)
    except ValueError:
        return _ui_redirect(f"/ui/weeks/{week_id}/couriers/{courier_id}?err=Data%20inv%C3%A1lida")

    rides = db.execute(
        sa_text(
            """
            SELECT id, source, order_dt, value_raw, fee_type, status, week_id, paid_in_week_id
            FROM rides
            WHERE courier_id = :courier_id
              AND ((week_id = :week_id AND paid_in_week_id IS NULL) OR paid_in_week_id = :week_id)
              AND (is_cancelled IS NULL OR is_cancelled = false)
              AND (:date_from IS NULL OR (order_dt::date >= :date_from::date))
              AND (:date_to IS NULL OR (order_dt::date <= :date_to::date))
            ORDER BY order_dt ASC
            """
        ),
        {"courier_id": courier_id, "week_id": week_id, "date_from": df, "date_to": dt_},
    ).mappings().all()

    ledger_entries = db.execute(
        sa_text(
            """
            SELECT id, effective_date, type, amount, note
            FROM ledger_entries
            WHERE courier_id = :courier_id
              AND week_id = :week_id
              AND (:date_from IS NULL OR (effective_date >= :date_from::date))
              AND (:date_to IS NULL OR (effective_date <= :date_to::date))
            ORDER BY effective_date ASC
            """
        ),
        {"courier_id": courier_id, "week_id": week_id, "date_from": df, "date_to": dt_},
    ).mappings().all()

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

    installments_due_amount = float(
        sum(max(0.0, float(i["amount"] or 0) - float(i["paid_amount"] or 0)) for i in installments_due)
    )
    pre_net = rides_amount + extras_amount - vales_amount
    installments_applied = max(0.0, min(pre_net, installments_due_amount))

    preview = {
        "rides_amount": rides_amount,
        "extras_amount": extras_amount,
        "vales_amount": vales_amount,
        "installments_due_amount": installments_due_amount,
        "installments_applied_amount": installments_applied,
        "net_amount": pre_net - installments_applied,
    }

    return templates.TemplateResponse(
        "week_courier_audit.html",
        {
            "request": request,
            "week_id": week_id,
            "courier_id": courier_id,
            "courier_nome": courier_row["nome_resumido"],
            "week": {"start_date": str(week.start_date), "end_date": str(week.end_date), "status": week.status},
            "rides": [dict(r) for r in rides],
            "ledger_entries": [dict(l) for l in ledger_entries],
            "installments_due": [
                {**dict(i), "remaining_amount": max(0.0, float(i["amount"] or 0) - float(i["paid_amount"] or 0))}
                for i in installments_due
            ],
            "preview": preview,
            "date_from": date_from,
            "date_to": date_to,
        },
    )


# -----------------------------
# Couriers UI
# -----------------------------
@router_admin.get("/couriers", response_class=HTMLResponse)
def couriers_page(
    request: Request,
    q: str | None = Query(default=None),
    active: bool | None = Query(default=True),
    db: Session = Depends(get_db),
):
    rows = list_couriers(db, active=active, categoria=None, q=q)
    couriers = [
        {
            "id": str(c.id),
            "nome_resumido": c.nome_resumido,
            "nome_completo": c.nome_completo,
            "categoria": c.categoria,
            "active": c.active,
        }
        for c in rows
    ]
    return templates.TemplateResponse(
        "couriers_list.html",
        {"request": request, "couriers": couriers, "q": q or "", "active": active},
    )


@router_admin.post("/couriers/create")
def couriers_create_ui(
    request: Request,
    nome_resumido: str = Form(...),
    nome_completo: str | None = Form(default=None),
    categoria: str = Form(default="SEMANAL"),
    active: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    c = create_courier(db, nome_resumido=nome_resumido, nome_completo=nome_completo, categoria=categoria, active=active)
    actor, role, ip = _actor_ctx(request)
    log_event(db, actor=actor, role=role, ip=ip, action="COURIER_CREATED", entity_type="courier", entity_id=c.id, meta={"nome_resumido": nome_resumido, "categoria": categoria, "active": bool(active)})
    return _ui_redirect("/ui/couriers?ok=1&msg=Entregador%20criado")


@router_admin.post("/couriers/quick-create", response_class=HTMLResponse)
def couriers_quick_create(
    request: Request,
    nome_resumido: str = Form(...),
    nome_completo: str | None = Form(default=None),
    categoria: str = Form(default="SEMANAL"),
    db: Session = Depends(get_db),
):
    c = create_courier(db, nome_resumido=nome_resumido, nome_completo=nome_completo, categoria=categoria, active=True)
    actor, role, ip = _actor_ctx(request)
    log_event(db, actor=actor, role=role, ip=ip, action="COURIER_CREATED", entity_type="courier", entity_id=c.id, meta={"nome_resumido": nome_resumido, "categoria": categoria, "active": True, "quick": True})

    # Return OOB fragment to refresh courier select options
    rows = list_couriers(db, active=True, categoria=None, q=None)
    courier_opts = [{"id": str(c.id), "nome": c.nome_resumido, "categoria": c.categoria} for c in rows]
    return templates.TemplateResponse(
        "partials/courier_options_fragment_oob.html",
        {"request": request, "courier_opts": courier_opts},
    )


@router_admin.get("/couriers/{courier_id}", response_class=HTMLResponse)
def couriers_detail(request: Request, courier_id: str, db: Session = Depends(get_db)):
    from app.models import Courier, CourierAlias, CourierPayment

    c = db.query(Courier).filter_by(id=courier_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="courier not found")

    aliases = db.query(CourierAlias).filter_by(courier_id=c.id).order_by(CourierAlias.alias_raw.asc()).all()
    payment = db.query(CourierPayment).filter_by(courier_id=c.id).first()

    return templates.TemplateResponse(
        "courier_detail.html",
        {
            "request": request,
            "c": {
                "id": str(c.id),
                "nome_resumido": c.nome_resumido,
                "nome_completo": c.nome_completo,
                "categoria": c.categoria,
                "active": c.active,
            },
            "aliases": [{"id": str(a.id), "alias_raw": a.alias_raw} for a in aliases],
            "payment": {
                "key_type": getattr(payment, "key_type", "") if payment else "",
                "key_value_raw": getattr(payment, "key_value_raw", "") if payment else "",
                "bank": getattr(payment, "bank", "") if payment else "",
            },
        },
    )


@router_admin.post("/couriers/{courier_id}/update")
def couriers_update_ui(
    request: Request,
    courier_id: str,
    nome_resumido: str = Form(...),
    nome_completo: str | None = Form(default=None),
    categoria: str = Form(default="SEMANAL"),
    active: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    patch_courier(
        db,
        courier_id,
        nome_resumido=nome_resumido,
        nome_completo=nome_completo,
        categoria=categoria,
        active=active,
    )
    actor, role, ip = _actor_ctx(request)
    log_event(db, actor=actor, role=role, ip=ip, action="COURIER_UPDATED", entity_type="courier", entity_id=courier_id, meta={"nome_resumido": nome_resumido, "categoria": categoria, "active": bool(active)})
    return _ui_redirect(f"/ui/couriers/{courier_id}?ok=1&msg=Entregador%20atualizado")


@router_admin.post("/couriers/{courier_id}/aliases/add", response_class=HTMLResponse)
def courier_add_alias_ui(request: Request, courier_id: str, alias_raw: str = Form(...), db: Session = Depends(get_db)):
    from app.models import CourierAlias

    add_alias(db, courier_id=courier_id, alias_raw=alias_raw)
    actor, role, ip = _actor_ctx(request)
    log_event(db, actor=actor, role=role, ip=ip, action="COURIER_ALIAS_ADDED", entity_type="courier", entity_id=courier_id, meta={"alias_raw": alias_raw})
    aliases = (
        db.query(CourierAlias)
        .filter_by(courier_id=courier_id)
        .order_by(CourierAlias.alias_raw.asc())
        .all()
    )
    return templates.TemplateResponse(
        "partials/alias_list.html",
        {"request": request, "courier_id": courier_id, "aliases": [{"id": str(a.id), "alias_raw": a.alias_raw} for a in aliases]},
    )


@router_admin.post("/couriers/{courier_id}/aliases/{alias_id}/delete", response_class=HTMLResponse)
def courier_delete_alias_ui(request: Request, courier_id: str, alias_id: str, db: Session = Depends(get_db)):
    from app.models import CourierAlias

    delete_alias(db, courier_id=courier_id, alias_id=alias_id)
    actor, role, ip = _actor_ctx(request)
    log_event(db, actor=actor, role=role, ip=ip, action="COURIER_ALIAS_DELETED", entity_type="courier", entity_id=courier_id, meta={"alias_id": alias_id})
    aliases = (
        db.query(CourierAlias)
        .filter_by(courier_id=courier_id)
        .order_by(CourierAlias.alias_raw.asc())
        .all()
    )
    return templates.TemplateResponse(
        "partials/alias_list.html",
        {"request": request, "courier_id": courier_id, "aliases": [{"id": str(a.id), "alias_raw": a.alias_raw} for a in aliases]},
    )


@router_admin.post("/couriers/{courier_id}/payment")
def courier_payment_ui(
    request: Request,
    courier_id: str,
    key_type: str = Form(default=""),
    key_value_raw: str = Form(default=""),
    bank: str = Form(default=""),
    db: Session = Depends(get_db),
):
    body = CourierPaymentIn(key_type=key_type or None, key_value_raw=key_value_raw or None, bank=bank or None)
    upsert_payment(db, courier_id=courier_id, key_type=body.key_type, key_value_raw=body.key_value_raw, bank=body.bank)
    actor, role, ip = _actor_ctx(request)
    log_event(db, actor=actor, role=role, ip=ip, action="COURIER_PAYMENT_UPSERT", entity_type="courier", entity_id=courier_id, meta={"key_type": body.key_type, "bank": body.bank})
    return _ui_redirect(f"/ui/couriers/{courier_id}?ok=1&msg=Pagamento%20salvo")


# Backward-compatible export
router = router_private


# -----------------------------
# Audit UI (P4)
# -----------------------------
@router_admin.get("/audit", response_class=HTMLResponse)
def audit_page(
    request: Request,
    actor: str | None = Query(default=None),
    action: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size

    rows_plus = list_audit(db, limit=page_size + 1, offset=offset, actor=actor, action=action)
    has_next = len(rows_plus) > page_size
    rows = rows_plus[:page_size] if has_next else rows_plus

    qs_parts = []
    if actor:
        qs_parts.append(f"actor={urllib.parse.quote(actor)}")
    if action:
        qs_parts.append(f"action={urllib.parse.quote(action)}")
    qs_parts.append(f"page_size={page_size}")
    qs_common = "&".join(qs_parts)

    return templates.TemplateResponse(
        "audit.html",
        {
            "request": request,
            "nav": "audit",
            "rows": rows,
            "actor": actor or "",
            "action": action or "",
            "page": page,
            "page_size": page_size,
            "has_prev": page > 1,
            "has_next": has_next,
            "qs_common": qs_common,
        },
    )
