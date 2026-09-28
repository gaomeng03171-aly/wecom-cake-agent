from sqlalchemy.orm import Session

from app.schemas.activity import DinnerActivityOut
from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse
from app.services.activities import create_activity_from_message
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

    activity = None
    if analysis.intent == "create_dinner":
        activity = create_activity_from_message(db, payload, analysis)

    return stored.model_copy(
        update={
            "analysis": analysis,
            "activity": DinnerActivityOut.model_validate(activity) if activity else None,
        }
    )
