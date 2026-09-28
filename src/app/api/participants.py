from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.activity import (
    ActivityParticipantOut,
    JoinActivityIn,
    UpdatePreferenceIn,
)
from app.services.participants import (
    ParticipantServiceError,
    join_activity,
    leave_activity,
    list_participants,
    update_preferences,
)

router = APIRouter(prefix="/activities", tags=["participants"])


def _raise_service_error(exc: ParticipantServiceError) -> None:
    status_code = 404 if "not found" in str(exc) else 409
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post("/{activity_id}/participants", response_model=ActivityParticipantOut)
def add_participant(
    activity_id: int,
    payload: JoinActivityIn,
    db: Session = Depends(get_db),
) -> ActivityParticipantOut:
    try:
        participant = join_activity(db, activity_id, payload)
    except ParticipantServiceError as exc:
        _raise_service_error(exc)
    return participant


@router.get(
    "/{activity_id}/participants",
    response_model=list[ActivityParticipantOut],
)
def get_participants(
    activity_id: int,
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> list[ActivityParticipantOut]:
    return list_participants(db, activity_id, active_only=active_only)


@router.put(
    "/{activity_id}/participants/{user_id}",
    response_model=ActivityParticipantOut,
)
def update_participant_preferences(
    activity_id: int,
    user_id: str,
    payload: UpdatePreferenceIn,
    db: Session = Depends(get_db),
) -> ActivityParticipantOut:
    try:
        participant = update_preferences(db, activity_id, user_id, payload)
    except ParticipantServiceError as exc:
        _raise_service_error(exc)
    return participant


@router.post(
    "/{activity_id}/participants/{user_id}/leave",
    response_model=ActivityParticipantOut,
)
def remove_participant(
    activity_id: int,
    user_id: str,
    db: Session = Depends(get_db),
) -> ActivityParticipantOut:
    try:
        participant = leave_activity(db, activity_id, user_id)
    except ParticipantServiceError as exc:
        _raise_service_error(exc)
    return participant
