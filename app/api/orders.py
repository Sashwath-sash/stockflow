import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.dependencies import AdminUser, CurrentUser, DbSession
from app.models.enums import MovementType, OrderStatus, UserRole
from app.models.inventory import Inventory
from app.models.order import Order
from app.schemas.orders import (
    OrderCreateRequest,
    OrderResponse,
    PaymentRequest,
    PaymentResult,
)
from app.services.inventory import record_movement
from app.services.orders import create_reserved_order, load_order, release_reservation

router = APIRouter(prefix="/orders", tags=["orders"])
admin_router = APIRouter(prefix="/admin/orders", tags=["administration"])


def authorized_order(db: DbSession, order_id: uuid.UUID, user: CurrentUser) -> Order:
    order = load_order(db, order_id)
    if order is None or (
        order.user_id != user.id and user.role != UserRole.ADMIN
    ):
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    payload: OrderCreateRequest,
    response: Response,
    db: DbSession,
    current_user: CurrentUser,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=128),
    ],
) -> Order:
    try:
        order, created = create_reserved_order(
            db,
            user_id=current_user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
    except Exception:
        db.rollback()
        raise
    if not created:
        response.status_code = status.HTTP_200_OK
    return order


@router.get("", response_model=list[OrderResponse])
def list_my_orders(db: DbSession, current_user: CurrentUser) -> list[Order]:
    statement = (
        select(Order)
        .where(Order.user_id == current_user.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc())
    )
    return list(db.scalars(statement).all())


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Order:
    return authorized_order(db, order_id, current_user)


@router.post("/{order_id}/payment", response_model=OrderResponse)
def simulate_payment(
    order_id: uuid.UUID,
    payload: PaymentRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> Order:
    order = authorized_order(db, order_id, current_user)
    if order.status != OrderStatus.RESERVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment is not allowed for an order in {order.status} status",
        )
    if order.reservation_expires_at and order.reservation_expires_at <= datetime.now(UTC):
        return release_reservation(
            db,
            order=order,
            final_status=OrderStatus.EXPIRED,
            reason="Reservation expired before payment",
        )
    if payload.result == PaymentResult.FAILURE:
        return release_reservation(
            db,
            order=order,
            final_status=OrderStatus.FAILED,
            reason="Simulated payment failed",
        )

    order.status = OrderStatus.PAID
    db.commit()
    refreshed = load_order(db, order.id)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="Order could not be loaded")
    return refreshed


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> Order:
    order = authorized_order(db, order_id, current_user)
    if order.status != OrderStatus.RESERVED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cancellation is not allowed for an order in {order.status} status",
        )
    return release_reservation(
        db,
        order=order,
        final_status=OrderStatus.CANCELLED,
        reason="Order cancelled by customer",
    )


@admin_router.get("", response_model=list[OrderResponse])
def list_all_orders(db: DbSession, _admin: AdminUser) -> list[Order]:
    return list(
        db.scalars(
            select(Order)
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
        ).all()
    )


@admin_router.post("/{order_id}/fulfil", response_model=OrderResponse)
def fulfil_order(
    order_id: uuid.UUID,
    db: DbSession,
    _admin: AdminUser,
) -> Order:
    order = load_order(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status != OrderStatus.PAID:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Fulfilment is not allowed for an order in {order.status} status",
        )

    inventory_ids = [item.inventory_id for item in order.items]
    inventories = {
        item.id: item
        for item in db.scalars(
            select(Inventory)
            .where(Inventory.id.in_(inventory_ids))
            .order_by(Inventory.id)
            .with_for_update()
        ).all()
    }
    for item in order.items:
        inventory = inventories[item.inventory_id]
        if inventory.reserved_quantity < item.quantity:
            raise HTTPException(status_code=500, detail="Reserved stock invariant failed")
        inventory.reserved_quantity -= item.quantity
        record_movement(
            db,
            inventory=inventory,
            order_id=order.id,
            movement_type=MovementType.ORDER_FULFILLED,
            available_delta=0,
            reserved_delta=-item.quantity,
            reason="Paid order fulfilled",
        )
    order.status = OrderStatus.FULFILLED
    db.commit()
    refreshed = load_order(db, order.id)
    if refreshed is None:
        raise HTTPException(status_code=500, detail="Order could not be loaded")
    return refreshed

