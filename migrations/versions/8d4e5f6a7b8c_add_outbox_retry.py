"""add outbox retry fields

Revision ID: 8d4e5f6a7b8c
Revises: 7a1c2b3d4e5f
Create Date: 2026-10-04 21:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d4e5f6a7b8c"
down_revision: Union[str, None] = "7a1c2b3d4e5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("outbox_messages") as batch_op:
        batch_op.add_column(
            sa.Column(
                "dispatch_channel",
                sa.String(length=32),
                nullable=False,
                server_default="reply",
            )
        )
        batch_op.add_column(
            sa.Column(
                "next_attempt_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_outbox_messages_dispatch_channel",
            ["dispatch_channel"],
        )
        batch_op.create_index(
            "ix_outbox_messages_next_attempt_at",
            ["next_attempt_at"],
        )

    op.execute(
        """
        UPDATE outbox_messages
        SET dispatch_channel = 'active'
        WHERE group_id LIKE 'direct-%'
          AND (
            content LIKE '新订单已确认：%'
            OR content LIKE '客户取消了订单：%'
          )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("outbox_messages") as batch_op:
        batch_op.drop_index("ix_outbox_messages_next_attempt_at")
        batch_op.drop_index("ix_outbox_messages_dispatch_channel")
        batch_op.drop_column("next_attempt_at")
        batch_op.drop_column("dispatch_channel")
