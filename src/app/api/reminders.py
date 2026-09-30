from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.activity import ReminderCreateIn, ReminderOut, ReminderScheduleIn
from app.services.reminders import (
    ReminderServiceError,
    cancel_reminder,
    create_reminder,
    dispatch_due_reminders,
    list_reminders,
    schedule_activity_reminders,
)

router = APIRouter(tags=["reminders"])


def _raise_service_error(exc: ReminderServiceError) -> None:
    status_code = 404 if "not found" in str(exc) else 409
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/activities/{activity_id}/reminders",
    response_model=ReminderOut,
)
def add_reminder(
    activity_id: int,
    payload: ReminderCreateIn,
    db: Session = Depends(get_db),
) -> ReminderOut:
    try:
        reminder = create_reminder(
            db,
            activity_id=activity_id,
            reminder_type=payload.reminder_type,
            content=payload.content,
            scheduled_at=payload.scheduled_at,
        )
    except ReminderServiceError as exc:
        _raise_service_error(exc)
    return reminder


@router.get(
    "/activities/{activity_id}/reminders",
    response_model=list[ReminderOut],
)
def get_reminders(
    activity_id: int,
    db: Session = Depends(get_db),
) -> list[ReminderOut]:
    return list_reminders(db, activity_id)


@router.post(
    "/activities/{activity_id}/schedule-reminders",
    response_model=list[ReminderOut],
)
def schedule_reminders(
    activity_id: int,
    payload: ReminderScheduleIn,
    db: Session = Depends(get_db),
) -> list[ReminderOut]:
    try:
        reminders = schedule_activity_reminders(
            db,
            activity_id=activity_id,
            deadline_at=payload.deadline_at,
            start_at=payload.start_at,
            deadline_notice_minutes=payload.deadline_notice_minutes,
            start_notice_minutes=payload.start_notice_minutes,
        )
    except ReminderServiceError as exc:
        _raise_service_error(exc)
    return reminders


@router.post("/reminders/dispatch-due", response_model=list[ReminderOut])
def dispatch_due(
    db: Session = Depends(get_db),
) -> list[ReminderOut]:
    return dispatch_due_reminders(db)


@router.post("/reminders/{reminder_id}/cancel", response_model=ReminderOut)
def cancel_existing_reminder(
    reminder_id: int,
    db: Session = Depends(get_db),
) -> ReminderOut:
    try:
        reminder = cancel_reminder(db, reminder_id)
    except ReminderServiceError as exc:
        _raise_service_error(exc)
    return reminder
