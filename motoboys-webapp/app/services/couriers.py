from __future__ import annotations

import re
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models import Courier, CourierAlias, CourierPayment
from app.services.courier_match import norm_text


def _alias_norm(raw: str) -> str:
    return norm_text(raw)


def ensure_alias_not_used_by_other_courier(db: Session, alias_norm: str, courier_id: Optional[str] = None) -> None:
    """Soft uniqueness: prevent alias_norm from belonging to multiple couriers (avoid ambiguous matching)."""
    q = db.query(CourierAlias).filter(CourierAlias.alias_norm == alias_norm)
    if courier_id:
        q = q.filter(CourierAlias.courier_id != courier_id)
    exists = q.first()
    if exists:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "ALIAS_JA_USADO",
                "alias_norm": alias_norm,
                "courier_id": str(exists.courier_id),
            },
        )


def get_courier_or_404(db: Session, courier_id: str) -> Courier:
    c = db.query(Courier).filter(Courier.id == courier_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="courier not found")
    return c


def list_couriers(
    db: Session,
    active: Optional[bool] = None,
    categoria: Optional[str] = None,
    q: Optional[str] = None,
):
    qry = db.query(Courier)
    if active is not None:
        qry = qry.filter(Courier.active == active)
    if categoria:
        qry = qry.filter(Courier.categoria == categoria)
    if q:
        # simple case-insensitive contains
        like = f"%{q.strip()}%"
        qry = qry.filter(Courier.nome_resumido.ilike(like))
    return qry.order_by(Courier.nome_resumido.asc()).all()


def create_courier(db: Session, *, nome_resumido: str, nome_completo: str | None, categoria: str, active: bool) -> Courier:
    nome_resumido = (nome_resumido or "").strip()
    if not nome_resumido:
        raise HTTPException(status_code=400, detail="nome_resumido is required")

    # default alias based on nome_resumido
    an = _alias_norm(nome_resumido)
    ensure_alias_not_used_by_other_courier(db, an, courier_id=None)

    c = Courier(nome_resumido=nome_resumido, nome_completo=nome_completo, categoria=categoria, active=active)
    db.add(c)
    db.flush()  # get id without committing yet

    a = CourierAlias(courier_id=c.id, alias_raw=nome_resumido, alias_norm=an)
    db.add(a)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="courier already exists or constraint violated")

    db.refresh(c)
    return c


def patch_courier(db: Session, courier_id: str, *, nome_resumido=None, nome_completo=None, categoria=None, active=None) -> Courier:
    c = get_courier_or_404(db, courier_id)

    if nome_resumido is not None:
        nn = (nome_resumido or "").strip()
        if not nn:
            raise HTTPException(status_code=400, detail="nome_resumido cannot be empty")
        # do not allow default alias collision
        an = _alias_norm(nn)
        ensure_alias_not_used_by_other_courier(db, an, courier_id=str(c.id))
        c.nome_resumido = nn
        # ensure alias exists for the new display name
        existing = db.query(CourierAlias).filter(
            CourierAlias.courier_id == c.id,
            CourierAlias.alias_norm == an,
        ).first()
        if not existing:
            db.add(CourierAlias(courier_id=c.id, alias_raw=nn, alias_norm=an))

    if nome_completo is not None:
        c.nome_completo = (nome_completo.strip() if isinstance(nome_completo, str) else None)
        if c.nome_completo:
            an = _alias_norm(c.nome_completo)
            ensure_alias_not_used_by_other_courier(db, an, courier_id=str(c.id))
            existing = db.query(CourierAlias).filter(
                CourierAlias.courier_id == c.id,
                CourierAlias.alias_norm == an,
            ).first()
            if not existing:
                db.add(CourierAlias(courier_id=c.id, alias_raw=c.nome_completo, alias_norm=an))

    if categoria is not None:
        c.categoria = categoria
    if active is not None:
        c.active = bool(active)

    db.commit()
    db.refresh(c)
    return c


def add_alias(db: Session, courier_id: str, alias_raw: str) -> CourierAlias:
    c = get_courier_or_404(db, courier_id)
    alias_raw = (alias_raw or "").strip()
    if not alias_raw:
        raise HTTPException(status_code=400, detail="alias_raw is required")
    an = _alias_norm(alias_raw)
    ensure_alias_not_used_by_other_courier(db, an, courier_id=str(c.id))

    existing = db.query(CourierAlias).filter(
        CourierAlias.courier_id == c.id,
        CourierAlias.alias_norm == an,
    ).first()
    if existing:
        return existing

    a = CourierAlias(courier_id=c.id, alias_raw=alias_raw, alias_norm=an)
    db.add(a)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="alias constraint violated")
    db.refresh(a)
    return a


def delete_alias(db: Session, courier_id: str, alias_id: str) -> None:
    c = get_courier_or_404(db, courier_id)
    a = db.query(CourierAlias).filter(CourierAlias.id == alias_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="alias not found")
    if str(a.courier_id) != str(c.id):
        raise HTTPException(status_code=400, detail="alias does not belong to courier")
    db.delete(a)
    db.commit()


def upsert_payment(db: Session, courier_id: str, *, key_type=None, key_value_raw=None, bank=None) -> CourierPayment:
    c = get_courier_or_404(db, courier_id)
    p = db.query(CourierPayment).filter(CourierPayment.courier_id == c.id).first()
    if p is None:
        p = CourierPayment(courier_id=c.id)
        db.add(p)

    p.key_type = key_type
    p.key_value_raw = key_value_raw.strip() if isinstance(key_value_raw, str) else key_value_raw
    p.bank = bank.strip() if isinstance(bank, str) else bank

    db.commit()
    db.refresh(p)
    return p


_ONLY_DIGITS = re.compile(r"\D+")


def infer_pix_key_type(key_value_raw: str | None) -> str:
    """Heuristic for seed JSON: infer enum payment_key_type for Brazil Pix keys."""
    if not key_value_raw:
        return "OUTRO"
    s = key_value_raw.strip()
    if "@" in s:
        return "EMAIL"

    digits = _ONLY_DIGITS.sub("", s)
    # TELEFONE: DDD(2) + 9 + 8 digits => 11 digits, third digit 9
    if len(digits) == 11 and digits[2] == "9":
        return "TELEFONE"
    if len(digits) == 14:
        return "CNPJ"
    if len(digits) == 11:
        return "CPF"
    if len(digits) == 32:
        return "ALEATORIA"
    return "OUTRO"
