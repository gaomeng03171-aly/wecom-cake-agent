from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import (
    Order,
    OrderStatus,
    OutboxMessage,
    QuoteStatus,
    utc_now,
)
from app.schemas.dify import OrderDifyOutput
from app.schemas.wecom import WeComMessageIn
from app.services.dify import DifyServiceError, analyze_order_message
from app.services.inbound import receive_message
from app.services.order_requirements import (
    MENU_INTRODUCTION_TEXT,
    UNSUPPORTED_ORDER_REPLY,
    build_order_requirements,
    format_order_confirmation,
    format_order_follow_up,
    format_order_summary,
    format_amount,
    format_quote_accepted_message,
    extract_customer_note,
    extract_order_reference,
    is_clear_context_command,
    is_menu_introduction_message,
    is_nonsense_order_message,
    missing_order_fields,
    parse_order_datetime,
)
from app.services.orders import (
    OrderServiceError,
    cancel_order,
    confirm_order,
    customer_approve_quote,
    customer_reject_quote,
    create_order,
    find_active_order,
    find_cancelled_orders,
    find_customer_order,
    find_orders_for_quote,
    get_or_create_customer,
    order_number_display,
    reopen_order_for_changes,
    restore_order,
    transition_order_status,
)
from app.services.outbox import enqueue_reply


UNRELATED_CUSTOMER_REPLY = (
    "您好，您的问题我不知道呢，您想订蛋糕吗？"
    "我们提供进口动物奶油和专属定制呢。"
)


@dataclass
class OrderFlowResult:
    accepted: bool
    duplicate: bool
    message_id: int | None
    analysis: OrderDifyOutput | None
    order: Order | None
    reply: str
    customer_outbox: OutboxMessage | None = None
    owner_notification: OutboxMessage | None = None
    error: str | None = None


def process_order_message(
    db: Session,
    payload: WeComMessageIn,
    settings: Settings | None = None,
    commit: bool = True,
) -> OrderFlowResult:
    active_settings = settings or get_settings()
    stored = receive_message(db, payload, commit=False)
    if stored.duplicate:
        return OrderFlowResult(
            accepted=True,
            duplicate=True,
            message_id=stored.message_id,
            analysis=None,
            order=None,
            reply="",
        )

    if is_clear_context_command(payload.content):
        active_order = find_active_order(db, payload.group_id)
        order = active_order
        owner_notification = None
        if active_order is not None:
            order = cancel_order(
                db,
                order_id=active_order.id,
                confirmation_text="客户清除临时订单记忆",
                confirmed_by=payload.sender_id,
                source_message_id=payload.msg_id,
                commit=False,
            )
            owner_notification = _owner_notification(
                db,
                order,
                "客户清除了临时订单记忆：",
                commit=False,
                settings=active_settings,
            )
        customer_outbox = enqueue_reply(
            db,
            payload.group_id,
            "已清除本会话的临时订单信息，请重新告诉我想订什么。",
            commit=False,
        )
        _finish(db, commit, customer_outbox, order, owner_notification)
        return OrderFlowResult(
            accepted=True,
            duplicate=False,
            message_id=stored.message_id,
            analysis=None,
            order=order,
            reply=customer_outbox.content,
            customer_outbox=customer_outbox,
            owner_notification=owner_notification,
        )

    if is_menu_introduction_message(payload.content):
        customer_outbox = enqueue_reply(
            db,
            payload.group_id,
            MENU_INTRODUCTION_TEXT,
            commit=False,
        )
        _finish(db, commit, customer_outbox)
        return OrderFlowResult(
            accepted=True,
            duplicate=False,
            message_id=stored.message_id,
            analysis=None,
            order=None,
            reply=customer_outbox.content,
            customer_outbox=customer_outbox,
        )

    if is_nonsense_order_message(payload.content):
        customer_outbox = enqueue_reply(
            db,
            payload.group_id,
            UNSUPPORTED_ORDER_REPLY,
            commit=False,
        )
        _finish(db, commit, customer_outbox)
        return OrderFlowResult(
            accepted=True,
            duplicate=False,
            message_id=stored.message_id,
            analysis=None,
            order=None,
            reply=customer_outbox.content,
            customer_outbox=customer_outbox,
        )

    try:
        analysis = analyze_order_message(payload.content)
    except DifyServiceError as exc:
        customer_outbox = enqueue_reply(
            db,
            payload.group_id,
            "订单信息暂时无法识别，请再描述一下商品和取货时间。",
            commit=False,
        )
        _finish(db, commit, customer_outbox)
        return OrderFlowResult(
            accepted=True,
            duplicate=False,
            message_id=stored.message_id,
            analysis=None,
            order=None,
            reply=customer_outbox.content,
            customer_outbox=customer_outbox,
            error=str(exc),
        )

    if analysis.intent == "unknown" and analysis.requirements:
        analysis = analysis.model_copy(update={"intent": "provide_requirement"})

    order_reference = (
        analysis.order_reference
        or extract_order_reference(payload.content)
    )
    if order_reference:
        analysis = analysis.model_copy(
            update={"order_reference": order_reference}
        )
    customer_note = (
        analysis.customer_note
        or extract_customer_note(payload.content)
    )
    if customer_note:
        analysis = analysis.model_copy(
            update={"customer_note": customer_note}
        )

    active_order = find_active_order(db, payload.group_id)
    quote_orders = find_orders_for_quote(
        db,
        payload.group_id,
        order_reference=order_reference,
    )
    quote_order = quote_orders[0] if len(quote_orders) == 1 else None
    cancelled_orders = find_cancelled_orders(
        db,
        payload.group_id,
        order_reference=order_reference,
    )
    cancelled_order = (
        cancelled_orders[0] if len(cancelled_orders) == 1 else None
    )
    restore_request = _is_restore_request(payload.content)
    modify_request = _is_modify_request(payload.content)
    pending_customer_orders = [
        order
        for order in quote_orders
        if order.quote_status == QuoteStatus.PENDING_CUSTOMER.value
    ]
    if pending_customer_orders and _is_explicit_quote_approval(
        payload.content
    ):
        analysis = analysis.model_copy(update={"intent": "confirm_quote"})
    elif (
        pending_customer_orders
        and not _is_explicit_cancel(payload.content)
    ):
        analysis = analysis.model_copy(
            update={
                "intent": "reject_quote",
                "customer_note": payload.content.strip(),
            }
        )
    elif (
        analysis.intent == "unknown"
        and quote_orders
        and _looks_like_quote_negotiation(payload.content)
    ):
        analysis = analysis.model_copy(
            update={
                "intent": "reject_quote",
                "customer_note": payload.content.strip(),
            }
        )
    customer_order = find_customer_order(db, payload.group_id)
    order = active_order
    owner_notification = None
    error = None
    reply = analysis.reply

    try:
        if (
            active_order is None
            and cancelled_orders
            and (order_reference or restore_request or modify_request)
        ):
            if len(cancelled_orders) > 1:
                reply = _cancelled_order_prompt(cancelled_orders)
            elif cancelled_order is None:
                reply = _cancelled_order_prompt(cancelled_orders)
            elif restore_request:
                order = restore_order(
                    db,
                    order_id=cancelled_order.id,
                    confirmed_by=payload.sender_id,
                    source_message_id=payload.msg_id,
                    commit=False,
                )
                reply = (
                    f"订单 {order_number_display(order)} 已恢复。"
                    "您可以继续确认或告诉我需要修改的内容。"
                )
                owner_notification = _owner_notification(
                    db,
                    order,
                    "客户恢复订单：",
                    commit=False,
                    settings=active_settings,
                )
            elif modify_request:
                order = reopen_order_for_changes(
                    db,
                    order_id=cancelled_order.id,
                    confirmed_by=payload.sender_id,
                    source_message_id=payload.msg_id,
                    commit=False,
                )
                reply = (
                    f"订单 {order_number_display(order)} 已重新打开，"
                    "请直接告诉我需要修改的备注、规格或商品。"
                )
                owner_notification = _owner_notification(
                    db,
                    order,
                    "客户要求修改已取消订单：",
                    commit=False,
                    settings=active_settings,
                )
            else:
                reply = _cancelled_order_prompt(cancelled_orders)
        elif analysis.intent == "cancel_order":
            order = quote_order or customer_order
            if order is None:
                reply = "当前没有可以取消的订单。"
            else:
                order = cancel_order(
                    db,
                    order_id=order.id,
                    confirmation_text="客户取消订单",
                    confirmed_by=payload.sender_id,
                    source_message_id=payload.msg_id,
                    commit=False,
                )
                reply = "订单已取消。"
                owner_notification = _owner_notification(
                    db,
                    order,
                    "客户取消了订单：",
                    commit=False,
                    settings=active_settings,
                )
        elif analysis.intent in {"confirm_quote", "reject_quote"} or (
            analysis.intent == "confirm_order"
            and active_order is None
            and quote_orders
            and any(
                order.quote_status == QuoteStatus.PENDING_CUSTOMER.value
                for order in quote_orders
            )
        ):
            if len(quote_orders) > 1:
                reply = _quote_choice_prompt(quote_orders)
            elif quote_order is None:
                if order_reference:
                    reply = (
                        f"没有找到订单号 {order_reference} "
                        "对应的待确认报价。"
                    )
                else:
                    reply = "当前没有待确认的报价。"
            elif quote_order.quote_status != QuoteStatus.PENDING_CUSTOMER.value:
                reply = (
                    f"订单 {order_number_display(quote_order)} "
                    "还没有等待客户确认的报价。"
                )
            elif analysis.intent == "reject_quote":
                feedback_text = customer_note or payload.content.strip()
                order = customer_reject_quote(
                    db,
                    order_id=quote_order.id,
                    feedback_text=feedback_text,
                    confirmed_by=payload.sender_id,
                    source_message_id=payload.msg_id,
                    commit=False,
                )
                reply = _quote_feedback_reply(feedback_text)
                owner_notification = _owner_notification(
                    db,
                    order,
                    "客户反馈报价，请重新报价：",
                    commit=False,
                    settings=active_settings,
                    extra=_quote_owner_detail(order, feedback_text),
                )
            else:
                order = customer_approve_quote(
                    db,
                    order_id=quote_order.id,
                    confirmation_text=(
                        "客户确认报价："
                        f"{format_amount(quote_order.quoted_total)}元"
                    ),
                    confirmed_by=payload.sender_id,
                    source_message_id=payload.msg_id,
                    commit=False,
                )
                reply = format_quote_accepted_message(
                    deposit_required=order.deposit_required,
                    deposit_amount=order.deposit_amount,
                )
                owner_notification = _owner_notification(
                    db,
                    order,
                    "客户已确认报价：",
                    commit=False,
                    settings=active_settings,
                    extra=_quote_owner_detail(order, customer_note),
                )
        elif active_order is None and quote_orders and customer_note:
            if len(quote_orders) > 1:
                reply = _quote_choice_prompt(quote_orders)
            else:
                order = quote_order
                reply = "已把备注转告店主。"
                owner_notification = _owner_notification(
                    db,
                    order,
                    "客户补充报价备注：",
                    commit=False,
                    settings=active_settings,
                    extra=_quote_owner_detail(order, customer_note),
                )
        elif analysis.intent == "confirm_order":
            order = active_order
            if order is None:
                if quote_order is not None:
                    reply = "订单已提交给店主，正在等待报价。"
                elif customer_order is not None:
                    reply = _status_reply(customer_order)
                else:
                    reply = "当前没有待确认的订单。"
            elif order.missing_fields:
                reply = format_order_follow_up(
                    order.missing_fields,
                    order.requirements,
                    order.scenario,
                )
            else:
                if not active_settings.wecom_owner_user_id:
                    raise OrderServiceError(
                        "WECOM_OWNER_USER_ID is required to notify the owner"
                    )
                order = confirm_order(
                    db,
                    order_id=order.id,
                    confirmation_text=order.confirmation_text or "",
                    confirmed_by=payload.sender_id,
                    source_message_id=payload.msg_id,
                    commit=False,
                )
                reply = "订单需求已确认，店主报价后会通知您确认。"
                owner_notification = _owner_notification(
                    db,
                    order,
                    "新订单待报价：",
                    commit=False,
                    settings=active_settings,
                    extra=_expected_price_detail(order),
                )
        elif analysis.intent in {
            "create_order",
            "provide_requirement",
            "update_requirement",
        }:
            if active_order is None or (
                analysis.intent == "create_order"
                and _is_explicit_new_order_request(payload.content)
            ):
                customer = get_or_create_customer(
                    db,
                    external_id=payload.sender_id,
                    name=payload.sender_name,
                    commit=False,
                )
                order = create_order(
                    db,
                    customer_id=customer.id,
                    conversation_id=payload.group_id,
                    conversation_name=payload.group_name,
                    scenario=analysis.scenario,
                    title=analysis.order_title or "蛋糕订单",
                    requirements=analysis.requirements,
                    missing_fields=analysis.missing_fields,
                    expected_price=_expected_price(analysis),
                    expected_price_text=_expected_price_text(analysis),
                    commit=False,
                )
            else:
                order = active_order
            _merge_requirements(order, analysis, active_settings)
            reply = _progress_reply(order)
        else:
            if active_order is None:
                if customer_order is not None:
                    reply = _status_reply(customer_order)
                else:
                    reply = UNRELATED_CUSTOMER_REPLY
            else:
                reply = _progress_reply(order)
    except OrderServiceError as exc:
        error = str(exc)
        reply = "订单处理失败，请稍后再试。"

    customer_outbox = enqueue_reply(
        db,
        payload.group_id,
        reply,
        commit=False,
    )
    _finish(db, commit, customer_outbox, order, owner_notification)

    return OrderFlowResult(
        accepted=True,
        duplicate=False,
        message_id=stored.message_id,
        analysis=analysis,
        order=order,
        reply=reply,
        customer_outbox=customer_outbox,
        owner_notification=owner_notification,
        error=error,
    )


def _merge_requirements(
    order: Order,
    analysis: OrderDifyOutput,
    settings: Settings,
) -> None:
    merged = dict(order.requirements or {})
    merged.update(analysis.requirements)
    order.requirements = merged
    expected_price = _expected_price(analysis)
    if expected_price is not None:
        order.customer_expected_price = expected_price
    if _expected_price_text(analysis) is not None:
        order.customer_expected_price_text = _expected_price_text(analysis)
    order.scheduled_at = _scheduled_at(merged, settings)
    order.missing_fields = missing_order_fields(merged, order.scenario)
    order.updated_at = utc_now()

    if order.missing_fields:
        order.confirmation_text = None
        return

    order.confirmation_text = format_order_confirmation(
        merged,
        order.scenario,
    )
    if order.status == OrderStatus.COLLECTING.value:
        transition_order_status(order, OrderStatus.PENDING_CONFIRMATION)


def _progress_reply(order: Order) -> str:
    if order.status == OrderStatus.CONFIRMED.value:
        if order.quote_status == QuoteStatus.PENDING_CUSTOMER.value:
            return (
                f"店主报价：{format_amount(order.quoted_total)} 元。"
                "请回复“确认报价”，或回复“不接受”，让店主重新报价。"
            )
        if order.quote_status == QuoteStatus.PENDING_OWNER.value:
            return "订单已提交给店主，正在等待报价。"
        if order.quote_status == QuoteStatus.REJECTED.value:
            return "店主已收到你的反馈，会重新报价。"
    if order.missing_fields:
        return format_order_follow_up(
            order.missing_fields,
            order.requirements,
            order.scenario,
        )
    return order.confirmation_text or format_order_confirmation(
        order.requirements,
        order.scenario,
    )


def _status_reply(order: Order) -> str:
    if order.status == OrderStatus.PREPARING.value:
        return "订单正在制作中，做好后会通知你。"
    if order.status == OrderStatus.READY.value:
        return "蛋糕已经做好，可以取货啦。"
    if order.status == OrderStatus.COMPLETED.value:
        return "订单已完成，感谢惠顾。"
    if order.status == OrderStatus.CANCELLED.value:
        return "订单已取消。"
    return _progress_reply(order)


def _owner_notification(
    db: Session,
    order: Order,
    prefix: str,
    commit: bool,
    settings: Settings,
    extra: str | None = None,
) -> OutboxMessage | None:
    if not settings.wecom_owner_user_id:
        return None
    content = prefix + "\n" + format_order_summary(
        order.requirements,
        order.scenario,
    )
    if extra:
        content += "\n" + extra
    dispatch_channel = _owner_notification_channel(settings)
    return enqueue_reply(
        db,
        f"direct-{settings.wecom_owner_user_id}",
        content,
        dispatch_channel=dispatch_channel,
        next_attempt_at=utc_now() + timedelta(
            seconds=settings.outbox_retry_base_seconds
        ),
        max_retries=10,
        commit=commit,
    )


def _owner_notification_channel(settings: Settings) -> str:
    configured = settings.order_notification_channel.strip().lower()
    if configured in {"app", "webhook", "active"}:
        return configured
    if (
        settings.wecom_corp_id
        and settings.wecom_app_secret
        and settings.wecom_agent_id
    ):
        return "app"
    if settings.wecom_webhook_url:
        return "webhook"
    return "active"


def _finish(
    db: Session,
    commit: bool,
    customer_outbox: OutboxMessage,
    order: Order | None = None,
    owner_notification: OutboxMessage | None = None,
) -> None:
    if not commit:
        db.flush()
        return

    db.commit()
    if customer_outbox.id is None:
        db.refresh(customer_outbox)
    if order is not None and order.id is None:
        db.refresh(order)
    if owner_notification is not None and owner_notification.id is None:
        db.refresh(owner_notification)


def _expected_price(analysis: OrderDifyOutput) -> Decimal | None:
    value = (
        analysis.customer_expected_price
        if analysis.customer_expected_price is not None
        else analysis.budget_max
    )
    if value is None:
        return None
    return Decimal(str(value))


def _expected_price_text(analysis: OrderDifyOutput) -> str | None:
    if analysis.customer_expected_price_text:
        return analysis.customer_expected_price_text
    value = _expected_price(analysis)
    if value is None:
        return None
    return f"{format_amount(value)}元"


def _scheduled_at(
    requirements: dict,
    settings: Settings,
) -> datetime | None:
    value = requirements.get("pickup_time") or requirements.get("delivery_time")
    if not value:
        return None
    now = datetime.now(ZoneInfo(settings.app_timezone))
    return parse_order_datetime(str(value), now)


def _quote_detail(order: Order) -> str:
    lines: list[str] = []
    if order.order_number:
        lines.append(f"订单号：{order_number_display(order)}")
    if order.quoted_total is not None:
        lines.append(f"报价：{format_amount(order.quoted_total)}元")
    if order.deposit_required and order.deposit_amount is not None:
        lines.append(f"定金：{format_amount(order.deposit_amount)}元")
    return "\n".join(lines)


def _quote_owner_detail(
    order: Order,
    customer_note: str | None = None,
) -> str:
    lines = [_quote_detail(order)]
    if customer_note and customer_note.strip():
        lines.append(f"客户留言：{customer_note.strip()}")
    return "\n".join(line for line in lines if line)


def _looks_like_quote_negotiation(content: str) -> bool:
    return any(
        keyword in content
        for keyword in (
            "便宜",
            "优惠",
            "折扣",
            "降价",
            "少一点",
            "太贵",
            "价格",
            "报价",
        )
    )


def _is_explicit_quote_approval(content: str) -> bool:
    normalized = content.replace(" ", "")
    if any(
        phrase in normalized
        for phrase in (
            "不接受",
            "不能接受",
            "无法接受",
            "接受不了",
            "不太能接受",
            "不太接受",
            "不同意",
            "不能同意",
            "不可以",
            "太贵",
            "好贵",
        )
    ):
        return False
    if "接受" in normalized and any(
        marker in normalized
        for marker in ("不能", "无法", "没法", "不太", "不怎么")
    ):
        return False

    if any(
        keyword in normalized
        for keyword in (
            "确认报价",
            "接受报价",
            "同意报价",
            "价格可以",
            "这个价格可以",
            "报价可以",
            "可以接受",
            "能接受",
            "我接受",
            "接受这个价格",
        )
    ):
        return True

    if normalized in {"接受", "同意", "可以"}:
        return True

    return bool(
        extract_order_reference(normalized)
        and (
            "确认" in normalized
            or "接受" in normalized
            or "同意" in normalized
        )
    )


def _is_explicit_new_order_request(content: str) -> bool:
    normalized = content.replace(" ", "")
    if "确认下单" in normalized or "确认订单" in normalized:
        return False
    return any(
        keyword in normalized
        for keyword in (
            "我想订",
            "我要订",
            "帮我订",
            "我想买",
            "我要买",
            "帮我买",
            "预订",
            "下单",
            "重新订",
            "再订",
            "帮我做",
            "做一个",
            "来一个",
            "要一个",
            "再做一个",
            "另外做一个",
            "重新做一个",
            "新订单",
            "另一个订单",
            "另外订",
            "单独订",
        )
    )


def _is_explicit_cancel(content: str) -> bool:
    normalized = content.replace(" ", "")
    if normalized in {"取消", "取消订单"}:
        return True
    return any(
        keyword in normalized
        for keyword in ("取消订单", "退订", "不订了", "不要了", "不买了")
    )


def _is_restore_request(content: str) -> bool:
    normalized = content.replace(" ", "")
    return any(
        keyword in normalized
        for keyword in (
            "恢复订单",
            "恢复订单号",
            "恢复",
            "反悔",
            "重新做",
            "继续做",
            "还要做",
        )
    )


def _is_modify_request(content: str) -> bool:
    normalized = content.replace(" ", "")
    return any(
        keyword in normalized
        for keyword in (
            "修改",
            "改一下",
            "改备注",
            "改规格",
            "改商品",
            "改尺寸",
            "换一个",
            "换成",
        )
    )


def _cancelled_order_prompt(orders: list[Order]) -> str:
    lines = ["您是在咨询已取消的订单吗？"]
    for order in orders:
        lines.append(f"- {order_number_display(order)}：{order.title}")
    lines.extend(
        [
            "",
            "请回复订单号，并告诉我您是想“恢复订单”还是“修改订单”。",
            "例如：恢复订单 10.08-0001",
        ]
    )
    return "\n".join(lines)


def _quote_feedback_reply(feedback: str) -> str:
    if any(
        keyword in feedback
        for keyword in (
            "好贵",
            "太贵",
            "贵",
            "坑",
            "便宜",
            "优惠",
            "折扣",
            "降价",
        )
    ):
        return (
            "小的试着逼店主一把，给您个骨折价，您先消消气哈，"
            "小的这就去找店主。"
        )
    return "已收到您的意见，店主会重新考虑报价。"


def _quote_choice_prompt(orders: list[Order]) -> str:
    lines = [
        "当前有多笔待确认报价，请回复订单号后再确认或拒绝：",
    ]
    for order in orders:
        amount = (
            f"{format_amount(order.quoted_total)}元"
            if order.quoted_total is not None
            else "待报价"
        )
        lines.append(
            f"- {order_number_display(order)}：{amount}"
        )
    lines.extend(
        [
            "",
            "例如：确认报价 10.07-0006",
        ]
    )
    return "\n".join(lines)


def _expected_price_detail(order: Order) -> str:
    if order.customer_expected_price is None:
        return ""
    return (
        "客户预期价格："
        f"{format_amount(order.customer_expected_price)}元"
    )
