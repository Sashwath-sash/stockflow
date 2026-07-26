from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin


class Inventory(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "inventory"
    __table_args__ = (
        UniqueConstraint("product_id", "warehouse_id"),
        CheckConstraint("available_quantity >= 0", name="available_non_negative"),
        CheckConstraint("reserved_quantity >= 0", name="reserved_non_negative"),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), index=True
    )
    warehouse_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"), index=True
    )
    available_quantity: Mapped[int] = mapped_column(Integer, default=0)
    reserved_quantity: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship(back_populates="inventory")
    warehouse: Mapped["Warehouse"] = relationship(back_populates="inventory")
    movements: Mapped[list["InventoryMovement"]] = relationship(
        back_populates="inventory"
    )
    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="inventory")

