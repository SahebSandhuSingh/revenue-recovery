"""Initial migration for Recoup schema (7 core tables)

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-23 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. events table
    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("customer_id", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_customer_id"), "events", ["customer_id"], unique=False)

    # 2. invoices table
    op.create_table(
        "invoices",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.String(length=255), nullable=False),
        sa.Column("invoice_number", sa.String(length=100), nullable=False),
        sa.Column("gst_number", sa.String(length=20), nullable=False),
        sa.Column("hsn_code", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("credit_terms", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invoices_customer_id"), "invoices", ["customer_id"], unique=False)
    op.create_index(op.f("ix_invoices_invoice_number"), "invoices", ["invoice_number"], unique=True)
    op.create_index(op.f("ix_invoices_status"), "invoices", ["status"], unique=False)

    # 3. diagnoses table (FK ondelete=CASCADE)
    op.create_table(
        "diagnoses",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("root_cause", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("reasoning", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_diagnoses_event_id"), "diagnoses", ["event_id"], unique=False)
    op.create_index(op.f("ix_diagnoses_root_cause"), "diagnoses", ["root_cause"], unique=False)

    # 4. actions table (FK ondelete=CASCADE)
    op.create_table(
        "actions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=100), nullable=True),
        sa.Column("channel", sa.String(length=50), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_actions_event_id"), "actions", ["event_id"], unique=False)

    # 5. promises table (FK ondelete=CASCADE)
    op.create_table(
        "promises",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("promised_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("promised_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_promises_event_id"), "promises", ["event_id"], unique=False)

    # 6. audit_log table (FK ondelete=CASCADE)
    op.create_table(
        "audit_log",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("event_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(length=100), nullable=False),
        sa.Column("decision", sa.Text(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_event_id"), "audit_log", ["event_id"], unique=False)

    # 7. compliance_limits table
    op.create_table(
        "compliance_limits",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.String(length=255), nullable=False),
        sa.Column("contact_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("escalation_flag", sa.Boolean(), server_default="false", nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_compliance_limits_customer_id"),
        "compliance_limits",
        ["customer_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_compliance_limits_customer_id"), table_name="compliance_limits")
    op.drop_table("compliance_limits")
    op.drop_index(op.f("ix_audit_log_event_id"), table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index(op.f("ix_promises_event_id"), table_name="promises")
    op.drop_table("promises")
    op.drop_index(op.f("ix_actions_event_id"), table_name="actions")
    op.drop_table("actions")
    op.drop_index(op.f("ix_diagnoses_root_cause"), table_name="diagnoses")
    op.drop_index(op.f("ix_diagnoses_event_id"), table_name="diagnoses")
    op.drop_table("diagnoses")
    op.drop_index(op.f("ix_invoices_status"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_invoice_number"), table_name="invoices")
    op.drop_index(op.f("ix_invoices_customer_id"), table_name="invoices")
    op.drop_table("invoices")
    op.drop_index(op.f("ix_events_customer_id"), table_name="events")
    op.drop_table("events")
