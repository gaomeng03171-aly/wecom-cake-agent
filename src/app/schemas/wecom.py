from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
