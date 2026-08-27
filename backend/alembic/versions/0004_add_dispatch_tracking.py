"""Add dispatch tracking columns to actions and reconciled_at to promises

Revision ID: 0004_add_dispatch_tracking
Revises: 0003_add_inbound_messages
Create Date: 2026-08-27 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0004_add_dispatch_tracking"
down_revision: Union[str, None] = "0003_add_inbound_messages"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add dispatch lifecycle columns to actions table
    op.add_column(
        "actions",
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "actions",
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "actions",
        sa.Column("dispatch_error", sa.Text(), nullable=True),
    )

    # 2. Add reconciliation columns to promises table
    op.add_column(
        "promises",
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "promises",
        sa.Column("reconciliation_source", sa.String(length=20), nullable=True),
    )

    # 3. Add index on actions.status for dispatch queries
    op.create_index(
        op.f("ix_actions_status"),
        "actions",
        ["status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_actions_status"), table_name="actions")
    op.drop_column("promises", "reconciliation_source")
    op.drop_column("promises", "reconciled_at")
    op.drop_column("actions", "dispatch_error")
    op.drop_column("actions", "delivered_at")
    op.drop_column("actions", "dispatched_at")
