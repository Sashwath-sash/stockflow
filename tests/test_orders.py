import uuid

from app.schemas.orders import OrderCreateRequest, OrderLineRequest
from app.services.orders import request_digest


def test_request_digest_is_stable() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    payload = OrderCreateRequest(
        items=[
            OrderLineRequest(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=2,
            )
        ]
    )

    assert request_digest(payload) == request_digest(payload)


def test_request_digest_changes_with_order_content() -> None:
    product_id = uuid.uuid4()
    warehouse_id = uuid.uuid4()
    first = OrderCreateRequest(
        items=[
            OrderLineRequest(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=1,
            )
        ]
    )
    second = OrderCreateRequest(
        items=[
            OrderLineRequest(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=2,
            )
        ]
    )

    assert request_digest(first) != request_digest(second)
