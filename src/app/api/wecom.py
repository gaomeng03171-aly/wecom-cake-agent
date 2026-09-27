from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse
from app.services.inbound import receive_message

router = APIRouter(prefix="/wecom", tags=["wecom"])


@router.post("/messages", response_model=WeComMessageReceiveResponse)
def receive_wecom_message(
    payload: WeComMessageIn,
    db: Session = Depends(get_db),
) -> WeComMessageReceiveResponse:
    return receive_message(db, payload)
