from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    ActivityParticipant,
    ActivityStatus,
    DinnerActivity,
    DinnerProposal,
    Vote,
)
from app.services.activities import transition_activity_status
from app.services.participants import get_participant


class ProposalServiceError(RuntimeError):
    pass


def get_activity_or_raise(db: Session, activity_id: int) -> DinnerActivity:
    activity = db.get(DinnerActivity, activity_id)
    if activity is None:
        raise ProposalServiceError("activity not found")
    return activity


def list_proposals(db: Session, activity_id: int) -> list[DinnerProposal]:
    return list(
        db.scalars(
            select(DinnerProposal)
            .where(DinnerProposal.activity_id == activity_id)
            .order_by(DinnerProposal.id)
        ).all()
    )


def _active_participants(
    db: Session,
    activity_id: int,
) -> list[ActivityParticipant]:
    return list(
        db.scalars(
            select(ActivityParticipant).where(
                ActivityParticipant.activity_id == activity_id,
                ActivityParticipant.left_at.is_(None),
            )
        ).all()
    )


def generate_proposals(
    db: Session,
    activity_id: int,
    commit: bool = True,
) -> tuple[DinnerActivity, list[DinnerProposal]]:
    activity = get_activity_or_raise(db, activity_id)
    existing = list_proposals(db, activity_id)
    if existing:
        return activity, existing

    if activity.status not in {
        ActivityStatus.COLLECTING.value,
        ActivityStatus.PROPOSING.value,
    }:
        raise ProposalServiceError("activity is not ready for proposals")

    participants = _active_participants(db, activity_id)
    if not participants:
        raise ProposalServiceError("no active participants")

    time_choice = next(
        (
            participant.available_time
            for participant in participants
            if participant.available_time
        ),
        "待确认",
    )
    cuisines = [
        participant.cuisine_preference
        for participant in participants
        if participant.cuisine_preference
    ]
    default_cuisines = ["火锅", "川菜", "烧烤"]
    cuisine_choices = list(dict.fromkeys(cuisines + default_cuisines))[:3]

    budgets = [
        participant.budget_max
        for participant in participants
        if participant.budget_max is not None
    ]
    budget_estimate = max(budgets) if budgets else None

    proposals = []
    for cuisine in cuisine_choices:
        proposal = DinnerProposal(
            activity_id=activity.id,
            title=f"{cuisine} · {time_choice}",
            proposed_time=time_choice,
            cuisine=cuisine,
            budget_estimate=budget_estimate,
            notes="根据当前参与者偏好生成",
        )
        db.add(proposal)
        proposals.append(proposal)

    if activity.status == ActivityStatus.COLLECTING.value:
        transition_activity_status(activity, ActivityStatus.PROPOSING)

    if commit:
        db.commit()
        for proposal in proposals:
            db.refresh(proposal)
        db.refresh(activity)
    else:
        db.flush()
    return activity, proposals


def start_voting(
    db: Session,
    activity_id: int,
    commit: bool = True,
) -> DinnerActivity:
    activity = get_activity_or_raise(db, activity_id)
    if not list_proposals(db, activity_id):
        raise ProposalServiceError("no proposals available")
    if activity.status == ActivityStatus.VOTING.value:
        return activity
    if activity.status != ActivityStatus.PROPOSING.value:
        raise ProposalServiceError("activity is not in proposing state")

    transition_activity_status(activity, ActivityStatus.VOTING)
    if commit:
        db.commit()
        db.refresh(activity)
    else:
        db.flush()
    return activity


def cast_vote(
    db: Session,
    activity_id: int,
    user_id: str,
    user_name: str,
    proposal_id: int,
    commit: bool = True,
) -> Vote:
    activity = get_activity_or_raise(db, activity_id)
    if activity.status != ActivityStatus.VOTING.value:
        raise ProposalServiceError("activity is not in voting state")

    proposal = db.get(DinnerProposal, proposal_id)
    if proposal is None or proposal.activity_id != activity_id:
        raise ProposalServiceError("proposal not found")

    participant = get_participant(db, activity_id, user_id)
    if participant is None or participant.left_at is not None:
        raise ProposalServiceError("active participant not found")

    existing_vote = db.scalar(
        select(Vote).where(
            Vote.activity_id == activity_id,
            Vote.user_id == user_id,
        )
    )
    if existing_vote is None:
        existing_vote = Vote(
            activity_id=activity_id,
            proposal_id=proposal_id,
            user_id=user_id,
            user_name=user_name,
        )
        db.add(existing_vote)
    else:
        existing_vote.proposal_id = proposal_id
        existing_vote.user_name = user_name or existing_vote.user_name

    if commit:
        db.commit()
        db.refresh(existing_vote)
    else:
        db.flush()
    return existing_vote


def confirm_activity(db: Session, activity_id: int) -> DinnerActivity:
    activity = get_activity_or_raise(db, activity_id)
    if activity.status != ActivityStatus.VOTING.value:
        raise ProposalServiceError("activity is not in voting state")

    votes = list(
        db.scalars(
            select(Vote).where(Vote.activity_id == activity_id)
        ).all()
    )
    if not votes:
        raise ProposalServiceError("no votes available")

    counts = Counter(vote.proposal_id for vote in votes)
    winning_proposal_id = max(counts, key=lambda proposal_id: (counts[proposal_id], -proposal_id))
    proposal = db.get(DinnerProposal, winning_proposal_id)
    if proposal is None:
        raise ProposalServiceError("winning proposal not found")

    activity.confirmed_plan = proposal.title
    transition_activity_status(activity, ActivityStatus.CONFIRMED)
    db.commit()
    db.refresh(activity)
    return activity
