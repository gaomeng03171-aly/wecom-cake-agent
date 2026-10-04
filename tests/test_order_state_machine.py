import pytest
from sqlalchemy import select

from app.db import get_session_factory
from app.models import OrderConfirmation, OrderStatus
from app.services.orders import (
    OrderServiceError,
    cancel_order,
    confirm_order,
    create_order,
    get_order,
    get_or_create_customer,
    transition_order_status,
)


def _create_order() -> int:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="cake-customer-001",
            name="张三",
        )
        order = create_order(
            db,
            customer_id=customer.id,
            conversation_id="cake-group-001",
            conversation_name="蛋糕订单群",
            scenario="cake",
            title="生日蛋糕",
            requirements={"size": "8寸", "flavor": "草莓"},
            missing_fields=["pickup_time"],
        )
        return order.id


def test_order_confirmation_state_machine_records_snapshot(client) -> None:
    order_id = _create_order()

    with get_session_factory()() as db:
        order = get_order(db, order_id)
        assert order is not None
        assert order.status == OrderStatus.COLLECTING.value

        transition_order_status(order, OrderStatus.PENDING_CONFIRMATION)
        db.commit()
        db.refresh(order)
        assert order.status == OrderStatus.PENDING_CONFIRMATION.value

        confirm_order(
            db,
            order_id=order.id,
            confirmation_text="确认制作草莓8寸蛋糕",
            confirmed_by="cake-customer-001",
            source_message_id="msg-confirm-001",
        )

        db.refresh(order)
        assert order.status == OrderStatus.CONFIRMED.value
        assert order.confirmed_at is not None
        assert order.confirmation_text == "确认制作草莓8寸蛋糕"

        confirmation = db.scalar(
            select(OrderConfirmation).where(
                OrderConfirmation.order_id == order.id
            )
        )
        assert confirmation is not None
        assert confirmation.confirmation_type == "customer_confirmed"
        assert confirmation.requirements_snapshot == {
            "size": "8寸",
            "flavor": "草莓",
        }
        assert confirmation.source_message_id == "msg-confirm-001"


def test_order_can_be_cancelled_from_collecting(client) -> None:
    order_id = _create_order()

    with get_session_factory()() as db:
        order = get_order(db, order_id)
        assert order is not None
        cancel_order(
            db,
            order_id=order.id,
            confirmation_text="客户取消订单",
            confirmed_by="cake-customer-001",
        )
        db.refresh(order)

        assert order.status == OrderStatus.CANCELLED.value
        assert order.cancelled_at is not None


def test_order_can_be_cancelled_from_pending_confirmation(client) -> None:
    order_id = _create_order()

    with get_session_factory()() as db:
        order = get_order(db, order_id)
        assert order is not None
        transition_order_status(order, OrderStatus.PENDING_CONFIRMATION)
        cancel_order(
            db,
            order_id=order.id,
            confirmation_text="客户在确认前取消",
            confirmed_by="cake-customer-001",
        )
        db.refresh(order)

        assert order.status == OrderStatus.CANCELLED.value
        confirmation = db.scalar(
            select(OrderConfirmation).where(
                OrderConfirmation.order_id == order.id
            )
        )
        assert confirmation is not None
        assert confirmation.confirmation_type == "customer_cancelled"


def test_order_rejects_invalid_transitions(client) -> None:
    order_id = _create_order()

    with get_session_factory()() as db:
        order = get_order(db, order_id)
        assert order is not None

        with pytest.raises(OrderServiceError, match="cannot transition"):
            transition_order_status(order, OrderStatus.CONFIRMED)

        transition_order_status(order, OrderStatus.PENDING_CONFIRMATION)
        confirm_order(
            db,
            order_id=order.id,
            confirmation_text="确认订单",
            confirmed_by="cake-customer-001",
        )

        with pytest.raises(OrderServiceError, match="cannot transition"):
            transition_order_status(order, OrderStatus.CANCELLED)


def test_customer_is_reused_by_channel_and_external_id(client) -> None:
    with get_session_factory()() as db:
        first = get_or_create_customer(
            db,
            external_id="repeat-customer-001",
            name="李四",
        )
        second = get_or_create_customer(
            db,
            external_id="repeat-customer-001",
            name="李四更新",
        )

        assert first.id == second.id
        assert second.name == "李四更新"
