from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import InboundMessage
from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse


def receive_message(
    db: Session,
    payload: WeComMessageIn,
    commit: bool = True,
) -> WeComMessageReceiveResponse:
    existing = db.scalar(
        select(InboundMessage).where(InboundMessage.wecom_msg_id == payload.msg_id)
    )
    if existing is not None:
        return WeComMessageReceiveResponse(
            accepted=True,
            duplicate=True,
            message_id=existing.id,
        )

    message = InboundMessage(
        wecom_msg_id=payload.msg_id,
        group_id=payload.group_id,
        group_name=payload.group_name,
        sender_id=payload.sender_id,
        sender_name=payload.sender_name,
        msg_type=payload.msg_type,
        content=payload.content,
        raw_payload=payload.raw_payload,
    )
    db.add(message)
    try:
        if commit:
            db.commit()
        else:
            db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(InboundMessage).where(
                InboundMessage.wecom_msg_id == payload.msg_id
            )
        )
        if existing is None:
            raise
        return WeComMessageReceiveResponse(
            accepted=True,
            duplicate=True,
            message_id=existing.id,
        )

    if commit:
        db.refresh(message)
    return WeComMessageReceiveResponse(
        accepted=True,
        duplicate=False,
        message_id=message.id,
    )
