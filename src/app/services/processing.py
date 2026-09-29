from sqlalchemy.orm import Session

from app.schemas.activity import ActivityParticipantOut, DinnerActivityOut
from app.schemas.activity import DinnerProposalOut, VoteOut
from app.schemas.wecom import WeComMessageIn, WeComMessageReceiveResponse
from app.services.activities import create_activity_from_message, find_active_activity
from app.services.dify import DifyServiceError, analyze_dinner_message
from app.services.inbound import receive_message
from app.services.participants import apply_preferences_from_message
from app.services.proposals import (
    ProposalServiceError,
    cast_vote,
    generate_proposals,
)


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
    participant = None
    proposals: list[DinnerProposalOut] = []
    vote = None

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
    elif analysis.intent == "generate_proposals":
        activity = find_active_activity(db, payload.group_id)
        if activity is None:
            return stored.model_copy(
                update={
                    "analysis": analysis,
                    "dify_error": "no active activity",
                }
            )
        try:
            activity, generated = generate_proposals(db, activity.id)
            proposals = [DinnerProposalOut.model_validate(item) for item in generated]
        except ProposalServiceError as exc:
            return stored.model_copy(
                update={
                    "analysis": analysis,
                    "dify_error": str(exc),
                }
            )
    elif analysis.intent == "vote":
        activity = find_active_activity(db, payload.group_id)
        if activity is None or analysis.proposal_choice is None:
            return stored.model_copy(
                update={
                    "analysis": analysis,
                    "dify_error": "no active activity or missing proposal choice",
                }
            )
        try:
            vote = cast_vote(
                db,
                activity.id,
                payload.sender_id,
                payload.sender_name,
                analysis.proposal_choice,
            )
        except ProposalServiceError as exc:
            return stored.model_copy(
                update={
                    "analysis": analysis,
                    "dify_error": str(exc),
                }
            )

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
        }
    )
