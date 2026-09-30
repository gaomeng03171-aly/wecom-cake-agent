from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ActivityStatus
from app.schemas.activity import (
    AdminActivityDetailOut,
    AdminInboundMessageOut,
    AdminOverviewOut,
    DinnerActivityOut,
)
from app.services.admin import (
    get_activity_detail,
    get_overview,
    list_activities,
    list_inbound_messages,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def require_admin_key(
    x_admin_key: Annotated[str | None, Header(alias="X-Admin-Key")] = None,
) -> None:
    settings = get_settings()
    if settings.admin_api_key and x_admin_key != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="invalid admin key")


@router.get(
    "/overview",
    response_model=AdminOverviewOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_overview(db: Session = Depends(get_db)) -> AdminOverviewOut:
    return get_overview(db)


@router.get(
    "/activities",
    response_model=list[DinnerActivityOut],
    dependencies=[Depends(require_admin_key)],
)
def admin_activities(
    group_id: str | None = None,
    status: ActivityStatus | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[DinnerActivityOut]:
    return list_activities(
        db,
        group_id=group_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/activities/{activity_id}",
    response_model=AdminActivityDetailOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_activity_detail(
    activity_id: int,
    db: Session = Depends(get_db),
) -> AdminActivityDetailOut:
    detail = get_activity_detail(db, activity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="activity not found")
    return detail


@router.get(
    "/messages",
    response_model=list[AdminInboundMessageOut],
    dependencies=[Depends(require_admin_key)],
)
def admin_messages(
    group_id: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[AdminInboundMessageOut]:
    return list_inbound_messages(
        db,
        group_id=group_id,
        limit=limit,
        offset=offset,
    )
