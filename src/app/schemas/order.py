from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models import OrderConfirmationType, OrderScenario, OrderStatus


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
    customer_id: int
    conversation_id: str
    conversation_name: str
    scenario: OrderScenario
    status: OrderStatus
    title: str
    requirements: dict[str, Any]
    missing_fields: list[str]
    confirmation_text: str | None
    confirmed_at: datetime | None
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


class AdminOrderDetailOut(BaseModel):
    order: OrderOut
    customer: CustomerOut
    confirmations: list[OrderConfirmationOut]
