from sqlalchemy.dialects.postgresql import ENUM as PGEnum

WeekStatus = PGEnum("OPEN", "CLOSED", "PAID", name="week_status", create_type=False)
CourierCategory = PGEnum("SEMANAL", "DIARISTA", name="courier_category", create_type=False)
ImportSource = PGEnum("SAIPOS", "YOOGA", name="import_source", create_type=False)
RideStatus = PGEnum(
    "OK",
    "PENDENTE_ATRIBUICAO",
    "PENDENTE_REVISAO",
    "PENDENTE_MATCH",
    "DESCARTADO",
    name="ride_status",
    create_type=False,
)
LedgerType = PGEnum("EXTRA", "VALE", name="ledger_type", create_type=False)
PaymentKeyType = PGEnum(
    "CPF",
    "CNPJ",
    "TELEFONE",
    "EMAIL",
    "ALEATORIA",
    "OUTRO",
    name="payment_key_type",
    create_type=False,
)
ReviewStatus = PGEnum("PENDING", "RESOLVED", name="review_status", create_type=False)
