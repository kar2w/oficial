from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Week(Base):
    __tablename__ = "weeks"

    id: Mapped[int] = mapped_column(primary_key=True)
    label: Mapped[str] = mapped_column(String(20), nullable=False)
