from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from db import table_registry


@table_registry.mapped_as_dataclass
class InventorySnapshot:
    __tablename__ = 'inventory_snapshots'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, init=False)
    agent_name: Mapped[str] = mapped_column(nullable=False, index=True)
    round_number: Mapped[int] = mapped_column(nullable=False, index=True)
    cash: Mapped[float] = mapped_column(nullable=False)
    apple: Mapped[int] = mapped_column(nullable=False)
    chip: Mapped[int] = mapped_column(nullable=False)
    gold: Mapped[int] = mapped_column(nullable=False)
    energy: Mapped[int] = mapped_column(nullable=False)
    is_alive: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(init=False, server_default=func.now())
