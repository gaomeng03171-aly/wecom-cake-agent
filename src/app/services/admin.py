from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ActivityParticipant,
    ActivityStatus,
    Customer,
    DinnerActivity,
    DinnerProposal,
    InboundMessage,
    Order,
    OrderConfirmation,
    OrderQuote,
    OrderStatus,
    OutboxMessage,
    OutboxStatus,
    PaymentStatus,
    QuoteStatus,
    Reminder,
    ReminderStatus,
    Vote,
)
from app.schemas.activity import (
    ActivityParticipantOut,
    AdminActivityDetailOut,
    AdminInboundMessageOut,
    AdminOverviewOut,
    DinnerActivityOut,
    DinnerProposalOut,
    OutboxMessageOut,
    ReminderOut,
    VoteOut,
)
from app.schemas.order import (
    AdminOrderDetailOut,
    CustomerOut,
    OrderConfirmationOut,
    OrderOut,
    OrderQuoteOut,
    OwnerMessageIn,
    OwnerQuoteIn,
)
from app.services.order_requirements import format_quote_request
from app.services.outbox import enqueue_reply, list_outbox_messages
from app.services.reminders import list_reminders
from app.services.orders import (
    OrderServiceError,
    mark_deposit_paid,
    mark_order_completed as mark_fulfillment_completed,
    mark_order_ready as mark_fulfillment_ready,
    owner_submit_quote,
)


class AdminOrderActionError(RuntimeError):
    pass


def _count(db: Session, model: type, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int(db.scalar(statement) or 0)


def get_overview(db: Session) -> AdminOverviewOut:
    active_statuses = [
        ActivityStatus.COLLECTING.value,
        ActivityStatus.PROPOSING.value,
        ActivityStatus.VOTING.value,
    ]
    now = datetime.now(ZoneInfo(get_settings().app_timezone))
    day_start = datetime.combine(
        now.date(),
        time.min,
        tzinfo=now.tzinfo,
    ).astimezone(timezone.utc)
    return AdminOverviewOut(
        total_orders=_count(db, Order),
        collecting_orders=_count(
            db,
            Order,
            Order.status == OrderStatus.COLLECTING.value,
        ),
        pending_confirmation_orders=_count(
            db,
            Order,
            Order.status == OrderStatus.PENDING_CONFIRMATION.value,
        ),
        confirmed_orders=_count(
            db,
            Order,
            Order.status == OrderStatus.CONFIRMED.value,
        ),
        pending_owner_quotes=_count(
            db,
            Order,
            Order.quote_status.in_(
                [
                    QuoteStatus.PENDING_OWNER.value,
                    QuoteStatus.REJECTED.value,
                ]
            ),
            Order.status == OrderStatus.CONFIRMED.value,
        ),
        pending_customer_quotes=_count(
            db,
            Order,
            Order.quote_status == QuoteStatus.PENDING_CUSTOMER.value,
            Order.status == OrderStatus.CONFIRMED.value,
        ),
        deposit_pending_orders=_count(
            db,
            Order,
            Order.payment_status == PaymentStatus.DEPOSIT_PENDING.value,
        ),
        preparing_orders=_count(
            db,
            Order,
            Order.status == OrderStatus.PREPARING.value,
        ),
        ready_orders=_count(
            db,
            Order,
            Order.status == OrderStatus.READY.value,
        ),
        completed_today=_count(
            db,
            Order,
            Order.status == OrderStatus.COMPLETED.value,
            Order.completed_at >= day_start,
        ),
        total_activities=_count(db, DinnerActivity),
        active_activities=_count(
            db,
            DinnerActivity,
            DinnerActivity.status.in_(active_statuses),
        ),
        inbound_messages=_count(db, InboundMessage),
        participants=_count(db, ActivityParticipant),
        proposals=_count(db, DinnerProposal),
        votes=_count(db, Vote),
        outbox_pending=_count(
            db,
            OutboxMessage,
            OutboxMessage.status == OutboxStatus.PENDING.value,
        ),
        outbox_sent=_count(
            db,
            OutboxMessage,
            OutboxMessage.status == OutboxStatus.SENT.value,
        ),
        outbox_failed=_count(
            db,
            OutboxMessage,
            OutboxMessage.status == OutboxStatus.FAILED.value,
        ),
        reminders_pending=_count(
            db,
            Reminder,
            Reminder.status == ReminderStatus.PENDING.value,
        ),
    )


def list_activities(
    db: Session,
    group_id: str | None = None,
    status: ActivityStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DinnerActivityOut]:
    statement = select(DinnerActivity)
    if group_id is not None:
        statement = statement.where(DinnerActivity.group_id == group_id)
    if status is not None:
        statement = statement.where(DinnerActivity.status == status.value)
    statement = (
        statement.order_by(DinnerActivity.created_at.desc(), DinnerActivity.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        DinnerActivityOut.model_validate(activity)
        for activity in db.scalars(statement).all()
    ]


def get_activity_detail(
    db: Session,
    activity_id: int,
) -> AdminActivityDetailOut | None:
    activity = db.get(DinnerActivity, activity_id)
    if activity is None:
        return None

    participants = list(
        db.scalars(
            select(ActivityParticipant)
            .where(ActivityParticipant.activity_id == activity_id)
            .order_by(ActivityParticipant.joined_at)
        ).all()
    )
    proposals = list(
        db.scalars(
            select(DinnerProposal)
            .where(DinnerProposal.activity_id == activity_id)
            .order_by(DinnerProposal.id)
        ).all()
    )
    votes = list(
        db.scalars(
            select(Vote)
            .where(Vote.activity_id == activity_id)
            .order_by(Vote.created_at, Vote.id)
        ).all()
    )

    return AdminActivityDetailOut(
        activity=DinnerActivityOut.model_validate(activity),
        participants=[
            ActivityParticipantOut.model_validate(participant)
            for participant in participants
        ],
        proposals=[
            DinnerProposalOut.model_validate(proposal) for proposal in proposals
        ],
        votes=[VoteOut.model_validate(vote) for vote in votes],
        outbox_messages=[
            OutboxMessageOut.model_validate(message)
            for message in list_outbox_messages(db, activity_id=activity_id)
        ],
        reminders=[
            ReminderOut.model_validate(reminder)
            for reminder in list_reminders(db, activity_id)
        ],
    )


def list_inbound_messages(
    db: Session,
    group_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminInboundMessageOut]:
    statement = select(InboundMessage)
    if group_id is not None:
        statement = statement.where(InboundMessage.group_id == group_id)
    statement = (
        statement.order_by(InboundMessage.created_at.desc(), InboundMessage.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        AdminInboundMessageOut.model_validate(message)
        for message in db.scalars(statement).all()
    ]


def list_orders(
    db: Session,
    status: OrderStatus | None = None,
    scenario: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[OrderOut]:
    statement = select(Order)
    if status is not None:
        statement = statement.where(Order.status == status.value)
    if scenario:
        statement = statement.where(Order.scenario == scenario)
    statement = (
        statement.order_by(Order.created_at.desc(), Order.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        OrderOut.model_validate(order)
        for order in db.scalars(statement).all()
    ]


def get_order_detail(
    db: Session,
    order_id: int,
) -> AdminOrderDetailOut | None:
    order = db.get(Order, order_id)
    if order is None:
        return None
    customer = db.get(Customer, order.customer_id)
    if customer is None:
        return None
    confirmations = list(
        db.scalars(
            select(OrderConfirmation)
            .where(OrderConfirmation.order_id == order_id)
            .order_by(OrderConfirmation.created_at, OrderConfirmation.id)
        ).all()
    )
    return AdminOrderDetailOut(
        order=OrderOut.model_validate(order),
        customer=CustomerOut.model_validate(customer),
        confirmations=[
            OrderConfirmationOut.model_validate(confirmation)
            for confirmation in confirmations
        ],
        quotes=[
            OrderQuoteOut.model_validate(quote)
            for quote in db.scalars(
                select(OrderQuote)
                .where(OrderQuote.order_id == order_id)
                .order_by(OrderQuote.version)
            ).all()
        ],
    )


def submit_owner_quote(
    db: Session,
    order_id: int,
    payload: OwnerQuoteIn,
):
    order = db.get(Order, order_id)
    if order is None:
        raise AdminOrderActionError("order not found")

    if payload.accept_expected_price:
        amount = order.customer_expected_price
        if amount is None:
            raise AdminOrderActionError("客户没有填写预期价格")
    else:
        amount = payload.amount
        if amount is None:
            raise AdminOrderActionError("请填写店主报价")

    try:
        owner_submit_quote(
            db,
            order_id=order_id,
            amount=amount,
            note=payload.note,
            commit=False,
        )
        content = format_quote_request(
            order.requirements or {},
            amount,
            order_number=(
                f"{order.business_date:%m.%d}-{order.order_number:04d}"
                if order.business_date is not None
                and order.order_number is not None
                else None
            ),
            note=payload.note,
            scenario=order.scenario,
        )
        outbox = enqueue_customer_notification(
            db,
            order,
            content,
        )
        db.commit()
        db.refresh(order)
        db.refresh(outbox)
        return order, outbox
    except OrderServiceError as exc:
        db.rollback()
        raise AdminOrderActionError(str(exc)) from exc


def mark_order_deposit_paid(
    db: Session,
    order_id: int,
):
    order = db.get(Order, order_id)
    if order is None:
        raise AdminOrderActionError("order not found")
    try:
        mark_deposit_paid(db, order_id=order_id, commit=False)
        outbox = enqueue_customer_notification(
            db,
            order,
            "已收到定金，订单开始制作。",
        )
        db.commit()
        db.refresh(order)
        db.refresh(outbox)
        return order, outbox
    except OrderServiceError as exc:
        db.rollback()
        raise AdminOrderActionError(str(exc)) from exc


def mark_order_ready(
    db: Session,
    order_id: int,
):
    order = db.get(Order, order_id)
    if order is None:
        raise AdminOrderActionError("order not found")
    try:
        mark_fulfillment_ready(db, order_id=order_id, commit=False)
        outbox = enqueue_customer_notification(
            db,
            order,
            "蛋糕已制作完成，可以取货啦。",
        )
        db.commit()
        db.refresh(order)
        db.refresh(outbox)
        return order, outbox
    except OrderServiceError as exc:
        db.rollback()
        raise AdminOrderActionError(str(exc)) from exc


def mark_order_completed(
    db: Session,
    order_id: int,
):
    order = db.get(Order, order_id)
    if order is None:
        raise AdminOrderActionError("order not found")
    try:
        mark_fulfillment_completed(db, order_id=order_id, commit=False)
        outbox = enqueue_customer_notification(
            db,
            order,
            "订单已完成，感谢惠顾。",
        )
        db.commit()
        db.refresh(order)
        db.refresh(outbox)
        return order, outbox
    except OrderServiceError as exc:
        db.rollback()
        raise AdminOrderActionError(str(exc)) from exc


def send_owner_message(
    db: Session,
    order_id: int,
    payload: OwnerMessageIn,
):
    order = db.get(Order, order_id)
    if order is None:
        raise AdminOrderActionError("order not found")
    content = payload.content.strip()
    if not content:
        raise AdminOrderActionError("留言不能为空")
    try:
        outbox = enqueue_customer_notification(
            db,
            order,
            f"店主留言：{content}",
        )
        db.commit()
        db.refresh(order)
        db.refresh(outbox)
        return order, outbox
    except Exception as exc:
        db.rollback()
        raise AdminOrderActionError(str(exc)) from exc


def enqueue_customer_notification(
    db: Session,
    order: Order,
    content: str,
) -> OutboxMessage:
    return enqueue_reply(
        db,
        order.conversation_id,
        content,
        dispatch_channel="active",
        next_attempt_at=None,
        max_retries=10,
        commit=False,
    )
