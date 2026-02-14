from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from app.models import Courier, CourierAlias, CourierPayment
from app.services.courier_match import norm_text
from app.services.couriers import ensure_alias_not_used_by_other_courier, infer_pix_key_type


def seed_weekly_couriers(db: Session, payload: dict) -> dict:
    entregadores = payload.get("entregadores", [])
    created = 0
    updated = 0
    aliases_created = 0
    payments_upserted = 0

    def ensure_alias(courier_id: str, raw: str) -> None:
        nonlocal aliases_created
        raw = (raw or "").strip()
        if not raw:
            return
        an = norm_text(raw)
        ensure_alias_not_used_by_other_courier(db, an, courier_id=courier_id)
        existing = (
            db.query(CourierAlias)
            .filter(
                CourierAlias.courier_id == courier_id,
                CourierAlias.alias_norm == an,
            )
            .first()
        )
        if existing:
            return
        db.add(CourierAlias(courier_id=courier_id, alias_raw=raw, alias_norm=an))
        aliases_created += 1

    def upsert_payment(courier_id: str, pagamento: dict) -> None:
        nonlocal payments_upserted
        if not pagamento:
            return
        chave = (pagamento.get("chave") or "").strip() or None
        banco = (pagamento.get("banco") or "").strip() or None
        key_type = infer_pix_key_type(chave)

        p = db.query(CourierPayment).filter(CourierPayment.courier_id == courier_id).first()
        if p is None:
            p = CourierPayment(courier_id=courier_id)
            db.add(p)
        p.key_type = key_type
        p.key_value_raw = chave
        p.bank = banco
        payments_upserted += 1

    for e in entregadores:
        nome = (e.get("nome_exibicao") or "").strip()
        if not nome:
            continue
        exists = db.query(Courier).filter(sql_text("upper(nome_resumido)=upper(:n)")).params(n=nome).first()

        if exists is None:
            c = Courier(
                nome_resumido=nome,
                nome_completo=e.get("nome_completo"),
                categoria="SEMANAL",
                active=True,
            )
            db.add(c)
            db.flush()
            created += 1
        else:
            c = exists
            c.active = True
            c.categoria = "SEMANAL"
            if not c.nome_completo and e.get("nome_completo"):
                c.nome_completo = e.get("nome_completo")
            updated += 1

        ensure_alias(str(c.id), nome)
        ensure_alias(str(c.id), e.get("nome_completo") or "")

        upsert_payment(str(c.id), e.get("pagamento") or {})

    db.commit()
    return {
        "created": created,
        "updated": updated,
        "aliases_created": aliases_created,
        "payments_upserted": payments_upserted,
    }
