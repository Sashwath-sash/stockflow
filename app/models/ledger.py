from __future__ import annotations

import uuid

from sqlalchemy import Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import MovementType


class InventoryMovement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory_movements"

    inventory_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("inventory.id", ondelete="RESTRICT"), index=True
    )
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    movement_type: Mapped[MovementType] = mapped_column(
        Enum(MovementType, native_enum=False, length=32), index=True
    )
    available_delta: Mapped[int] = mapped_column(Integer)
    reserved_delta: Mapped[int] = mapped_column(Integer)
    available_after: Mapped[int] = mapped_column(Integer)
    reserved_after: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    inventory: Mapped["Inventory"] = relationship(back_populates="movements")
    order: Mapped["Order | None"] = relationship(back_populates="movements")

