import pytest
from fastapi import HTTPException

from app.services.import_saipos import _resolve_saipos_cols
from app.services.import_yooga import _detect_excel_engine, _resolve_yooga_cols


def test_resolve_saipos_cols_accepts_aliases():
    headers = [
        "ID pedido",
        "Data venda",
        "Motoboy",
        "Taxa entregador",
        "Cancelado",
    ]

    idx_id, idx_dt, idx_courier, idx_val, idx_cancel = _resolve_saipos_cols(headers)

    assert (idx_id, idx_dt, idx_courier, idx_val, idx_cancel) == (0, 1, 2, 3, 4)


def test_resolve_saipos_cols_reports_missing_required_columns():
    with pytest.raises(HTTPException) as exc:
        _resolve_saipos_cols(["Data da venda", "Entregador"])

    detail = exc.value.detail
    assert detail["error"] == "MISSING_REQUIRED_COLUMNS"
    assert "Id do pedido no parceiro" in detail["missing"]
    assert "Valor Entregador" in detail["missing"]


def test_resolve_yooga_cols_accepts_aliases():
    headers = ["Entregador", "Taxa entrega", "Data pedido", "Entregue em"]

    idx_moto, idx_fee, idx_order, idx_delivery = _resolve_yooga_cols(headers)

    assert (idx_moto, idx_fee, idx_order, idx_delivery) == (0, 1, 2, 3)


def test_detect_excel_engine_by_extension_and_magic_bytes():
    assert _detect_excel_engine("arquivo.xls", b"dummy") == "xlrd"
    assert _detect_excel_engine("arquivo.any", b"PK\x03\x04anything") == "openpyxl"
