import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OrderStatus


class OrderLineRequest(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity: int = Field(ge=1, le=100)


class OrderCreateRequest(BaseModel):
    items: list[OrderLineRequest] = Field(min_length=1, max_length=25)


class OrderItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    inventory_id: uuid.UUID
    quantity: int
    unit_price: Decimal


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: OrderStatus
    total_amount: Decimal
    reservation_expires_at: datetime | None
    created_at: datetime
    items: list[OrderItemResponse]


class PaymentResult(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"


class PaymentRequest(BaseModel):
    result: PaymentResult

