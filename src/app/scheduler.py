from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_settings
from app.db import get_session_factory
from app.services.reminders import dispatch_due_reminders

_scheduler: BackgroundScheduler | None = None


def _run_due_reminders() -> None:
    db = get_session_factory()()
    try:
        dispatch_due_reminders(db)
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler

    if _scheduler is not None:
        return

    settings = get_settings()
    if settings.app_env == "test" or not settings.reminder_scheduler_enabled:
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _run_due_reminders,
        trigger="interval",
        seconds=settings.reminder_poll_seconds,
        id="dispatch-due-reminders",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    _scheduler = scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
