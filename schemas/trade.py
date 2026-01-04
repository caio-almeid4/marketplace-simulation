from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from db import table_registry


@table_registry.mapped_as_dataclass
class Trade:
    __tablename__ = 'trades'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    supplier: Mapped[str] = mapped_column(nullable=False)
    buyer: Mapped[str] = mapped_column(nullable=False)
    item: Mapped[str] = mapped_column(nullable=False)
    quantity: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)
    message: Mapped[str]
    offer_type: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())


class UnitTrade(BaseModel):
    supplier: str
    buyer: str
    item: str
    quantity: int
    price: float
