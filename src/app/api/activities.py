from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas.activity import ActivityTransitionIn, DinnerActivityOut
from app.services.activities import (
    ActivityStateError,
    find_active_activity,
    get_activity,
    transition_activity_status,
)

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("/{group_id}/active", response_model=DinnerActivityOut)
def active_activity(
    group_id: str,
    db: Session = Depends(get_db),
) -> DinnerActivityOut:
    activity = find_active_activity(db, group_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="no active activity")
    return activity


@router.post("/{activity_id}/transition", response_model=DinnerActivityOut)
def transition_activity(
    activity_id: int,
    payload: ActivityTransitionIn,
    db: Session = Depends(get_db),
) -> DinnerActivityOut:
    activity = get_activity(db, activity_id)
    if activity is None:
        raise HTTPException(status_code=404, detail="activity not found")

    try:
        transition_activity_status(activity, payload.status)
    except ActivityStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    db.refresh(activity)
    return activity
