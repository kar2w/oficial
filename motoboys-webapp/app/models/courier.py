from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Courier(Base):
    __tablename__ = "couriers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
