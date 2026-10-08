"""add quote and fulfillment workflow

Revision ID: 2a3b4c5d6e7f
Revises: 8d4e5f6a7b8c
Create Date: 2026-10-07 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2a3b4c5d6e7f"
down_revision: Union[str, None] = "8d4e5f6a7b8c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column("order_number", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("business_date", sa.Date(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "quote_status",
                sa.String(length=32),
                nullable=False,
                server_default="pending_owner",
            )
        )
        batch_op.add_column(
            sa.Column(
                "payment_status",
                sa.String(length=32),
                nullable=False,
                server_default="not_required",
            )
        )
        batch_op.add_column(
            sa.Column(
                "customer_expected_price",
                sa.Numeric(12, 3),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "customer_expected_price_text",
                sa.String(length=255),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("quoted_total", sa.Numeric(12, 3), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "deposit_required",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
        batch_op.add_column(
            sa.Column("deposit_amount", sa.Numeric(12, 3), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "scheduled_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "preparing_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "ready_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "completed_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_orders_business_date",
            ["business_date"],
        )
        batch_op.create_index(
            "ix_orders_quote_status",
            ["quote_status"],
        )
        batch_op.create_index(
            "ix_orders_payment_status",
            ["payment_status"],
        )
        batch_op.create_index(
            "ix_orders_scheduled_at",
            ["scheduled_at"],
        )
        batch_op.create_unique_constraint(
            "uq_order_business_date_number",
            ["business_date", "order_number"],
        )

    op.create_table(
        "order_quotes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.Numeric(12, 3), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_id",
            "version",
            name="uq_order_quote_version",
        ),
    )
    op.create_index("ix_order_quotes_order_id", "order_quotes", ["order_id"])
    op.create_index("ix_order_quotes_source", "order_quotes", ["source"])
    op.create_index("ix_order_quotes_status", "order_quotes", ["status"])

    op.create_table(
        "order_daily_sequences",
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("business_date"),
    )


def downgrade() -> None:
    op.drop_table("order_daily_sequences")

    op.drop_index("ix_order_quotes_status", table_name="order_quotes")
    op.drop_index("ix_order_quotes_source", table_name="order_quotes")
    op.drop_index("ix_order_quotes_order_id", table_name="order_quotes")
    op.drop_table("order_quotes")

    with op.batch_alter_table("orders") as batch_op:
        batch_op.drop_constraint(
            "uq_order_business_date_number",
            type_="unique",
        )
        batch_op.drop_index("ix_orders_scheduled_at")
        batch_op.drop_index("ix_orders_payment_status")
        batch_op.drop_index("ix_orders_quote_status")
        batch_op.drop_index("ix_orders_business_date")
        batch_op.drop_column("completed_at")
        batch_op.drop_column("ready_at")
        batch_op.drop_column("preparing_at")
        batch_op.drop_column("scheduled_at")
        batch_op.drop_column("deposit_amount")
        batch_op.drop_column("deposit_required")
        batch_op.drop_column("quoted_total")
        batch_op.drop_column("customer_expected_price_text")
        batch_op.drop_column("customer_expected_price")
        batch_op.drop_column("payment_status")
        batch_op.drop_column("quote_status")
        batch_op.drop_column("business_date")
        batch_op.drop_column("order_number")
