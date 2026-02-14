from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ImportResponse(BaseModel):
    import_id: str
    source: str
    filename: str | None = None
    inserted: int
    pendente_atribuicao: int
    pendente_revisao: int


class AssignRideBody(BaseModel):
    courier_id: str
    pay_in_current_week: bool = False


class ResolveYoogaBody(BaseModel):
    action: str
    keep_ride_id: str | None = None


class SeedCourierPayment(BaseModel):
    chave: Optional[str] = None
    banco: Optional[str] = None


class SeedCourier(BaseModel):
    nome_exibicao: str
    nome_completo: Optional[str] = None
    pagamento: Optional[SeedCourierPayment] = None


class SeedRequest(BaseModel):
    entregadores: list[SeedCourier]


CourierCategoryLiteral = Literal["SEMANAL", "DIARISTA"]
PaymentKeyTypeLiteral = Literal["CPF", "CNPJ", "TELEFONE", "EMAIL", "ALEATORIA", "OUTRO"]


class CourierPaymentIn(BaseModel):
    key_type: Optional[PaymentKeyTypeLiteral] = None
    key_value_raw: Optional[str] = None
    bank: Optional[str] = None


class CourierPaymentOut(CourierPaymentIn):
    courier_id: str


class CourierAliasCreate(BaseModel):
    alias_raw: str = Field(..., min_length=1)


class CourierAliasOut(BaseModel):
    id: str
    courier_id: str
    alias_raw: str
    alias_norm: str


class CourierCreate(BaseModel):
    nome_resumido: str = Field(..., min_length=1)
    nome_completo: Optional[str] = None
    categoria: CourierCategoryLiteral = "DIARISTA"
    active: bool = True


class CourierPatch(BaseModel):
    nome_resumido: Optional[str] = Field(default=None, min_length=1)
    nome_completo: Optional[str] = None
    categoria: Optional[CourierCategoryLiteral] = None
    active: Optional[bool] = None


class CourierOut(BaseModel):
    id: str
    nome_resumido: str
    nome_completo: Optional[str]
    categoria: CourierCategoryLiteral
    active: bool
    payment: Optional[CourierPaymentOut] = None
    aliases: list[CourierAliasOut] = []


class LedgerEntryCreate(BaseModel):
    courier_id: str
    week_id: str
    effective_date: date
    type: str
    amount: float
    related_ride_id: str | None = None
    note: str | None = None


class LedgerEntryOut(BaseModel):
    id: str
    courier_id: str
    week_id: str
    effective_date: date
    type: str
    amount: float
    related_ride_id: str | None = None
    note: str | None = None


class WeekPayoutPreviewRow(BaseModel):
    courier_id: str | None = None
    courier_nome: str | None = None
    rides_count: int
    rides_amount: float
    rides_value_raw_amount: float = 0.0
    extras_amount: float
    vales_amount: float
    installments_amount: float
    net_amount: float
    pending_count: int


class WeekPayoutSnapshotRow(BaseModel):
    courier_id: str
    courier_nome: str
    rides_amount: float
    extras_amount: float
    vales_amount: float
    installments_amount: float
    net_amount: float
    pending_count: int
    is_flag_red: bool
    computed_at: str | datetime
    paid_at: str | datetime | None = None
