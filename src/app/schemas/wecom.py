from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.activity import (
    ActivityParticipantOut,
    DinnerActivityOut,
    DinnerProposalOut,
    VoteOut,
)
from app.schemas.dify import DinnerDifyOutput


class WeComMessageIn(BaseModel):
    msg_id: str
    group_id: str
    group_name: str = ""
    sender_id: str
    sender_name: str = ""
    msg_type: str = "text"
    content: str = ""
    create_time: datetime | None = None
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class WeComMessageReceiveResponse(BaseModel):
    accepted: bool
    duplicate: bool
    message_id: int | None = None
    analysis: DinnerDifyOutput | None = None
    dify_error: str | None = None
    activity: DinnerActivityOut | None = None
    participant: ActivityParticipantOut | None = None
    proposals: list[DinnerProposalOut] = Field(default_factory=list)
    vote: VoteOut | None = None
