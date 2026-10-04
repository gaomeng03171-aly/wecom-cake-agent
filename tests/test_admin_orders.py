from app.db import get_session_factory
from app.models import OrderStatus
from app.services.orders import (
    confirm_order,
    create_order,
    get_or_create_customer,
    transition_order_status,
)


def _create_confirmed_order() -> int:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="admin-order-customer-001",
            name="张三",
        )
        order = create_order(
            db,
            customer_id=customer.id,
            conversation_id="admin-order-group-001",
            conversation_name="蛋糕订单群",
            scenario="cake",
            title="生日蛋糕",
            requirements={"size": "8寸", "flavor": "草莓"},
        )
        transition_order_status(order, OrderStatus.PENDING_CONFIRMATION)
        confirm_order(
            db,
            order_id=order.id,
            confirmation_text="确认制作草莓8寸蛋糕",
            confirmed_by="admin-order-customer-001",
            source_message_id="admin-order-message-001",
        )
        return order.id


def test_admin_order_list_and_detail(client) -> None:
    order_id = _create_confirmed_order()

    list_response = client.get("/admin/orders")
    assert list_response.status_code == 200
    orders = list_response.json()
    assert len(orders) == 1
    assert orders[0]["id"] == order_id
    assert orders[0]["status"] == "confirmed"

    detail_response = client.get(f"/admin/orders/{order_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["order"]["scenario"] == "cake"
    assert detail["order"]["requirements"]["flavor"] == "草莓"
    assert detail["customer"]["external_id"] == "admin-order-customer-001"
    assert len(detail["confirmations"]) == 1
    assert detail["confirmations"][0]["confirmation_type"] == "customer_confirmed"


def test_admin_overview_includes_order_counts(client) -> None:
    _create_confirmed_order()

    response = client.get("/admin/overview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_orders"] == 1
    assert payload["confirmed_orders"] == 1
    assert payload["collecting_orders"] == 0
    assert payload["pending_confirmation_orders"] == 0
