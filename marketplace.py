"""Shared marketplace data and operations for the Streamlit storefront."""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal

from pwdlib import PasswordHash
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    create_engine,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

password_hash = PasswordHash.recommended()


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "marketplace_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_digest: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10), index=True)
    public_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    public_location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    public_contact: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class Listing(Base):
    __tablename__ = "marketplace_listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("marketplace_accounts.id"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    quantity: Mapped[int] = mapped_column(Integer)
    low_stock_at: Mapped[int] = mapped_column(Integer, default=5)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    seller: Mapped[Account] = relationship()


class Purchase(Base):
    __tablename__ = "marketplace_purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("marketplace_accounts.id"), index=True)
    buyer_id: Mapped[int] = mapped_column(ForeignKey("marketplace_accounts.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="requested")
    buyer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    listing: Mapped[Listing] = relationship()
    seller: Mapped[Account] = relationship(foreign_keys=[seller_id])
    buyer: Mapped[Account] = relationship(foreign_keys=[buyer_id])


class StockMovement(Base):
    __tablename__ = "marketplace_stock_movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("marketplace_listings.id"), index=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("marketplace_accounts.id"), index=True)
    quantity_change: Mapped[int] = mapped_column(Integer)
    resulting_quantity: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    listing: Mapped[Listing] = relationship()


def database_url() -> str:
    url = os.environ.get("STOCKFLOW_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not url:
        try:
            import streamlit as st

            url = st.secrets.get("STOCKFLOW_DATABASE_URL") or st.secrets.get("DATABASE_URL")
        except (FileNotFoundError, KeyError):
            pass
    if not url:
        raise RuntimeError(
            "STOCKFLOW_DATABASE_URL is required. Use a hosted PostgreSQL database for a public app."
        )
    return url


def make_session_factory(url: str | None = None):
    url = url or database_url()
    if url.startswith("postgres://"):
        url = "postgresql+psycopg://" + url[len("postgres://") :]
    elif url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://") :]
    engine = create_engine(url, pool_pre_ping=True)
    Base.metadata.create_all(engine)
    return sessionmaker(engine, expire_on_commit=False)


@contextmanager
def session_scope(factory):
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def register(
    factory,
    *,
    email: str,
    name: str,
    password: str,
    role: str,
    public_name: str = "",
    public_location: str = "",
    public_contact: str = "",
) -> Account:
    email = email.strip().lower()
    name = name.strip()
    if role not in {"seller", "buyer"} or not name or "@" not in email or len(password) < 8:
        raise ValueError("Enter a name, valid email, and password of at least 8 characters.")
    if role == "seller" and not public_name.strip():
        raise ValueError("Enter a public shop name.")
    account = Account(
        email=email,
        name=name,
        password_digest=password_hash.hash(password),
        role=role,
        public_name=public_name.strip() or None,
        public_location=public_location.strip() or None,
        public_contact=public_contact.strip() or None,
    )
    try:
        with session_scope(factory) as db:
            db.add(account)
            db.flush()
        return account
    except IntegrityError:
        raise ValueError("An account with this email already exists.") from None


def authenticate(factory, email: str, password: str) -> Account | None:
    with session_scope(factory) as db:
        account = db.scalar(select(Account).where(Account.email == email.strip().lower()))
        if (
            account
            and account.role in {"seller", "buyer"}
            and password_hash.verify(password, account.password_digest)
        ):
            return account
    return None


def get_account(factory, account_id: int) -> Account | None:
    with session_scope(factory) as db:
        account = db.get(Account, account_id)
        return account if account and account.role in {"seller", "buyer"} else None


def update_seller_profile(
    factory, seller_id: int, *, public_name: str, public_location: str, public_contact: str
) -> None:
    if not public_name.strip():
        raise ValueError("Shop name is required.")
    with session_scope(factory) as db:
        seller = db.get(Account, seller_id)
        if seller is None or seller.role != "seller":
            raise PermissionError("Seller account required.")
        seller.public_name = public_name.strip()
        seller.public_location = public_location.strip() or None
        seller.public_contact = public_contact.strip() or None


def create_listing(
    factory,
    seller_id: int,
    *,
    title: str,
    description: str,
    category: str,
    price: Decimal,
    currency: str,
    quantity: int,
    low_stock_at: int = 5,
) -> Listing:
    if (
        not title.strip()
        or not category.strip()
        or price <= 0
        or quantity < 0
        or low_stock_at < 0
        or currency not in {"INR", "USD", "EUR", "GBP"}
    ):
        raise ValueError("Enter a title, category, positive price, and valid stock quantity.")
    with session_scope(factory) as db:
        seller = db.get(Account, seller_id)
        if seller is None or seller.role != "seller":
            raise PermissionError("Seller account required.")
        listing = Listing(
            seller_id=seller_id,
            title=title.strip(),
            description=description.strip(),
            category=category.strip(),
            price=price,
            currency=currency,
            quantity=quantity,
            low_stock_at=low_stock_at,
        )
        db.add(listing)
        db.flush()
        if quantity:
            db.add(
                StockMovement(
                    listing_id=listing.id,
                    seller_id=seller_id,
                    quantity_change=quantity,
                    resulting_quantity=quantity,
                    reason="Initial stock",
                )
            )
        return listing


def update_listing(
    factory,
    seller_id: int,
    listing_id: int,
    *,
    title: str,
    description: str,
    category: str,
    price: Decimal,
    currency: str,
    active: bool,
    low_stock_at: int = 5,
) -> None:
    if (
        not title.strip()
        or not category.strip()
        or price <= 0
        or low_stock_at < 0
        or currency not in {"INR", "USD", "EUR", "GBP"}
    ):
        raise ValueError("Enter a title, category, positive price, and valid stock quantity.")
    with session_scope(factory) as db:
        listing = db.get(Listing, listing_id)
        if listing is None or listing.seller_id != seller_id:
            raise PermissionError("This listing is not yours.")
        listing.title, listing.description, listing.category = (
            title.strip(),
            description.strip(),
            category.strip(),
        )
        listing.price, listing.currency, listing.active, listing.low_stock_at = (
            price,
            currency,
            active,
            low_stock_at,
        )


def adjust_stock(
    factory, seller_id: int, listing_id: int, quantity_change: int, reason: str
) -> int:
    if quantity_change == 0 or not reason.strip():
        raise ValueError("Enter a nonzero stock change and a reason.")
    with session_scope(factory) as db:
        listing = db.get(Listing, listing_id)
        if listing is None or listing.seller_id != seller_id:
            raise PermissionError("This listing is not yours.")
        result = db.execute(
            update(Listing)
            .where(Listing.id == listing_id, Listing.quantity + quantity_change >= 0)
            .values(quantity=Listing.quantity + quantity_change)
        )
        if result.rowcount != 1:
            raise ValueError("This adjustment would make stock negative.")
        db.refresh(listing)
        db.add(
            StockMovement(
                listing_id=listing_id,
                seller_id=seller_id,
                quantity_change=quantity_change,
                resulting_quantity=listing.quantity,
                reason=reason.strip()[:120],
            )
        )
        return listing.quantity


def stock_movements(factory, seller_id: int, limit: int = 100) -> list[StockMovement]:
    with session_scope(factory) as db:
        movements = list(
            db.scalars(
                select(StockMovement)
                .where(StockMovement.seller_id == seller_id)
                .order_by(StockMovement.created_at.desc(), StockMovement.id.desc())
                .limit(limit)
            ).all()
        )
        for movement in movements:
            _ = movement.listing
        return movements


def public_listings(factory, search: str = "") -> list[Listing]:
    with session_scope(factory) as db:
        query = select(Listing).where(Listing.active.is_(True)).order_by(Listing.created_at.desc())
        if search.strip():
            query = query.where(Listing.title.ilike(f"%{search.strip()}%"))
        listings = list(db.scalars(query).all())
        for item in listings:
            _ = item.seller
        return listings


def seller_listings(factory, seller_id: int) -> list[Listing]:
    with session_scope(factory) as db:
        return list(
            db.scalars(
                select(Listing)
                .where(Listing.seller_id == seller_id)
                .order_by(Listing.created_at.desc())
            ).all()
        )


def place_order(factory, buyer_id: int, listing_id: int, quantity: int, note: str = "") -> Purchase:
    if quantity < 1:
        raise ValueError("Quantity must be at least one.")
    with session_scope(factory) as db:
        buyer = db.get(Account, buyer_id)
        if buyer is None or buyer.role != "buyer":
            raise PermissionError("Buyer account required.")
        listing = db.get(Listing, listing_id)
        if listing is None or not listing.active:
            raise ValueError("This listing is no longer available.")
        result = db.execute(
            update(Listing)
            .where(Listing.id == listing_id, Listing.active.is_(True), Listing.quantity >= quantity)
            .values(quantity=Listing.quantity - quantity)
        )
        if result.rowcount != 1:
            raise ValueError("There is not enough stock for this order.")
        purchase = Purchase(
            listing_id=listing_id,
            seller_id=listing.seller_id,
            buyer_id=buyer_id,
            quantity=quantity,
            unit_price=listing.price,
            currency=listing.currency,
            buyer_note=note.strip()[:1000] or None,
        )
        db.add(purchase)
        db.flush()
        db.refresh(listing)
        db.add(
            StockMovement(
                listing_id=listing_id,
                seller_id=listing.seller_id,
                quantity_change=-quantity,
                resulting_quantity=listing.quantity,
                reason=f"Buyer order #{purchase.id}",
            )
        )
        return purchase


def orders_for(factory, account_id: int, role: str) -> list[Purchase]:
    if role not in {"seller", "buyer"}:
        return []
    condition = (
        Purchase.seller_id == account_id if role == "seller" else Purchase.buyer_id == account_id
    )
    with session_scope(factory) as db:
        orders = list(
            db.scalars(select(Purchase).where(condition).order_by(Purchase.created_at.desc())).all()
        )
        for order in orders:
            _ = order.listing, order.buyer, order.seller
        return orders


def change_order_status(factory, account_id: int, role: str, order_id: int, status: str) -> None:
    with session_scope(factory) as db:
        order = db.get(Purchase, order_id)
        if order is None or order.status != "requested":
            raise ValueError("Only requested orders can be updated.")
        if status == "fulfilled" and role == "seller" and order.seller_id == account_id:
            pass
        elif status == "cancelled" and (
            (role == "seller" and order.seller_id == account_id)
            or (role == "buyer" and order.buyer_id == account_id)
        ):
            pass
        else:
            raise PermissionError("You cannot update this order.")
        result = db.execute(
            update(Purchase)
            .where(Purchase.id == order_id, Purchase.status == "requested")
            .values(status=status)
        )
        if result.rowcount != 1:
            raise ValueError("This order was already updated.")
        if status == "cancelled":
            db.execute(
                update(Listing)
                .where(Listing.id == order.listing_id)
                .values(quantity=Listing.quantity + order.quantity)
            )
            listing = db.get(Listing, order.listing_id)
            db.refresh(listing)
            db.add(
                StockMovement(
                    listing_id=order.listing_id,
                    seller_id=order.seller_id,
                    quantity_change=order.quantity,
                    resulting_quantity=listing.quantity,
                    reason=f"Cancelled order #{order.id}",
                )
            )
