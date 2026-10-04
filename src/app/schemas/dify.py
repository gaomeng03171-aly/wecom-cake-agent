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
