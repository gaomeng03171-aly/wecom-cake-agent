from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Customer,
    Order,
    OrderConfirmation,
    OrderConfirmationType,
    OrderScenario,
    OrderStatus,
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
    OrderStatus.CONFIRMED: set(),
    OrderStatus.CANCELLED: set(),
}

ACTIVE_ORDER_STATUSES = {
    OrderStatus.COLLECTING,
    OrderStatus.PENDING_CONFIRMATION,
}


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
    requirements: dict | None = None,
    missing_fields: list[str] | None = None,
    commit: bool = True,
) -> Order:
    if db.get(Customer, customer_id) is None:
        raise OrderServiceError("customer not found")

    order = Order(
        customer_id=customer_id,
        conversation_id=conversation_id,
        conversation_name=conversation_name,
        scenario=scenario,
        title=title,
        status=OrderStatus.COLLECTING.value,
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
    order.confirmation_text = confirmation_text
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
