import datetime as dt
import uuid

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, Text, text as sql_text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin
from .enums import WeekStatus


class Week(Base, TimestampMixin):
    __tablename__ = "weeks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    closing_seq: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=sql_text("nextval('week_closing_seq_seq')"))
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(WeekStatus, nullable=False, server_default=sql_text("'OPEN'"))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class WeekPayout(Base):
    __tablename__ = "week_payouts"

    week_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("weeks.id", ondelete="CASCADE"), primary_key=True
    )
    courier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("couriers.id", ondelete="CASCADE"), primary_key=True
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
