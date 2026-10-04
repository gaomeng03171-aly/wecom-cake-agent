from sqlalchemy import select
from sqlalchemy.orm import Session

from app.clients.wecom import SendResult, WeComSender, get_wecom_sender
from app.models import OutboxMessage, OutboxStatus, utc_now


class OutboxServiceError(RuntimeError):
    pass


def enqueue_reply(
    db: Session,
    group_id: str,
    content: str,
    activity_id: int | None = None,
    commit: bool = True,
) -> OutboxMessage:
    message = OutboxMessage(
        activity_id=activity_id,
        group_id=group_id,
        content=content,
        status=OutboxStatus.PENDING.value,
    )
    db.add(message)
    if commit:
        db.commit()
        db.refresh(message)
    else:
        db.flush()
    return message


def get_outbox_message(db: Session, message_id: int) -> OutboxMessage | None:
    return db.get(OutboxMessage, message_id)


def list_outbox_messages(
    db: Session,
    status: OutboxStatus | None = None,
    group_id: str | None = None,
    activity_id: int | None = None,
) -> list[OutboxMessage]:
    statement = select(OutboxMessage)
    if status is not None:
        statement = statement.where(OutboxMessage.status == status.value)
    if group_id is not None:
        statement = statement.where(OutboxMessage.group_id == group_id)
    if activity_id is not None:
        statement = statement.where(OutboxMessage.activity_id == activity_id)
    statement = statement.order_by(OutboxMessage.id.desc())
    return list(db.scalars(statement).all())


def dispatch_message(
    db: Session,
    message_id: int,
    sender: WeComSender | None = None,
) -> OutboxMessage:
    message = get_outbox_message(db, message_id)
    if message is None:
        raise OutboxServiceError("outbox message not found")
    if message.status == OutboxStatus.SENT.value:
        return message

    active_sender = sender or get_wecom_sender()
    try:
        result = active_sender.send(message)
    except Exception as exc:
        result = SendResult(success=False, error=str(exc))

    return apply_send_result(db, message_id, result)


def apply_send_result(
    db: Session,
    message_id: int,
    result: SendResult,
) -> OutboxMessage:
    message = get_outbox_message(db, message_id)
    if message is None:
        raise OutboxServiceError("outbox message not found")
    if message.status == OutboxStatus.SENT.value:
        return message

    if result.success:
        message.status = OutboxStatus.SENT.value
        message.provider_message_id = result.provider_message_id
        message.last_error = None
        message.sent_at = utc_now()
    else:
        message.retry_count += 1
        message.last_error = result.error or "send failed"
        if message.retry_count >= message.max_retries:
            message.status = OutboxStatus.FAILED.value
        else:
            message.status = OutboxStatus.PENDING.value

    db.commit()
    db.refresh(message)
    return message


def dispatch_pending(db: Session, limit: int = 50) -> list[OutboxMessage]:
    messages = list(
        db.scalars(
            select(OutboxMessage)
            .where(OutboxMessage.status == OutboxStatus.PENDING.value)
            .order_by(OutboxMessage.id)
            .limit(limit)
        ).all()
    )
    for message in messages:
        dispatch_message(db, message.id)
    return messages


def retry_message(db: Session, message_id: int) -> OutboxMessage:
    message = get_outbox_message(db, message_id)
    if message is None:
        raise OutboxServiceError("outbox message not found")
    if message.status == OutboxStatus.SENT.value:
        return message

    message.status = OutboxStatus.PENDING.value
    message.retry_count = 0
    message.last_error = None
    db.commit()
    db.refresh(message)
    return dispatch_message(db, message.id)
