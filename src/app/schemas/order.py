from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import (
    OrderConfirmationType,
    OrderScenario,
    OrderStatus,
    PaymentStatus,
    QuoteSource,
    QuoteStatus,
)


class CustomerOut(BaseModel):
    id: int
    channel: str
    external_id: str
    name: str
    phone: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderOut(BaseModel):
    id: int
    order_number: int | None
    business_date: date | None
    customer_id: int
    conversation_id: str
    conversation_name: str
    scenario: OrderScenario
    status: OrderStatus
    quote_status: QuoteStatus
    payment_status: PaymentStatus
    title: str
    customer_expected_price: Decimal | None
    customer_expected_price_text: str | None
    quoted_total: Decimal | None
    deposit_required: bool
    deposit_amount: Decimal | None
    scheduled_at: datetime | None
    requirements: dict[str, Any]
    missing_fields: list[str]
    confirmation_text: str | None
    confirmed_at: datetime | None
    preparing_at: datetime | None
    ready_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderConfirmationOut(BaseModel):
    id: int
    order_id: int
    confirmation_type: OrderConfirmationType
    confirmation_text: str
    requirements_snapshot: dict[str, Any]
    confirmed_by: str
    source_message_id: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderQuoteOut(BaseModel):
    id: int
    order_id: int
    version: int
    source: QuoteSource
    amount: Decimal
    status: QuoteStatus
    note: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OwnerQuoteIn(BaseModel):
    amount: Decimal | None = None
    note: str | None = None
    accept_expected_price: bool = False


class OwnerMessageIn(BaseModel):
    content: str


class AdminOrderDetailOut(BaseModel):
    order: OrderOut
    customer: CustomerOut
    confirmations: list[OrderConfirmationOut]
    quotes: list[OrderQuoteOut]
