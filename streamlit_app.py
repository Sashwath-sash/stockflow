"""Public StockFlow marketplace for Streamlit Community Cloud."""

from decimal import Decimal

import streamlit as st

from marketplace import (
    adjust_stock,
    authenticate,
    change_order_status,
    create_listing,
    database_url,
    get_account,
    make_session_factory,
    orders_for,
    place_order,
    public_listings,
    register,
    seller_listings,
    stock_movements,
    update_listing,
    update_seller_profile,
)

st.set_page_config(page_title="StockFlow Marketplace", page_icon="📦", layout="wide")


@st.cache_resource
def db_factory(url: str):
    return make_session_factory(url)


try:
    factory = db_factory(database_url())
except Exception:
    st.error(
        "Database connection failed. Set STOCKFLOW_DATABASE_URL in Streamlit app secrets and retry."
    )
    st.stop()

st.title("📦 StockFlow")
st.caption("Inventory management for sellers, with a public catalog and buyer ordering.")

account = (
    get_account(factory, st.session_state["account_id"])
    if "account_id" in st.session_state
    else None
)
if "account_id" in st.session_state and account is None:
    del st.session_state["account_id"]

with st.sidebar:
    if account:
        st.write(f"Signed in as **{account.name}**")
        st.caption(account.role.capitalize())
        if st.button("Sign out", width="stretch"):
            del st.session_state["account_id"]
            st.rerun()
    else:
        st.write("Browse freely. Sign in to place orders or manage a shop.")

if not account:
    shop_tab, login_tab, register_tab = st.tabs(["Shop", "Sign in", "Create account"])
else:
    names = (
        ["Shop", "My orders"]
        if account.role == "buyer"
        else [
            "Inventory dashboard",
            "Products & stock",
            "Seller orders",
            "Shop profile",
            "Public shop",
        ]
    )
    tabs = st.tabs(names)
    shop_tab = tabs[0] if account.role == "buyer" else tabs[4]

with shop_tab:
    search = st.text_input("Search products", placeholder="Search by product name")
    listings = public_listings(factory, search)
    if not listings:
        st.info("No products listed yet. Sellers can add the first listing after signing up.")
    for item in listings:
        with st.container(border=True):
            left, right = st.columns([3, 1])
            with left:
                st.subheader(item.title)
                st.write(item.description or "No description provided.")
                st.caption(
                    f"{item.category} · Sold by {item.seller.public_name or item.seller.name}"
                    + (f" · {item.seller.public_location}" if item.seller.public_location else "")
                )
                if item.seller.public_contact:
                    st.caption(f"Seller contact: {item.seller.public_contact}")
            with right:
                st.metric("Price", f"{item.currency} {item.price:,.2f}")
                st.write(f"{item.quantity} in stock" if item.quantity else "Out of stock")
                if account and account.role == "buyer" and item.quantity:
                    with st.form(f"order_{item.id}"):
                        quantity = st.number_input(
                            "Quantity",
                            min_value=1,
                            max_value=item.quantity,
                            step=1,
                            key=f"quantity_{item.id}",
                        )
                        note = st.text_input("Note to seller (optional)", key=f"note_{item.id}")
                        if st.form_submit_button("Request order", width="stretch"):
                            try:
                                order = place_order(
                                    factory, account.id, item.id, int(quantity), note
                                )
                                st.success(f"Order #{order.id} placed. No payment was taken.")
                                st.rerun()
                            except (ValueError, PermissionError) as exc:
                                st.error(str(exc))
                elif not account and item.quantity:
                    st.caption("Sign in as a buyer to order.")

if not account:
    with login_tab:
        with st.form("login"):
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")
            if st.form_submit_button("Sign in"):
                signed_in = authenticate(factory, email, password)
                if signed_in:
                    st.session_state["account_id"] = signed_in.id
                    st.rerun()
                else:
                    st.error("Incorrect email or password.")

    with register_tab:
        with st.form("register"):
            role = st.radio("I want to", ["Buy products", "Sell products"], horizontal=True)
            name = st.text_input("Your name")
            email = st.text_input("Email address")
            password = st.text_input("Password (at least 8 characters)", type="password")
            st.caption(
                "For sellers, the shop fields below are public. Your sign-in email stays private."
            )
            public_name = st.text_input("Shop name (required for sellers)")
            public_location = st.text_input("Shop location (optional)")
            public_contact = st.text_input("Public contact details (optional)")
            if st.form_submit_button("Create account"):
                try:
                    new_account = register(
                        factory,
                        email=email,
                        name=name,
                        password=password,
                        role="seller" if role == "Sell products" else "buyer",
                        public_name=public_name,
                        public_location=public_location,
                        public_contact=public_contact,
                    )
                    st.session_state["account_id"] = new_account.id
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

if account and account.role == "seller":
    inventory = seller_listings(factory, account.id)
    with tabs[0]:
        st.header("Inventory dashboard")
        total_products = len(inventory)
        units = sum(item.quantity for item in inventory)
        low_stock = [item for item in inventory if item.quantity <= item.low_stock_at]
        open_orders = sum(
            order.status == "requested" for order in orders_for(factory, account.id, "seller")
        )
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Products", total_products)
        col2.metric("Units in stock", units)
        col3.metric("Low stock alerts", len(low_stock))
        col4.metric("Open orders", open_orders)
        if inventory:
            st.subheader("Stock overview")
            st.dataframe(
                [
                    {
                        "Product": item.title,
                        "Category": item.category,
                        "In stock": item.quantity,
                        "Low stock at": item.low_stock_at,
                        "Status": "Low stock" if item.quantity <= item.low_stock_at else "OK",
                        "Price": f"{item.currency} {item.price:,.2f}",
                        "Visible": item.active,
                    }
                    for item in inventory
                ],
                width="stretch",
                hide_index=True,
            )
        if low_stock:
            st.subheader("Needs attention")
            for item in low_stock:
                st.warning(f"{item.title}: {item.quantity} left (alert at {item.low_stock_at})")
        st.subheader("Recent stock activity")
        movements = stock_movements(factory, account.id)
        if movements:
            st.dataframe(
                [
                    {
                        "Product": m.listing.title,
                        "Change": m.quantity_change,
                        "Stock after": m.resulting_quantity,
                        "Reason": m.reason,
                        "Time": m.created_at,
                    }
                    for m in movements
                ],
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("Stock movements will appear here after you add products or adjust stock.")
    with tabs[1]:
        st.header("Products & stock")
        with st.expander("Add a product", expanded=True):
            with st.form("create_listing"):
                title = st.text_input("Product name")
                description = st.text_area("Description")
                category = st.text_input("Category")
                price = st.number_input("Unit price", min_value=0.01, value=1.00, step=0.01)
                currency = st.selectbox("Currency", ["INR", "USD", "EUR", "GBP"])
                quantity = st.number_input("Stock quantity", min_value=0, step=1)
                low_stock_at = st.number_input(
                    "Low stock alert threshold", min_value=0, value=5, step=1
                )
                if st.form_submit_button("Publish listing"):
                    try:
                        create_listing(
                            factory,
                            account.id,
                            title=title,
                            description=description,
                            category=category,
                            price=Decimal(str(price)),
                            currency=currency,
                            quantity=int(quantity),
                            low_stock_at=int(low_stock_at),
                        )
                        st.success("Listing published.")
                        st.rerun()
                    except (ValueError, PermissionError) as exc:
                        st.error(str(exc))
        for item in inventory:
            with st.expander(
                f"{item.title} · {item.currency} {item.price:,.2f} · {item.quantity} in stock"
                + (" · hidden" if not item.active else "")
            ):
                st.write(
                    f"Current stock: **{item.quantity}** · "
                    f"Low stock alert at **{item.low_stock_at}**"
                )
                with st.form(f"stock_{item.id}"):
                    change = st.number_input(
                        "Stock change (+ received / − removed)",
                        value=0,
                        step=1,
                        key=f"change_{item.id}",
                    )
                    reason = st.text_input(
                        "Reason",
                        placeholder="Received delivery, damaged stock, count correction",
                        key=f"reason_{item.id}",
                    )
                    if st.form_submit_button("Record stock movement"):
                        try:
                            adjust_stock(factory, account.id, item.id, int(change), reason)
                            st.success("Stock updated and recorded.")
                            st.rerun()
                        except (ValueError, PermissionError) as exc:
                            st.error(str(exc))
                with st.form(f"edit_{item.id}"):
                    title = st.text_input("Product name", value=item.title)
                    description = st.text_area("Description", value=item.description)
                    category = st.text_input("Category", value=item.category)
                    price = st.number_input(
                        "Unit price", min_value=0.01, value=float(item.price), step=0.01
                    )
                    currency = st.selectbox(
                        "Currency",
                        ["INR", "USD", "EUR", "GBP"],
                        index=["INR", "USD", "EUR", "GBP"].index(item.currency),
                    )
                    low_stock_at = st.number_input(
                        "Low stock alert threshold", min_value=0, value=item.low_stock_at, step=1
                    )
                    active = st.checkbox("Visible in public shop", value=item.active)
                    if st.form_submit_button("Save changes"):
                        try:
                            update_listing(
                                factory,
                                account.id,
                                item.id,
                                title=title,
                                description=description,
                                category=category,
                                price=Decimal(str(price)),
                                currency=currency,
                                active=active,
                                low_stock_at=int(low_stock_at),
                            )
                            st.success("Listing updated.")
                            st.rerun()
                        except (ValueError, PermissionError) as exc:
                            st.error(str(exc))

    with tabs[2]:
        st.header("Orders for my shop")
        seller_orders = orders_for(factory, account.id, "seller")
        if not seller_orders:
            st.info("No orders yet.")
        for order in seller_orders:
            with st.container(border=True):
                st.write(f"**Order #{order.id} · {order.status.title()}**")
                st.write(
                    f"{order.listing.title} × {order.quantity} · "
                    f"{order.currency} {order.unit_price * order.quantity:,.2f}"
                )
                st.caption(f"Buyer: {order.buyer.name} · {order.buyer.email}")
                if order.buyer_note:
                    st.write(f"Buyer note: {order.buyer_note}")
                if order.status == "requested":
                    col1, col2 = st.columns(2)
                    if col1.button("Mark fulfilled", key=f"fulfil_{order.id}"):
                        change_order_status(factory, account.id, "seller", order.id, "fulfilled")
                        st.rerun()
                    if col2.button("Cancel and restock", key=f"seller_cancel_{order.id}"):
                        change_order_status(factory, account.id, "seller", order.id, "cancelled")
                        st.rerun()

    with tabs[3]:
        st.header("Public shop profile")
        with st.form("profile"):
            public_name = st.text_input("Shop name", value=account.public_name or "")
            public_location = st.text_input("Location", value=account.public_location or "")
            public_contact = st.text_input(
                "Public contact details", value=account.public_contact or ""
            )
            st.caption(
                "These details appear on each of your public listings. "
                "Your sign-in email is private."
            )
            if st.form_submit_button("Save profile"):
                try:
                    update_seller_profile(
                        factory,
                        account.id,
                        public_name=public_name,
                        public_location=public_location,
                        public_contact=public_contact,
                    )
                    st.success("Profile updated.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

if account and account.role == "buyer":
    with tabs[1]:
        st.header("My orders")
        buyer_orders = orders_for(factory, account.id, "buyer")
        if not buyer_orders:
            st.info("You have not placed an order yet.")
        for order in buyer_orders:
            with st.container(border=True):
                st.write(f"**Order #{order.id} · {order.status.title()}**")
                st.write(
                    f"{order.listing.title} × {order.quantity} · "
                    f"{order.currency} {order.unit_price * order.quantity:,.2f}"
                )
                st.caption(f"Seller: {order.seller.public_name or order.seller.name}")
                if order.status == "requested" and st.button(
                    "Cancel order", key=f"buyer_cancel_{order.id}"
                ):
                    change_order_status(factory, account.id, "buyer", order.id, "cancelled")
                    st.rerun()

st.divider()
st.caption(
    "Orders are requests to sellers. StockFlow does not collect payments or arrange shipping."
)
