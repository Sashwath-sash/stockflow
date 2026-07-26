import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.enums import MovementType, OrderStatus
from app.models.idempotency import IdempotencyRecord
from app.models.inventory import Inventory
from app.models.order import Order, OrderItem
from app.models.product import Product
from app.schemas.orders import OrderCreateRequest
from app.services.inventory import record_movement

RESERVATION_MINUTES = 15


def request_digest(payload: OrderCreateRequest) -> str:
    value = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(value.encode()).hexdigest()


def load_order(db: Session, order_id: uuid.UUID) -> Order | None:
    return db.scalar(
        select(Order)
        .where(Order.id == order_id)
        .options(selectinload(Order.items))
    )


def create_reserved_order(
    db: Session,
    *,
    user_id: uuid.UUID,
    payload: OrderCreateRequest,
    idempotency_key: str,
) -> tuple[Order, bool]:
    digest = request_digest(payload)
    existing = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != digest:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This idempotency key was already used for a different request",
            )
        order = load_order(db, existing.order_id)
        if order is None:
            raise HTTPException(status_code=500, detail="Stored order could not be loaded")
        return order, False

    grouped: dict[tuple[uuid.UUID, uuid.UUID], int] = {}
    for line in payload.items:
        key = (line.product_id, line.warehouse_id)
        grouped[key] = grouped.get(key, 0) + line.quantity

    order = Order(
        user_id=user_id,
        status=OrderStatus.PENDING,
        total_amount=Decimal("0.00"),
        reservation_expires_at=datetime.now(UTC) + timedelta(minutes=RESERVATION_MINUTES),
    )
    db.add(order)
    db.flush()

    total = Decimal("0.00")
    sorted_lines = sorted(grouped.items(), key=lambda item: (str(item[0][1]), str(item[0][0])))
    for (product_id, warehouse_id), quantity in sorted_lines:
        inventory = db.scalar(
            select(Inventory)
            .where(
                Inventory.product_id == product_id,
                Inventory.warehouse_id == warehouse_id,
            )
            .with_for_update()
        )
        product = db.get(Product, product_id)
        if product is None or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product {product_id} was not found or is inactive",
            )
        if inventory is None or inventory.available_quantity < quantity:
            available = inventory.available_quantity if inventory else 0
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"Insufficient stock for {product.name}: "
                    f"requested {quantity}, available {available}"
                ),
            )

        inventory.available_quantity -= quantity
        inventory.reserved_quantity += quantity
        item = OrderItem(
            order_id=order.id,
            product_id=product.id,
            inventory_id=inventory.id,
            quantity=quantity,
            unit_price=product.price,
        )
        db.add(item)
        total += product.price * quantity
        record_movement(
            db,
            inventory=inventory,
            order_id=order.id,
            movement_type=MovementType.STOCK_RESERVED,
            available_delta=-quantity,
            reserved_delta=quantity,
            reason="Inventory reserved for order",
        )

    order.total_amount = total
    order.status = OrderStatus.RESERVED
    db.add(
        IdempotencyRecord(
            user_id=user_id,
            key=idempotency_key,
            request_hash=digest,
            order_id=order.id,
        )
    )
    db.commit()
    loaded = load_order(db, order.id)
    if loaded is None:
        raise HTTPException(status_code=500, detail="Order could not be loaded")
    return loaded, True


def release_reservation(
    db: Session,
    *,
    order: Order,
    final_status: OrderStatus,
    reason: str,
) -> Order:
    item_ids = [item.inventory_id for item in order.items]
    inventories = {
        inventory.id: inventory
        for inventory in db.scalars(
            select(Inventory)
            .where(Inventory.id.in_(item_ids))
            .order_by(Inventory.id)
            .with_for_update()
        ).all()
    }
    for item in order.items:
        inventory = inventories[item.inventory_id]
        if inventory.reserved_quantity < item.quantity:
            raise HTTPException(
                status_code=500,
                detail="Inventory reservation invariant was violated",
            )
        inventory.available_quantity += item.quantity
        inventory.reserved_quantity -= item.quantity
        record_movement(
            db,
            inventory=inventory,
            order_id=order.id,
            movement_type=MovementType.RESERVATION_RELEASED,
            available_delta=item.quantity,
            reserved_delta=-item.quantity,
            reason=reason,
        )
    order.status = final_status
    db.commit()
    refreshed = load_order(db, order.id)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="Order could not be loaded")
    return refreshed

