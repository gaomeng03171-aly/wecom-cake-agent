from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    ActivityParticipant,
    ActivityStatus,
    DinnerActivity,
    DinnerProposal,
    InboundMessage,
    OutboxMessage,
    OutboxStatus,
    Reminder,
    ReminderStatus,
    Vote,
)
from app.schemas.activity import (
    ActivityParticipantOut,
    AdminActivityDetailOut,
    AdminInboundMessageOut,
    AdminOverviewOut,
    DinnerActivityOut,
    DinnerProposalOut,
    OutboxMessageOut,
    ReminderOut,
    VoteOut,
)
from app.services.outbox import list_outbox_messages
from app.services.reminders import list_reminders


def _count(db: Session, model: type, *conditions) -> int:
    statement = select(func.count()).select_from(model)
    if conditions:
        statement = statement.where(*conditions)
    return int(db.scalar(statement) or 0)


def get_overview(db: Session) -> AdminOverviewOut:
    active_statuses = [
        ActivityStatus.COLLECTING.value,
        ActivityStatus.PROPOSING.value,
        ActivityStatus.VOTING.value,
    ]
    return AdminOverviewOut(
        total_activities=_count(db, DinnerActivity),
        active_activities=_count(
            db,
            DinnerActivity,
            DinnerActivity.status.in_(active_statuses),
        ),
        inbound_messages=_count(db, InboundMessage),
        participants=_count(db, ActivityParticipant),
        proposals=_count(db, DinnerProposal),
        votes=_count(db, Vote),
        outbox_pending=_count(
            db,
            OutboxMessage,
            OutboxMessage.status == OutboxStatus.PENDING.value,
        ),
        outbox_sent=_count(
            db,
            OutboxMessage,
            OutboxMessage.status == OutboxStatus.SENT.value,
        ),
        outbox_failed=_count(
            db,
            OutboxMessage,
            OutboxMessage.status == OutboxStatus.FAILED.value,
        ),
        reminders_pending=_count(
            db,
            Reminder,
            Reminder.status == ReminderStatus.PENDING.value,
        ),
    )


def list_activities(
    db: Session,
    group_id: str | None = None,
    status: ActivityStatus | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[DinnerActivityOut]:
    statement = select(DinnerActivity)
    if group_id is not None:
        statement = statement.where(DinnerActivity.group_id == group_id)
    if status is not None:
        statement = statement.where(DinnerActivity.status == status.value)
    statement = (
        statement.order_by(DinnerActivity.created_at.desc(), DinnerActivity.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        DinnerActivityOut.model_validate(activity)
        for activity in db.scalars(statement).all()
    ]


def get_activity_detail(
    db: Session,
    activity_id: int,
) -> AdminActivityDetailOut | None:
    activity = db.get(DinnerActivity, activity_id)
    if activity is None:
        return None

    participants = list(
        db.scalars(
            select(ActivityParticipant)
            .where(ActivityParticipant.activity_id == activity_id)
            .order_by(ActivityParticipant.joined_at)
        ).all()
    )
    proposals = list(
        db.scalars(
            select(DinnerProposal)
            .where(DinnerProposal.activity_id == activity_id)
            .order_by(DinnerProposal.id)
        ).all()
    )
    votes = list(
        db.scalars(
            select(Vote)
            .where(Vote.activity_id == activity_id)
            .order_by(Vote.created_at, Vote.id)
        ).all()
    )

    return AdminActivityDetailOut(
        activity=DinnerActivityOut.model_validate(activity),
        participants=[
            ActivityParticipantOut.model_validate(participant)
            for participant in participants
        ],
        proposals=[
            DinnerProposalOut.model_validate(proposal) for proposal in proposals
        ],
        votes=[VoteOut.model_validate(vote) for vote in votes],
        outbox_messages=[
            OutboxMessageOut.model_validate(message)
            for message in list_outbox_messages(db, activity_id=activity_id)
        ],
        reminders=[
            ReminderOut.model_validate(reminder)
            for reminder in list_reminders(db, activity_id)
        ],
    )
def list_inbound_messages(
    db: Session,
    group_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[AdminInboundMessageOut]:
    statement = select(InboundMessage)
    if group_id is not None:
        statement = statement.where(InboundMessage.group_id == group_id)
    statement = (
        statement.order_by(InboundMessage.created_at.desc(), InboundMessage.id.desc())
        .offset(offset)
        .limit(limit)
    )
    return [
        AdminInboundMessageOut.model_validate(message)
        for message in db.scalars(statement).all()
    ]
