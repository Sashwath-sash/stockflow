from decimal import Decimal

import pytest

from marketplace import (
    Account,
    adjust_stock,
    authenticate,
    change_order_status,
    create_listing,
    get_account,
    make_session_factory,
    orders_for,
    place_order,
    public_listings,
    register,
    seller_listings,
    session_scope,
    stock_movements,
    update_listing,
)


@pytest.fixture
def marketplace(tmp_path):
    factory = make_session_factory(f"sqlite:///{tmp_path / 'marketplace.db'}")
    seller = register(
        factory,
        email="seller@example.com",
        name="Seller",
        password="secret123",
        role="seller",
        public_name="Seller Shop",
    )
    other_seller = register(
        factory,
        email="other@example.com",
        name="Other",
        password="secret123",
        role="seller",
        public_name="Other Shop",
    )
    buyer = register(
        factory, email="buyer@example.com", name="Buyer", password="secret123", role="buyer"
    )
    listing = create_listing(
        factory,
        seller.id,
        title="Blue widget",
        description="A widget",
        category="Tools",
        price=Decimal("10.00"),
        currency="USD",
        quantity=3,
        low_stock_at=1,
    )
    return factory, seller, other_seller, buyer, listing


def test_seller_inventory_isolated_and_audited(marketplace):
    factory, seller, other_seller, buyer, listing = marketplace
    assert len(seller_listings(factory, seller.id)) == 1
    assert seller_listings(factory, other_seller.id) == []
    with pytest.raises(PermissionError):
        adjust_stock(factory, other_seller.id, listing.id, 2, "Delivery")
    with pytest.raises(PermissionError):
        create_listing(
            factory,
            buyer.id,
            title="Forbidden",
            description="",
            category="Tools",
            price=Decimal("2"),
            currency="USD",
            quantity=1,
        )
    assert adjust_stock(factory, seller.id, listing.id, 2, "Delivery") == 5
    assert [(m.quantity_change, m.reason) for m in stock_movements(factory, seller.id)] == [
        (2, "Delivery"),
        (3, "Initial stock"),
    ]
    with pytest.raises(ValueError):
        adjust_stock(factory, seller.id, listing.id, -6, "Overdraw")
    assert seller_listings(factory, seller.id)[0].quantity == 5


def test_buyer_order_reserves_and_cancellation_restocks(marketplace):
    factory, seller, other_seller, buyer, listing = marketplace
    order = place_order(factory, buyer.id, listing.id, 2, "Please hold")
    assert order.seller_id == seller.id
    assert seller_listings(factory, seller.id)[0].quantity == 1
    assert len(orders_for(factory, buyer.id, "buyer")) == 1
    assert orders_for(factory, other_seller.id, "seller") == []
    with pytest.raises(ValueError):
        place_order(factory, buyer.id, listing.id, 2)
    with pytest.raises(PermissionError):
        change_order_status(factory, other_seller.id, "seller", order.id, "fulfilled")
    change_order_status(factory, buyer.id, "buyer", order.id, "cancelled")
    assert seller_listings(factory, seller.id)[0].quantity == 3
    with pytest.raises(ValueError):
        change_order_status(factory, buyer.id, "buyer", order.id, "cancelled")
    assert seller_listings(factory, seller.id)[0].quantity == 3


def test_hidden_listing_not_public_and_ownership_enforced(marketplace):
    factory, seller, other_seller, _, listing = marketplace
    with pytest.raises(PermissionError):
        update_listing(
            factory,
            other_seller.id,
            listing.id,
            title="Changed",
            description="",
            category="Tools",
            price=Decimal("9"),
            currency="USD",
            active=False,
        )
    update_listing(
        factory,
        seller.id,
        listing.id,
        title="Blue widget",
        description="A widget",
        category="Tools",
        price=Decimal("10"),
        currency="USD",
        active=False,
    )
    assert public_listings(factory) == []


def test_disabled_account_cannot_sign_in(marketplace):
    factory, seller, _, _, _ = marketplace
    with session_scope(factory) as db:
        db.get(Account, seller.id).role = "disabled"
    assert authenticate(factory, seller.email, "secret123") is None
    assert get_account(factory, seller.id) is None
