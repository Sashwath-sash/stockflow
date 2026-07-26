import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MovementType


class ProductCreate(BaseModel):
    sku: str = Field(min_length=2, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    sku: str
    name: str
    description: str | None
    price: Decimal
    is_active: bool
    available_quantity: int = 0


class WarehouseCreate(BaseModel):
    code: str = Field(min_length=2, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=120)
    location: str = Field(min_length=2, max_length=255)


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    name: str
    location: str
    is_active: bool


class StockAdjustmentRequest(BaseModel):
    product_id: uuid.UUID
    warehouse_id: uuid.UUID
    quantity_delta: int = Field(ne=0, ge=-100000, le=100000)
    reason: str = Field(min_length=3, max_length=255)


class InventoryResponse(BaseModel):
    id: uuid.UUID
    product_id: uuid.UUID
    product_name: str
    product_sku: str
    warehouse_id: uuid.UUID
    warehouse_name: str
    available_quantity: int
    reserved_quantity: int


class MovementResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    inventory_id: uuid.UUID
    order_id: uuid.UUID | None
    movement_type: MovementType
    available_delta: int
    reserved_delta: int
    available_after: int
    reserved_after: int
    reason: str | None
    created_at: datetime

