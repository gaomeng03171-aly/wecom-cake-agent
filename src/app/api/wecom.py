from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse
from app.services.processing import process_inbound_message

router = APIRouter(prefix="/wecom", tags=["wecom"])


@router.post("/messages", response_model=WeComMessageReceiveResponse)
def receive_wecom_message(
    payload: WeComMessageIn,
    db: Session = Depends(get_db),
) -> WeComMessageReceiveResponse:
    return process_inbound_message(db, payload)
