import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Event, Invoice


def build_case_context(event_id: uuid.UUID, db: Session) -> Dict[str, Any]:
    """Build rich case context for root-cause diagnosis.

    Extracts event metadata and computes historical customer reliability signals
    across B2B invoice histories or consumer transaction patterns.

    Args:
        event_id: UUID of the target event.
        db: SQLAlchemy database session.

    Returns:
        Dict[str, Any]: Structured case context payload for the LLM agent.
    """
    event = db.get(Event, event_id)
    if not event:
        raise ValueError(f"Event with ID {event_id} not found.")

    today = date.today()
    now_utc = datetime.now(timezone.utc)

    # Base event information
    context: Dict[str, Any] = {
        "event_id": str(event.id),
        "source_type": event.source_type,
        "source_id": event.source_id,
        "customer_id": event.customer_id,
        "amount": float(event.amount) if event.amount is not None else 0.0,
        "currency": event.currency,
        "status": event.status,
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "raw_payload": event.raw_payload or {},
    }

    # Context enrichment for B2B Invoices
    if event.source_type == "invoice":
        days_overdue = event.raw_payload.get("days_overdue", 0)
        credit_terms = event.raw_payload.get("credit_terms", "net_30")

        # Query all invoices for this customer
        cust_invoices = db.scalars(
            select(Invoice).where(Invoice.customer_id == event.customer_id)
        ).all()

        total_invoices = len(cust_invoices)
        paid_invoices = [inv for inv in cust_invoices if inv.status == "paid"]
        disputed_invoices = [inv for inv in cust_invoices if inv.status == "disputed"]
        overdue_invoices = [inv for inv in cust_invoices if inv.status == "overdue"]

        pct_paid_on_time = (
            round((len(paid_invoices) / total_invoices) * 100, 2)
            if total_invoices > 0
            else 0.0
        )
        pct_ever_disputed = (
            round((len(disputed_invoices) / total_invoices) * 100, 2)
            if total_invoices > 0
            else 0.0
        )

        # Average days late when late
        late_days_list = []
        for inv in overdue_invoices:
            if inv.due_date:
                delay = (today - inv.due_date).days
                if delay > 0:
                    late_days_list.append(delay)

        avg_days_late = (
            round(sum(late_days_list) / len(late_days_list), 1)
            if late_days_list
            else 0.0
        )

        # Check first offense: only 1 overdue/disputed invoice total across history
        non_paid_count = len(disputed_invoices) + len(overdue_invoices)
        is_first_offense = non_paid_count <= 1

        context["b2b_context"] = {
            "days_overdue": days_overdue,
            "credit_terms": credit_terms,
            "gst_number": event.raw_payload.get("gst_number"),
            "hsn_code": event.raw_payload.get("hsn_code"),
            "customer_history": {
                "total_invoices": total_invoices,
                "pct_paid_on_time": pct_paid_on_time,
                "pct_ever_disputed": pct_ever_disputed,
                "avg_days_late_when_late": avg_days_late,
                "is_first_offense": is_first_offense,
                "paid_invoices_count": len(paid_invoices),
                "overdue_invoices_count": len(overdue_invoices),
                "disputed_invoices_count": len(disputed_invoices),
            },
        }

    # Context enrichment for Consumer Events (checkout, subscription, mandate)
    else:
        # Query all events for this customer
        cust_events = db.scalars(
            select(Event).where(Event.customer_id == event.customer_id)
        ).all()

        total_events = len(cust_events)
        failed_statuses = {"failed", "halted", "cancelled", "revoked", "expired"}
        failed_events = [e for e in cust_events if e.status in failed_statuses]

        pct_failed = (
            round((len(failed_events) / total_events) * 100, 2)
            if total_events > 0
            else 0.0
        )

        # Failure count in last 30 days
        thirty_days_ago = now_utc - timedelta(days=30)
        recent_failures = [
            e
            for e in failed_events
            if e.created_at and (
                e.created_at >= thirty_days_ago
                if e.created_at.tzinfo
                else e.created_at >= thirty_days_ago.replace(tzinfo=None)
            )
        ]

        context["consumer_context"] = {
            "total_events": total_events,
            "pct_failed": pct_failed,
            "recent_failure_count_last_30_days": len(recent_failures),
            "historical_failures_count": len(failed_events),
        }

    return context
