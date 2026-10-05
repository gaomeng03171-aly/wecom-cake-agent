from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import Order, OrderStatus, OutboxMessage, utc_now
from app.schemas.dify import OrderDifyOutput
from app.schemas.wecom import WeComMessageIn
from app.services.dify import DifyServiceError, analyze_order_message
from app.services.inbound import receive_message
from app.services.order_requirements import (
    build_order_requirements,
    format_order_confirmation,
    format_order_follow_up,
    format_order_summary,
    missing_order_fields,
)
from app.services.orders import (
    OrderServiceError,
    cancel_order,
    confirm_order,
    create_order,
    find_active_order,
    get_or_create_customer,
    transition_order_status,
)
from app.services.outbox import enqueue_reply


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

    order = find_active_order(db, payload.group_id)
    owner_notification = None
    error = None
    reply = analysis.reply

    try:
        if analysis.intent == "cancel_order":
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
        elif analysis.intent == "confirm_order":
            if order is None:
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
                reply = "订单已确认，店主会尽快联系你。"
                owner_notification = _owner_notification(
                    db,
                    order,
                    "新订单已确认：",
                    commit=False,
                    settings=active_settings,
                )
        elif analysis.intent in {
            "create_order",
            "provide_requirement",
            "update_requirement",
        }:
            if order is None:
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
                    commit=False,
                )
            _merge_requirements(order, analysis)
            reply = _progress_reply(order)
        else:
            if order is None:
                reply = "请告诉我想订什么商品、数量、尺寸、口味和取货时间。"
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
) -> None:
    merged = dict(order.requirements or {})
    merged.update(analysis.requirements)
    order.requirements = merged
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


def _owner_notification(
    db: Session,
    order: Order,
    prefix: str,
    commit: bool,
    settings: Settings,
) -> OutboxMessage | None:
    if not settings.wecom_owner_user_id:
        return None
    content = prefix + "\n" + format_order_summary(
        order.requirements,
        order.scenario,
    )
    return enqueue_reply(
        db,
        f"direct-{settings.wecom_owner_user_id}",
        content,
        dispatch_channel="active",
        next_attempt_at=utc_now() + timedelta(
            seconds=settings.outbox_retry_base_seconds
        ),
        max_retries=10,
        commit=commit,
    )


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
    db.refresh(customer_outbox)
    if order is not None:
        db.refresh(order)
    if owner_notification is not None:
        db.refresh(owner_notification)
