import re
import unicodedata
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import Courier, CourierAlias


INVALID_PLACEHOLDERS = {"0", "-", "—", "--", "---", "N/A"}


def norm_text(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.upper()
    s2 = unicodedata.normalize("NFKD", s)
    s2 = "".join(ch for ch in s2 if not unicodedata.combining(ch))
    return s2


def compute_fee_type(value_raw: float) -> int:
    return 10 if round(float(value_raw), 2) == 10.00 else 6


def saipos_pending_reason(courier_raw: str | None) -> str | None:
    n = norm_text(courier_raw or "")
    if not n:
        return "VAZIO"
    if n in INVALID_PLACEHOLDERS:
        return "PLACEHOLDER"
    if n == "ENTREGADOR NAO ENCONTRADO":
        return "SAIPOS_ENTREGADOR_NAO_ENCONTRADO"
    if n == "ENTREGADOR NAO INFORMADO":
        return "SAIPOS_ENTREGADOR_NAO_INFORMADO"
    return None


def match_courier_id(db: Session, courier_name_raw: str | None) -> Tuple[Optional[str], Optional[str]]:
    n = norm_text(courier_name_raw or "")
    if not n:
        return None, "VAZIO"

    alias_rows = db.query(CourierAlias.courier_id).filter(CourierAlias.alias_norm == n).distinct().all()
    if len(alias_rows) == 1:
        return str(alias_rows[0][0]), None
    if len(alias_rows) > 1:
        return None, "ALIAS_AMBIGUO"

    candidates = db.query(Courier.id, Courier.nome_resumido).all()
    hits = [str(cid) for (cid, nome) in candidates if norm_text(nome or "") == n]
    if len(hits) == 1:
        return hits[0], None
    if len(hits) > 1:
        return None, "ALIAS_AMBIGUO"

    return None, "NOME_NAO_CADASTRADO"
