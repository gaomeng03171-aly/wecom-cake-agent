from sqlalchemy import select

from app.db import get_session_factory
from app.models import OrderConfirmation, OrderStatus
from app.schemas.dify import OrderDifyOutput
from app.schemas.wecom import WeComMessageIn
from app.services.order_flow import process_order_message
from app.services.order_requirements import (
    MENU_INTRODUCTION_TEXT,
    UNSUPPORTED_ORDER_REPLY,
)
from app.services.orders import (
    create_order,
    get_or_create_customer,
    transition_order_status,
)


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
                "我叫张三，电话13800138000，我想订一个8寸草莓蛋糕",
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
        assert "新订单待报价" in third.owner_notification.content

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


def test_new_order_does_not_merge_old_draft(client) -> None:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="cake-customer-001",
            name="张三",
        )
        old_order = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-cake-customer-001",
            requirements={"notes": "如果我是帅哥，就给我送蛋糕"},
            missing_fields=[],
        )
        transition_order_status(
            old_order,
            OrderStatus.PENDING_CONFIRMATION,
        )
        db.commit()
        old_order_id = old_order.id

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message(
                "order-flow-new-001",
                "我要买一盒红丝绒小蛋糕，一盒里装四个，草莓味的",
            ),
        )
        assert result.order is not None
        assert result.order.id != old_order_id
        assert result.order.requirements["规格"] == "一套四个"
        assert "如果我是帅哥" not in result.order.requirements.values()


def test_help_me_make_order_starts_new_draft(client) -> None:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="cake-customer-001",
            name="张三",
        )
        old_order = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-cake-customer-001",
            requirements={"notes": "旧订单备注"},
            missing_fields=["pickup_time"],
        )
        old_order_id = old_order.id

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message(
                "order-flow-new-phrase-001",
                "帮我做一个巧克力蛋糕",
            ),
        )
        assert result.order is not None
        assert result.order.id != old_order_id
        assert "旧订单备注" not in result.order.requirements.values()


def test_supplemental_create_order_intent_merges_active_draft(
    client,
    monkeypatch,
) -> None:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="cake-customer-001",
            name="张三",
        )
        draft = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-cake-customer-001",
            requirements={
                "product_name": "蛋糕",
                "quantity": 1,
                "flavor": "芒果慕斯",
            },
            missing_fields=[
                "customer_name",
                "phone",
                "size",
                "pickup_time",
            ],
        )
        draft_id = draft.id

    monkeypatch.setattr(
        "app.services.order_flow.analyze_order_message",
        lambda _content: OrderDifyOutput(
            intent="create_order",
            reply="",
            requirements={
                "customer_name": "王总",
                "phone": "16438353124",
                "size": "六寸",
                "pickup_time": "(10.10)后天下午三点",
            },
        ),
    )

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message(
                "order-flow-merge-001",
                "王总，16438353124，六寸，后天下午三点取货。",
            ),
        )

        assert result.error is None
        assert result.order is not None
        assert result.order.id == draft_id
        assert result.order.requirements["customer_name"] == "王总"
        assert result.order.requirements["flavor"] == "芒果慕斯"
        assert result.order.missing_fields == []


def test_clear_memory_cancels_draft_and_starts_clean_context(client) -> None:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="cake-customer-001",
            name="张三",
        )
        old_order = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-cake-customer-001",
            requirements={"notes": "如果我是帅哥，就给我送蛋糕"},
            missing_fields=[],
        )
        transition_order_status(
            old_order,
            OrderStatus.PENDING_CONFIRMATION,
        )
        db.commit()
        old_order_id = old_order.id

    with get_session_factory()() as db:
        cleared = process_order_message(
            db,
            _message("order-flow-clear-001", "清除记忆"),
        )
        assert cleared.order is not None
        assert cleared.order.id == old_order_id
        assert cleared.order.status == OrderStatus.CANCELLED.value
        assert "已清除本会话" in cleared.reply

    with get_session_factory()() as db:
        fresh = process_order_message(
            db,
            _message(
                "order-flow-clear-002",
                "我要买一盒红丝绒小蛋糕，一盒里装四个，草莓味的",
            ),
        )
        assert fresh.order is not None
        assert fresh.order.id != old_order_id
        assert fresh.order.requirements["规格"] == "一套四个"


def test_nonsense_product_is_rejected_before_order_creation(client) -> None:
    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message(
                "order-flow-nonsense-001",
                "我要订一个混凝土蛋糕",
            ),
        )

        assert result.error is None
        assert result.order is None
        assert result.reply == UNSUPPORTED_ORDER_REPLY


def test_greeting_returns_menu_without_creating_order(client) -> None:
    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("order-flow-menu-001", "你好"),
        )

        assert result.error is None
        assert result.order is None
        assert result.reply == MENU_INTRODUCTION_TEXT
        assert "巧克力系列" in result.reply
        assert "高端私人定制" in result.reply


def test_menu_question_returns_menu_without_creating_order(client) -> None:
    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("order-flow-menu-002", "你这里有什么蛋糕"),
        )

        assert result.error is None
        assert result.order is None
        assert result.reply == MENU_INTRODUCTION_TEXT


def test_menu_question_does_not_modify_active_draft(client) -> None:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="cake-customer-001",
            name="张三",
        )
        draft = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-cake-customer-001",
            requirements={"product_name": "蛋糕"},
            missing_fields=["pickup_time"],
            commit=True,
        )
        draft_id = draft.id

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("order-flow-menu-003", "你这里有什么蛋糕"),
        )

        draft = db.get(type(draft), draft_id)
        assert result.error is None
        assert result.reply == MENU_INTRODUCTION_TEXT
        assert draft is not None
        assert draft.requirements == {"product_name": "蛋糕"}
        assert draft.missing_fields == ["pickup_time"]


def test_impossible_delivery_is_rejected_with_menu(client) -> None:
    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message(
                "order-flow-distance-001",
                "我想订一个蛋糕送到月球",
            ),
        )

        assert result.error is None
        assert result.order is None
        assert result.reply == UNSUPPORTED_ORDER_REPLY
        assert "我们这里不支持这种类型" in result.reply
        assert "巧克力系列" in result.reply
