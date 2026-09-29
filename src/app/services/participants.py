from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ActivityParticipant, ActivityStatus, DinnerActivity, utc_now
from app.schemas.activity import (
    ActivityParticipantOut,
    JoinActivityIn,
    UpdatePreferenceIn,
)


class ParticipantServiceError(RuntimeError):
    pass


def get_activity_or_raise(
    db: Session,
    activity_id: int,
) -> DinnerActivity:
    activity = db.get(DinnerActivity, activity_id)
    if activity is None:
        raise ParticipantServiceError("activity not found")
    if activity.status in {
        ActivityStatus.COMPLETED.value,
        ActivityStatus.CANCELLED.value,
    }:
        raise ParticipantServiceError("activity is not active")
    return activity


def get_participant(
    db: Session,
    activity_id: int,
    user_id: str,
) -> ActivityParticipant | None:
    return db.scalar(
        select(ActivityParticipant).where(
            ActivityParticipant.activity_id == activity_id,
            ActivityParticipant.user_id == user_id,
        )
    )


def join_activity(
    db: Session,
    activity_id: int,
    payload: JoinActivityIn,
) -> ActivityParticipant:
    get_activity_or_raise(db, activity_id)
    participant = get_participant(db, activity_id, payload.user_id)

    if participant is None:
        participant = ActivityParticipant(
            activity_id=activity_id,
            user_id=payload.user_id,
            user_name=payload.user_name,
            available_time=payload.available_time,
            cuisine_preference=payload.cuisine_preference,
            budget_max=payload.budget_max,
            notes=payload.notes,
        )
        db.add(participant)
    else:
        if payload.user_name:
            participant.user_name = payload.user_name
        if "available_time" in payload.model_fields_set:
            participant.available_time = payload.available_time
        if "cuisine_preference" in payload.model_fields_set:
            participant.cuisine_preference = payload.cuisine_preference
        if "budget_max" in payload.model_fields_set:
            participant.budget_max = payload.budget_max
        if "notes" in payload.model_fields_set:
            participant.notes = payload.notes
        participant.left_at = None

    db.commit()
    db.refresh(participant)
    return participant


def leave_activity(
    db: Session,
    activity_id: int,
    user_id: str,
) -> ActivityParticipant:
    get_activity_or_raise(db, activity_id)
    participant = get_participant(db, activity_id, user_id)
    if participant is None:
        raise ParticipantServiceError("participant not found")

    participant.left_at = utc_now()
    db.commit()
    db.refresh(participant)
    return participant


def update_preferences(
    db: Session,
    activity_id: int,
    user_id: str,
    payload: UpdatePreferenceIn,
) -> ActivityParticipant:
    get_activity_or_raise(db, activity_id)
    participant = get_participant(db, activity_id, user_id)
    if participant is None or participant.left_at is not None:
        raise ParticipantServiceError("active participant not found")

    if "available_time" in payload.model_fields_set:
        participant.available_time = payload.available_time
    if "cuisine_preference" in payload.model_fields_set:
        participant.cuisine_preference = payload.cuisine_preference
    if "budget_max" in payload.model_fields_set:
        participant.budget_max = payload.budget_max
    if "notes" in payload.model_fields_set:
        participant.notes = payload.notes

    db.commit()
    db.refresh(participant)
    return participant


def list_participants(
    db: Session,
    activity_id: int,
    active_only: bool = True,
) -> list[ActivityParticipant]:
    statement = select(ActivityParticipant).where(
        ActivityParticipant.activity_id == activity_id
    )
    if active_only:
        statement = statement.where(ActivityParticipant.left_at.is_(None))
    statement = statement.order_by(ActivityParticipant.joined_at)
    return list(db.scalars(statement).all())


def apply_preferences_from_message(
    db: Session,
    activity_id: int,
    user_id: str,
    user_name: str,
    analysis,
) -> ActivityParticipant:
    payload = JoinActivityIn(
        user_id=user_id,
        user_name=user_name,
        available_time=analysis.available_time,
        cuisine_preference=analysis.cuisine_preference,
        budget_max=analysis.budget_max,
        notes=analysis.notes,
    )
    return join_activity(db, activity_id, payload)
