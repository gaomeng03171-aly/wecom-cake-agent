from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import ActivityStatus, OrderStatus
from app.schemas.activity import (
    AdminActivityDetailOut,
    AdminInboundMessageOut,
    AdminOverviewOut,
    DinnerActivityOut,
    IntegrationStatusOut,
)
from app.schemas.order import (
    AdminOrderDetailOut,
    OrderOut,
    OwnerMessageIn,
    OwnerQuoteIn,
)
from app.services.admin import (
    AdminOrderActionError,
    get_activity_detail,
    get_order_detail,
    get_overview,
    list_activities,
    list_inbound_messages,
    list_orders,
    mark_order_completed,
    mark_order_ready,
    mark_order_deposit_paid,
    send_owner_message,
    submit_owner_quote,
)
from app.services.integration_status import get_integration_status

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


@router.get(
    "/integration-status",
    response_model=IntegrationStatusOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_integration_status() -> IntegrationStatusOut:
    return get_integration_status(get_settings())


@router.get(
    "/orders",
    response_model=list[OrderOut],
    dependencies=[Depends(require_admin_key)],
)
def admin_orders(
    status: OrderStatus | None = None,
    scenario: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> list[OrderOut]:
    return list_orders(
        db,
        status=status,
        scenario=scenario,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/orders/{order_id}",
    response_model=AdminOrderDetailOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_order_detail(
    order_id: int,
    db: Session = Depends(get_db),
) -> AdminOrderDetailOut:
    detail = get_order_detail(db, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="order not found")
    return detail


@router.post(
    "/orders/{order_id}/quote",
    response_model=AdminOrderDetailOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_submit_order_quote(
    order_id: int,
    payload: OwnerQuoteIn,
    db: Session = Depends(get_db),
) -> AdminOrderDetailOut:
    try:
        submit_owner_quote(db, order_id, payload)
    except AdminOrderActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    detail = get_order_detail(db, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="order not found")
    return detail


@router.post(
    "/orders/{order_id}/deposit-paid",
    response_model=AdminOrderDetailOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_mark_deposit_paid(
    order_id: int,
    db: Session = Depends(get_db),
) -> AdminOrderDetailOut:
    try:
        mark_order_deposit_paid(db, order_id)
    except AdminOrderActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    detail = get_order_detail(db, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="order not found")
    return detail


@router.post(
    "/orders/{order_id}/ready",
    response_model=AdminOrderDetailOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_mark_order_ready(
    order_id: int,
    db: Session = Depends(get_db),
) -> AdminOrderDetailOut:
    try:
        mark_order_ready(db, order_id)
    except AdminOrderActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    detail = get_order_detail(db, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="order not found")
    return detail


@router.post(
    "/orders/{order_id}/completed",
    response_model=AdminOrderDetailOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_mark_order_completed(
    order_id: int,
    db: Session = Depends(get_db),
) -> AdminOrderDetailOut:
    try:
        mark_order_completed(db, order_id)
    except AdminOrderActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    detail = get_order_detail(db, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="order not found")
    return detail


@router.post(
    "/orders/{order_id}/message",
    response_model=AdminOrderDetailOut,
    dependencies=[Depends(require_admin_key)],
)
def admin_send_owner_message(
    order_id: int,
    payload: OwnerMessageIn,
    db: Session = Depends(get_db),
) -> AdminOrderDetailOut:
    try:
        send_owner_message(db, order_id, payload)
    except AdminOrderActionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    detail = get_order_detail(db, order_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="order not found")
    return detail
