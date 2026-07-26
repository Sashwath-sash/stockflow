"""Create the initial StockFlow schema.

Revision ID: 20260725_0001
Revises:
Create Date: 2026-07-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260725_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(120), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "products",
        sa.Column("sku", sa.String(64), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
        sa.UniqueConstraint("sku", name="uq_products_sku"),
    )
    op.create_index("ix_products_sku", "products", ["sku"])
    op.create_index("ix_products_name", "products", ["name"])

    op.create_table(
        "warehouses",
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_warehouses"),
        sa.UniqueConstraint("code", name="uq_warehouses_code"),
    )
    op.create_index("ix_warehouses_code", "warehouses", ["code"])

    op.create_table(
        "inventory",
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("warehouse_id", sa.Uuid(), nullable=False),
        sa.Column("available_quantity", sa.Integer(), nullable=False),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.CheckConstraint(
            "available_quantity >= 0", name="ck_inventory_available_non_negative"
        ),
        sa.CheckConstraint(
            "reserved_quantity >= 0", name="ck_inventory_reserved_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"], ["warehouses.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory"),
        sa.UniqueConstraint(
            "product_id", "warehouse_id", name="uq_inventory_product_id"
        ),
    )
    op.create_index("ix_inventory_product_id", "inventory", ["product_id"])
    op.create_index("ix_inventory_warehouse_id", "inventory", ["warehouse_id"])

    op.create_table(
        "orders",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("reservation_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
    )
    op.create_index("ix_orders_user_id", "orders", ["user_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index(
        "ix_orders_reservation_expires_at", "orders", ["reservation_expires_at"]
    )

    op.create_table(
        "order_items",
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("inventory_id", sa.Uuid(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["inventory_id"], ["inventory.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_order_items"),
    )
    op.create_index("ix_order_items_order_id", "order_items", ["order_id"])
    op.create_index("ix_order_items_product_id", "order_items", ["product_id"])
    op.create_index("ix_order_items_inventory_id", "order_items", ["inventory_id"])

    op.create_table(
        "inventory_movements",
        sa.Column("inventory_id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=True),
        sa.Column("movement_type", sa.String(32), nullable=False),
        sa.Column("available_delta", sa.Integer(), nullable=False),
        sa.Column("reserved_delta", sa.Integer(), nullable=False),
        sa.Column("available_after", sa.Integer(), nullable=False),
        sa.Column("reserved_after", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["inventory_id"], ["inventory.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_inventory_movements"),
    )
    op.create_index(
        "ix_inventory_movements_inventory_id",
        "inventory_movements",
        ["inventory_id"],
    )
    op.create_index(
        "ix_inventory_movements_order_id", "inventory_movements", ["order_id"]
    )
    op.create_index(
        "ix_inventory_movements_movement_type",
        "inventory_movements",
        ["movement_type"],
    )

    op.create_table(
        "idempotency_records",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        *timestamps(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_idempotency_records"),
        sa.UniqueConstraint(
            "user_id", "key", name="uq_idempotency_records_user_id"
        ),
        sa.UniqueConstraint(
            "order_id", name="uq_idempotency_records_order_id"
        ),
    )
    op.create_index(
        "ix_idempotency_records_user_id", "idempotency_records", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_table("inventory_movements")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("inventory")
    op.drop_table("warehouses")
    op.drop_table("products")
    op.drop_table("users")

