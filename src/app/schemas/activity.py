from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ActivityStatus, OutboxStatus, ReminderStatus, ReminderType


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


class DinnerProposalOut(BaseModel):
    id: int
    activity_id: int
    title: str
    proposed_time: str
    cuisine: str
    budget_estimate: int | None
    notes: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoteOut(BaseModel):
    id: int
    activity_id: int
    proposal_id: int
    user_id: str
    user_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoteIn(BaseModel):
    user_id: str
    user_name: str = ""
    proposal_id: int


class OutboxMessageOut(BaseModel):
    id: int
    activity_id: int | None
    group_id: str
    content: str
    status: OutboxStatus
    retry_count: int
    max_retries: int
    last_error: str | None
    provider_message_id: str | None
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class OutboxCreateIn(BaseModel):
    group_id: str
    content: str
    activity_id: int | None = None
    dispatch: bool = True


class ReminderOut(BaseModel):
    id: int
    activity_id: int
    reminder_type: ReminderType
    content: str
    scheduled_at: datetime
    status: ReminderStatus
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class ReminderCreateIn(BaseModel):
    reminder_type: ReminderType = ReminderType.CUSTOM
    content: str
    scheduled_at: datetime


class ReminderScheduleIn(BaseModel):
    deadline_at: datetime | None = None
    start_at: datetime | None = None
    deadline_notice_minutes: int = 10
    start_notice_minutes: int = 120


class AdminInboundMessageOut(BaseModel):
    id: int
    wecom_msg_id: str
    group_id: str
    group_name: str
    sender_id: str
    sender_name: str
    msg_type: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminOverviewOut(BaseModel):
    total_orders: int
    collecting_orders: int
    pending_confirmation_orders: int
    confirmed_orders: int
    total_activities: int
    active_activities: int
    inbound_messages: int
    participants: int
    proposals: int
    votes: int
    outbox_pending: int
    outbox_sent: int
    outbox_failed: int
    reminders_pending: int


class AdminActivityDetailOut(BaseModel):
    activity: DinnerActivityOut
    participants: list[ActivityParticipantOut]
    proposals: list[DinnerProposalOut]
    votes: list[VoteOut]
    outbox_messages: list[OutboxMessageOut]
    reminders: list[ReminderOut]


class IntegrationStatusOut(BaseModel):
    order_dify_mode: str
    order_dify_ready: bool
    missing_order_dify_config: list[str]
    wecom_sender_mode: str
    wecom_sender_ready: bool
    missing_wecom_sender_config: list[str]
    wecom_aibot_ready: bool
    missing_wecom_aibot_config: list[str]
    wecom_callback_ready: bool
    missing_wecom_callback_config: list[str]
    wecom_callback_url: str
    dify_client_mode: str
    dify_ready: bool
    missing_dify_config: list[str]
    database_dialect: str
