import datetime as dt
import io
from typing import Tuple

import pandas as pd
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Import, Ride, YoogaReviewGroup, YoogaReviewItem
from app.services.courier_match import compute_fee_type, match_courier_id, norm_text
from app.services.week_service import get_open_week_for_date, get_or_create_week_for_date


def _to_float(x) -> float | None:
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return float(x)
    s = str(x).strip().replace("R$", "").strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def _to_dt(x) -> dt.datetime | None:
    if x is None:
        return None
    if isinstance(x, dt.datetime):
        return x
    if isinstance(x, dt.date):
        return dt.datetime.combine(x, dt.time(0, 0))
    s = str(x).strip()
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _detect_excel_engine(filename: str, file_bytes: bytes) -> str | None:
    fn = (filename or "").lower().strip()
    if fn.endswith(".xls"):
        return "xlrd"
    if fn.endswith(".xlsx") or fn.endswith(".xlsm"):
        return "openpyxl"
    if len(file_bytes) >= 2 and file_bytes[:2] == b"PK":
        return "openpyxl"
    if len(file_bytes) >= 8 and file_bytes[:8] == b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1":
        return "xlrd"
    return None


def _read_excel_any(file_bytes: bytes, filename: str) -> pd.DataFrame:
    engine = _detect_excel_engine(filename, file_bytes)
    try:
        if engine:
            return pd.read_excel(io.BytesIO(file_bytes), header=None, engine=engine, dtype=object)
        return pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=object)
    except ImportError as e:
        raise HTTPException(status_code=400, detail=f"Dependência ausente para ler o arquivo Excel ({engine or 'auto'}). Erro: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Arquivo Excel inválido/incompatível: {e}")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Falha ao ler o Excel do Yooga: {e}")


def _resolve_col(headers: list[str], canonical: str, aliases: list[str]) -> int:
    normalized = {norm_text(h): i for i, h in enumerate(headers)}
    for name in [canonical, *aliases]:
        idx = normalized.get(norm_text(name))
        if idx is not None:
            return idx
    raise KeyError(canonical)


def _resolve_yooga_cols(headers: list[str]) -> tuple[int, int, int, int]:
    mapping = {
        "Motoboy": ["Entregador", "Entregador(a)", "Moto boy"],
        "Valor Taxa Motoboy": ["Taxa motoboy", "Valor motoboy", "Valor taxa", "Taxa entrega"],
        "Data do pedido": ["Data pedido", "Data da venda", "Pedido em"],
        "Data de entrega": ["Data entrega", "Entregue em", "Data da entrega"],
    }
    out: dict[str, int] = {}
    missing: list[str] = []
    for canonical, aliases in mapping.items():
        try:
            out[canonical] = _resolve_col(headers, canonical, aliases)
        except KeyError:
            missing.append(canonical)
    if missing:
        raise HTTPException(
            status_code=400,
            detail={"error": "MISSING_REQUIRED_COLUMNS", "source": "YOOGA", "missing": missing, "headers_found": headers},
        )
    return out["Motoboy"], out["Valor Taxa Motoboy"], out["Data do pedido"], out["Data de entrega"]


def import_yooga(db: Session, file_bytes: bytes, filename: str, file_hash: str) -> Tuple[str, int, int, int, int, list[str]]:
    imp = Import(source="YOOGA", filename=filename, file_hash=file_hash, status="DONE", meta={})
    db.add(imp)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(Import).filter(Import.source == "YOOGA", Import.file_hash == file_hash).first()
        return str(existing.id), 0, 0, 0, int((existing.meta or {}).get("redirected_closed_week") or 0), list((existing.meta or {}).get("week_ids_touched") or [])
    db.refresh(imp)

    df = _read_excel_any(file_bytes, filename)

    header_idx = None
    for i in range(min(40, len(df))):
        row = [str(x).strip() if pd.notna(x) else "" for x in df.iloc[i].tolist()]
        normalized = {norm_text(x) for x in row}
        if ("MOTOBOY" in normalized or "ENTREGADOR" in normalized) and any("DATA" in n for n in normalized):
            header_idx = i
            break
    if header_idx is None:
        header_idx = 0

    headers = [str(x).strip() if pd.notna(x) else "" for x in df.iloc[header_idx].tolist()]
    c_moto, c_vtm, c_ped, c_ent = _resolve_yooga_cols(headers)

    inserted = 0
    pend_review = 0
    pend_assign = 0
    redirected_closed_week = 0
    week_ids_touched: set[str] = set()

    sig_counts: dict[str, int] = {}
    rows: list[tuple[int, str, float, dt.datetime, dt.datetime | None, str]] = []

    for i in range(header_idx + 1, len(df)):
        r = df.iloc[i].tolist()
        moto = r[c_moto] if c_moto < len(r) else None
        if moto is None:
            continue
        moto_s = str(moto).strip()
        if not moto_s or norm_text(moto_s) == "TOTAL":
            continue

        value_raw = _to_float(r[c_vtm] if c_vtm < len(r) else None)
        order_dt = _to_dt(r[c_ped] if c_ped < len(r) else None)
        delivery_dt = _to_dt(r[c_ent] if c_ent < len(r) else None)
        if value_raw is None or order_dt is None:
            continue

        signature = f"YOOGA|{order_dt.isoformat()}|{(delivery_dt.isoformat() if delivery_dt else '')}|{norm_text(moto_s)}|{round(value_raw, 2):.2f}"
        sig_counts[signature] = sig_counts.get(signature, 0) + 1
        rows.append((i + 1, moto_s, value_raw, order_dt, delivery_dt, signature))

    existing_sigs = set()
    if rows:
        sig_list = [sig for *_, sig in rows]
        for j in range(0, len(sig_list), 500):
            chunk = sig_list[j : j + 500]
            q = db.query(Ride.signature_key).filter(Ride.source == "YOOGA", Ride.signature_key.in_(chunk))
            existing_sigs.update([x[0] for x in q.all() if x[0] is not None])

    rides: list[Ride] = []
    review_refs: list[tuple] = []
    for row_number, moto_s, value_raw, order_dt, delivery_dt, signature in rows:
        fee_type = compute_fee_type(value_raw)
        order_date = order_dt.date()
        week = get_or_create_week_for_date(db, order_date)
        week_ids_touched.add(str(week.id))

        paid_in_week_id = None
        ops_week_id = week.id
        if week.status != "OPEN":
            payable_week = get_open_week_for_date(db, dt.date.today())
            paid_in_week_id = payable_week.id
            ops_week_id = payable_week.id
            week_ids_touched.add(str(payable_week.id))
            redirected_closed_week += 1

        needs_review = (sig_counts.get(signature, 0) > 1) or (signature in existing_sigs)
        courier_id, match_reason = match_courier_id(db, moto_s)

        if needs_review:
            status = "PENDENTE_REVISAO"
            pending_reason = "YOOGA_ASSINATURA_COLISAO"
            pend_review += 1
        elif courier_id:
            status = "OK"
            pending_reason = None
        else:
            status = "PENDENTE_ATRIBUICAO"
            pending_reason = match_reason or "NOME_NAO_CADASTRADO"
            pend_assign += 1

        ride = Ride(
            source="YOOGA",
            import_id=imp.id,
            external_id=None,
            source_row_number=row_number,
            signature_key=signature,
            order_dt=order_dt,
            delivery_dt=delivery_dt,
            order_date=order_date,
            week_id=week.id,
            courier_id=courier_id,
            courier_name_raw=moto_s,
            courier_name_norm=norm_text(moto_s),
            value_raw=value_raw,
            fee_type=fee_type,
            is_cancelled=None,
            status=status,
            pending_reason=pending_reason,
            paid_in_week_id=paid_in_week_id,
            meta={"row": row_number},
        )
        rides.append(ride)
        if needs_review:
            review_refs.append((ops_week_id, signature, ride))

    if rides:
        db.add_all(rides)
        db.flush()

        groups_by_key: dict[tuple, YoogaReviewGroup] = {}
        for week_id, signature, ride in review_refs:
            key = (week_id, signature)
            grp = groups_by_key.get(key)
            if grp is None:
                grp = db.query(YoogaReviewGroup).filter(YoogaReviewGroup.week_id == week_id, YoogaReviewGroup.signature_key == signature).first()
                if grp is None:
                    grp = YoogaReviewGroup(week_id=week_id, signature_key=signature, status="PENDING")
                    db.add(grp)
                    db.flush()
                groups_by_key[key] = grp
            db.add(YoogaReviewItem(group_id=grp.id, ride_id=ride.id))

        meta = dict(imp.meta or {})
        meta["redirected_closed_week"] = int(redirected_closed_week)
        meta["week_ids_touched"] = sorted(week_ids_touched)
        imp.meta = meta
        db.commit()
        inserted = len(rides)

    return str(imp.id), inserted, pend_assign, pend_review, redirected_closed_week, sorted(week_ids_touched)
