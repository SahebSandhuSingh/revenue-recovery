"""Extend actions table with message_draft and priority

Revision ID: 0002_extend_actions_table
Revises: 0001_initial_schema
Create Date: 2026-08-25 01:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_extend_actions_table"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("actions", sa.Column("priority", sa.String(length=10), nullable=True))
    op.add_column("actions", sa.Column("message_draft", sa.Text(), nullable=True))
    op.create_index(op.f("ix_actions_action_type"), "actions", ["action_type"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_actions_action_type"), table_name="actions")
    op.drop_column("actions", "message_draft")
    op.drop_column("actions", "priority")
