from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ActivityStatus(StrEnum):
    COLLECTING = "collecting"
    PROPOSING = "proposing"
    VOTING = "voting"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class InboundMessage(Base):
    __tablename__ = "inbound_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    wecom_msg_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    group_id: Mapped[str] = mapped_column(String(128), index=True)
    group_name: Mapped[str] = mapped_column(String(255), default="")
    sender_id: Mapped[str] = mapped_column(String(128), index=True)
    sender_name: Mapped[str] = mapped_column(String(255), default="")
    msg_type: Mapped[str] = mapped_column(String(32), default="text")
    content: Mapped[str] = mapped_column(Text, default="")
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class DinnerActivity(Base):
    __tablename__ = "dinner_activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    group_id: Mapped[str] = mapped_column(String(128), index=True)
    group_name: Mapped[str] = mapped_column(String(255), default="")
    initiator_id: Mapped[str] = mapped_column(String(128))
    initiator_name: Mapped[str] = mapped_column(String(255), default="")
    title: Mapped[str] = mapped_column(String(255), default="聚餐")
    status: Mapped[str] = mapped_column(
        String(32),
        default=ActivityStatus.COLLECTING.value,
        index=True,
    )
    suggested_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed_plan: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
