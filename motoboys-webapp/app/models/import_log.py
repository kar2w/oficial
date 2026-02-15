import datetime as dt
import uuid

from sqlalchemy import DateTime, Text, text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .dbtypes import GUID, JSONText
from .enums import ImportSource


class Import(Base):
    __tablename__ = "imports"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
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
    meta: Mapped[dict] = mapped_column(JSONText(), nullable=False, default=dict, server_default=sql_text("'{}'"))
