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


class ActivityParticipantOut(BaseModel):
    id: int
    activity_id: int
    user_id: str
    user_name: str
    available_time: str | None
    cuisine_preference: str | None
    budget_max: int | None
    notes: str | None
    joined_at: datetime
    left_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class JoinActivityIn(BaseModel):
    user_id: str
    user_name: str = ""
    available_time: str | None = None
    cuisine_preference: str | None = None
    budget_max: int | None = None
    notes: str | None = None


class UpdatePreferenceIn(BaseModel):
    available_time: str | None = None
    cuisine_preference: str | None = None
    budget_max: int | None = None
    notes: str | None = None
