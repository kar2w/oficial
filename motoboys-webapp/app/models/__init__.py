import uuid
import datetime as dt

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    Text,
    Boolean,
    Date,
    DateTime,
    Numeric,
    Integer,
    BigInteger,
    SmallInteger,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM as PGEnum
from sqlalchemy import text as sql_text


class Base(DeclarativeBase):
    pass


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
LoanStatus = PGEnum("ACTIVE", "PAUSED", "DONE", "CANCELLED", name="loan_status", create_type=False)
InstallmentStatus = PGEnum(
    "DUE",
    "PAUSED",
    "PARTIAL",
    "ROLLED",
    "PAID",
    "CANCELLED",
    name="installment_status",
    create_type=False,
)
RoundingMode = PGEnum("REAL", "CENT", name="rounding_mode", create_type=False)


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )


class Week(Base, TimestampMixin):
    __tablename__ = "weeks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    closing_seq: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        server_default=sql_text("nextval('week_closing_seq_seq')"),
    )
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(WeekStatus, nullable=False, server_default=sql_text("'OPEN'"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Courier(Base, TimestampMixin):
    __tablename__ = "couriers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    nome_resumido: Mapped[str] = mapped_column(Text, nullable=False)
    nome_completo: Mapped[str | None] = mapped_column(Text, nullable=True)
    categoria: Mapped[str] = mapped_column(CourierCategory, nullable=False, server_default=sql_text("'DIARISTA'"))
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("true"))


class CourierPayment(Base, TimestampMixin):
    __tablename__ = "courier_payment"

    courier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couriers.id", ondelete="CASCADE"),
        primary_key=True,
    )
    key_type: Mapped[str | None] = mapped_column(PaymentKeyType, nullable=True)
    key_value_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    bank: Mapped[str | None] = mapped_column(Text, nullable=True)


class CourierAlias(Base):
    __tablename__ = "courier_aliases"
    __table_args__ = (
        UniqueConstraint("courier_id", "alias_norm", name="courier_aliases_courier_id_alias_norm_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    courier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couriers.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_raw: Mapped[str] = mapped_column(Text, nullable=False)
    alias_norm: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(ImportSource, nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    imported_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=sql_text("'DONE'"))
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))


class Ride(Base, TimestampMixin):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(ImportSource, nullable=False)
    import_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("imports.id", ondelete="CASCADE"),
        nullable=False,
    )

    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signature_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    order_dt: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    delivery_dt: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    order_date: Mapped[dt.date] = mapped_column(Date, nullable=False)

    week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weeks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    courier_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couriers.id", ondelete="SET NULL"),
        nullable=True,
    )

    courier_name_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    courier_name_norm: Mapped[str | None] = mapped_column(Text, nullable=True)

    value_raw: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fee_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    is_cancelled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(RideStatus, nullable=False, server_default=sql_text("'OK'"))
    pending_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    paid_in_week_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weeks.id", ondelete="SET NULL"),
        nullable=True,
    )

    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=sql_text("'{}'::jsonb"))


class YoogaReviewGroup(Base, TimestampMixin):
    __tablename__ = "yooga_review_groups"
    __table_args__ = (
        UniqueConstraint("week_id", "signature_key", name="yooga_review_groups_week_id_signature_key_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weeks.id", ondelete="CASCADE"),
        nullable=False,
    )
    signature_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(ReviewStatus, nullable=False, server_default=sql_text("'PENDING'"))


class YoogaReviewItem(Base):
    __tablename__ = "yooga_review_items"

    group_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("yooga_review_groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    ride_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="CASCADE"),
        primary_key=True,
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    courier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couriers.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weeks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    effective_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(LedgerType, nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    related_ride_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rides.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )


class WeekPayout(Base):
    __tablename__ = "week_payouts"

    week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weeks.id", ondelete="CASCADE"),
        primary_key=True,
    )
    courier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couriers.id", ondelete="CASCADE"),
        primary_key=True,
    )

    rides_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    extras_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    vales_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    installments_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    net_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    pending_count: Mapped[int] = mapped_column(Integer, nullable=False)
    is_flag_red: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=sql_text("false"))

    computed_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )
    paid_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LoanPlan(Base):
    __tablename__ = "loan_plans"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    courier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("couriers.id", ondelete="CASCADE"),
        nullable=False,
    )

    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    n_installments: Mapped[int] = mapped_column(Integer, nullable=False)

    rounding: Mapped[str] = mapped_column(
        RoundingMode,
        nullable=False,
        server_default=sql_text("'REAL'"),
    )
    status: Mapped[str] = mapped_column(
        LoanStatus,
        nullable=False,
        server_default=sql_text("'ACTIVE'"),
    )

    start_closing_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )


class LoanInstallment(Base):
    __tablename__ = "loan_installments"
    __table_args__ = (
        UniqueConstraint("plan_id", "installment_no", name="loan_installments_plan_id_installment_no_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loan_plans.id", ondelete="CASCADE"),
        nullable=False,
    )

    installment_no: Mapped[int] = mapped_column(Integer, nullable=False)
    due_closing_seq: Mapped[int] = mapped_column(BigInteger, nullable=False)

    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    paid_amount: Mapped[float] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        server_default=sql_text("0"),
    )

    status: Mapped[str] = mapped_column(
        InstallmentStatus,
        nullable=False,
        server_default=sql_text("'DUE'"),
    )

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )


class LoanInstallmentApplication(Base):
    __tablename__ = "loan_installment_applications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    installment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("loan_installments.id", ondelete="CASCADE"),
        nullable=False,
    )
    week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("weeks.id", ondelete="CASCADE"),
        nullable=False,
    )

    applied_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    applied_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
