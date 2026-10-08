from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.db import get_session_factory
from app.models import (
    Order,
    OrderConfirmation,
    OrderQuote,
    OrderStatus,
    OutboxMessage,
    PaymentStatus,
    QuoteStatus,
)
from app.schemas.dify import OrderDifyOutput
from app.schemas.wecom import WeComMessageIn
from app.services.order_flow import process_order_message
from app.services.orders import (
    cancel_order,
    confirm_order,
    create_order,
    get_order,
    get_or_create_customer,
    transition_order_status,
)


def _create_order_for_quote(
    *,
    scheduled_offset_days: int = 10,
    expected_price: Decimal | None = Decimal("200"),
) -> int:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="quote-customer-001",
            name="张三",
        )
        order = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-quote-customer-001",
            conversation_name="张三",
            scenario="cake",
            title="蛋糕订单",
            expected_price=expected_price,
            requirements={
                "customer_name": "张三",
                "phone": "13800138000",
                "product_name": "蛋糕",
                "quantity": 1,
                "size": "8寸",
                "flavor": "草莓",
                "pickup_time": "(10.20)下周一",
            },
            missing_fields=[],
        )
        transition_order_status(order, OrderStatus.PENDING_CONFIRMATION)
        confirm_order(
            db,
            order_id=order.id,
            confirmation_text="确认订单信息",
            confirmed_by="quote-customer-001",
        )
        order.scheduled_at = datetime.combine(
            order.business_date + timedelta(days=scheduled_offset_days),
            time(hour=15),
            tzinfo=timezone.utc,
        )
        db.commit()
        return order.id


def _message(content: str, *, msg_id: str) -> WeComMessageIn:
    return WeComMessageIn(
        msg_id=msg_id,
        group_id="direct-quote-customer-001",
        sender_id="quote-customer-001",
        sender_name="张三",
        content=content,
    )


def test_owner_quote_is_sent_to_customer_and_customer_approval_prepares_order(
    client,
) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)

    response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "228", "note": "含8寸定制"},
    )

    assert response.status_code == 200
    detail = response.json()
    assert detail["order"]["quote_status"] == "pending_customer"
    assert detail["order"]["quoted_total"] == "228.000"
    assert len(detail["quotes"]) == 2

    with get_session_factory()() as db:
        outbox = db.scalar(
            select(OutboxMessage)
            .where(OutboxMessage.group_id == "direct-quote-customer-001")
            .order_by(OutboxMessage.id.desc())
            .limit(1)
        )
        assert outbox is not None
        assert outbox.dispatch_channel == "active"
        assert "228" in outbox.content
        assert "店主备注：含8寸定制" in outbox.content
        assert "确认报价" in outbox.content

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("确认报价", msg_id="quote-confirm-001"),
        )
        assert result.error is None
        assert result.order is not None
        assert result.order.quote_status == QuoteStatus.APPROVED.value
        assert result.order.status == OrderStatus.PREPARING.value
        assert result.order.payment_status == PaymentStatus.NOT_REQUIRED.value

    ready_response = client.post(f"/admin/orders/{order_id}/ready")
    assert ready_response.status_code == 200
    assert ready_response.json()["order"]["status"] == "ready"

    completed_response = client.post(f"/admin/orders/{order_id}/completed")
    assert completed_response.status_code == 200
    assert completed_response.json()["order"]["status"] == "completed"


def test_explicit_quote_reply_wins_over_active_draft(
    client,
    monkeypatch,
) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)
    quote_response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "288"},
    )
    assert quote_response.status_code == 200

    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="quote-customer-001",
            name="张三",
        )
        draft = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-quote-customer-001",
            requirements={"product_name": "蛋糕"},
            missing_fields=["pickup_time"],
        )
        draft_id = draft.id

    monkeypatch.setattr(
        "app.services.order_flow.analyze_order_message",
        lambda _content: OrderDifyOutput(
            intent="confirm_order",
            reply="",
        ),
    )

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("确认报价", msg_id="quote-confirm-active-draft-001"),
        )

        assert result.error is None
        assert result.order is not None
        assert result.order.id == order_id
        assert result.order.quote_status == QuoteStatus.APPROVED.value
        assert result.order.status == OrderStatus.PREPARING.value

        confirmation = db.scalar(
            select(OrderConfirmation)
            .where(OrderConfirmation.order_id == order_id)
            .order_by(OrderConfirmation.id.desc())
            .limit(1)
        )
        assert confirmation is not None
        assert confirmation.confirmation_type == "quote_approved"
        assert confirmation.confirmed_by == "quote-customer-001"
        assert "288" in confirmation.confirmation_text

        draft = get_order(db, draft_id)
        assert draft is not None
        assert draft.status == OrderStatus.COLLECTING.value


def test_bargaining_rejects_quote_before_active_draft(
    client,
    monkeypatch,
) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=5)
    quote_response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "289"},
    )
    assert quote_response.status_code == 200

    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="quote-customer-001",
            name="张三",
        )
        draft = create_order(
            db,
            customer_id=customer.id,
            conversation_id="direct-quote-customer-001",
            requirements={"product_name": "蛋糕"},
            missing_fields=["pickup_time"],
        )
        draft_id = draft.id

    monkeypatch.setattr(
        "app.services.order_flow.analyze_order_message",
        lambda _content: OrderDifyOutput(
            intent="create_order",
            reply="",
            requirements={"product_name": "蛋糕"},
        ),
    )

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("有点贵，不接受", msg_id="quote-bargain-active-draft-001"),
        )

        assert result.error is None
        assert result.order is not None
        assert result.order.id == order_id
        assert result.order.quote_status == QuoteStatus.REJECTED.value
        assert result.owner_notification is not None
        assert "客户留言：有点贵，不接受" in result.owner_notification.content

        draft = get_order(db, draft_id)
        assert draft is not None
        assert draft.requirements == {"product_name": "蛋糕"}

        feedback = db.scalar(
            select(OrderConfirmation)
            .where(OrderConfirmation.order_id == order_id)
            .order_by(OrderConfirmation.id.desc())
            .limit(1)
        )
        assert feedback is not None
        assert feedback.confirmation_type == "quote_feedback"
        assert feedback.confirmation_text == "有点贵，不接受"


def test_deposit_is_calculated_from_final_quote_without_rounding(client) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=10)

    quote_response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "228"},
    )
    assert quote_response.status_code == 200

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("确认报价", msg_id="quote-confirm-deposit-001"),
        )
        assert result.error is None
        order = get_order(db, order_id)
        assert order is not None
        assert order.quote_status == QuoteStatus.APPROVED.value
        assert order.status == OrderStatus.CONFIRMED.value
        assert order.deposit_required is True
        assert order.deposit_amount == Decimal("45.600")
        assert order.payment_status == PaymentStatus.DEPOSIT_PENDING.value

    deposit_response = client.post(
        f"/admin/orders/{order_id}/deposit-paid",
    )
    assert deposit_response.status_code == 200
    detail = deposit_response.json()
    assert detail["order"]["payment_status"] == "deposit_paid"
    assert detail["order"]["status"] == "preparing"


def test_customer_can_reject_quote_and_owner_can_requote(client) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)
    first_quote = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "288"},
    )
    assert first_quote.status_code == 200

    with get_session_factory()() as db:
        rejected = process_order_message(
            db,
            _message("太贵了，不接受", msg_id="quote-reject-001"),
        )
        assert rejected.error is None
        assert rejected.order is not None
        assert rejected.order.quote_status == QuoteStatus.REJECTED.value
        assert rejected.owner_notification is not None
        assert "重新报价" in rejected.owner_notification.content
        assert "客户留言：太贵了，不接受" in rejected.owner_notification.content

    second_quote = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "238"},
    )
    assert second_quote.status_code == 200

    with get_session_factory()() as db:
        order = get_order(db, order_id)
        assert order is not None
        assert order.quote_status == QuoteStatus.PENDING_CUSTOMER.value
        quotes = list(
            db.scalars(
                select(OrderQuote)
                .where(OrderQuote.order_id == order_id)
                .order_by(OrderQuote.version)
            ).all()
        )
        assert [quote.status for quote in quotes] == [
            "superseded",
            "rejected",
            "pending_customer",
        ]


def test_quote_approval_handles_positive_phrases(client) -> None:
    for amount, phrase in (
        ("188", "报价可以"),
        ("198", "可以接受"),
    ):
        order_id = _create_order_for_quote(scheduled_offset_days=2)
        quote_response = client.post(
            f"/admin/orders/{order_id}/quote",
            json={"amount": amount},
        )
        assert quote_response.status_code == 200

        with get_session_factory()() as db:
            result = process_order_message(
                db,
                _message(phrase, msg_id=f"quote-positive-{amount}"),
            )
            assert result.error is None
            assert result.order is not None
            assert result.order.quote_status == QuoteStatus.APPROVED.value


def test_quote_rejection_handles_negated_acceptance(client) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)
    quote_response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "288"},
    )
    assert quote_response.status_code == 200

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message(
                "我不太能接受这个价格",
                msg_id="quote-negated-acceptance-001",
            ),
        )
        assert result.error is None
        assert result.order is not None
        assert result.order.quote_status == QuoteStatus.REJECTED.value


def test_greeting_with_quote_feedback_is_not_menu(client) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)
    quote_response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "288"},
    )
    assert quote_response.status_code == 200

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("你好，太贵了", msg_id="quote-greeting-feedback-001"),
        )
        assert result.error is None
        assert result.order is not None
        assert result.order.quote_status == QuoteStatus.REJECTED.value
        assert "巧克力系列" not in result.reply


def test_owner_can_accept_customer_expected_price(client) -> None:
    order_id = _create_order_for_quote(
        scheduled_offset_days=2,
        expected_price=Decimal("188.5"),
    )

    response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"accept_expected_price": True},
    )

    assert response.status_code == 200
    detail = response.json()
    assert detail["order"]["quoted_total"] == "188.500"
    assert detail["quotes"][-1]["source"] == "owner"
    assert detail["quotes"][-1]["amount"] == "188.500"


def test_multiple_pending_quotes_require_order_reference(client) -> None:
    first_order_id = _create_order_for_quote(scheduled_offset_days=2)
    second_order_id = _create_order_for_quote(scheduled_offset_days=3)

    assert (
        client.post(
            f"/admin/orders/{first_order_id}/quote",
            json={"amount": "188"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/admin/orders/{second_order_id}/quote",
            json={"amount": "238"},
        ).status_code
        == 200
    )

    with get_session_factory()() as db:
        ambiguous = process_order_message(
            db,
            _message("确认报价", msg_id="quote-ambiguous-001"),
        )
        assert ambiguous.error is None
        assert "当前有多笔待确认报价" in ambiguous.reply

        second_order = get_order(db, second_order_id)
        assert second_order is not None
        reference = (
            f"{second_order.business_date:%m-%d}-{second_order.order_number:04d}"
        )

    with get_session_factory()() as db:
        selected = process_order_message(
            db,
            _message(
                f"确认报价 {reference}",
                msg_id="quote-ambiguous-002",
            ),
        )
        assert selected.error is None
        assert selected.order is not None
        assert selected.order.id == second_order_id
        assert selected.order.quote_status == QuoteStatus.APPROVED.value

        first_order = get_order(db, first_order_id)
        assert first_order is not None
        assert first_order.quote_status == QuoteStatus.PENDING_CUSTOMER.value


def test_customer_note_during_quote_is_forwarded_to_owner(client) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)
    quote_response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "188"},
    )
    assert quote_response.status_code == 200

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("备注需要十八根蜡烛", msg_id="quote-customer-note-001"),
        )
        assert result.error is None
        assert result.reply == "已收到您的意见，店主会重新考虑报价。"
        assert result.owner_notification is not None
        assert "客户留言：需要十八根蜡烛" in result.owner_notification.content
        order = get_order(db, order_id)
        assert order is not None
        assert order.quote_status == QuoteStatus.REJECTED.value


def test_bargaining_feedback_does_not_cancel_an_order(
    client,
    monkeypatch,
) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=5)
    quote_response = client.post(
        f"/admin/orders/{order_id}/quote",
        json={"amount": "289", "note": "新客户优惠价"},
    )
    assert quote_response.status_code == 200

    monkeypatch.setattr(
        "app.services.order_flow.analyze_order_message",
        lambda _content: OrderDifyOutput(
            intent="cancel_order",
            reply="",
        ),
    )

    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message(
                "不接受，你这太坑了，好贵",
                msg_id="quote-bargain-001",
            ),
        )
        assert result.error is None
        assert result.order is not None
        assert result.order.status == OrderStatus.CONFIRMED.value
        assert result.order.quote_status == QuoteStatus.REJECTED.value
        assert result.reply == (
            "小的试着逼店主一把，给您个骨折价，您先消消气哈，"
            "小的这就去找店主。"
        )
        assert result.owner_notification is not None
        assert "客户反馈报价" in result.owner_notification.content
        assert "太坑了，好贵" in result.owner_notification.content

        feedback = db.scalar(
            select(OrderConfirmation)
            .where(OrderConfirmation.order_id == order_id)
            .order_by(OrderConfirmation.id.desc())
            .limit(1)
        )
        assert feedback is not None
        assert feedback.confirmation_type == "quote_feedback"
        assert feedback.confirmation_text == "不接受，你这太坑了，好贵"


def test_cancelled_order_supports_owner_message_and_restore(client) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)
    with get_session_factory()() as db:
        cancelled = cancel_order(
            db,
            order_id=order_id,
            confirmation_text="客户取消订单",
            confirmed_by="quote-customer-001",
        )
        reference = f"{cancelled.business_date:%m.%d}-{cancelled.order_number:04d}"

    message_response = client.post(
        f"/admin/orders/{order_id}/message",
        json={"content": "如果需要重新安排，可以告诉我"},
    )
    assert message_response.status_code == 200
    with get_session_factory()() as db:
        outbox = db.scalar(
            select(OutboxMessage)
            .where(OutboxMessage.group_id == "direct-quote-customer-001")
            .order_by(OutboxMessage.id.desc())
            .limit(1)
        )
        assert outbox is not None
        assert "店主留言：如果需要重新安排，可以告诉我" in outbox.content

    with get_session_factory()() as db:
        restored = process_order_message(
            db,
            _message(
                f"恢复订单 {reference}",
                msg_id="cancelled-restore-001",
            ),
        )
        assert restored.error is None
        assert restored.order is not None
        assert restored.order.status != OrderStatus.CANCELLED.value
        assert "已恢复" in restored.reply


def test_cancelled_order_can_be_reopened_for_modification(client) -> None:
    order_id = _create_order_for_quote(scheduled_offset_days=2)
    with get_session_factory()() as db:
        cancelled = cancel_order(
            db,
            order_id=order_id,
            confirmation_text="客户取消订单",
            confirmed_by="quote-customer-001",
        )
        reference = f"{cancelled.business_date:%m.%d}-{cancelled.order_number:04d}"

    with get_session_factory()() as db:
        reopened = process_order_message(
            db,
            _message(
                f"修改订单 {reference}",
                msg_id="cancelled-modify-001",
            ),
        )
        assert reopened.error is None
        assert reopened.order is not None
        assert reopened.order.status == OrderStatus.PENDING_CONFIRMATION.value
        assert reopened.order.quote_status == QuoteStatus.PENDING_OWNER.value
        assert "已重新打开" in reopened.reply

        confirmation = db.scalar(
            select(OrderConfirmation)
            .where(OrderConfirmation.order_id == order_id)
            .order_by(OrderConfirmation.id.desc())
            .limit(1)
        )
        assert confirmation is not None
        assert confirmation.confirmation_type == "customer_modify_request"


def test_unrelated_message_uses_brand_fallback(client) -> None:
    with get_session_factory()() as db:
        result = process_order_message(
            db,
            _message("今天天气不错", msg_id="unrelated-001"),
        )
        assert result.reply == (
            "您好，您的问题我不知道呢，您想订蛋糕吗？"
            "我们提供进口动物奶油和专属定制呢。"
        )


def test_daily_order_numbers_are_sequential(client) -> None:
    with get_session_factory()() as db:
        customer = get_or_create_customer(
            db,
            external_id="daily-number-customer",
            name="李四",
        )
        first = create_order(
            db,
            customer_id=customer.id,
            conversation_id="daily-number-group",
            title="第一单",
        )
        second = create_order(
            db,
            customer_id=customer.id,
            conversation_id="daily-number-group",
            title="第二单",
        )
        assert first.order_number == 1
        assert second.order_number == 2
        assert first.business_date == second.business_date


def test_parse_order_datetime_supports_annotated_relative_time() -> None:
    from app.services.order_requirements import parse_order_datetime

    now = datetime(2026, 10, 7, 9, 0)
    parsed = parse_order_datetime("(10.8)明天下午三点", now)
    assert parsed is not None
    assert parsed == datetime(2026, 10, 8, 15, 0)
