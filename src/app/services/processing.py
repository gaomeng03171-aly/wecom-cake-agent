from sqlalchemy.orm import Session

from app.schemas.activity import (
    ActivityParticipantOut,
    DinnerActivityOut,
    DinnerProposalOut,
    OutboxMessageOut,
    VoteOut,
)
from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse
from app.services.activities import create_activity_from_message, find_active_activity
from app.services.dify import DifyServiceError, analyze_dinner_message
from app.services.inbound import receive_message
from app.services.participants import apply_preferences_from_message
from app.services.proposals import (
    ProposalServiceError,
    cast_vote,
    generate_proposals,
    list_proposals,
)
from app.services.outbox import dispatch_message, enqueue_reply


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
        outbox = enqueue_reply(
            db,
            payload.group_id,
            "我暂时无法理解这条消息，请稍后再试。",
        )
        outbox = dispatch_message(db, outbox.id)
        return stored.model_copy(
            update={
                "dify_error": str(exc),
                "outbox": OutboxMessageOut.model_validate(outbox),
            }
        )

    activity = None
    participant = None
    proposals: list[DinnerProposalOut] = []
    vote = None
    error = None

    if analysis.intent == "create_dinner":
        activity = create_activity_from_message(db, payload, analysis)
    elif analysis.intent == "provide_preference":
        activity = find_active_activity(db, payload.group_id)
        if activity is not None:
            participant = apply_preferences_from_message(
                db,
                activity.id,
                payload.sender_id,
                payload.sender_name,
                analysis,
            )
        else:
            error = "no active activity"
    elif analysis.intent == "generate_proposals":
        activity = find_active_activity(db, payload.group_id)
        if activity is None:
            error = "no active activity"
        else:
            try:
                activity, generated = generate_proposals(db, activity.id)
                proposals = [
                    DinnerProposalOut.model_validate(item) for item in generated
                ]
            except ProposalServiceError as exc:
                error = str(exc)
    elif analysis.intent == "vote":
        activity = find_active_activity(db, payload.group_id)
        if activity is None or analysis.proposal_choice is None:
            error = "no active activity or missing proposal choice"
        else:
            try:
                activity_proposals = list_proposals(db, activity.id)
                choice_index = analysis.proposal_choice - 1
                if choice_index < 0 or choice_index >= len(activity_proposals):
                    raise ProposalServiceError("proposal choice is out of range")
                vote = cast_vote(
                    db,
                    activity.id,
                    payload.sender_id,
                    payload.sender_name,
                    activity_proposals[choice_index].id,
                )
            except ProposalServiceError as exc:
                error = str(exc)

    reply = analysis.reply if error is None else "暂时无法处理这条消息，请稍后再试。"
    outbox = enqueue_reply(
        db,
        payload.group_id,
        reply,
        activity_id=activity.id if activity else None,
    )
    outbox = dispatch_message(db, outbox.id)

    return stored.model_copy(
        update={
            "analysis": analysis,
            "activity": DinnerActivityOut.model_validate(activity) if activity else None,
            "participant": (
                ActivityParticipantOut.model_validate(participant)
                if participant
                else None
            ),
            "proposals": proposals,
            "vote": VoteOut.model_validate(vote) if vote else None,
            "dify_error": error,
            "outbox": OutboxMessageOut.model_validate(outbox),
        }
    )
