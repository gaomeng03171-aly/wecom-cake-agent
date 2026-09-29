from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.activity import (
    DinnerActivityOut,
    DinnerProposalOut,
    VoteIn,
    VoteOut,
)
from app.services.proposals import (
    ProposalServiceError,
    cast_vote,
    confirm_activity,
    generate_proposals,
    list_proposals,
    start_voting,
)

router = APIRouter(prefix="/activities", tags=["proposals"])


def _raise_service_error(exc: ProposalServiceError) -> None:
    status_code = 404 if "not found" in str(exc) else 409
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.post(
    "/{activity_id}/generate-proposals",
    response_model=list[DinnerProposalOut],
)
def create_proposals(
    activity_id: int,
    db: Session = Depends(get_db),
) -> list[DinnerProposalOut]:
    try:
        _, proposals = generate_proposals(db, activity_id)
    except ProposalServiceError as exc:
        _raise_service_error(exc)
    return proposals


@router.get(
    "/{activity_id}/proposals",
    response_model=list[DinnerProposalOut],
)
def get_proposals(
    activity_id: int,
    db: Session = Depends(get_db),
) -> list[DinnerProposalOut]:
    return list_proposals(db, activity_id)


@router.post(
    "/{activity_id}/start-voting",
    response_model=DinnerActivityOut,
)
def start_activity_voting(
    activity_id: int,
    db: Session = Depends(get_db),
) -> DinnerActivityOut:
    try:
        activity = start_voting(db, activity_id)
    except ProposalServiceError as exc:
        _raise_service_error(exc)
    return activity


@router.post("/{activity_id}/votes", response_model=VoteOut)
def submit_vote(
    activity_id: int,
    payload: VoteIn,
    db: Session = Depends(get_db),
) -> VoteOut:
    try:
        vote = cast_vote(
            db,
            activity_id,
            payload.user_id,
            payload.user_name,
            payload.proposal_id,
        )
    except ProposalServiceError as exc:
        _raise_service_error(exc)
    return vote


@router.post(
    "/{activity_id}/confirm",
    response_model=DinnerActivityOut,
)
def confirm_activity_plan(
    activity_id: int,
    db: Session = Depends(get_db),
) -> DinnerActivityOut:
    try:
        activity = confirm_activity(db, activity_id)
    except ProposalServiceError as exc:
        _raise_service_error(exc)
    return activity
