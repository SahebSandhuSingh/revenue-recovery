"""Add inbound_messages table and raw_reply_text to promises

Revision ID: 0003_add_inbound_messages
Revises: 0002_extend_actions_table
Create Date: 2026-08-25 01:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic. (<=32 chars for alembic_version column)
revision: str = "0003_add_inbound_messages"
down_revision: Union[str, None] = "0002_extend_actions_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create inbound_messages table with CASCADE delete on event_id (FIX 7)
    op.create_table(
        "inbound_messages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("reply_type", sa.String(length=20), nullable=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_inbound_messages_event_id"),
        "inbound_messages",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_inbound_messages_reply_type"),
        "inbound_messages",
        ["reply_type"],
        unique=False,
    )

    # 2. Add raw_reply_text column to promises table
    op.add_column("promises", sa.Column("raw_reply_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("promises", "raw_reply_text")
    op.drop_index(op.f("ix_inbound_messages_reply_type"), table_name="inbound_messages")
    op.drop_index(op.f("ix_inbound_messages_event_id"), table_name="inbound_messages")
    op.drop_table("inbound_messages")
