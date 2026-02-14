from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ImportLog(Base):
    __tablename__ = "import_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
