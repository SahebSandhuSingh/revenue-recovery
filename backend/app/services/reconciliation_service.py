"""Payment reconciliation service — marks promises as 'kept' when payment is confirmed.

In production, this would be triggered by real payment gateway webhooks (Razorpay, Stripe, etc.).
For Step 5, we provide:
1. reconcile_payment() — manually confirm a specific promise as kept
2. simulate_payment_reconciliation() — auto-reconcile a subset of delivered actions' promises
   (simulating the scenario where some customers actually paid after receiving our outreach)
"""

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import Action, AuditLog, Event, Promise

logger = logging.getLogger(__name__)


def reconcile_payment(
    promise_id: uuid.UUID,
    db: Session,
    source: str = "manual",
) -> Dict[str, Any]:
    """Mark a specific promise as 'kept' (payment confirmed).

    Args:
        promise_id: The Promise UUID to reconcile.
        db: Database session.
        source: Reconciliation source ('webhook', 'manual', 'simulated').

    Returns:
        Dict with promise details and reconciliation status.
    """
    promise = db.get(Promise, promise_id)
    if not promise:
        raise ValueError(f"Promise {promise_id} not found.")

    if promise.status == "kept":
        logger.info(f"Promise {promise_id} is already marked as 'kept'.")
        return {
            "promise_id": str(promise.id),
            "event_id": str(promise.event_id),
            "status": "kept",
            "already_reconciled": True,
            "reconciled_at": promise.reconciled_at.isoformat() if promise.reconciled_at else None,
            "source": promise.reconciliation_source,
        }

    now = datetime.now(timezone.utc)
    previous_status = promise.status

    promise.status = "kept"
    promise.reconciled_at = now
    promise.reconciliation_source = source

    # Audit trail
    audit_entry = AuditLog(
        event_id=promise.event_id,
        agent_name="payment_reconciliation",
        decision="kept",
        reasoning=(
            f"Promise {promise.id} reconciled as 'kept' (was '{previous_status}'). "
            f"Amount: ₹{promise.promised_amount:,.2f}, "
            f"Source: {source}"
        ),
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(promise)

    logger.info(
        f"Promise {promise.id} marked KEPT via {source} "
        f"(₹{promise.promised_amount:,.2f})"
    )

    return {
        "promise_id": str(promise.id),
        "event_id": str(promise.event_id),
        "status": "kept",
        "already_reconciled": False,
        "reconciled_at": now.isoformat(),
        "source": source,
        "promised_amount": float(promise.promised_amount) if promise.promised_amount else None,
        "promised_date": promise.promised_date.isoformat() if promise.promised_date else None,
    }


def simulate_payment_reconciliation(
    db: Session,
    reconciliation_rate: float = 0.60,
) -> Dict[str, Any]:
    """Simulate payment confirmations for pending promises linked to delivered actions.

    This simulates the scenario where customers actually follow through on
    their payment promises after receiving our outreach (which was delivered
    successfully). Only pending promises whose parent event has a delivered
    action are eligible.

    Args:
        db: Database session.
        reconciliation_rate: Fraction of eligible promises to mark as 'kept' (default 60%).

    Returns:
        Dict with total_eligible, reconciled_count, and skipped_count.
    """
    # Find pending promises whose parent event has at least one delivered action
    delivered_event_ids = select(Action.event_id).where(
        Action.status == "delivered"
    ).distinct()

    eligible_promises = db.scalars(
        select(Promise)
        .where(
            Promise.status == "pending",
            Promise.event_id.in_(delivered_event_ids),
        )
        .order_by(Promise.created_at.asc())
    ).all()

    total_eligible = len(eligible_promises)
    reconciled_count = 0
    skipped_count = 0

    logger.info(
        f"Found {total_eligible} eligible pending promises for simulated reconciliation "
        f"(rate: {reconciliation_rate:.0%})"
    )

    for promise in eligible_promises:
        if random.random() < reconciliation_rate:
            try:
                reconcile_payment(promise.id, db, source="simulated")
                reconciled_count += 1
            except Exception as exc:
                logger.error(f"Failed to reconcile promise {promise.id}: {exc}")
                skipped_count += 1
        else:
            skipped_count += 1

    return {
        "total_eligible": total_eligible,
        "reconciled_count": reconciled_count,
        "skipped_count": skipped_count,
        "reconciliation_rate": reconciliation_rate,
    }
