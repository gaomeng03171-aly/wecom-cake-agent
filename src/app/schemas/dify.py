from typing import Any, Literal

from pydantic import BaseModel, Field


class DifyWorkflowResult(BaseModel):
    success: bool
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class DinnerDifyOutput(BaseModel):
    intent: Literal[
        "create_dinner",
        "provide_preference",
        "generate_proposals",
        "summarize",
        "confirm",
        "vote",
        "unknown",
    ] = "unknown"
    activity_title: str | None = None
    suggested_time: str | None = None
    deadline: str | None = None
    available_time: str | None = None
    cuisine_preference: str | None = None
    budget_max: int | None = None
    notes: str | None = None
    proposal_choice: int | None = None
    missing_fields: list[str] = Field(default_factory=list)
    reply: str = ""


class OrderDifyOutput(BaseModel):
    intent: Literal[
        "create_order",
        "provide_requirement",
        "update_requirement",
        "confirm_order",
        "confirm_quote",
        "reject_quote",
        "cancel_order",
        "unknown",
    ] = "unknown"
    scenario: str = "cake"
    order_title: str | None = None
    customer_name: str | None = None
    phone: str | None = None
    product_name: str | None = None
    quantity: int | None = None
    size: str | None = None
    flavor: str | None = None
    message_on_cake: str | None = None
    pickup_time: str | None = None
    delivery_time: str | None = None
    delivery_address: str | None = None
    budget_max: int | None = None
    customer_expected_price: float | None = None
    customer_expected_price_text: str | None = None
    order_reference: str | None = None
    customer_note: str | None = None
    notes: str | None = None
    extra_requirements: dict[str, Any] = Field(default_factory=dict)
    requirements: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    confirmation_text: str | None = None
    reply: str = ""
