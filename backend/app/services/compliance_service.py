import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import (
    MAX_BROKEN_PROMISES_BEFORE_ESCALATION,
    MAX_CONTACTS_BEFORE_ESCALATION,
)
from app.models import ComplianceLimit, Event, Promise

logger = logging.getLogger(__name__)


def get_or_create_compliance_record(
    customer_id: str, db: Session
) -> ComplianceLimit:
    """Fetch existing compliance guardrail record for customer or create default."""
    record = db.scalar(
        select(ComplianceLimit).where(ComplianceLimit.customer_id == customer_id)
    )
    if not record:
        record = ComplianceLimit(
            customer_id=customer_id,
            contact_count=0,
            last_contact_at=None,
            escalation_flag=False,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
    return record


def count_broken_promises_for_customer(customer_id: str, db: Session) -> int:
    """Count broken promise commitments associated with this customer."""
    broken_count = (
        db.scalar(
            select(func.count(Promise.id))
            .join(Event, Promise.event_id == Event.id)
            .where(
                Event.customer_id == customer_id,
                Promise.status == "broken",
            )
        )
        or 0
    )
    return broken_count


def register_contact(customer_id: str, db: Session) -> Dict[str, Any]:
    """Register an outbound customer contact, evaluate stopping rules, and update escalation flag.

    Stopping Rules:
    1. contact_count >= MAX_CONTACTS_BEFORE_ESCALATION (3)
    2. broken_promises >= MAX_BROKEN_PROMISES_BEFORE_ESCALATION (1)

    Returns:
        Dict[str, Any]: Updated compliance status and escalation reason if blocked.
    """
    record = get_or_create_compliance_record(customer_id, db)
    record.contact_count += 1
    record.last_contact_at = datetime.now(timezone.utc)

    broken_promises = count_broken_promises_for_customer(customer_id, db)

    escalation_reasons = []
    if record.contact_count >= MAX_CONTACTS_BEFORE_ESCALATION:
        record.escalation_flag = True
        escalation_reasons.append(
            f"Maximum contact attempts reached ({record.contact_count}/{MAX_CONTACTS_BEFORE_ESCALATION})"
        )

    if broken_promises >= MAX_BROKEN_PROMISES_BEFORE_ESCALATION:
        record.escalation_flag = True
        escalation_reasons.append(
            f"Broken payment promise detected ({broken_promises}/{MAX_BROKEN_PROMISES_BEFORE_ESCALATION})"
        )

    db.commit()
    db.refresh(record)

    reason_str = "; ".join(escalation_reasons) if escalation_reasons else None
    if record.escalation_flag:
        logger.warning(
            f"Customer {customer_id} ESCALATED: {reason_str}"
        )

    return {
        "id": str(record.id),
        "customer_id": record.customer_id,
        "contact_count": record.contact_count,
        "last_contact_at": record.last_contact_at.isoformat() if record.last_contact_at else None,
        "escalation_flag": record.escalation_flag,
        "broken_promises_count": broken_promises,
        "escalation_reason": reason_str,
    }


def is_customer_blocked(customer_id: str, db: Session) -> bool:
    """Return True if customer is blocked / escalated from further automated outreach."""
    record = db.scalar(
        select(ComplianceLimit).where(ComplianceLimit.customer_id == customer_id)
    )
    if not record:
        return False
    return bool(record.escalation_flag)
