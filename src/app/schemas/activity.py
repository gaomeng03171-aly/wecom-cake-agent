from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ActivityStatus


class DinnerActivityOut(BaseModel):
    id: int
    group_id: str
    group_name: str
    initiator_id: str
    initiator_name: str
    title: str
    status: ActivityStatus
    suggested_time: str | None
    deadline: str | None
    confirmed_plan: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityTransitionIn(BaseModel):
    status: ActivityStatus
