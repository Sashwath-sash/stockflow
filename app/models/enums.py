from enum import StrEnum


class UserRole(StrEnum):
    CUSTOMER = "customer"
    ADMIN = "admin"


class OrderStatus(StrEnum):
    PENDING = "pending"
    RESERVED = "reserved"
    PAID = "paid"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    FAILED = "failed"
    EXPIRED = "expired"


class MovementType(StrEnum):
    STOCK_ADDED = "stock_added"
    STOCK_ADJUSTED = "stock_adjusted"
    STOCK_RESERVED = "stock_reserved"
    RESERVATION_RELEASED = "reservation_released"
    ORDER_FULFILLED = "order_fulfilled"

