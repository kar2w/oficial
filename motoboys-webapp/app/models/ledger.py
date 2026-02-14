from sqlalchemy import Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Ledger(Base):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
