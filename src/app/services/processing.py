from sqlalchemy.orm import Session

from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse
from app.services.dify import DifyServiceError, analyze_dinner_message
from app.services.inbound import receive_message


def process_inbound_message(
    db: Session,
    payload: WeComMessageIn,
) -> WeComMessageReceiveResponse:
    stored = receive_message(db, payload)
    if stored.duplicate:
        return stored

    try:
        analysis = analyze_dinner_message(payload.content)
    except DifyServiceError as exc:
        return stored.model_copy(
            update={"dify_error": str(exc)},
        )

    return stored.model_copy(update={"analysis": analysis})
