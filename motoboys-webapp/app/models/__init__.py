import datetime as dt
import uuid

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, text as sql_text
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base

CourierCategory = PGEnum("SEMANAL", "DIARISTA", name="courier_category", create_type=False)
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


class TimestampMixin:
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sql_text("now()")
    )


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


from .import_log import ImportLog

# Backward-compatible alias expected by import services
Import = ImportLog
