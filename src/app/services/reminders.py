from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import (
    DinnerActivity,
    Reminder,
    ReminderStatus,
    ReminderType,
    utc_now,
)
from app.services.outbox import dispatch_message, enqueue_reply


class ReminderServiceError(RuntimeError):
    pass


def get_activity_or_raise(db: Session, activity_id: int) -> DinnerActivity:
    activity = db.get(DinnerActivity, activity_id)
    if activity is None:
        raise ReminderServiceError("activity not found")
    return activity


def create_reminder(
    db: Session,
    activity_id: int,
    reminder_type: ReminderType,
    content: str,
    scheduled_at: datetime,
) -> Reminder:
    activity = get_activity_or_raise(db, activity_id)
    existing = db.scalar(
        select(Reminder).where(
            Reminder.activity_id == activity_id,
            Reminder.reminder_type == reminder_type.value,
            Reminder.status == ReminderStatus.PENDING.value,
        )
    )
    if existing is not None:
        return existing

    reminder = Reminder(
        activity_id=activity.id,
        reminder_type=reminder_type.value,
        content=content,
        scheduled_at=scheduled_at,
        status=ReminderStatus.PENDING.value,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)
    return reminder


def list_reminders(
    db: Session,
    activity_id: int,
) -> list[Reminder]:
    return list(
        db.scalars(
            select(Reminder)
            .where(Reminder.activity_id == activity_id)
            .order_by(Reminder.scheduled_at, Reminder.id)
        ).all()
    )


def cancel_reminder(db: Session, reminder_id: int) -> Reminder:
    reminder = db.get(Reminder, reminder_id)
    if reminder is None:
        raise ReminderServiceError("reminder not found")
    if reminder.status == ReminderStatus.PENDING.value:
        reminder.status = ReminderStatus.CANCELLED.value
        db.commit()
        db.refresh(reminder)
    return reminder


def schedule_activity_reminders(
    db: Session,
    activity_id: int,
    deadline_at: datetime | None,
    start_at: datetime | None,
    deadline_notice_minutes: int = 10,
    start_notice_minutes: int = 120,
) -> list[Reminder]:
    activity = get_activity_or_raise(db, activity_id)
    reminders = []

    if deadline_at is not None:
        reminders.append(
            create_reminder(
                db,
                activity_id=activity.id,
                reminder_type=ReminderType.VOTING_DEADLINE,
                content=f"{activity.title}的投票即将截止，请尽快选择方案。",
                scheduled_at=deadline_at
                - timedelta(minutes=deadline_notice_minutes),
            )
        )

    if start_at is not None:
        reminders.append(
            create_reminder(
                db,
                activity_id=activity.id,
                reminder_type=ReminderType.ACTIVITY_START,
                content=f"{activity.title}即将开始，请确认时间和地点。",
                scheduled_at=start_at - timedelta(minutes=start_notice_minutes),
            )
        )

    if not reminders:
        raise ReminderServiceError("no reminder schedule provided")
    return reminders


def dispatch_due_reminders(
    db: Session,
    now: datetime | None = None,
    limit: int = 50,
) -> list[Reminder]:
    due_before = now or utc_now()
    reminders = list(
        db.scalars(
            select(Reminder)
            .where(
                Reminder.status == ReminderStatus.PENDING.value,
                Reminder.scheduled_at <= due_before,
            )
            .order_by(Reminder.scheduled_at, Reminder.id)
            .limit(limit)
        ).all()
    )

    for reminder in reminders:
        claim = db.execute(
            update(Reminder)
            .where(
                Reminder.id == reminder.id,
                Reminder.status == ReminderStatus.PENDING.value,
            )
            .values(status=ReminderStatus.PROCESSING.value)
        )
        db.commit()
        if claim.rowcount != 1:
            continue
        db.refresh(reminder)

        try:
            outbox = enqueue_reply(
                db,
                group_id=_activity_group_id(db, reminder.activity_id),
                content=reminder.content,
                activity_id=reminder.activity_id,
            )
            outbox = dispatch_message(db, outbox.id)
        except Exception as exc:
            reminder.status = ReminderStatus.FAILED.value
            reminder.last_error = str(exc)
            db.commit()
            continue

        if outbox.status == "sent":
            reminder.status = ReminderStatus.SENT.value
            reminder.sent_at = utc_now()
            reminder.last_error = None
        else:
            reminder.status = ReminderStatus.FAILED.value
            reminder.last_error = outbox.last_error
        db.commit()
        db.refresh(reminder)

    return reminders


def _activity_group_id(db: Session, activity_id: int) -> str:
    activity = db.get(DinnerActivity, activity_id)
    if activity is None:
        raise ReminderServiceError("activity not found")
    return activity.group_id
