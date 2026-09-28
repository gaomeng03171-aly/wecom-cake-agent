from typing import Any, Literal

from pydantic import BaseModel, Field


class DifyWorkflowResult(BaseModel):
    success: bool
    outputs: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class DinnerDifyOutput(BaseModel):
    intent: Literal["create_dinner", "provide_preference", "vote", "unknown"] = (
        "unknown"
    )
    activity_title: str | None = None
    suggested_time: str | None = None
    deadline: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    reply: str = ""
