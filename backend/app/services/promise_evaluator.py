import logging
from datetime import date
from typing import Any, Dict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Promise

logger = logging.getLogger(__name__)


def evaluate_promise_statuses(db: Session) -> Dict[str, Any]:
    """Evaluate pending promises against current date and transition expired ones to broken.

    Note: this step cannot auto-detect "kept" promises without real payment-status webhooks —
    that reconciliation is deferred to Step 5. Do not attempt to infer "kept" status here.

    Args:
        db: SQLAlchemy database session.

    Returns:
        Dict[str, Any]: Evaluation summary with evaluated, newly_broken, and still_pending counts.
    """
    today = date.today()

    pending_promises = db.scalars(
        select(Promise).where(Promise.status == "pending")
    ).all()

    evaluated_count = len(pending_promises)
    newly_broken_count = 0
    still_pending_count = 0

    for promise in pending_promises:
        if promise.promised_date and promise.promised_date < today:
            promise.status = "broken"
            newly_broken_count += 1

            # Log evaluation decision to audit log
            audit_entry = AuditLog(
                event_id=promise.event_id,
                agent_name="promise_evaluator",
                decision="broken",
                reasoning=f"Promised payment date {promise.promised_date} has passed without confirmed settlement",
            )
            db.add(audit_entry)
            logger.info(
                f"Promise {promise.id} for event {promise.event_id} marked BROKEN (due: {promise.promised_date})"
            )
        else:
            still_pending_count += 1

    db.commit()

    return {
        "evaluated": evaluated_count,
        "newly_broken": newly_broken_count,
        "still_pending": still_pending_count,
    }
