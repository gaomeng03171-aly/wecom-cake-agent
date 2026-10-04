"""add order domain

Revision ID: 7a1c2b3d4e5f
Revises: 4dc355121299
Create Date: 2026-10-04 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7a1c2b3d4e5f"
down_revision: Union[str, None] = "4dc355121299"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel",
            "external_id",
            name="uq_customer_channel_external_id",
        ),
    )
    op.create_index("ix_customers_channel", "customers", ["channel"])
    op.create_index("ix_customers_external_id", "customers", ["external_id"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.String(length=128), nullable=False),
        sa.Column("conversation_name", sa.String(length=255), nullable=False),
        sa.Column("scenario", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("requirements", sa.JSON(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("confirmation_text", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orders_customer_id", "orders", ["customer_id"])
    op.create_index("ix_orders_conversation_id", "orders", ["conversation_id"])
    op.create_index("ix_orders_scenario", "orders", ["scenario"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_confirmations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("confirmation_type", sa.String(length=32), nullable=False),
        sa.Column("confirmation_text", sa.Text(), nullable=False),
        sa.Column("requirements_snapshot", sa.JSON(), nullable=False),
        sa.Column("confirmed_by", sa.String(length=128), nullable=False),
        sa.Column("source_message_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_order_confirmations_order_id",
        "order_confirmations",
        ["order_id"],
    )
    op.create_index(
        "ix_order_confirmations_confirmation_type",
        "order_confirmations",
        ["confirmation_type"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_order_confirmations_confirmation_type",
        table_name="order_confirmations",
    )
    op.drop_index("ix_order_confirmations_order_id", table_name="order_confirmations")
    op.drop_table("order_confirmations")

    op.drop_index("ix_orders_status", table_name="orders")
    op.drop_index("ix_orders_scenario", table_name="orders")
    op.drop_index("ix_orders_conversation_id", table_name="orders")
    op.drop_index("ix_orders_customer_id", table_name="orders")
    op.drop_table("orders")

    op.drop_index("ix_customers_external_id", table_name="customers")
    op.drop_index("ix_customers_channel", table_name="customers")
    op.drop_table("customers")
