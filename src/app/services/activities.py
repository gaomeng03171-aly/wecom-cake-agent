from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityParticipant, ActivityStatus, DinnerActivity, utc_now
from app.schemas.dify import DinnerDifyOutput
from app.schemas.wecom import WeComMessageIn

ACTIVE_STATUSES = {
    ActivityStatus.COLLECTING,
    ActivityStatus.PROPOSING,
    ActivityStatus.VOTING,
}

ACTIVE_PARTICIPATION_STATUSES = {
    ActivityStatus.COLLECTING,
    ActivityStatus.PROPOSING,
    ActivityStatus.VOTING,
}

ALLOWED_TRANSITIONS: dict[ActivityStatus, set[ActivityStatus]] = {
    ActivityStatus.COLLECTING: {
        ActivityStatus.PROPOSING,
        ActivityStatus.CANCELLED,
    },
    ActivityStatus.PROPOSING: {
        ActivityStatus.VOTING,
        ActivityStatus.CANCELLED,
    },
    ActivityStatus.VOTING: {
        ActivityStatus.CONFIRMED,
        ActivityStatus.CANCELLED,
    },
    ActivityStatus.CONFIRMED: {
        ActivityStatus.COMPLETED,
        ActivityStatus.CANCELLED,
    },
    ActivityStatus.COMPLETED: set(),
    ActivityStatus.CANCELLED: set(),
}


class ActivityStateError(RuntimeError):
    pass


def find_active_activity(db: Session, group_id: str) -> DinnerActivity | None:
    statuses = [status.value for status in ACTIVE_STATUSES]
    return db.scalar(
        select(DinnerActivity)
        .where(
            DinnerActivity.group_id == group_id,
            DinnerActivity.status.in_(statuses),
        )
        .order_by(DinnerActivity.created_at.desc())
        .limit(1)
    )


def get_activity(db: Session, activity_id: int) -> DinnerActivity | None:
    return db.get(DinnerActivity, activity_id)


def create_activity_from_message(
    db: Session,
    message: WeComMessageIn,
    analysis: DinnerDifyOutput,
) -> DinnerActivity:
    existing = find_active_activity(db, message.group_id)
    if existing is not None:
        return existing

    activity = DinnerActivity(
        group_id=message.group_id,
        group_name=message.group_name,
        initiator_id=message.sender_id,
        initiator_name=message.sender_name,
        title=analysis.activity_title or "聚餐",
        status=ActivityStatus.COLLECTING.value,
        suggested_time=analysis.suggested_time,
        deadline=analysis.deadline,
    )
    db.add(activity)
    db.flush()
    db.add(
        ActivityParticipant(
            activity_id=activity.id,
            user_id=message.sender_id,
            user_name=message.sender_name,
        )
    )
    db.commit()
    db.refresh(activity)
    return activity


def transition_activity_status(
    activity: DinnerActivity,
    new_status: ActivityStatus,
) -> None:
    current = ActivityStatus(activity.status)
    allowed = ALLOWED_TRANSITIONS.get(current, set())

    if new_status not in allowed:
        raise ActivityStateError(
            f"cannot transition from {current.value} to {new_status.value}"
        )

    activity.status = new_status.value
    activity.updated_at = utc_now()
