from sqlalchemy import Enum


def _enum(*values: str, name: str):
    return Enum(*values, name=name, native_enum=False, create_constraint=False)


WeekStatus = _enum("OPEN", "CLOSED", "PAID", name="week_status")
CourierCategory = _enum("SEMANAL", "DIARISTA", name="courier_category")
ImportSource = _enum("SAIPOS", "YOOGA", name="import_source")
RideStatus = _enum(
    "OK",
    "PENDENTE_ATRIBUICAO",
    "PENDENTE_REVISAO",
    "PENDENTE_MATCH",
    "DESCARTADO",
    name="ride_status",
)
LedgerType = _enum("EXTRA", "VALE", name="ledger_type")
PaymentKeyType = _enum(
    "CPF",
    "CNPJ",
    "TELEFONE",
    "EMAIL",
    "ALEATORIA",
    "OUTRO",
    name="payment_key_type",
)
ReviewStatus = _enum("PENDING", "RESOLVED", name="review_status")
