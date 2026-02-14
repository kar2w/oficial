from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


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


class SeedRequest(BaseModel):
    items: list[dict] = []


class CourierCreate(BaseModel):
    nome_resumido: str
    nome_completo: str | None = None
    categoria: str
    active: bool = True


class CourierPatch(BaseModel):
    nome_resumido: str | None = None
    nome_completo: str | None = None
    categoria: str | None = None
    active: bool | None = None


class CourierAliasCreate(BaseModel):
    alias_raw: str


class CourierAliasOut(BaseModel):
    id: str
    courier_id: str
    alias_raw: str
    alias_norm: str


class CourierPaymentIn(BaseModel):
    key_type: str
    key_value_raw: str
    bank: str | None = None


class CourierPaymentOut(BaseModel):
    courier_id: str
    key_type: str
    key_value_raw: str
    bank: str | None = None


class CourierOut(BaseModel):
    id: str
    nome_resumido: str
    nome_completo: str | None = None
    categoria: str
    active: bool
    payment: CourierPaymentOut | None = None
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
