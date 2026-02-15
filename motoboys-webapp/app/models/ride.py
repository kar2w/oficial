import datetime as dt
import uuid

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, SmallInteger, Text, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin
from .dbtypes import GUID, JSONText
from .enums import ImportSource, ReviewStatus, RideStatus


class Ride(Base, TimestampMixin):
    __tablename__ = "rides"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    source: Mapped[str] = mapped_column(ImportSource, nullable=False)
    import_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("imports.id", ondelete="CASCADE"), nullable=False)

    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    signature_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    order_dt: Mapped[dt.datetime] = mapped_column(DateTime(timezone=False), nullable=False)
    delivery_dt: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=False), nullable=True)
    order_date: Mapped[dt.date] = mapped_column(Date, nullable=False)

    week_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("weeks.id", ondelete="RESTRICT"), nullable=False)
    courier_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("couriers.id", ondelete="SET NULL"), nullable=True)

    courier_name_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    courier_name_norm: Mapped[str | None] = mapped_column(Text, nullable=True)

    value_raw: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    fee_type: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    is_cancelled: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    status: Mapped[str] = mapped_column(RideStatus, nullable=False, server_default=sql_text("'OK'"))
    pending_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    paid_in_week_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(), ForeignKey("weeks.id", ondelete="SET NULL"), nullable=True
    )

    meta: Mapped[dict] = mapped_column(JSONText(), nullable=False, default=dict, server_default=sql_text("'{}'"))


class YoogaReviewGroup(Base, TimestampMixin):
    __tablename__ = "yooga_review_groups"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
        server_default=sql_text("gen_random_uuid()"),
    )
    week_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("weeks.id", ondelete="CASCADE"), nullable=False)
    signature_key: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(ReviewStatus, nullable=False, server_default=sql_text("'PENDING'"))


class YoogaReviewItem(Base):
    __tablename__ = "yooga_review_items"

    group_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("yooga_review_groups.id", ondelete="CASCADE"), primary_key=True
    )
    ride_id: Mapped[uuid.UUID] = mapped_column(
        GUID(), ForeignKey("rides.id", ondelete="CASCADE"), primary_key=True
    )
