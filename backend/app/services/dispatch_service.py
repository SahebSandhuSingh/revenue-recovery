"""Dispatch service — simulated channel delivery stubs and action lifecycle management.

This module provides simulated dispatch for all outreach channels (email, whatsapp, sms, voice).
In production, each stub would be replaced with real integrations (e.g., SendGrid, Twilio,
WhatsApp Business API). For Step 5 & 6, all dispatches are simulated with realistic success/failure
rates to exercise the full action lifecycle.

Real dispatch integration is deferred to a future step. Do NOT attempt to send real messages here.

SIMULATION LIMITATION & STATUS CONVENTION (Part 0 Fix):
In a real production environment, silent retries would invoke payment gateway APIs (e.g., Razorpay/Stripe).
For demo and testing purposes, silent retry outcomes are simulated probabilistically with a ~40% success
and ~60% persistent decline weighting.
- Simulated SUCCESS: status="sent", dispatch_status="sent", dispatched_at=now(), delivered_at=now(), dispatch_error=None
- Simulated STILL FAILING: status="failed", dispatch_status="failed", dispatched_at=None, delivered_at=None,
  dispatch_error="[SIMULATED OUTCOME - still failing, see code comment for limitation]"
"""

import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import ACTION_STATUSES
from app.models import Action, AuditLog, Event

logger = logging.getLogger(__name__)

# Simulated dispatch success rates per channel
# In production, these would be replaced by actual API call outcomes.
CHANNEL_SUCCESS_RATES = {
    "email": 0.92,      # ~8% bounce/spam filter rate
    "whatsapp": 0.95,   # ~5% undelivered (phone off, blocked)
    "sms": 0.88,        # ~12% undelivered (wrong number, DND)
    "voice": 0.75,      # ~25% unanswered/voicemail
}


def _simulate_channel_dispatch(
    channel: str, action_type: str, message_draft: str, customer_id: str
) -> Dict[str, Any]:
    """Simulate sending a message through a channel stub.

    Returns a dict with:
        - result: "success" | "failed"
        - channel: the channel used
        - error: error message if failed, None otherwise
        - simulated: True (always, for audit trail clarity)
    """
    success_rate = CHANNEL_SUCCESS_RATES.get(channel, 0.90)
    succeeded = random.random() < success_rate

    if succeeded:
        logger.info(
            f"[DISPATCH STUB] {channel.upper()} delivered to {customer_id}: "
            f"{action_type} ({len(message_draft or '')} chars)"
        )
        return {
            "result": "success",
            "channel": channel,
            "error": None,
            "simulated": True,
        }
    else:
        error_messages = {
            "email": "Simulated: recipient mailbox full or address bounced",
            "whatsapp": "Simulated: WhatsApp number unreachable or blocked",
            "sms": "Simulated: SMS delivery failed — DND or invalid number",
            "voice": "Simulated: call went unanswered after 30 seconds",
        }
        error = error_messages.get(channel, "Simulated: unknown delivery failure")
        logger.warning(
            f"[DISPATCH STUB] {channel.upper()} FAILED for {customer_id}: {error}"
        )
        return {
            "result": "failed",
            "channel": channel,
            "error": error,
            "simulated": True,
        }


def _execute_silent_retry(action: Action, event: Event) -> Dict[str, Any]:
    """Simulate a silent payment retry (no customer contact).

    Simulation convention (Part 0 Fix):
    - Simulated SUCCESS: status="sent", dispatched_at=now(), dispatch_error=None (~40% success)
    - Simulated STILL FAILING: status="failed", dispatched_at=None,
      dispatch_error="[SIMULATED OUTCOME - still failing, see code comment for limitation]" (~60% failure)

    Note on simulation limitation: In production, this calls the payment gateway retry API
    (e.g., Razorpay/Stripe API). For demo/testing, outcomes are simulated probabilistically.
    """
    # 40% success / 60% still failing weighting matching Step 5 spec
    succeeded = random.random() < 0.40
    if succeeded:
        logger.info(
            f"[SILENT RETRY STUB] Retry succeeded for event {event.id} "
            f"(₹{event.amount:,.2f})"
        )
        return {
            "result": "success",
            "channel": "none",
            "dispatch_status": "sent",
            "error": None,
            "simulated": True,
        }
    else:
        logger.warning(
            f"[SILENT RETRY STUB] Retry FAILED for event {event.id} — "
            f"payment gateway returned persistent decline"
        )
        return {
            "result": "failed",
            "channel": "none",
            "dispatch_status": "failed",
            "error": "[SIMULATED OUTCOME - still failing, see code comment for limitation]",
            "simulated": True,
        }


def dispatch_action(
    action_id: uuid.UUID,
    db: Session,
) -> Dict[str, Any]:
    """Execute dispatch for a single planned action.

    Transitions the action through the lifecycle:
        planned → dispatched → delivered / sent (or failed)

    Blocked or already-dispatched actions are skipped.

    Args:
        action_id: The action UUID to dispatch.
        db: Database session.

    Returns:
        Dict with action_id, status, channel, result, and error fields.
    """
    action = db.get(Action, action_id)
    if not action:
        raise ValueError(f"Action {action_id} not found.")

    event = db.get(Event, action.event_id)
    if not event:
        raise ValueError(f"Event {action.event_id} not found for action {action_id}.")

    # Guard: only dispatch "planned" actions
    if action.status != "planned":
        logger.info(
            f"Skipping action {action_id}: status is '{action.status}', not 'planned'"
        )
        return {
            "action_id": str(action_id),
            "status": action.status,
            "dispatch_status": action.status,
            "channel": action.channel,
            "result": "skipped",
            "error": f"Action status is '{action.status}', not 'planned'",
            "simulated": True,
        }

    now = datetime.now(timezone.utc)

    # 1. Mark as dispatched
    action.status = "dispatched"
    action.dispatched_at = now
    db.flush()

    # 2. Execute channel stub
    if action.action_type == "silent_retry":
        dispatch_result = _execute_silent_retry(action, event)
    else:
        dispatch_result = _simulate_channel_dispatch(
            channel=action.channel,
            action_type=action.action_type,
            message_draft=action.message_draft or "",
            customer_id=event.customer_id,
        )

    # 3. Transition to final state (Part 0 Fix applied)
    if dispatch_result["result"] == "success":
        if action.action_type == "silent_retry":
            action.status = "sent"
            action.dispatched_at = now
            action.delivered_at = now
        else:
            action.status = "delivered"
            action.delivered_at = now
        action.dispatch_error = None
    else:
        action.status = "failed"
        if action.action_type == "silent_retry":
            # For silent retry failure, dispatched_at is set to None per Part 0 spec
            action.dispatched_at = None
            action.delivered_at = None
        action.dispatch_error = dispatch_result["error"]

    # 4. Audit trail
    decision_str = f"dispatch_{dispatch_result['result']}"
    audit_entry = AuditLog(
        event_id=event.id,
        agent_name="dispatch_service",
        decision=decision_str,
        reasoning=(
            f"Channel {action.channel} dispatch {'succeeded' if dispatch_result['result'] == 'success' else 'failed'} "
            f"for {action.action_type} action. "
            f"{'Delivered at ' + action.delivered_at.isoformat() if action.delivered_at else dispatch_result.get('error', '')}"
        ),
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(action)

    return {
        "action_id": str(action.id),
        "event_id": str(action.event_id),
        "customer_id": event.customer_id,
        "action_type": action.action_type,
        "channel": action.channel,
        "status": action.status,
        "dispatch_status": action.status,
        "result": dispatch_result["result"],
        "error": dispatch_result.get("error"),
        "dispatched_at": action.dispatched_at.isoformat() if action.dispatched_at else None,
        "delivered_at": action.delivered_at.isoformat() if action.delivered_at else None,
        "simulated": True,
    }


def run_silent_retries(db: Session, seed: Optional[int] = 42) -> Dict[str, Any]:
    """Execute or re-evaluate silent retries with the ~40/60 outcome weighting (Part 0).

    Args:
        db: Database session.
        seed: Optional random seed for reproducible demo outcomes.

    Returns:
        Dict with total_silent_retries, sent_count (recovered), failed_count (still failing), and by_status split.
    """
    if seed is not None:
        random.seed(seed)

    silent_actions = db.scalars(
        select(Action)
        .where(Action.action_type == "silent_retry")
        .order_by(Action.created_at.asc())
    ).all()

    total = len(silent_actions)
    sent_count = 0
    failed_count = 0
    now = datetime.now(timezone.utc)

    for act in silent_actions:
        event = db.get(Event, act.event_id)
        if not event:
            continue

        res = _execute_silent_retry(act, event)
        if res["result"] == "success":
            act.status = "sent"
            act.dispatched_at = now
            act.delivered_at = now
            act.dispatch_error = None
            sent_count += 1
        else:
            act.status = "failed"
            act.dispatched_at = None
            act.delivered_at = None
            act.dispatch_error = res["error"]
            failed_count += 1

        # Audit entry
        db.add(
            AuditLog(
                event_id=event.id,
                agent_name="dispatch_service",
                decision=f"silent_retry_{res['result']}",
                reasoning=f"Silent retry simulation: {res['result']}. {res.get('error') or 'Simulated payment recovery success'}",
            )
        )

    db.commit()

    return {
        "total_silent_retries": total,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "by_status": {
            "sent": sent_count,
            "failed": failed_count,
        },
    }


def run_dispatch_batch(db: Session) -> Dict[str, Any]:
    """Dispatch all planned actions in batch.

    Finds all actions with status='planned' and dispatches each one through
    the appropriate channel stub. Silent retries are dispatched without
    customer contact.

    Returns:
        Dict with total_dispatched, by_status, by_channel, and failures.
    """
    planned_actions = db.scalars(
        select(Action)
        .where(Action.status == "planned")
        .order_by(Action.created_at.asc())
    ).all()

    total_planned = len(planned_actions)
    logger.info(f"Found {total_planned} planned actions to dispatch.")

    dispatched_count = 0
    by_status: Dict[str, int] = {}
    by_channel: Dict[str, int] = {}
    failures: List[Dict[str, Any]] = []

    for idx, action in enumerate(planned_actions, start=1):
        try:
            result = dispatch_action(action.id, db)
            status = result["status"]
            channel = result["channel"]

            by_status[status] = by_status.get(status, 0) + 1
            by_channel[channel] = by_channel.get(channel, 0) + 1
            dispatched_count += 1

            logger.info(
                f"[{idx}/{total_planned}] Dispatched action {action.id} -> "
                f"{status} via {channel}"
            )
        except Exception as exc:
            failures.append({
                "action_id": str(action.id),
                "error": str(exc),
            })
            logger.error(f"Failed to dispatch action {action.id}: {exc}")

    return {
        "total_dispatched": dispatched_count,
        "by_status": by_status,
        "by_channel": by_channel,
        "by_dispatch_status": by_status,
        "failures": failures,
    }
