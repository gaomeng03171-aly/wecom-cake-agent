from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import OutboxStatus
from app.schemas.activity import OutboxCreateIn, OutboxMessageOut
from app.services.outbox import (
    OutboxServiceError,
    dispatch_message,
    dispatch_pending,
    enqueue_reply,
    list_outbox_messages,
    retry_message,
)

router = APIRouter(prefix="/outbox", tags=["outbox"])


def _raise_service_error(exc: OutboxServiceError) -> None:
    raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("", response_model=OutboxMessageOut)
def create_outbox_message(
    payload: OutboxCreateIn,
    db: Session = Depends(get_db),
) -> OutboxMessageOut:
    message = enqueue_reply(
        db,
        group_id=payload.group_id,
        content=payload.content,
        activity_id=payload.activity_id,
    )
    if payload.dispatch:
        message = dispatch_message(db, message.id)
    return message


@router.get("", response_model=list[OutboxMessageOut])
def get_outbox_messages(
    status: OutboxStatus | None = None,
    group_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[OutboxMessageOut]:
    return list_outbox_messages(db, status=status, group_id=group_id)


@router.post("/{message_id}/dispatch", response_model=OutboxMessageOut)
def dispatch_outbox_message(
    message_id: int,
    db: Session = Depends(get_db),
) -> OutboxMessageOut:
    try:
        message = dispatch_message(db, message_id)
    except OutboxServiceError as exc:
        _raise_service_error(exc)
    return message


@router.post("/dispatch-pending", response_model=list[OutboxMessageOut])
def dispatch_pending_messages(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[OutboxMessageOut]:
    return dispatch_pending(db, limit=limit)


@router.post("/{message_id}/retry", response_model=OutboxMessageOut)
def retry_outbox_message(
    message_id: int,
    db: Session = Depends(get_db),
) -> OutboxMessageOut:
    try:
        message = retry_message(db, message_id)
    except OutboxServiceError as exc:
        _raise_service_error(exc)
    return message
