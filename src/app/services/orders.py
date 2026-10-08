import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Customer,
    Order,
    OrderConfirmation,
    OrderConfirmationType,
    OrderDailySequence,
    OrderQuote,
    OrderScenario,
    OrderStatus,
    PaymentStatus,
    QuoteSource,
    QuoteStatus,
    utc_now,
)


class OrderServiceError(RuntimeError):
    pass


ALLOWED_ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.COLLECTING: {
        OrderStatus.PENDING_CONFIRMATION,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PENDING_CONFIRMATION: {
        OrderStatus.CONFIRMED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.CONFIRMED: {
        OrderStatus.PREPARING,
        OrderStatus.CANCELLED,
    },
    OrderStatus.PREPARING: {
        OrderStatus.READY,
        OrderStatus.CANCELLED,
    },
    OrderStatus.READY: {
        OrderStatus.COMPLETED,
        OrderStatus.CANCELLED,
    },
    OrderStatus.COMPLETED: set(),
    OrderStatus.CANCELLED: set(),
}

ACTIVE_ORDER_STATUSES = {
    OrderStatus.COLLECTING,
    OrderStatus.PENDING_CONFIRMATION,
}

CUSTOMER_ACTION_STATUSES = {
    OrderStatus.COLLECTING,
    OrderStatus.PENDING_CONFIRMATION,
    OrderStatus.CONFIRMED,
    OrderStatus.PREPARING,
    OrderStatus.READY,
}


def order_number_display(order: Order) -> str | None:
    if order.business_date is None or order.order_number is None:
        return None
    return f"{order.business_date:%m.%d}-{order.order_number:04d}"


def get_or_create_customer(
    db: Session,
    *,
    external_id: str,
    name: str = "",
    channel: str = "wecom",
    phone: str | None = None,
    notes: str | None = None,
    commit: bool = True,
) -> Customer:
    customer = db.scalar(
        select(Customer).where(
            Customer.channel == channel,
            Customer.external_id == external_id,
        )
    )
    if customer is None:
        customer = Customer(
            channel=channel,
            external_id=external_id,
            name=name,
            phone=phone,
            notes=notes,
        )
        db.add(customer)
    else:
        if name:
            customer.name = name
        if phone is not None:
            customer.phone = phone
        if notes is not None:
            customer.notes = notes
        customer.updated_at = utc_now()

    if commit:
        db.commit()
        db.refresh(customer)
    else:
        db.flush()
    return customer


def create_order(
    db: Session,
    *,
    customer_id: int,
    conversation_id: str,
    conversation_name: str = "",
    scenario: str = OrderScenario.CAKE.value,
    title: str = "订单",
    expected_price: Decimal | None = None,
    expected_price_text: str | None = None,
    scheduled_at: datetime | None = None,
    requirements: dict | None = None,
    missing_fields: list[str] | None = None,
    commit: bool = True,
) -> Order:
    if db.get(Customer, customer_id) is None:
        raise OrderServiceError("customer not found")

    business_date = _current_business_date()
    order_number = _allocate_order_number(db, business_date)
    order = Order(
        order_number=order_number,
        business_date=business_date,
        customer_id=customer_id,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        scenario=scenario,
        title=title,
        status=OrderStatus.COLLECTING.value,
        quote_status=QuoteStatus.PENDING_OWNER.value,
        payment_status=PaymentStatus.NOT_REQUIRED.value,
        customer_expected_price=expected_price,
        customer_expected_price_text=expected_price_text,
        scheduled_at=scheduled_at,
        requirements=requirements or {},
        missing_fields=missing_fields or [],
    )
    db.add(order)
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def _current_business_date() -> date:
    timezone = ZoneInfo(get_settings().app_timezone)
    return datetime.now(timezone).date()


def _allocate_order_number(
    db: Session,
    business_date: date,
) -> int:
    dialect = db.get_bind().dialect.name
    values = {
        "business_date": business_date,
        "last_number": 1,
        "updated_at": utc_now(),
    }
    update_values = {
        "last_number": OrderDailySequence.last_number + 1,
        "updated_at": utc_now(),
    }

    if dialect == "postgresql":
        statement = (
            postgresql_insert(OrderDailySequence)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[OrderDailySequence.business_date],
                set_=update_values,
            )
            .returning(OrderDailySequence.last_number)
        )
        return int(db.scalar(statement))

    if dialect == "sqlite":
        statement = (
            sqlite_insert(OrderDailySequence)
            .values(**values)
            .on_conflict_do_update(
                index_elements=[OrderDailySequence.business_date],
                set_=update_values,
            )
            .returning(OrderDailySequence.last_number)
        )
        return int(db.scalar(statement))

    # Non-SQLite/PostgreSQL development databases fall back to a
    # savepoint-protected read-modify-write sequence.
    for _ in range(3):
        try:
            with db.begin_nested():
                sequence = db.scalar(
                    select(OrderDailySequence)
                    .where(
                        OrderDailySequence.business_date == business_date
                    )
                    .with_for_update()
                )
                if sequence is None:
                    sequence = OrderDailySequence(
                        business_date=business_date,
                        last_number=1,
                    )
                    db.add(sequence)
                else:
                    sequence.last_number += 1
                db.flush()
            return int(sequence.last_number)
        except IntegrityError:
            continue

    raise OrderServiceError("failed to allocate order number")


def get_order(db: Session, order_id: int) -> Order | None:
    return db.get(Order, order_id)


def find_active_order(
    db: Session,
    conversation_id: str,
) -> Order | None:
    statuses = [status.value for status in ACTIVE_ORDER_STATUSES]
    return db.scalar(
        select(Order)
        .where(
            Order.conversation_id == conversation_id,
            Order.status.in_(statuses),
        )
        .order_by(Order.created_at.desc())
        .limit(1)
    )


def find_customer_order(
    db: Session,
    conversation_id: str,
) -> Order | None:
    statuses = [status.value for status in CUSTOMER_ACTION_STATUSES]
    return db.scalar(
        select(Order)
        .where(
            Order.conversation_id == conversation_id,
            Order.status.in_(statuses),
        )
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(1)
    )


def transition_order_status(
    order: Order,
    new_status: OrderStatus | str,
) -> Order:
    current = OrderStatus(order.status)
    target = OrderStatus(new_status)
    if target not in ALLOWED_ORDER_TRANSITIONS.get(current, set()):
        raise OrderServiceError(
            f"cannot transition order from {current.value} to {target.value}"
        )

    now = utc_now()
    order.status = target.value
    order.updated_at = now
    if target == OrderStatus.CONFIRMED:
        order.confirmed_at = now
    elif target == OrderStatus.PREPARING:
        order.preparing_at = now
    elif target == OrderStatus.READY:
        order.ready_at = now
    elif target == OrderStatus.COMPLETED:
        order.completed_at = now
    elif target == OrderStatus.CANCELLED:
        order.cancelled_at = now
    return order


def record_order_confirmation(
    db: Session,
    *,
    order_id: int,
    confirmation_type: OrderConfirmationType | str,
    confirmation_text: str = "",
    requirements_snapshot: dict | None = None,
    confirmed_by: str = "",
    source_message_id: str | None = None,
    commit: bool = True,
) -> OrderConfirmation:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")

    confirmation = OrderConfirmation(
        order_id=order.id,
        confirmation_type=OrderConfirmationType(confirmation_type).value,
        confirmation_text=confirmation_text,
        requirements_snapshot=(
            requirements_snapshot
            if requirements_snapshot is not None
            else dict(order.requirements or {})
        ),
        confirmed_by=confirmed_by,
        source_message_id=source_message_id,
    )
    db.add(confirmation)
    if commit:
        db.commit()
        db.refresh(confirmation)
    else:
        db.flush()
    return confirmation


def confirm_order(
    db: Session,
    *,
    order_id: int,
    confirmation_text: str = "",
    confirmed_by: str = "",
    source_message_id: str | None = None,
    commit: bool = True,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if order.status == OrderStatus.CONFIRMED.value:
        return order
    if order.status != OrderStatus.PENDING_CONFIRMATION.value:
        raise OrderServiceError("order is not pending confirmation")

    transition_order_status(order, OrderStatus.CONFIRMED)
    order.quote_status = QuoteStatus.PENDING_OWNER.value
    order.payment_status = PaymentStatus.NOT_REQUIRED.value
    order.confirmation_text = confirmation_text
    if order.customer_expected_price is not None:
        _create_order_quote(
            db,
            order,
            source=QuoteSource.CUSTOMER,
            amount=order.customer_expected_price,
            status=QuoteStatus.PENDING_OWNER,
            note="客户预期价格",
        )
    record_order_confirmation(
        db,
        order_id=order.id,
        confirmation_type=OrderConfirmationType.CUSTOMER_CONFIRMED,
        confirmation_text=confirmation_text,
        confirmed_by=confirmed_by,
        source_message_id=source_message_id,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def cancel_order(
    db: Session,
    *,
    order_id: int,
    confirmation_text: str = "",
    confirmed_by: str = "",
    source_message_id: str | None = None,
    commit: bool = True,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if order.status == OrderStatus.CANCELLED.value:
        return order

    transition_order_status(order, OrderStatus.CANCELLED)
    record_order_confirmation(
        db,
        order_id=order.id,
        confirmation_type=OrderConfirmationType.CUSTOMER_CANCELLED,
        confirmation_text=confirmation_text,
        confirmed_by=confirmed_by,
        source_message_id=source_message_id,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def find_cancelled_orders(
    db: Session,
    conversation_id: str,
    order_reference: str | None = None,
) -> list[Order]:
    orders = list(
        db.scalars(
            select(Order)
            .where(
                Order.conversation_id == conversation_id,
                Order.status == OrderStatus.CANCELLED.value,
            )
            .order_by(Order.created_at.desc(), Order.id.desc())
        ).all()
    )
    if not order_reference:
        return orders
    return [
        order
        for order in orders
        if _order_matches_reference(order, order_reference)
    ]


def find_cancelled_order(
    db: Session,
    conversation_id: str,
    order_reference: str | None = None,
) -> Order | None:
    orders = find_cancelled_orders(
        db,
        conversation_id,
        order_reference=order_reference,
    )
    return orders[0] if len(orders) == 1 else None


def restore_order(
    db: Session,
    *,
    order_id: int,
    confirmed_by: str = "",
    source_message_id: str | None = None,
    commit: bool = True,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if order.status != OrderStatus.CANCELLED.value:
        raise OrderServiceError("order is not cancelled")

    order.status = _restored_status(order).value
    order.cancelled_at = None
    order.updated_at = utc_now()
    record_order_confirmation(
        db,
        order_id=order.id,
        confirmation_type=OrderConfirmationType.CUSTOMER_RESTORED,
        confirmation_text="客户恢复订单",
        confirmed_by=confirmed_by,
        source_message_id=source_message_id,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def reopen_order_for_changes(
    db: Session,
    *,
    order_id: int,
    confirmed_by: str = "",
    source_message_id: str | None = None,
    commit: bool = True,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if order.status != OrderStatus.CANCELLED.value:
        raise OrderServiceError("order is not cancelled")

    order.status = OrderStatus.PENDING_CONFIRMATION.value
    order.cancelled_at = None
    order.quote_status = QuoteStatus.PENDING_OWNER.value
    order.quoted_total = None
    order.deposit_required = False
    order.deposit_amount = None
    order.payment_status = PaymentStatus.NOT_REQUIRED.value
    order.updated_at = utc_now()
    record_order_confirmation(
        db,
        order_id=order.id,
        confirmation_type=OrderConfirmationType.CUSTOMER_MODIFY_REQUEST,
        confirmation_text="客户要求恢复并修改订单",
        confirmed_by=confirmed_by,
        source_message_id=source_message_id,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def _restored_status(order: Order) -> OrderStatus:
    if order.ready_at is not None:
        return OrderStatus.READY
    if order.preparing_at is not None:
        return OrderStatus.PREPARING
    if order.confirmed_at is not None:
        return OrderStatus.CONFIRMED
    return OrderStatus.PENDING_CONFIRMATION


def find_orders_for_quote(
    db: Session,
    conversation_id: str,
    order_reference: str | None = None,
) -> list[Order]:
    orders = list(
        db.scalars(
            select(Order)
            .where(
                Order.conversation_id == conversation_id,
                Order.status == OrderStatus.CONFIRMED.value,
                Order.quote_status.in_(
                    [
                        QuoteStatus.PENDING_OWNER.value,
                        QuoteStatus.PENDING_CUSTOMER.value,
                        QuoteStatus.REJECTED.value,
                    ]
                ),
            )
            .order_by(Order.created_at.desc(), Order.id.desc())
        ).all()
    )
    if not order_reference:
        return orders
    return [
        order
        for order in orders
        if _order_matches_reference(order, order_reference)
    ]


def find_order_for_quote(
    db: Session,
    conversation_id: str,
    order_reference: str | None = None,
) -> Order | None:
    orders = find_orders_for_quote(
        db,
        conversation_id,
        order_reference=order_reference,
    )
    return orders[0] if len(orders) == 1 else None


def _order_matches_reference(order: Order, reference: str) -> bool:
    value = reference.strip().lower()
    display = order_number_display(order)
    if display and value == display.lower():
        return True

    date_match = re.fullmatch(
        r"(\d{1,2})[.\-](\d{1,2})-(\d{1,4})",
        value,
    )
    if date_match and order.business_date is not None:
        return (
            order.business_date.month == int(date_match.group(1))
            and order.business_date.day == int(date_match.group(2))
            and order.order_number == int(date_match.group(3))
        )

    digits = re.sub(r"\D", "", value)
    if not digits or order.order_number is None:
        return False
    return int(digits) == order.order_number


def owner_submit_quote(
    db: Session,
    *,
    order_id: int,
    amount: Decimal | int | float | str,
    note: str | None = None,
    commit: bool = True,
) -> OrderQuote:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if order.status != OrderStatus.CONFIRMED.value:
        raise OrderServiceError("order is not awaiting a quote")
    if order.quote_status not in {
        QuoteStatus.PENDING_OWNER.value,
        QuoteStatus.PENDING_CUSTOMER.value,
        QuoteStatus.REJECTED.value,
    }:
        raise OrderServiceError("order quote cannot be changed")

    amount_decimal = Decimal(str(amount))
    if amount_decimal <= 0:
        raise OrderServiceError("quote amount must be positive")

    order.quoted_total = amount_decimal
    order.quote_status = QuoteStatus.PENDING_CUSTOMER.value
    order.updated_at = utc_now()
    quote = _create_order_quote(
        db,
        order,
        source=QuoteSource.OWNER,
        amount=amount_decimal,
        status=QuoteStatus.PENDING_CUSTOMER,
        note=note,
    )
    if commit:
        db.commit()
        db.refresh(order)
        db.refresh(quote)
    else:
        db.flush()
    return quote


def customer_approve_quote(
    db: Session,
    *,
    order_id: int,
    confirmation_text: str = "",
    confirmed_by: str = "",
    source_message_id: str | None = None,
    commit: bool = True,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if order.quote_status != QuoteStatus.PENDING_CUSTOMER.value:
        raise OrderServiceError("order has no customer-pending quote")
    if order.quoted_total is None:
        raise OrderServiceError("order quote amount is missing")

    order.quote_status = QuoteStatus.APPROVED.value
    _mark_latest_quote_status(db, order, QuoteStatus.APPROVED)
    deposit_required, deposit_amount = calculate_deposit(order)
    order.deposit_required = deposit_required
    order.deposit_amount = deposit_amount

    if deposit_required:
        order.payment_status = PaymentStatus.DEPOSIT_PENDING.value
    else:
        order.payment_status = PaymentStatus.NOT_REQUIRED.value
        if order.status == OrderStatus.CONFIRMED.value:
            transition_order_status(order, OrderStatus.PREPARING)

    order.updated_at = utc_now()
    record_order_confirmation(
        db,
        order_id=order.id,
        confirmation_type=OrderConfirmationType.QUOTE_APPROVED,
        confirmation_text=confirmation_text,
        confirmed_by=confirmed_by,
        source_message_id=source_message_id,
        commit=False,
    )
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def customer_reject_quote(
    db: Session,
    *,
    order_id: int,
    feedback_text: str = "",
    confirmed_by: str = "",
    source_message_id: str | None = None,
    commit: bool = True,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if order.quote_status != QuoteStatus.PENDING_CUSTOMER.value:
        raise OrderServiceError("order has no customer-pending quote")

    order.quote_status = QuoteStatus.REJECTED.value
    order.updated_at = utc_now()
    _mark_latest_quote_status(db, order, QuoteStatus.REJECTED)
    if feedback_text.strip():
        record_order_confirmation(
            db,
            order_id=order.id,
            confirmation_type=OrderConfirmationType.QUOTE_FEEDBACK,
            confirmation_text=feedback_text.strip(),
            confirmed_by=confirmed_by,
            source_message_id=source_message_id,
            commit=False,
        )
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def mark_deposit_paid(
    db: Session,
    *,
    order_id: int,
    commit: bool = True,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    if not order.deposit_required:
        raise OrderServiceError("order does not require a deposit")
    if order.payment_status != PaymentStatus.DEPOSIT_PENDING.value:
        raise OrderServiceError("order deposit is not pending")

    order.payment_status = PaymentStatus.DEPOSIT_PAID.value
    if order.status == OrderStatus.CONFIRMED.value:
        transition_order_status(order, OrderStatus.PREPARING)
    order.updated_at = utc_now()
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def mark_order_ready(
    db: Session,
    *,
    order_id: int,
    commit: bool = True,
) -> Order:
    return _transition_fulfillment(
        db,
        order_id=order_id,
        target=OrderStatus.READY,
        commit=commit,
    )


def mark_order_completed(
    db: Session,
    *,
    order_id: int,
    commit: bool = True,
) -> Order:
    return _transition_fulfillment(
        db,
        order_id=order_id,
        target=OrderStatus.COMPLETED,
        commit=commit,
    )


def calculate_deposit(order: Order) -> tuple[bool, Decimal | None]:
    if (
        order.quoted_total is None
        or order.scheduled_at is None
        or order.business_date is None
    ):
        return False, None

    pickup_date = order.scheduled_at.date()
    days_until_pickup = (pickup_date - order.business_date).days
    if days_until_pickup <= 5 or order.quoted_total <= Decimal("200"):
        return False, None

    return True, order.quoted_total * Decimal("0.20")


def _transition_fulfillment(
    db: Session,
    *,
    order_id: int,
    target: OrderStatus,
    commit: bool,
) -> Order:
    order = get_order(db, order_id)
    if order is None:
        raise OrderServiceError("order not found")
    transition_order_status(order, target)
    if commit:
        db.commit()
        db.refresh(order)
    else:
        db.flush()
    return order


def _next_quote_version(db: Session, order_id: int) -> int:
    latest = db.scalar(
        select(OrderQuote)
        .where(OrderQuote.order_id == order_id)
        .order_by(OrderQuote.version.desc())
        .limit(1)
    )
    return (latest.version + 1) if latest else 1


def _create_order_quote(
    db: Session,
    order: Order,
    *,
    source: QuoteSource | str,
    amount: Decimal,
    status: QuoteStatus | str,
    note: str | None,
) -> OrderQuote:
    for quote in order.quotes:
        if quote.status in {
            QuoteStatus.PENDING_OWNER.value,
            QuoteStatus.PENDING_CUSTOMER.value,
        }:
            quote.status = QuoteStatus.SUPERSEDED.value

    quote = OrderQuote(
        order_id=order.id,
        version=_next_quote_version(db, order.id),
        source=QuoteSource(source).value,
        amount=amount,
        status=QuoteStatus(status).value,
        note=note,
    )
    db.add(quote)
    db.flush()
    return quote


def _mark_latest_quote_status(
    db: Session,
    order: Order,
    status: QuoteStatus,
) -> None:
    quote = db.scalar(
        select(OrderQuote)
        .where(OrderQuote.order_id == order.id)
        .order_by(OrderQuote.version.desc())
        .limit(1)
    )
    if quote is not None:
        quote.status = status.value
