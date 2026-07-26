import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.dependencies import AdminUser, DbSession
from app.models.enums import MovementType
from app.models.inventory import Inventory
from app.models.ledger import InventoryMovement
from app.models.product import Product
from app.models.warehouse import Warehouse
from app.schemas.catalog import (
    InventoryResponse,
    MovementResponse,
    ProductCreate,
    ProductResponse,
    StockAdjustmentRequest,
    WarehouseCreate,
    WarehouseResponse,
)
from app.services.inventory import record_movement

router = APIRouter(prefix="/catalog", tags=["catalog"])
admin_router = APIRouter(prefix="/admin", tags=["administration"])


@router.get("/products", response_model=list[ProductResponse])
def list_products(
    db: DbSession,
    search: str | None = Query(default=None, max_length=100),
) -> list[ProductResponse]:
    stock = (
        select(
            Inventory.product_id,
            func.coalesce(func.sum(Inventory.available_quantity), 0).label("available"),
        )
        .group_by(Inventory.product_id)
        .subquery()
    )
    statement = (
        select(Product, func.coalesce(stock.c.available, 0))
        .outerjoin(stock, Product.id == stock.c.product_id)
        .where(Product.is_active.is_(True))
        .order_by(Product.name)
    )
    if search:
        statement = statement.where(Product.name.ilike(f"%{search}%"))
    rows = db.execute(statement).all()
    return [
        ProductResponse.model_validate(product).model_copy(
            update={"available_quantity": int(available)}
        )
        for product, available in rows
    ]


@router.get("/availability", response_model=list[InventoryResponse])
def list_availability(db: DbSession) -> list[InventoryResponse]:
    statement = (
        select(Inventory)
        .options(
            selectinload(Inventory.product),
            selectinload(Inventory.warehouse),
        )
        .where(
            Inventory.available_quantity > 0,
            Product.is_active.is_(True),
            Warehouse.is_active.is_(True),
        )
        .join(Inventory.product)
        .join(Inventory.warehouse)
        .order_by(Product.name, Warehouse.name)
    )
    records = db.scalars(statement).all()
    return [
        InventoryResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name,
            product_sku=item.product.sku,
            warehouse_id=item.warehouse_id,
            warehouse_name=item.warehouse.name,
            available_quantity=item.available_quantity,
            reserved_quantity=item.reserved_quantity,
        )
        for item in records
    ]


@admin_router.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    payload: ProductCreate,
    db: DbSession,
    _admin: AdminUser,
) -> ProductResponse:
    product = Product(
        sku=payload.sku.upper(),
        name=payload.name.strip(),
        description=payload.description,
        price=payload.price,
    )
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A product with this SKU already exists",
        ) from None
    db.refresh(product)
    return ProductResponse.model_validate(product)


@admin_router.get("/warehouses", response_model=list[WarehouseResponse])
def list_warehouses(db: DbSession, _admin: AdminUser) -> list[Warehouse]:
    return list(db.scalars(select(Warehouse).order_by(Warehouse.name)).all())


@admin_router.post(
    "/warehouses",
    response_model=WarehouseResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_warehouse(
    payload: WarehouseCreate,
    db: DbSession,
    _admin: AdminUser,
) -> Warehouse:
    warehouse = Warehouse(
        code=payload.code.upper(),
        name=payload.name.strip(),
        location=payload.location.strip(),
    )
    db.add(warehouse)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A warehouse with this code already exists",
        ) from None
    db.refresh(warehouse)
    return warehouse


@admin_router.get("/inventory", response_model=list[InventoryResponse])
def list_inventory(db: DbSession, _admin: AdminUser) -> list[InventoryResponse]:
    statement = (
        select(Inventory)
        .options(
            selectinload(Inventory.product),
            selectinload(Inventory.warehouse),
        )
        .order_by(Inventory.updated_at.desc())
    )
    records = db.scalars(statement).all()
    return [
        InventoryResponse(
            id=item.id,
            product_id=item.product_id,
            product_name=item.product.name,
            product_sku=item.product.sku,
            warehouse_id=item.warehouse_id,
            warehouse_name=item.warehouse.name,
            available_quantity=item.available_quantity,
            reserved_quantity=item.reserved_quantity,
        )
        for item in records
    ]


@admin_router.post("/inventory/adjust", response_model=InventoryResponse)
def adjust_inventory(
    payload: StockAdjustmentRequest,
    db: DbSession,
    _admin: AdminUser,
) -> InventoryResponse:
    product = db.get(Product, payload.product_id)
    warehouse = db.get(Warehouse, payload.warehouse_id)
    if product is None or warehouse is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product or warehouse not found",
        )

    inventory = db.scalar(
        select(Inventory)
        .where(
            Inventory.product_id == payload.product_id,
            Inventory.warehouse_id == payload.warehouse_id,
        )
        .with_for_update()
    )
    if inventory is None:
        if payload.quantity_delta < 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot remove stock from an empty inventory record",
            )
        inventory = Inventory(
            product_id=payload.product_id,
            warehouse_id=payload.warehouse_id,
        )
        db.add(inventory)
        db.flush()

    new_quantity = inventory.available_quantity + payload.quantity_delta
    if new_quantity < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Adjustment would make available inventory negative",
        )
    inventory.available_quantity = new_quantity
    record_movement(
        db,
        inventory=inventory,
        movement_type=(
            MovementType.STOCK_ADDED
            if payload.quantity_delta > 0
            else MovementType.STOCK_ADJUSTED
        ),
        available_delta=payload.quantity_delta,
        reserved_delta=0,
        reason=payload.reason,
    )
    db.commit()
    db.refresh(inventory)
    return InventoryResponse(
        id=inventory.id,
        product_id=inventory.product_id,
        product_name=product.name,
        product_sku=product.sku,
        warehouse_id=inventory.warehouse_id,
        warehouse_name=warehouse.name,
        available_quantity=inventory.available_quantity,
        reserved_quantity=inventory.reserved_quantity,
    )


@admin_router.get("/inventory/movements", response_model=list[MovementResponse])
def list_movements(
    db: DbSession,
    _admin: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[InventoryMovement]:
    return list(
        db.scalars(
            select(InventoryMovement)
            .order_by(InventoryMovement.created_at.desc())
            .limit(limit)
        ).all()
    )
