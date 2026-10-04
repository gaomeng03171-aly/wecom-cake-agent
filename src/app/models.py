from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

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


class ActivityParticipant(Base):
    __tablename__ = "activity_participants"
    __table_args__ = (
        UniqueConstraint(
            "activity_id",
            "user_id",
            name="uq_activity_participant",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("dinner_activities.id"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    user_name: Mapped[str] = mapped_column(String(255), default="")
    available_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cuisine_preference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class DinnerProposal(Base):
    __tablename__ = "dinner_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("dinner_activities.id"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255))
    proposed_time: Mapped[str] = mapped_column(String(255), default="待确认")
    cuisine: Mapped[str] = mapped_column(String(255), default="待确认")
    budget_estimate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class Vote(Base):
    __tablename__ = "votes"
    __table_args__ = (
        UniqueConstraint("activity_id", "user_id", name="uq_activity_vote"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("dinner_activities.id"),
        index=True,
    )
    proposal_id: Mapped[int] = mapped_column(
        ForeignKey("dinner_proposals.id"),
        index=True,
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    user_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )


class OutboxStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class OutboxMessage(Base):
    __tablename__ = "outbox_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("dinner_activities.id"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[str] = mapped_column(String(128), index=True)
    content: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(32),
        default=OutboxStatus.PENDING.value,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class ReminderStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ReminderType(StrEnum):
    VOTING_DEADLINE = "voting_deadline"
    ACTIVITY_START = "activity_start"
    CUSTOM = "custom"


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("dinner_activities.id"),
        index=True,
    )
    reminder_type: Mapped[str] = mapped_column(String(32), index=True)
    content: Mapped[str] = mapped_column(Text)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=ReminderStatus.PENDING.value,
        index=True,
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class OrderStatus(StrEnum):
    COLLECTING = "collecting"
    PENDING_CONFIRMATION = "pending_confirmation"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class OrderScenario(StrEnum):
    CAKE = "cake"
    FLOWER = "flower"
    REPAIR = "repair"
    OTHER = "other"


class OrderConfirmationType(StrEnum):
    CUSTOMER_CONFIRMED = "customer_confirmed"
    CUSTOMER_CANCELLED = "customer_cancelled"


class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint(
            "channel",
            "external_id",
            name="uq_customer_channel_external_id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(32), default="wecom", index=True)
    external_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="customer",
        cascade="all, delete-orphan",
    )


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id"),
        index=True,
    )
    conversation_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_name: Mapped[str] = mapped_column(String(255), default="")
    scenario: Mapped[str] = mapped_column(
        String(32),
        default=OrderScenario.CAKE.value,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=OrderStatus.COLLECTING.value,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), default="订单")
    requirements: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, default=list)
    confirmation_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    customer: Mapped[Customer] = relationship(back_populates="orders")
    confirmations: Mapped[list["OrderConfirmation"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderConfirmation(Base):
    __tablename__ = "order_confirmations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id"),
        index=True,
    )
    confirmation_type: Mapped[str] = mapped_column(String(32), index=True)
    confirmation_text: Mapped[str] = mapped_column(Text, default="")
    requirements_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    confirmed_by: Mapped[str] = mapped_column(String(128), default="")
    source_message_id: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
    )

    order: Mapped[Order] = relationship(back_populates="confirmations")
