from sqlalchemy import select

from app.db import get_session_factory
from app.models import OrderConfirmation, OrderStatus
from app.schemas.wecom import WeComMessageIn
from app.services.order_flow import process_order_message


def _message(
    msg_id: str,
    content: str,
    *,
    sender_id: str = "cake-customer-001",
) -> WeComMessageIn:
    return WeComMessageIn(
        msg_id=msg_id,
        group_id="direct-cake-customer-001",
        sender_id=sender_id,
        sender_name="张三",
        msg_type="text",
        content=content,
    )


def test_order_flow_collects_completes_and_confirms_order(client) -> None:
    with get_session_factory()() as db:
        first = process_order_message(
            db,
            _message(
                "order-flow-001",
                "我想订一个8寸草莓蛋糕",
            ),
        )
        assert first.error is None
        assert first.order is not None
        assert first.order.status == OrderStatus.COLLECTING.value
        assert first.order.missing_fields == ["pickup_time"]
        assert "取货" in first.reply
        order_id = first.order.id

    with get_session_factory()() as db:
        second = process_order_message(
            db,
            _message(
                "order-flow-002",
                "明天下午三点取",
            ),
        )
        assert second.error is None
        assert second.order is not None
        assert second.order.id == order_id
        assert second.order.status == OrderStatus.PENDING_CONFIRMATION.value
        assert second.order.missing_fields == []
        assert second.order.confirmation_text is not None
        assert "请确认订单信息" in second.reply

    with get_session_factory()() as db:
        third = process_order_message(
            db,
            _message(
                "order-flow-003",
                "确认下单",
            ),
        )
        assert third.error is None
        assert third.order is not None
        assert third.order.status == OrderStatus.CONFIRMED.value
        assert third.owner_notification is not None
        assert third.owner_notification.group_id == "direct-owner-001"
        assert third.owner_notification.dispatch_channel == "app"
        assert "新订单已确认" in third.owner_notification.content

        confirmation = db.scalar(
            select(OrderConfirmation).where(
                OrderConfirmation.order_id == order_id
            )
        )
        assert confirmation is not None
        assert confirmation.confirmation_type == "customer_confirmed"


def test_order_flow_can_cancel_order(client) -> None:
    with get_session_factory()() as db:
        created = process_order_message(
            db,
            _message("order-flow-cancel-001", "我想订一个蛋糕"),
        )
        assert created.order is not None

    with get_session_factory()() as db:
        cancelled = process_order_message(
            db,
            _message("order-flow-cancel-002", "取消订单"),
        )
        assert cancelled.error is None
        assert cancelled.order is not None
        assert cancelled.order.status == OrderStatus.CANCELLED.value
        assert cancelled.reply == "订单已取消。"
