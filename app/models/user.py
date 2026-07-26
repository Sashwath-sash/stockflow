from __future__ import annotations

from sqlalchemy import Boolean, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import UserRole


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, native_enum=False, length=20),
        default=UserRole.CUSTOMER,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    orders: Mapped[list["Order"]] = relationship(back_populates="user")
    idempotency_records: Mapped[list["IdempotencyRecord"]] = relationship(
        back_populates="user"
    )

