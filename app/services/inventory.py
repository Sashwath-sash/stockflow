import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MovementType
from app.models.inventory import Inventory
from app.models.ledger import InventoryMovement


def lock_inventory(
    db: Session,
    *,
    product_id: uuid.UUID,
    warehouse_id: uuid.UUID,
) -> Inventory | None:
    statement = (
        select(Inventory)
        .where(
            Inventory.product_id == product_id,
            Inventory.warehouse_id == warehouse_id,
        )
        .with_for_update()
    )
    return db.scalar(statement)


def record_movement(
    db: Session,
    *,
    inventory: Inventory,
    movement_type: MovementType,
    available_delta: int,
    reserved_delta: int,
    order_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> InventoryMovement:
    movement = InventoryMovement(
        inventory_id=inventory.id,
        order_id=order_id,
        movement_type=movement_type,
        available_delta=available_delta,
        reserved_delta=reserved_delta,
        available_after=inventory.available_quantity,
        reserved_after=inventory.reserved_quantity,
        reason=reason,
    )
    db.add(movement)
    return movement

