from pydantic import BaseModel, Field
from typing import Literal, Optional, List

class ImportResponse(BaseModel):
    import_id: str
    source: Literal["SAIPOS","YOOGA"]
    filename: str
    inserted: int
    pendente_atribuicao: int
    pendente_revisao: int

class AssignRideBody(BaseModel):
    courier_id: str
    pay_in_current_week: bool = True

class ResolveYoogaBody(BaseModel):
    action: Literal["APPROVE_ALL", "KEEP_ONE"]
    keep_ride_id: Optional[str] = None

class SeedCourier(BaseModel):
    nome_exibicao: str
    nome_completo: Optional[str] = None
    tipo_contrato: Optional[str] = "semanais"
    pagamento: Optional[dict] = None

class SeedRequest(BaseModel):
    entregadores: List[SeedCourier]


# =====================
# Couriers CRUD (v1.0)
# =====================

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
    aliases: List[CourierAliasOut] = []


# =====================
# Ledger (extras/vales)
# =====================

LedgerTypeLiteral = Literal["EXTRA", "VALE"]


class LedgerEntryCreate(BaseModel):
    courier_id: str
    week_id: str
    effective_date: str  # YYYY-MM-DD
    type: LedgerTypeLiteral
    amount: float = Field(..., gt=0)
    related_ride_id: Optional[str] = None
    note: Optional[str] = None


class LedgerEntryOut(BaseModel):
    id: str
    courier_id: str
    week_id: str
    effective_date: str
    type: LedgerTypeLiteral
    amount: float
    related_ride_id: Optional[str] = None
    note: Optional[str] = None
    created_at: str


# =====================
# Week payouts
# =====================


class WeekPayoutPreviewRow(BaseModel):
    courier_id: Optional[str] = None
    courier_nome: Optional[str] = None
    rides_count: int = 0
    rides_amount: float = 0.0
    rides_value_raw_amount: float = 0.0
    extras_amount: float = 0.0
    vales_amount: float = 0.0
    installments_amount: float = 0.0
    net_amount: float = 0.0
    pending_count: int = 0


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
    computed_at: str
    paid_at: Optional[str] = None
